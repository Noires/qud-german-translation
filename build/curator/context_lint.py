"""Kontext-Prüfregeln: korpusweite Verallgemeinerung der Befunde, die die
Szenen-Vorschau sichtbar gemacht hat. Eingehängt in lint.LintEngine.all_findings.

  K1 ID veraltet: Context existiert im Spiel-Gesprächsbaum, die ID
     (englischer Text) stimmt aber nicht mehr — der Wert greift nie   warning
  K2 Anrede weicht von der Richtlinie ab (du/Sie/Ihr, glossary.json)  warning
  K3 konjde ohne Subjekt-Namen, wo die Vorlage Does (mit Name) hat    warning
  K4 Possessiv-Token ohne Kasus/Genus vor Folgewort (undekliniert)    info
  K5 Weichen-Token (ifplayerplural/isplural) mit englischen Argumenten
     oder doppelter Anrede dahinter                                  warning
  K6 =X.them=/=X.objective= nach Dativ-Präposition/-Verb ohne :dat     warning
  G1 Glossar-Begriff im EN, deutsche Festlegung fehlt / verbotene Variante  warning
  G2 Artikel vor Glossar-Begriff passt nicht zum Genus (inkl. Genitiv-s)    warning

Heuristiken sind bewusst konservativ formuliert; die Meldung nennt immer die
Fundstelle, damit der Kurator in der Vorschau entscheiden kann.
"""
import os
import re
import threading

from . import convtree, german, grammar_emu
from .glossary import GLOSSARY

TOKEN_RE = grammar_emu.TOKEN_RE
_lock = threading.Lock()
_cache = {"sig": None, "findings": []}

# --- K2: Anrede-Formen (auf sichtbarem Text ohne Tokens) ---------------------
_DU = re.compile(r"\b(?:du|dich|dir|dein|deine[mnrs]?)\b", re.I)
# Höflichkeits-Ihr: großgeschriebene Formen (Euch/Euer/Eure…, "Ihr habt").
# Kleingeschriebenes euch/euer/"ihr habt" OHNE großes Gegenstück ist meist echte
# Plural-Anrede an eine Gruppe -> eigene Form "ihr" (nur Hinweis, nicht erzwungen du).
# Verb klein („Ihr Licht“ ≠ Ihr habt); „seid“ endet nicht auf -t (fehlte bis 2026-10-22)
_IHR = re.compile(r"\b(?:Euch|Euer|Eure[mnrs]?)\b|\bIhr\s+(?:[a-zäöüß]\w*t|seid)\b")
_IHR_BARE = re.compile(r"\bIhr\b(?!\s*[A-ZÄÖÜ])")
_IHR_PL = re.compile(r"\b(?:euch|euer|eure[mnrs]?)\b|\bihr\s+\w+t\b")
_SIE_POSS = re.compile(r"\b(?:Ihnen|Ihre[mnrs]?)\b")
_SIE_CAP = re.compile(r"\bSie\b")
_SENTENCE_START = re.compile(r"(?:^|[.!?:\"„»«*\n]\s*)$")
_CHOICE_SEG = re.compile(r"Choice\d*$")


def _visible(value):
    return german.visible_text(TOKEN_RE.sub(" ", value or ""))


def address_forms(value):
    """-> {form: Beleg} für du / Sie / Ihr (Spieler-Anrede-Heuristik)."""
    txt = _visible(value)
    out = {}
    m = _DU.search(txt)
    if m:
        out["du"] = m.group(0)
    m = _IHR.search(txt)
    if m:
        out["Ihr"] = m.group(0)
    else:
        # "weil Ihr =reason=": großes Ihr satzintern OHNE folgendes Nomen ist das
        # Pronomen (Ihr + Nomen wäre Possessiv „Ihr Licht“ = ihr/ihres)
        for m in _IHR_BARE.finditer(txt):
            if not _SENTENCE_START.search(txt[:m.start()]):
                out["Ihr"] = txt[max(0, m.start() - 12):m.end()].strip()
                break
    m = _IHR_PL.search(txt)
    if m:
        # mit großem Ihr im selben Text ist auch das kleine euch Höflichkeitsform
        out["Ihr" if "Ihr" in out else "ihr"] = out.get("Ihr") or m.group(0)
    for m in _SIE_POSS.finditer(txt):
        if not _SENTENCE_START.search(txt[:m.start()]):
            out["Sie"] = m.group(0)
            break
    if "Sie" not in out:
        for m in _SIE_CAP.finditer(txt):
            if not _SENTENCE_START.search(txt[:m.start()]):
                out["Sie"] = txt[max(0, m.start() - 12):m.end()].strip()
                break
    return out


def is_choice_context(context):
    segs = (context or "").split(".")
    return any(_CHOICE_SEG.search(s) for s in segs[1:-1])


