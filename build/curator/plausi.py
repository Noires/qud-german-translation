"""Plausibilitätsprüfungen: korpusweite Regeln für Fehlerklassen, die im
Spieler-Feedback 2026-11-11 aufgefallen sind. Eingehängt in
lint.LintEngine.all_findings; zusätzlich als Gate aufrufbar:

    py -m curator.plausi            (aus build/)  -> Exit 1 bei error-Befunden

  S1 String-ID veraltet: Context existiert im Manifest, die ID (englischer
     Text) aber nicht mehr — Wert greift nie (Upstream-Update)        warning
  S2 Kontextloser String, den das Spiel nur MIT Context abfragt — tot  warning
  S3 Manifest-String fehlt bei uns (zeigt im Spiel Englisch)          warning
  L1 Eigener Loader ohne Load="Merge" — ersetzt Base-Daten komplett
     (Baetyl-Belohnungen waren leer)                                  error
  H1 InventoryAction-Hotkey ist nicht genau ein Zeichen               error
  H2 InventoryAction-Anzeige, die C# per .Display vergleicht/als ID
     nutzt, ist nicht kleingeschrieben (Tutorial blockiert)           error
  D1 Wortdopplung im Anzeigenamen („X X“, „{{c|A-B}}B“)               warning
  D2 Stufen-Ziffer (I–VIII) im Namen, die das Englische nicht hat     warning
  D3 Englisches Material-/Attributwort im deutschen Namen             warning

Alle Prüfungen lesen nur Dateien; Basisdaten (Manifest, Blueprints) werden
pro mtime gecacht.
"""
import glob
import html
import os
import re
import sys
import threading
import xml.etree.ElementTree as ET

from . import config

_lock = threading.Lock()
_cache = {"sig": None, "findings": []}
_base_cache = {}

# --- L1: Loader, die per Name ERSETZEN, sofern das Element kein Load="Merge" trägt.
# Datei -> Elementname. Erweitern, wenn ein weiterer Loader dieses Verhalten zeigt.
REPLACE_BY_NAME_LOADERS = {
    "SparkingBaetyls.de.xml": "reward",
}

# --- H2: InventoryActions, deren .Display der C#-Code liest (Tutorial-Vergleich
# gegen QudMenuItem.simpleText = ToLower(), Highlight-IDs, Container-Text).
CODE_READ_ACTIONS = {
    "CommandAutoEquipObject", "CommandEquipObject", "CommandTakeObject",
    "Examine", "Look", "OpenCasual",
}

# --- D2/D3
TIER_RE = re.compile(r"\b(?:I|II|III|IV|V|VI|VII|VIII)\b")
ENGLISH_NAME_WORDS = re.compile(
    r"\b(?:crysteel|fullerite|zetachrome|carbide|flawless|folded|two-handed)\b", re.I)

_ACTION_RE = re.compile(r"inventoryAction\[([^\]]+)\]")


def _mk(uid, rule, severity, message):
    return {"uid": uid, "rule": rule, "severity": severity, "message": message}


def plain(value):
    """Sichtbarer Text ohne Farb-Markup ({{x|…}} verschachtelt, &x-Codes)."""
    prev = None
    v = value or ""
    while prev != v:
        prev = v
        v = re.sub(r"\{\{[^|{}]*\|([^{}]*)\}\}", r"\1", v)
    return re.sub(r"&[a-zA-Z]", "", v)


def repeated_words(value, max_len=4):
    """-> wiederholte Wortfolge (Länge 1..max_len) direkt hintereinander, sonst None.
    Bindestrich-Komposita zählen ihr Grundwort mit: „Plastifer-WamsWams“ wird über
    die Suffix-Prüfung in D1 erkannt, hier nur ganze Wörter."""
    w = [x.lower().strip(",.;:!?") for x in plain(value).split()]
    for k in range(1, max_len + 1):
        for i in range(len(w) - 2 * k + 1):
            if w[i:i + k] == w[i + k:i + 2 * k] and any(len(x) > 2 for x in w[i:i + k]):
                return " ".join(w[i:i + k])
    return None


