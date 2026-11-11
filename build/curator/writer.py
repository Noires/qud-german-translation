"""Chirurgischer, formaterhaltender Writer für die *.de.xml-Dateien.

Kontrakte, die hier erzwungen werden (docs/GRAMMAR_ENGINE.md §9, Projekt-Skill):
  1. ID="…"/Context/Name-Attribute werden NIE verändert — es gibt keinen
     Codepfad, der in einen Schlüssel schreibt, und der Post-Verify prüft
     Key-Set-Invarianz zusätzlich.
  2. Die Datei bleibt wohlgeformt (ElementTree-Parse vor dem Persistieren).
  3. Naming ⊇ Strings Substring-Kontrakt blockiert verletzende Saves
     (nur token-freie Werte — Token-Werte expandieren erst zur Laufzeit
     und werden stattdessen von der Lint-Engine gemeldet).
  4. Byte-Erhalt: Splice in den Original-Text; BOM und EOLs unangetastet;
     No-op-Saves schreiben gar nicht.
Persistiert wird atomar über eine Temp-Datei + os.replace.
"""
import os
import threading
import xml.etree.ElementTree as ET

from . import xmlscan

_write_lock = threading.Lock()
NAMING_FILE = "Naming.de.xml"
NAMING_CTX_SUFFIX = "Naming.xml Context"


class WriteError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def naming_attr_values(text):
    """Alle Attributwerte aus Naming.de.xml (inkl. Name= — dort stehen die
    kontraktrelevanten Titel wie <value Name="König" />)."""
    vals = set()
    for m in xmlscan.TAG_RE.finditer(text):
        if m.group("name") is None or m.group("close"):
            continue
        for am in xmlscan.ATTR_RE.finditer(m.group("attrs")):
            vals.add(xmlscan.xml_unescape(am.group("val")))
    return vals


def naming_contract_problems(strings_units, naming_text):
    """Naming ⊇ Strings: jeder token-freie Wert eines *Naming.xml-Context*-
    Strings-Eintrags muss Substring eines Naming.de.xml-Attributwerts sein."""
    problems = []
    naming_vals = naming_attr_values(naming_text)
    for u in strings_units:
        if u.kind not in ("string", "string-text"):
            continue
        ctx = u.context or ""
        if not ctx.endswith(NAMING_CTX_SUFFIX):
            continue
        val = u.display_value()
        if not val.strip() or "=" in val:
            continue  # Token-Werte expandieren erst zur Laufzeit -> Lint, nicht Block
        if not any(val in nv for nv in naming_vals):
            problems.append(
                "Naming-Substring-Kontrakt: „%s“ (Context: %s) kommt in keinem "
                "Naming.de.xml-Wert vor — Helden verlieren sonst wertabhängige "
                "Boni. Beide Seiten zusammen ändern." % (val, ctx))
    return problems


def _contract_problems(store_obj, filename, scan_for_file):
    """Alle Kontrakt-3-Befunde eines Zustands (scan_for_file ersetzt die
    Sicht auf `filename`; None = aktueller Stand)."""
    def view(fn):
        if scan_for_file is not None and fn == filename:
            return scan_for_file
        return store_obj.files.get(fn)

    naming = view(NAMING_FILE)
    if naming is None:
        return set()
    problems = set()
    for fn in store_obj.files:
        res = view(fn)
        if res is None or res.root_tag != "strings":
            continue
        problems.update(naming_contract_problems(res.units, naming.text))
    return problems


def _contract_check(store_obj, filename, new_scan):
    """Kontrakt 3 als REGRESSIONS-Gate: geblockt werden nur Verletzungen, die
    durch diese Änderung NEU entstehen. Bestandsfälle (z. B. Werte wie
    „Clan Hotur“, die erst zur Laufzeit aus Template+Wert zusammengesetzt
    werden) blockieren nicht — die meldet die Prüf-Engine."""
    baseline = _contract_problems(store_obj, filename, None)
    candidate = _contract_problems(store_obj, filename, new_scan)
    return sorted(candidate - baseline)