# --- K3: Does -> konjde ohne Subjekt -----------------------------------------
_DOES = re.compile(r"=(\w+)\.[Dd](?:oes|id)[:#=]")
_NAMING_KEYS = {"the.name", "t", "name", "nominativ", "a.name", "a.nominativ",
                "subjective", "refname", "they", "formattedname", "the.name's",
                "t's", "name's", "does", "did"}


def _token_role_key(inner):
    head = inner.split("|")[0].split("#")[0].split(":")[0]
    segs = head.split(".")
    if len(segs) < 2:
        return None, None
    key = ".".join(s[:1].lower() + s[1:] for s in segs[1:]).lower()
    return segs[0].lower(), key


def konjde_without_subject(english, value):
    roles = {m.group(1).lower() for m in _DOES.finditer(english or "")}
    if not roles:
        return []
    have_konjde, named = set(), set()
    for m in TOKEN_RE.finditer(value or ""):
        role, key = _token_role_key(m.group(1))
        if role is None:
            continue
        if key == "konjde":
            have_konjde.add(role)
        elif key in _NAMING_KEYS:
            named.add(role)
    return sorted((roles & have_konjde) - named)


# --- K4: Possessiv ohne Annotation -------------------------------------------
_POSS = re.compile(r"=(\w+)\.(possessive|its|their|possessiveAdjective)=\s+(\w+)", re.I)


def unannotated_possessive(value):
    return [("=%s.%s=" % (m.group(1), m.group(2)), m.group(3)) for m in _POSS.finditer(value or "")]


# --- K5: Text-Argumente von Weichen-Tokens unübersetzt -----------------------
# TernaryPlural & Co. geben ein Argument WÖRTLICH aus — es ist übersetzbarer Text
_TERNARY = re.compile(r"=((?:\w+\.)?(?:ifplayerplural|isplural|ifplural)):([^=]*)=", re.I)
# „hast"/„art" fehlen bewusst (deutsch: du hast, die Art) — wörtliche Reste der
# Vorlage fängt der Vergleich mit den englischen Argumenten
_EN_ARG = re.compile(r"\b(?:ye|thou|thee|thy|thine|hath|thou'rt|wilt|shalt|wouldst|"
                     r"shouldst|couldst|canst|mayest|mayst|dost|doth|needest|knowest|askest|"
                     r"seekest|you|your|yours|have|has|are|is|were|would|shall|should|might|"
                     r"need|know|seek|ask|the)\b|\b\w+eth\b", re.I)
_DU_AFTER = re.compile(r"^\s*(?:du|dich|dir|dein\w*)\b", re.I)


def untranslated_token_args(english, value):
    """-> [Meldung] für Weichen-Tokens mit englischen Argumenten bzw. mit
    doppelter deutscher Anrede direkt dahinter (Token + „du …“)."""
    en_args = {m.group(0) for m in _TERNARY.finditer(english or "")}
    out = []
    for m in _TERNARY.finditer(value or ""):
        if _EN_ARG.search(m.group(2)) or (m.group(0) in en_args and re.search(r"[A-Za-z]", m.group(2))):
            out.append("%s: Argumente englisch — werden im Spiel wörtlich ausgegeben" % m.group(0))
        elif m.group(1).lower() == "ifplayerplural" and _DU_AFTER.search(value[m.end():]):
            out.append("%s: Anrede steht doppelt (Token + „%s“)"
                       % (m.group(0), _DU_AFTER.search(value[m.end():]).group(0).strip()))
    return out


# --- K6: Objektpronomen ohne Dativ nach Dativ-Wort ---------------------------
# =X.them= / =X.objective= liefert den Akkusativ (ihn/sie/es) — nach reinen
# Dativ-Präpositionen und Dativ-Verben braucht es =X.them:dat= (ihm/ihr/ihnen).
# Wechselpräpositionen (in/an/auf/unter/über …) entscheidet der Kurator (Bewegung = Akk.).
DATIVE_TRIGGERS = ("von", "mit", "aus", "zu", "nahe", "bei", "nach", "seit", "gegenüber",
                   "außer", "entgegen", "hilft", "helfen", "half", "halfen", "geholfen",
                   "dankt", "danken", "folgt", "folgen", "gehört", "gehören")
_OBJ_PRON = re.compile(r"(?:\b(%s)|=\w+\.isplural:helfen:hilft=)\s+(=\w+\.(?:them|objective)=)"
                       % "|".join(DATIVE_TRIGGERS), re.I)


def object_pronoun_without_dative(value):
    return [(m.group(1) or "helfen", m.group(2)) for m in _OBJ_PRON.finditer(value or "")]