def glued_suffix_dup(value):
    """„{{c|Chrommantel}}mantel“: Wrapper-Inhalt endet auf das direkt angehängte Wort."""
    for m in re.finditer(r"\{\{[^|{}]+\|([^{}]+)\}\}([^\s{}\"]{3,})", value or ""):
        inner, after = m.group(1).lower(), m.group(2).lower().lstrip("-")
        if len(after) >= 3 and inner.replace("-", "").endswith(after.replace("-", "")):
            return m.group(0)
    return None


# ------------------------------------------------------------------ Basisdaten
def _example_dir():
    return config.CFG["game_example_dir"]


def _base_dir():
    return os.path.dirname(_example_dir().rstrip("/\\"))


def _mtime_sig(paths):
    out = []
    for p in paths:
        try:
            out.append((p, os.path.getmtime(p)))
        except OSError:
            pass
    return tuple(out)


def manifest_strings():
    """{context: {id,...}} aus ExampleLanguage/Strings*.example.xml."""
    paths = sorted(glob.glob(os.path.join(_example_dir(), "Strings*.example.xml")))
    sig = _mtime_sig(paths)
    hit = _base_cache.get("strings")
    if hit and hit[0] == sig:
        return hit[1]
    man = {}
    for p in paths:
        try:
            for s in ET.parse(p).iter("string"):
                man.setdefault(s.get("Context") or None, set()).add(s.get("ID"))
        except (ET.ParseError, OSError):
            pass
    _base_cache["strings"] = (sig, man)
    return man


def base_display_names():
    """{Blueprint-Name: englischer DisplayName} aus Base/ObjectBlueprints."""
    paths = sorted(glob.glob(os.path.join(_base_dir(), "ObjectBlueprints", "*.xml")))
    sig = _mtime_sig(paths)
    hit = _base_cache.get("names")
    if hit and hit[0] == sig:
        return hit[1]
    objre = re.compile(r'<object Name="([^"]+)"[^>]*>(.*?)</object>', re.S)
    dnre = re.compile(r'<part Name="Render"[^>]*?\bDisplayName="([^"]*)"')
    names = {}
    for p in paths:
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                txt = f.read()
        except OSError:
            continue
        for m in objre.finditer(txt):
            dm = dnre.search(m.group(2))
            if dm:
                names[html.unescape(m.group(1))] = html.unescape(dm.group(1))
    _base_cache["names"] = (sig, names)
    return names


# ------------------------------------------------------------------ Regeln
def string_context(u):
    """Context einer String-Einheit, normalisiert: fehlend/leer -> None.
    Textknoten-Einträge (<string ID=..>Wert</string>) tragen ihn nur im key
    („Context|ID@#text“)."""
    ctx = u.context
    if u.kind == "string-text" and not ctx:
        ctx = (u.key or "").split("|", 1)[0]
    return ctx or None


def _strings_rules(store):
    out = []
    man = manifest_strings()
    if not man:
        return out
    units = [u for u in store.all_units()
             if u.kind in ("string", "string-text") and u.file.startswith("Strings")]
    ours = {(string_context(u), u.english) for u in units}
    for u in units:
        ctx, en = string_context(u), u.english
        if ctx is None:
            ctxs = None
            for c, ids in man.items():
                if en in ids:
                    ctxs = (ctxs or set()) | {c}
            if ctxs and None not in ctxs:
                out.append(_mk(u.uid, "S2", "warning",
                               "Kontextloser Eintrag — das Spiel fragt diese ID nur mit Context ab "
                               "(%s); der Wert greift nie" % ", ".join(sorted(ctxs))[:160]))
            continue
        ids = man.get(ctx)
        if ids is not None and en not in ids and not ctx.startswith("Conversation "):
            if all((ctx, i) in ours for i in ids):
                msg = ("Toter Alteintrag: Context „%s“ hat diese ID nicht mehr, die aktuelle "
                       "Fassung ist bereits übersetzt — löschen" % ctx)
            else:
                msg = ("ID veraltet: Context „%s“ hat im Spiel einen anderen englischen Text — "
                       "ID auf die neue Fassung nachziehen" % ctx)
            out.append(_mk(u.uid, "S1", "warning", msg))
    for ctx, ids in man.items():
        for i in ids:
            if (ctx, i) not in ours:
                out.append(_mk(None, "S3", "warning",
                               "Fehlt: Context „%s“ ID „%s“" % (ctx, (i or "")[:120])))
    return out


