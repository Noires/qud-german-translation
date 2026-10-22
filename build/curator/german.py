"""Python-Ports der reinen Grammatikfunktionen aus VariableReplacers.de.cs.

NUR für Vorschau/Lint in der UI — die Wahrheit ist immer das Spiel.
Portiert 1:1 (Zeilenangaben Stand 2026-07-18):
  WeakConjugate   (VariableReplacers.de.cs:709)
  VisibleText     (:124), HeadNoun (:140), GuessGender (:150)
Paritätstest: tests/test_german.py gegen die C#-Selbsttest-Vektoren.
"""
import re

from . import config

# 0 = 3. Sg (er/sie/es), 1 = 2. Pl / "Ihr" (Spieler), 2 = 3. Pl.
PERSON_LABELS = ("s3 (er/sie/es)", "p2 (Ihr)", "p3 (sie)")

SEPARABLE_PREFIXES = (
    "ab", "an", "auf", "aus", "bei", "ein", "fort", "her", "hin", "los",
    "mit", "nach", "vor", "weg", "zurück", "zurueck", "zusammen", "zu",
)
# oft untrennbar — nur Hinweis, kein Fehler
AMBIGUOUS_PREFIXES = ("um", "über", "ueber", "unter", "durch", "wieder", "wider")


def weak_conjugate(inf, person):
    """Schwaches Präsens aus dem Infinitiv (C# WeakConjugate).
    person: 0 = s3, 1 = p2, 2 = p3, 3 = s2 ("du")."""
    if not inf:
        return inf
    if person == 2:
        return inf  # 3. Plural = Infinitiv
    stem = inf[:-2] if inf.endswith("en") else (inf[:-1] if inf.endswith("n") else inf)
    last = stem[-1] if stem else " "
    if person == 3:
        return stem + ("est" if last in ("t", "d") else ("t" if last in "sßxz" else "st"))
    return stem + ("et" if last in ("t", "d") else "t")


def derive_s2(s3, inf):
    """du-Form eines starken Verbs aus s3 (C# DeriveS2): sieht->siehst,
    lässt->lässt, hält->hältst (t-Stamm), lädt->lädst (d-Stamm)."""
    if not s3:
        return weak_conjugate(inf, 3)
    stem = inf[:-2] if inf and inf.endswith("en") else (inf or "")
    sl = stem[-1] if stem else " "
    if s3.endswith(("st", "ßt", "zt", "xt")):  # löst, lässt, zerbirst, heißt
        return s3
    if not s3.endswith("t"):
        return s3
    if sl == "t":
        return s3[:-1] + "st" if s3.endswith("et") else s3 + "st"
    return s3[:-1] + "st"


def visible_text(value):
    """Farb-Markup entfernen (C# VisibleText, Zeile 124)."""
    if not value:
        return value or ""
    result = value
    while True:
        nxt = re.sub(r"\{\{[^{}|]+\|([^{}]*)\}\}", r"\1", result)
        if nxt == result:
            break
        result = nxt
    result = re.sub(r"&.", "", result)
    result = re.sub(r"\^.", "", result)
    return result.strip()


def head_noun(name):
    """Letztes alphabetisches Wort; Bindestrich-Komposita nehmen das Grundwort."""
    words = re.findall(r"[A-Za-zÄÖÜäöüß-]+", visible_text(name))
    if not words:
        return ""
    last = words[-1]
    dash = last.rfind("-")
    if 0 <= dash < len(last) - 1:
        last = last[dash + 1:]
    return last


_FEM_END = ("ung", "heit", "keit", "schaft", "ion", "tät", "taet", "ik",
            "enz", "anz", "ur", "ie")
_NEUT_END = ("chen", "lein", "ment", "tum", "um")
_MASC_END = ("er", "ling", "ismus", "ich", "ig", "ant", "or", "ast")