# --- G2: Artikel/Genus ---------------------------------------------------------
def _determiners(g):
    out = set()
    for c in (grammar_emu.NOM, grammar_emu.ACC, grammar_emu.DAT, grammar_emu.GEN):
        out.add(grammar_emu.definite(g, c))
        ind = grammar_emu.indefinite(g, c)
        if ind:
            out.add(ind)
    return out


ALL_DETS = sorted(_determiners("m") | _determiners("f") | _determiners("n") | _determiners("p"),
                  key=len, reverse=True)


def article_mismatches(value, term):
    """Bestimmer direkt vor dem Begriff (max. 2 kleingeschriebene Wörter
    dazwischen) passt in keinem Kasus zum Glossar-Genus; Genitiv m/n ohne -s."""
    g = term.get("gender")
    de = term.get("de")
    if not g or not de:
        return []
    ok = _determiners(g)
    # nur Bestimmer und Begriff case-insensitiv; dazwischen ausschließlich
    # kleingeschriebene Wörter (Adjektive/Adverbien) — sonst gehört der
    # Artikel zu einem anderen Nomen ("der Nähe zum Baetyl")
    rx = re.compile(r"\b(?i:(%s))\s+((?:[a-zäöüß][\w-]*\s+){0,2})(?i:(%s))(s|es)?\b"
                    % ("|".join(ALL_DETS), re.escape(de)))
    plural_dets = _determiners("p")
    out = []
    txt = _visible(value)
    for m in rx.finditer(txt):
        det = m.group(1).lower()
        if m.group(4) and det in plural_dets:
            # -s-Form nach die/der/den = Plural-Gebrauch ("der Baetyls")
            pl = term.get("plural")
            if pl and pl.lower() != (m.group(3) + m.group(4)).lower():
                out.append("„%s“: Plural laut Glossar „%s“" % (m.group(0), pl))
            continue
        if det not in ok:
            out.append("„%s“ passt nicht zu %s (%s)" % (m.group(0), de, g))
        elif det in ("des", "eines") and g in ("m", "n") and not m.group(4):
            out.append("„%s“: Genitiv %s ohne -s" % (m.group(0), de))
    return out


def term_missing(english, value, term):
    en = term.get("en")
    if not en or not re.search(r"\b%s\b" % re.escape(en), _visible(english), re.I):
        return None
    vis = _visible(value)
    for bad in term.get("variants_forbidden") or []:
        if re.search(r"\b%s\b" % re.escape(bad), vis, re.I):
            return "verbotene Variante „%s“ statt „%s“" % (bad, term["de"])
    forms = [term.get("de"), term.get("plural")]
    if any(f and re.search(r"\b%s" % re.escape(f), vis, re.I) for f in forms):
        return None
    return "„%s“ im Englischen, aber „%s“ fehlt im Deutschen" % (en, term["de"])


# --- Aggregation ---------------------------------------------------------------
def _mk(uid, rule, severity, message):
    return {"uid": uid, "rule": rule, "severity": severity, "message": message}


def _log_path():
    from . import config
    return config.CFG.get("player_log")


def _log_sig():
    try:
        st = os.stat(_log_path())
        return (st.st_mtime_ns, st.st_size)
    except (OSError, TypeError):
        return None


def _signature(store):
    tree_sig = convtree.TREE._sig
    return (id(store.units), GLOSSARY.sig(), tree_sig, _log_sig())


def logged_misses():
    """(Context, erste ID-Zeile) aller String-Misses des letzten Spiel-Laufs.
    Mehrzeilige IDs stehen im Log umbrochen — verglichen wird die erste Zeile."""
    if _log_sig() is None:
        return set()
    from . import playerlog
    try:
        res = playerlog.parse_log(_log_path())
    except OSError:
        return set()
    import html
    # das Spiel loggt die ID XML-escaped (Zeilenumbrüche als &#xA;)
    return {(m["context"], html.unescape(m["id"]).split("\n")[0].strip())
            for m in res.get("misses", [])}