def _loader_rules(store):
    out = []
    for fn, elem in REPLACE_BY_NAME_LOADERS.items():
        res = store.files.get(fn)
        if res is None:
            continue
        for m in re.finditer(r"<%s\b([^>]*)>" % re.escape(elem), res.text):
            attrs = m.group(1)
            if 'Load="Merge"' not in attrs:
                nm = re.search(r'Name="([^"]*)"', attrs)
                out.append(_mk(None, "L1", "error",
                               "%s: <%s Name=\"%s\"> ohne Load=\"Merge\" — ersetzt den Base-Eintrag "
                               "komplett (Nutzdaten gehen verloren)" % (fn, elem, nm.group(1) if nm else "?")))
    return out


def unit_findings(u):
    """Regeln, die nur den Wert einer Einheit brauchen (H1/H2/D1–D3)."""
    out = []
    value = u.display_value() if u.value is not None else ""
    if u.file == "InventoryActions.de.xml":
        m = _ACTION_RE.search(u.key or "")
        action = m.group(1) if m else None
        if u.elem == "key" and len(value) != 1:
            out.append(_mk(u.uid, "H1", "error",
                           "Hotkey „%s“ ist nicht genau ein Zeichen (%s)" % (value, action)))
        if u.elem == "display" and action in CODE_READ_ACTIONS and value != value.lower():
            out.append(_mk(u.uid, "H2", "error",
                           "„%s“ (%s) muss kleingeschrieben sein — der Code vergleicht mit "
                           "simpleText (ToLower), sonst blockiert u. a. das Tutorial" % (value, action)))
    if u.attr == "DisplayName" and u.objname and value:
        dup = repeated_words(value) or glued_suffix_dup(value)
        if dup:
            out.append(_mk(u.uid, "D1", "warning", "Wortdopplung im Namen: „%s“" % dup))
        en = base_display_names().get(u.objname)
        if en is not None:
            if TIER_RE.search(plain(value)) and not TIER_RE.search(plain(en)):
                out.append(_mk(u.uid, "D2", "warning",
                               "Stufen-Ziffer im Namen, Englisch: „%s“ — Material statt Stufe?" % plain(en)))
            w = ENGLISH_NAME_WORDS.search(plain(value))
            if w:
                out.append(_mk(u.uid, "D3", "warning",
                               "Englisches Wort „%s“ im deutschen Namen (Englisch: „%s“)"
                               % (w.group(0), plain(en))))
    return out


def _signature(store):
    return tuple(sorted((fn, res.digest) for fn, res in store.files.items()))


def findings(store):
    sig = _signature(store)
    with _lock:
        if _cache["sig"] == sig:
            return _cache["findings"]
    out = []
    out += _strings_rules(store)
    out += _loader_rules(store)
    for u in store.all_units():
        out += unit_findings(u)
    with _lock:
        _cache["sig"] = sig
        _cache["findings"] = out
    return out


def main(argv=None):
    from . import store as store_mod
    s = store_mod.Store()
    s.refresh()
    fs = findings(s)
    units = {u.uid: u for u in s.all_units()}
    by = {}
    for f in fs:
        by.setdefault((f["rule"], f["severity"]), []).append(f)
    for (rule, sev), lst in sorted(by.items()):
        print("%s %-7s %4d" % (rule, sev, len(lst)))
        for f in lst[:5]:
            u = units.get(f["uid"])
            where = "%s:%s" % (u.file, u.line) if u else "-"
            print("    %s  %s" % (where, f["message"][:150]))
    errors = sum(1 for f in fs if f["severity"] == "error")
    print("Summe: %d Befunde, davon %d error" % (len(fs), errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
