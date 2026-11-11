"""Prüf-Engine (Lint) über den Übersetzungs-Korpus.

Regeln (Schwere: error > warning > info):
  T1 Unbekanntes Token im deutschen Wert                       warning
  T2 Rolle/Token der englischen Vorlage fehlt im Deutschen     warning
  T3 Token nur im Deutschen (kein Gegenstück in der Vorlage)   info
  T4 Unausgewogene =-Delimiter / {{ }}                         warning
  T5 konjde-Infinitiv nicht in Verbs.json (schwach ok?)        info/warning
  T6 Trennbares Präfix-Verb bei konjde                         warning/info
  B1 Boolesches Attribut übersetzt                             error
  N1 Naming ⊇ Strings Substring-Kontrakt                       error/warning
  X1 Entity-/Zeichenfehler                                     error
  X2 Elementpfad nicht im Spiel-Manifest                       warning
  P1 Parität zur Vorlage: Zahlen, Leerraum am Rand/doppelt, Klammern   warning/info
  K1–K7, G1/G2 Kontext-/Glossar-Regeln (korpusweit)        siehe context_lint.py
  S1–S3, L1, H1/H2, D1–D3 Plausibilitätsprüfungen            siehe plausi.py

Schwere je Regel übersteuerbar (glossary.json „rules“: off|info|warning|error).
„error“ blockt zusätzlich das Speichern, wenn die Änderung einen NEUEN Befund
dieser Regel erzeugt (writer.save -> new_errors).
  (L1/L2 Lexikon-Regeln liegen in lexicon.py, wo die Datei gelesen wird.)

Ergebnisse werden pro Datei-Hash gecacht; ein Save invalidiert nur die Datei.
"""
import glob
import json
import os
import re
import threading
import xml.etree.ElementTree as ET

from . import config, german, tokens, writer

TOKEN_RE = tokens.TOKEN_RE
ROLE_RE = re.compile(r"^[A-Za-z][\w']*")

# Attribute, deren Wert ein englisches Boolean bleiben MUSS (B1). Aus dem
# Manifest abgeleitete true/false-Attribute plus bekannte Fälle (Worlds.de.xml).
BOOL_VALUES = {"true", "false"}


class Finding(dict):
    pass


def _mk(uid, rule, severity, message):
    return {"uid": uid, "rule": rule, "severity": severity, "message": message}


def apply_levels(findings, levels=None):
    """Schwere-Übersteuerung aus dem Glossar anwenden; „off“ entfernt den Befund."""
    if levels is None:
        from .glossary import GLOSSARY
        levels = GLOSSARY.rules()
    if not levels:
        return findings
    out = []
    for f in findings:
        lv = levels.get(f["rule"])
        if lv == "off":
            continue
        out.append(dict(f, severity=lv) if lv and lv != f["severity"] else f)
    return out


# P1: Zahlen außerhalb von Tokens/Markup; deutsches Dezimal-/Tausender-Komma ist egal,
# weil nur die Ziffernfolgen verglichen werden („1.5“ ≙ „1,5“)
_NUM_STRIP = re.compile(r"=[^=\s][^=]*=|\{\{[^|{}]*\||&[A-Za-z]|\^[A-Za-z]")


def _numbers(s):
    return sorted(re.findall(r"\d+", _NUM_STRIP.sub(" ", s or "")))


def parity_findings(uid, en, de):
    out = []
    if not en or not de:
        return out
    ne, nd = _numbers(en), _numbers(de)
    if ne != nd:
        out.append(_mk(uid, "P1", "warning",
                       "Zahlen weichen von der Vorlage ab: EN %s, DE %s."
                       % (" ".join(ne) or "–", " ".join(nd) or "–")))
    for side, rx in (("Anfang", r"^\s"), ("Ende", r"\s$")):
        if bool(re.search(rx, en)) != bool(re.search(rx, de)):
            out.append(_mk(uid, "P1", "warning",
                           "Leerraum am %s anders als in der Vorlage." % side))
    if "  " in de.strip() and "  " not in en:
        out.append(_mk(uid, "P1", "info", "Doppeltes Leerzeichen im deutschen Wert."))
    for o, c in ("()", "[]"):
        if de.count(o) != de.count(c) and en.count(o) == en.count(c):
            out.append(_mk(uid, "P1", "warning", "Klammern %s%s unausgewogen." % (o, c)))
    return out