def findings(store):
    convtree.TREE.load() if convtree.TREE.available() else None
    sig = _signature(store)
    with _lock:
        if _cache["sig"] == sig:
            return _cache["findings"]
    out = []
    out += _k1(store)
    policy = GLOSSARY.policy()
    terms = GLOSSARY.terms()
    for u in store.all_units():
        value = u.display_value()
        if not value:
            continue
        english = u.english or ""
        # Anrede gilt korpusweit (Spielmeldungen sprechen den Spieler genauso an)
        conv = (u.context or "").startswith("Conversation ")
        choice = conv and is_choice_context(u.context)
        want = policy["choice_address"] if choice else policy["player_address"]
        forms = address_forms(value)
        bad = {f: ev for f, ev in forms.items() if f != want and f != "ihr"}
        where = "Antwort" if choice else ("NPC-Text" if conv else "Spieltext")
        if bad:
            out.append(_mk(u.uid, "K2", "warning", "Anrede %s — Richtlinie: %s (%s)" % (
                ", ".join("%s-Form „%s“" % (f, ev) for f, ev in sorted(bad.items())), want, where)))
        elif "ihr" in forms and want != "Ihr":
            out.append(_mk(u.uid, "K2", "info", "Plural-Anrede „%s“ (Gruppe?) — prüfen, ob "
                           "der Spieler gemeint ist (%s)" % (forms["ihr"], where)))
        for role in konjde_without_subject(english, value):
            out.append(_mk(u.uid, "K3", "warning",
                           "=%s.Does…= (Name + Verb) wurde zu konjde ohne Namen von %s — "
                           "im Spiel fehlt das Subjekt (z. B. =%s.The.name= ergänzen)"
                           % (role, role, role)))
        for msg in untranslated_token_args(english, value):
            out.append(_mk(u.uid, "K5", "warning", msg))
        for word, tok in object_pronoun_without_dative(value):
            out.append(_mk(u.uid, "K6", "warning",
                           "„%s %s“: Objektpronomen nach Dativ-Wort ohne :dat — im Spiel "
                           "steht der Akkusativ („von ihn“)" % (word, tok)))
        for tok, nxt in unannotated_possessive(value):
            out.append(_mk(u.uid, "K4", "info",
                           "%s vor „%s“ ohne Kasus/Genus (:nom:f …) — wird undekliniert "
                           "(sein/ihr) ausgegeben" % (tok, nxt)))
        for t in terms:
            miss = term_missing(english, value, t) if english else None
            if miss:
                out.append(_mk(u.uid, "G1", "warning", "Glossar: " + miss))
            for msg in article_mismatches(value, t):
                out.append(_mk(u.uid, "G2", "warning", "Glossar-Genus: " + msg))
    with _lock:
        _cache["sig"] = sig
        _cache["findings"] = out
    return out


def _k1(store):
    if not convtree.TREE.available():
        return []
    from .scenes import SceneBuilder
    b = SceneBuilder(store)
    misses = logged_misses()
    manifest = manifest_conversation_ids()
    out = []
    seen = set()
    for path, en in tree_texts().items():
        u, match = b.lookup(path, en)
        # Manifest-ID ist maßgeblich: stimmt der Eintrag byte-genau damit überein, ist er
        # aktuell (dynamisch zusammengesetzte Knoten weichen im Baum-Text ab)
        if match == "staleid" and manifest.get(path) == u.english:
            continue
        if match == "staleid" and u.uid not in seen:
            seen.add(u.uid)
            confirmed = (path, en.split("\n")[0].strip()) in misses
            out.append(_mk(u.uid, "K1", "warning",
                           "ID veraltet — Spieltext ist jetzt „%s“; dieser Eintrag (ID „%s“) "
                           "greift nie. Neu anlegen mit aktueller ID.%s" % (
                               _short(en), _short(u.english),
                               " ✓ im Spiel bestätigt (Player.log-Miss)" if confirmed else
                               " (Bestätigung: Gespräch im Spiel einmal aufrufen → Player.log-Miss)")))
    return out


def rekey(store, uid):
    """K1-Behebung: neuen Eintrag mit der AKTUELLEN englischen ID anlegen
    (gleicher Context, alter Wert). Der alte bleibt — der Writer löscht nie.
    -> (neue Einheit, alte Einheit)."""
    from . import writer
    u = store.get(uid)
    if u is None:
        raise LookupError("Einheit nicht gefunden — Index neu laden.")
    current = tree_texts().get(u.context or "")
    if not current or current == u.english:
        raise ValueError("Keine veraltete ID: Context nicht im Spielbaum oder ID aktuell.")
    new = writer.create_string_entry(store, u.file, u.context, current, u.display_value())
    return new, u


def manifest_conversation_ids():
    """Context -> exakte ID aus Strings.Conversations.example.xml (▶-Manifest)."""
    import xml.etree.ElementTree as ET
    from . import config
    p = os.path.join(config.CFG["game_example_dir"], "Strings.Conversations.example.xml")
    try:
        root = ET.parse(p).getroot()
    except (OSError, ET.ParseError):
        return {}
    return {el.get("Context"): el.get("ID") for el in root.iter("string")}


def tree_texts():
    """Context-Pfad -> aktueller englischer Text (alle Texte des Baums)."""
    out = {}
    for c in convtree.TREE.load().values():
        def add(items):
            for x in items:
                out[x["path"]] = x["en"]
        for n in c["nodes"]:
            add(n["texts"])
            add(n["parts"])
            for ch in n["choices"]:
                add(ch["texts"])
                add(ch["parts"])
        for ch in c["choices"]:
            add(ch["texts"])
            add(ch["parts"])
    return out


def _short(s, n=60):
    s = (s or "").replace("\n", " ")
    return s if len(s) <= n else s[:n - 1] + "…"