def _verify(new_text, filename, expect_keys, describe):
    """Wohlgeformtheit + Key-Set-Invarianz auf dem In-Memory-Kandidaten."""
    try:
        ET.fromstring(new_text)
    except ET.ParseError as ex:
        raise WriteError(422, "Abgelehnt — XML wäre nicht mehr wohlgeformt: %s" % ex)
    new_scan = xmlscan.scan_text(new_text, filename)
    got = sorted((u.kind, u.key) for u in new_scan.units)
    if got != expect_keys:
        raise WriteError(422, "Abgelehnt — %s hätte die Schlüsselmenge verändert "
                              "(ID-/Struktur-Schutz)." % describe)
    return new_scan


def _persist(path, new_text, bom):
    tmp = path + ".curator-tmp"
    with open(tmp, "wb") as f:
        f.write(bom + new_text.encode("utf-8"))
    os.replace(tmp, path)


def _severity_errors(store_obj, u, new_value):
    """Neue Befunde von Regeln mit Schwere „error“ (glossary.json „rules“ bzw.
    Standard-error-Regeln wie B1/X1) blocken das Speichern."""
    from . import lint
    cand = xmlscan.Unit(**{k: getattr(u, k) for k in xmlscan.Unit.__slots__})
    cand.value = u.escape_back(new_value)
    return lint.get_engine(store_obj).new_errors(u, cand)


def save(store_obj, uid, old_value, new_value):
    """Speichert einen geänderten Wert. -> Unit (frisch gescannt).
    old_value/new_value sind Display-Werte (entschärft, \\n statt &#10;)."""
    with _write_lock:
        store_obj.refresh()
        u = store_obj.get(uid)
        if u is None:
            raise WriteError(404, "Einheit nicht gefunden — Index neu laden.")
        if u.display_value() != old_value:
            raise WriteError(409, "Datei wurde extern geändert — Eintrag neu laden "
                                  "und Änderung wiederholen.")
        if new_value == old_value:
            return u  # No-op: garantiert byte-identisch, nichts zu tun

        res = store_obj.files[u.file]
        s, e = u.span
        new_text = res.text[:s] + u.escape_back(new_value) + res.text[e:]

        expect = sorted((x.kind, x.key) for x in res.units)
        if u.kind == "json":
            from . import jsonscan
            try:
                new_scan, same = jsonscan.verify(new_text, u.file, expect)
            except (AssertionError, ValueError, IndexError) as ex:
                raise WriteError(422, "Abgelehnt — JSON wäre nicht mehr gültig: %s" % ex)
            if not same:
                raise WriteError(422, "Abgelehnt — die Änderung hätte die JSON-Pfade verändert.")
        else:
            new_scan = _verify(new_text, u.file, expect, "die Änderung")

        problems = _contract_check(store_obj, u.file, new_scan)
        if problems:
            raise WriteError(422, " / ".join(problems))
        errs = _severity_errors(store_obj, u, new_value)
        if errs:
            raise WriteError(422, "Abgelehnt — Prüfregel auf „error“: " + " / ".join(
                "%s %s" % (r, msg) for r, msg in errs))

        _persist(store_obj.path(u.file), new_text, res.bom)
        store_obj.refresh()
        fresh = store_obj.get(uid)
        if fresh is None or fresh.display_value() != new_value:
            raise WriteError(500, "Nachprüfung fehlgeschlagen — bitte git diff prüfen!")
        return fresh