class LintEngine:
    def __init__(self, store_obj):
        self.store = store_obj
        self.lock = threading.RLock()
        self.registry = None
        self._file_cache = {}     # filename -> (digest, [findings])
        self._verbs = None        # (mtime, {inf,...})
        self._bool_attrs = None   # aus Manifest abgeleitet
        self._schema_paths = None  # {examplefile: set(pfad-tupel)}

    # ---------------------------------------------------------- Datenquellen
    def _get_registry(self):
        if self.registry is None:
            reg = tokens.Registry()
            english = []
            for res in self.store.files.values():
                for u in res.units:
                    if u.english:
                        english.append(u.english)
            for ex in glob.glob(os.path.join(config.CFG["game_example_dir"],
                                             "*.example.xml")):
                try:
                    with open(ex, encoding="utf-8") as f:
                        english.append(f.read())
                except OSError:
                    pass
            reg.add_corpus(english)
            self.registry = reg
        return self.registry

    def strong_verbs(self):
        try:
            mtime = os.stat(config.VERBS_JSON).st_mtime_ns
        except OSError:
            return set()
        if self._verbs and self._verbs[0] == mtime:
            return self._verbs[1]
        try:
            with open(config.VERBS_JSON, encoding="utf-8") as f:
                data = json.load(f)
            verbs = {v["inf"].lower() for v in data.get("verbs", [])
                     if v.get("inf") and v.get("s3")}
        except Exception:
            verbs = set()
        self._verbs = (mtime, verbs)
        return verbs

    def bool_attrs(self):
        """(Element-Tag, Attribut)-Paare, deren Beispielwert im Manifest ein
        UNMARKIERTES true/false ist (▶-markierte Werte sind übersetzbar und
        gerade KEINE Booleans). Paarweise, weil Attributnamen wie „Value“
        generisch sind."""
        if self._bool_attrs is not None:
            return self._bool_attrs
        per_pair = {}
        for ex in glob.glob(os.path.join(config.CFG["game_example_dir"],
                                         "*.example.xml")):
            try:
                root = ET.parse(ex).getroot()
            except Exception:
                continue
            for el in root.iter():
                for a, v in el.attrib.items():
                    per_pair.setdefault((el.tag, a), set()).add(v.strip().lower())
        # boolean-only: ALLE Beispielwerte des Paars sind true/false
        # (<case Value="1|true|Melee"> ist ein Switch-Key, kein Boolean)
        pairs = {p for p, vals in per_pair.items() if vals and vals <= BOOL_VALUES}
        pairs |= {("*", "ProperName"), ("*", "Plural")}
        self._bool_attrs = pairs
        return pairs

    def schema_paths(self, filename):
        """Erlaubte Elementpfade (Tag-Ketten) laut *.example.xml."""
        if self._schema_paths is None:
            self._schema_paths = {}
        name = filename.replace(".de.xml", "")
        if name in self._schema_paths:
            return self._schema_paths[name]
        paths = None
        ex = os.path.join(config.CFG["game_example_dir"], name + ".example.xml")
        if os.path.exists(ex):
            try:
                root = ET.parse(ex).getroot()
                paths = set()

                def walk(el, chain):
                    chain = chain + (el.tag,)
                    paths.add(chain)
                    for ch in el:
                        walk(ch, chain)
                walk(root, ())
            except Exception:
                paths = None
        self._schema_paths[name] = paths
        return paths

    # ---------------------------------------------------------- Kernregeln
    def lint_value(self, u):
        """Regeln T1–T6, B1, X1 für eine Einheit."""
        out = []
        de = u.display_value()
        en = u.english or ""

        # X1: Entity-Fehler im ROH-Wert (kaputtes '&' übersteht den Parser nicht,
        # aber ein nach Unescape verbliebenes '<' oder einsames '&' im Display
        # deutet auf doppelt-escapten Murks hin)
        raw = u.value
        for m in re.finditer(r"&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)", raw):
            out.append(_mk(u.uid, "X1", "error",
                           "Rohes '&' ohne gültige Entity im Wert (Position %d)."
                           % m.start()))
            break

        # B1: boolesches Attribut übersetzt
        if u.kind == "attr":
            pairs = self.bool_attrs()
            if (u.elem, u.attr) in pairs or ("*", u.attr) in pairs:
                if de.strip().lower() not in BOOL_VALUES:
                    out.append(_mk(u.uid, "B1", "error",
                                   "Attribut %s (in <%s>) ist ein Boolean und muss "
                                   "englisch true/false bleiben (aktuell: „%s“)."
                                   % (u.attr, u.elem, de)))
                return out  # Boolean-Attribute brauchen keine Token-Regeln

        de_tokens = [m.group(1) for m in TOKEN_RE.finditer(de)]
        en_tokens = [m.group(1) for m in TOKEN_RE.finditer(en)]

        # T4: unausgewogene Delimiter. Literales „ = “ (beidseitig Whitespace,
        # z. B. "max = 5" in Prosa) zählt nicht als Token-Delimiter.
        stripped = re.sub(r"&#\d+;|&#x[0-9a-fA-F]+;", "", de)
        stripped = re.sub(r"(?<=\s)=(?=\s)", "", stripped)
        if stripped.count("=") % 2 == 1:
            out.append(_mk(u.uid, "T4", "warning",
                           "Ungerade Anzahl '=' im deutschen Wert — Token evtl. "
                           "nicht geschlossen."))
        if de.count("{{") != de.count("}}"):
            out.append(_mk(u.uid, "T4", "warning",
                           "Unausgewogene {{…}}-Farbklammern."))

        reg = self._get_registry()
        # Laufzeit-Variablen der EIGENEN englischen Vorlage sind gültige Basen
        # (z. B. =quill= im Englischen erlaubt =quill|capitalize= im Deutschen)
        en_bases = set()
        for t in en_tokens:
            b, r = tokens.token_base(t)
            if b:
                en_bases.add(b.lower())
                en_bases.add(b.split(".")[0].lower())
        for t in de_tokens:
            # T1: unbekanntes Token
            base, _rest = tokens.token_base(t)
            if base and base.split(".")[0].lower() in en_bases:
                pass
            elif not reg.known(t):
                out.append(_mk(u.uid, "T1", "warning",
                               "Unbekanntes Token =%s= (weder Replacer noch im "
                               "englischen Korpus)." % t))
            # T5/T6: konjde-Prüfung
            km = re.match(r"^(?:[\w']+\.)*[Kk]onjde:(.+)$", t)
            if km:
                inf = km.group(1).strip()
                low = inf.lower()
                if low not in self.strong_verbs():
                    if not low.endswith("n"):
                        out.append(_mk(u.uid, "T5", "warning",
                                       "konjde:%s — „%s“ sieht nicht wie ein "
                                       "Infinitiv aus (endet nicht auf -n)."
                                       % (inf, inf)))
                    else:
                        out.append(_mk(u.uid, "T5", "info",
                                       "konjde:%s ist nicht in Verbs.json — schwache "
                                       "Konjugation ergibt „%s / %s / %s“."
                                       % (inf,
                                          german.weak_conjugate(low, 0),
                                          german.weak_conjugate(low, 1),
                                          german.weak_conjugate(low, 2))))
                pref, ambig = german.separable_prefix(inf)
                if pref and low not in self.strong_verbs():
                    out.append(_mk(u.uid, "T6", "info" if ambig else "warning",
                                   "konjde:%s — Präfix „%s-“ ist %strennbar; "
                                   "trennbare Verben brechen die Wortstellung "
                                   "(Verbs.json-Hinweis)." %
                                   (inf, pref, "oft " if ambig else "")))

        # T2/T3: Rollen-Vergleich englisch vs. deutsch (nur wortartige Rollen)
        if en:
            en_roles = {r for r in (self._role(t) for t in en_tokens)
                        if ROLE_RE.match(r or "")}
            de_roles = {r for r in (self._role(t) for t in de_tokens)
                        if ROLE_RE.match(r or "")}
            for r in sorted(en_roles - de_roles):
                out.append(_mk(u.uid, "T2", "warning",
                               "Rolle/Token „%s“ aus der englischen Vorlage fehlt "
                               "im deutschen Wert." % r))
            for r in sorted(de_roles - en_roles):
                out.append(_mk(u.uid, "T3", "info",
                               "Token-Rolle „%s“ nur im deutschen Wert." % r))
        if u.kind != "json":  # Gewürz-Listen haben keine 1:1-Vorlage
            out.extend(parity_findings(u.uid, en, de))
        return out

    @staticmethod
    def _role(token_content):
        """Vergleichs-Rolle eines Tokens: erstes Segment, wenn es ein Ziel ist
        (subject/object/var), sonst der Basisname — so ist
        =object.t= -> =object.dativ= KEIN Befund."""
        base, rest = tokens.token_base(token_content)
        if rest:
            return base.split(".")[0].lower()
        return base.lower()

    # ---------------------------------------------------------- Datei-Läufe
    def lint_file(self, filename):
        res = self.store.files.get(filename)
        if res is None:
            return []
        cached = self._file_cache.get(filename)
        if cached and cached[0] == res.digest:
            return cached[1]
        findings = []
        for u in res.units:
            findings.extend(self.lint_value(u))
        # X2: Schema-Platzierung (nur Blueprint-Dateien mit Manifest)
        paths = self.schema_paths(filename) if res.root_tag != "strings" else None
        if paths:
            findings.extend(self._check_schema(res, paths))
        self._file_cache[filename] = (res.digest, findings)
        return findings

    def _check_schema(self, res, allowed):
        """Tag-Ketten direkt aus dem geparsten Baum (Namen mit Sonderzeichen
        sicher), Befund auf Datei-Ebene (uid=None)."""
        out = []
        try:
            root = ET.fromstring(res.text)
        except ET.ParseError:
            return out
        seen = set()

        def walk(el, chain):
            chain = chain + (el.tag,)
            if chain not in allowed and chain not in seen:
                seen.add(chain)
                out.append(_mk(None, "X2", "warning",
                               "Elementpfad %s existiert nicht im Spiel-Manifest "
                               "— wird evtl. still ignoriert (MODWARN prüfen)."
                               % "/".join(chain)))
            for ch in el:
                walk(ch, chain)
        walk(root, ())
        return out

    def naming_findings(self):
        """N1 als Lint: ALLE Bestandsverletzungen (der Writer blockt nur neue).
        Token-Werte -> warning (expandieren evtl. zur Laufzeit), sonst error."""
        naming = self.store.files.get(writer.NAMING_FILE)
        if naming is None:
            return []
        out = []
        vals = writer.naming_attr_values(naming.text)
        for res in self.store.files.values():
            if res.root_tag != "strings":
                continue
            for u in res.units:
                ctx = u.context or ""
                if not ctx.endswith(writer.NAMING_CTX_SUFFIX):
                    continue
                v = u.display_value()
                if not v.strip():
                    continue
                if any(v in nv for nv in vals):
                    continue
                if "=" in v:
                    continue  # Laufzeit-Expansion, nicht datenseitig prüfbar
                # Teilwort-Heuristik: Wert aus Template+Wert zusammengesetzt
                # ("Clan Weißzunge" -> "Weißzunge" vorhanden)?
                parts = [p for p in v.split() if len(p) >= 3]
                partial = any(any(p in nv for nv in vals) for p in parts)
                out.append(_mk(
                    u.uid, "N1", "warning" if partial else "error",
                    "Naming-Substring: „%s“ (Context: %s) kommt in keinem "
                    "Naming.de.xml-Wert vor%s." %
                    (v, ctx, " — Teilwort gefunden, vermutlich Template-"
                             "Komposition (prüfen)" if partial else "")))
        return out

    # ---------------------------------------------------------- Aggregation
    def all_findings(self):
        with self.lock:
            self.store.refresh()
            out = []
            for fn in self.store.files:
                out.extend(self.lint_file(fn))
            out.extend(self.naming_findings())
            out.extend(self.context_findings())
            out.extend(self.plausi_findings())
            return apply_levels(out)

    def context_findings(self):
        try:
            from . import context_lint
        except ImportError:
            return []
        return context_lint.findings(self.store)

    def plausi_findings(self):
        try:
            from . import plausi
        except ImportError:
            return []
        return plausi.findings(self.store)

    def findings_for(self, u):
        with self.lock:
            per_file = self.lint_file(u.file)
            mine = [f for f in per_file if f["uid"] == u.uid]
            mine.extend(f for f in self.naming_findings() if f["uid"] == u.uid)
            mine.extend(f for f in self.context_findings() if f["uid"] == u.uid)
            mine.extend(f for f in self.plausi_findings() if f["uid"] == u.uid)
            return apply_levels(mine)

    def value_findings(self, u):
        """Befunde, die nur vom Wert dieser Einheit abhängen (für Kandidaten-Werte)."""
        from . import context_lint, plausi
        with self.lock:
            return apply_levels(self.lint_value(u) + context_lint.unit_findings(u)
                                + plausi.unit_findings(u))

    def new_errors(self, old_u, new_u):
        """error-Befunde, die der neue Wert ZUSÄTZLICH erzeugt (Bestand blockt nicht)."""
        def errs(x):
            return {(f["rule"], f["message"]) for f in self.value_findings(x)
                    if f["severity"] == "error"}
        return sorted(errs(new_u) - errs(old_u))

    def uids_with_findings(self, severity=None):
        sevs = {severity} if severity else {"error", "warning", "info"}
        return [f["uid"] for f in self.all_findings()
                if f["uid"] and f["severity"] in sevs]

    def summary(self):
        finds = self.all_findings()
        by_rule = {}
        by_sev = {"error": 0, "warning": 0, "info": 0}
        for f in finds:
            by_rule.setdefault(f["rule"], []).append(f)
            by_sev[f["severity"]] = by_sev.get(f["severity"], 0) + 1
        units = {u.uid: u for u in self.store.all_units()}
        det = {}
        for rule, fs in sorted(by_rule.items()):
            det[rule] = {
                "count": len(fs),
                "severity": fs[0]["severity"],
                "samples": [dict(f, file=units[f["uid"]].file if f["uid"] in units else "?",
                                 english=(units[f["uid"]].english or units[f["uid"]].key)
                                 if f["uid"] in units else "?")
                            for f in fs[:200]],
            }
        from .glossary import GLOSSARY
        return {"by_severity": by_sev, "rules": det, "total": len(finds),
                "levels": GLOSSARY.rules()}


_engine = None


def get_engine(store_obj):
    global _engine
    if _engine is None or _engine.store is not store_obj:
        _engine = LintEngine(store_obj)
    return _engine