# Inline-Overrides aus VariableReplacers.de.cs (Zeilen 66–84) — die TSV wird
# im C# ÜBER diese Tabelle gemergt; für Parität muss die Vorschau sie kennen.
INLINE_OVERRIDES = {
    "bär": "m", "baer": "m", "spinne": "f", "käfer": "m", "kaefer": "m",
    "amöbe": "f", "amoebe": "f", "schwein": "n", "hund": "m", "katze": "f",
    "schlange": "f", "ratte": "f", "fledermaus": "f", "vogel": "m", "fisch": "m",
    "leiche": "f", "kadaver": "m", "pilz": "m", "pflanze": "f", "schnecke": "f",
    "affe": "m", "pavian": "m", "wurm": "m", "biene": "f", "skorpion": "m",
    "stein": "m", "wand": "f", "mauer": "f", "boden": "m", "fels": "m",
    "schiefer": "m", "sandstein": "m", "kalkstein": "m", "marmor": "m", "glas": "n",
    "tür": "f", "tuer": "f", "zaun": "m", "säule": "f", "saeule": "f",
    "klinge": "f", "axt": "f", "dolch": "m", "schwert": "n", "speer": "m",
    "stiefel": "m", "handschuh": "m", "helm": "m", "rüstung": "f", "ruestung": "f",
    "haut": "f", "fell": "n", "panzer": "m", "schnabel": "m", "horn": "n",
    "auge": "n", "arm": "m", "bein": "n", "kopf": "m", "hand": "f",
    "flügel": "m", "fluegel": "m", "schwanz": "m", "zunge": "f", "zahn": "m",
}


def load_lexicon(path=None):
    """Effektive Genus-Tabelle wie im C#: Inline-Overrides + TSV darüber
    gemergt (Datei-Einträge gewinnen)."""
    lex = dict(INLINE_OVERRIDES)
    p = path or config.GENDER_LEXICON
    try:
        with open(p, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = raw.split("\t")
                if len(parts) < 2:
                    continue
                noun = parts[0].strip().lower()
                g = parts[1].strip().lower()
                if noun and g in ("m", "f", "n", "p"):
                    lex[noun] = g
    except OSError:
        pass
    return lex


def guess_gender(name, lexicon):
    """C# GuessGender (Zeile 150): exakt -> längster Suffix >=3 -> Endung -> m.
    -> (gender, quelle) mit quelle in {'exakt','suffix:<key>','endung','default'}."""
    head = head_noun(name)
    if not head:
        return "n", "leer"
    h = head.lower()
    if h in lexicon:
        return lexicon[h], "exakt"
    best_len, best_g, best_k = 0, "m", None
    for k, g in lexicon.items():
        if len(k) >= 3 and len(k) < len(h) and len(k) > best_len \
           and h.endswith(k):
            best_len, best_g, best_k = len(k), g, k
    if best_len:
        return best_g, "suffix:%s" % best_k
    for e in _FEM_END:
        if h.endswith(e):
            return "f", "endung"
    for e in _NEUT_END:
        if h.endswith(e):
            return "n", "endung"
    for e in _MASC_END:
        if h.endswith(e):
            return "m", "endung"
    if h.endswith("e"):
        return "f", "endung"
    return "m", "default"


def separable_prefix(inf):
    """-> (prefix, ambiguous) oder (None, False)."""
    low = (inf or "").lower()
    for p in SEPARABLE_PREFIXES:
        if low.startswith(p) and len(low) > len(p) + 2:
            return p, False
    for p in AMBIGUOUS_PREFIXES:
        if low.startswith(p) and len(low) > len(p) + 2:
            return p, True
    return None, False


def suffix_consequences(noun, gender, lexicon, candidates):
    """Konsequenz-Vorschau für einen (neuen) Lexikon-Eintrag noun->gender:
    welche Kopf-Nomen aus `candidates` würden ihr Genus dadurch ändern?
    -> Liste (kopfnomen, alt(gender,quelle), neu(gender,quelle))."""
    new_lex = dict(lexicon)
    new_lex[noun.lower()] = gender
    changes = []
    for cand in candidates:
        old = guess_gender(cand, lexicon)
        new = guess_gender(cand, new_lex)
        if old != new:
            changes.append((cand, old, new))
    return changes