def delete_string_entry(store_obj, uid, expect_value=None):
    """Entfernt einen <string …>-Eintrag samt Zeilenumbruch (nur String-Tabellen).
    Byte-erhaltend: genau die Zeile des Elements fällt weg; Kandidat wird wie bei
    save() geparst und gegen die um GENAU diesen Schlüssel verkleinerte
    Schlüsselmenge geprüft. Die Fachregel, WANN gelöscht werden darf (z. B. nur
    verwaiste Einträge nach K1-Neuanlage), liegt beim Aufrufer.
    -> gelöschter Schlüssel."""
    with _write_lock:
        store_obj.refresh()
        u = store_obj.get(uid)
        if u is None:
            raise WriteError(404, "Einheit nicht gefunden — Index neu laden.")
        if u.kind not in ("string", "string-text"):
            raise WriteError(422, "Löschen gibt es nur für String-Tabellen-Einträge.")
        if expect_value is not None and u.display_value() != expect_value:
            raise WriteError(409, "Wert hat sich geändert — Eintrag neu laden.")
        res = store_obj.files[u.file]
        text = res.text
        start = text.rfind("<string", 0, u.span[0])
        line_start = text.rfind("\n", 0, start) + 1
        if start < 0 or text[line_start:start].strip():
            raise WriteError(422, "Eintrag steht nicht allein auf seiner Zeile — "
                                  "manuell entfernen.")
        if u.kind == "string":
            end = text.find("/>", u.span[1])
            end = end + 2 if end >= 0 else -1
        else:
            end = text.find("</string>", u.span[1])
            end = end + len("</string>") if end >= 0 else -1
        if end < 0:
            raise WriteError(422, "Elementende nicht gefunden.")
        if text.startswith("\r\n", end):
            end += 2
        elif text.startswith("\n", end):
            end += 1
        others = [x for x in res.units if x.uid != uid
                  and line_start <= x.span[0] < end]
        if others:
            raise WriteError(422, "Weitere Einheiten in derselben Zeile — manuell entfernen.")
        new_text = text[:line_start] + text[end:]
        expect = sorted((x.kind, x.key) for x in res.units if x.uid != uid)
        new_scan = _verify(new_text, u.file, expect, "das Löschen")
        problems = _contract_check(store_obj, u.file, new_scan)
        if problems:
            raise WriteError(422, " / ".join(problems))
        _persist(store_obj.path(u.file), new_text, res.bom)
        store_obj.refresh()
        if store_obj.get(uid) is not None:
            raise WriteError(500, "Nachprüfung fehlgeschlagen — Eintrag noch vorhanden!")
        return u.key


def create_string_entry(store_obj, filename, context, string_id, value):
    """Legt einen neuen <string ...>-Eintrag in einer String-Tabellen-Datei an.
    Einfügepunkt: hinter dem letzten Eintrag mit gleichem Context, sonst vor
    dem schließenden Root-Tag; Zeilenstil vom Nachbarn geklont."""
    if not string_id:
        raise WriteError(422, "ID darf nicht leer sein.")
    with _write_lock:
        store_obj.refresh()
        if filename not in store_obj.files:
            raise WriteError(404, "Datei nicht gefunden: %s" % filename)
        res = store_obj.files[filename]
        if res.root_tag != "strings":
            raise WriteError(422, "Neuanlage gibt es nur für String-Tabellen "
                                  "(<strings>-Root), nicht für %s." % filename)
        key = "%s|%s" % (context or "", string_id)
        for x in res.units:
            if x.kind in ("string", "string-text") and x.key == key:
                raise WriteError(409, "Eintrag existiert bereits (Context+ID identisch).")

        text = res.text
        eol = "\r\n" if "\r\n" in text else "\n"

        same_ctx = [x for x in res.units if x.kind == "string"
                    and x.context == (context or "")]
        if same_ctx:
            last = max(same_ctx, key=lambda x: x.span[1])
            nl = text.find("\n", last.span[1])
            anchor = (nl + 1) if nl >= 0 else len(text)
            indent_pos = last.span[0]
        else:
            close = text.rfind("</strings>")
            if close < 0:
                raise WriteError(422, "Schließendes </strings> nicht gefunden.")
            anchor = text.rfind("\n", 0, close) + 1
            indent_pos = res.units[0].span[0] if res.units else None

        indent = "  "
        if indent_pos is not None:
            ls = text.rfind("\n", 0, indent_pos) + 1
            line = text[ls:]
            indent = line[:len(line) - len(line.lstrip())] or "  "

        attrs = []
        if context:
            attrs.append('Context="%s"' % xmlscan.xml_escape_attr(context))
        attrs.append('ID="%s"' % xmlscan.xml_escape_attr(string_id))
        attrs.append('Value="%s"' % xmlscan.xml_escape_attr(value or ""))
        new_line = "%s<string %s />%s" % (indent, " ".join(attrs), eol)
        new_text = text[:anchor] + new_line + text[anchor:]

        expect = sorted([(x.kind, x.key) for x in res.units] + [("string", key)])
        new_scan = _verify(new_text, filename, expect, "die Neuanlage")
        problems = _contract_check(store_obj, filename, new_scan)
        if problems:
            raise WriteError(422, " / ".join(problems))

        _persist(store_obj.path(filename), new_text, res.bom)
        store_obj.refresh()
        for x in store_obj.files[filename].units:
            if x.kind == "string" and x.key == key:
                return x
        raise WriteError(500, "Neuer Eintrag nach dem Schreiben nicht auffindbar.")
