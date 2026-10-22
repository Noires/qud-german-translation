"""Python-Emulation der deutschen Token-Replacer für die Szenen-Vorschau.

NUR Vorschau — die Wahrheit ist immer das Spiel. 1:1-Port der deutschen
Replacer aus languages/lang-de/CODE/VariableReplacers.de.cs (Kasus-System,
Adjektivdeklination, Possessive, konjde/Does, Körperteile) auf Stichproben-
Objekten statt GameObjects. Paritätstest: tests/test_grammar_emu.py gegen
die C#-Selbsttest-Vektoren und [VariableExample]-Attribute.

Was NICHT im C# der Mod steht (Spiel-eigene Replacer: Pronomen, name,
Faction-/Zahl-Tokens …), wird angenähert (Pronomen aus Genders.de.xml,
Gewürz-Texte aus HistorySpice.jsonc) oder aus der Stichproben-Tabelle
data/sample_values.json gefüllt. Unbekanntes bleibt sichtbar als Token.

resolve(template, ctx) -> {"text": str mit Markern, "tokens": [...]}
  Jede Token-Ausgabe steht im Text zwischen TOK_START und TOK_END; tokens[k]
  beschreibt das k-te Token: {src, out, how} mit how in
  emu (Mod-Replacer emuliert) | approx (Spiel-Replacer angenähert) |
  spice | sample | unknown | en (englischer Fallback des Spiels).
"""
import json
import os
import re
import threading
import xml.etree.ElementTree as ET

from . import config, german

TOK_START = "\u0001"
TOK_END = "\u0002"

M, F, N, P = "m", "f", "n", "p"
NOM, ACC, DAT, GEN = 0, 1, 2, 3
WEAK, MIXED, STRONG = 0, 1, 2

TOKEN_RE = re.compile(r"=([^=\s][^=]*?)=")

SAMPLES_PATH = os.path.join(config.DATA_DIR, "sample_values.json")
GENDERS_XML = os.path.join(config.LANG_DE, "Genders.de.xml")
SPICE_JSONC = os.path.join(config.LANG_DE, "HistorySpice.jsonc")

_lock = threading.Lock()
_cache = {}


def _cached(key, path, loader):
    """Datei-gebundener Cache (mtime+size), wie Store/Review."""
    try:
        st = os.stat(path)
        sig = (st.st_mtime_ns, st.st_size)
    except OSError:
        sig = None
    with _lock:
        hit = _cache.get(key)
        if hit and hit[0] == sig:
            return hit[1]
    val = loader(path) if sig else loader(None)
    with _lock:
        _cache[key] = (sig, val)
    return val


# ------------------------------------------------------------ Datenquellen

def lexicon():
    return _cached("lex", config.GENDER_LEXICON, lambda p: german.load_lexicon(p))


def _load_verbs(path):
    by_inf, by_en = {}, {}
    if not path:
        return by_inf, by_en
    try:
        with open(path, encoding="utf-8") as f:
            arr = json.load(f).get("verbs", [])
    except (OSError, ValueError):
        return by_inf, by_en
    for v in arr:
        inf, s3 = v.get("inf"), v.get("s3")
        # wie LoadVerbs: nur STARKE Verben (explizites s3) kommen in die Tabelle
        if not inf or not s3:
            continue
        forms = [s3, v.get("p2") or inf, v.get("p3") or inf,
                 v.get("s2") or german.derive_s2(s3, inf)]
        by_inf[inf.lower()] = forms
        for e in (v.get("en") or "").split("/"):
            if e.strip():
                by_en[e.strip().lower()] = forms
    return by_inf, by_en


def verbs():
    return _cached("verbs", config.VERBS_JSON, _load_verbs)


PLURAL_LEXICON = os.path.join(config.LANG_DE, "COQDE", "PluralLexicon.tsv")


def _load_plurals(path):
    out = {}
    if not path:
        return out
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = raw.split("\t")
                if len(parts) < 2:
                    continue
                sg, pl = parts[0].strip().lower(), parts[1].strip().lower()
                if sg and pl:
                    out[sg] = pl
    except OSError:
        pass
    return out


def plurals():
    return _cached("plurals", PLURAL_LEXICON, _load_plurals)


def _load_genders(path):
    out = {}
    if not path:
        return out
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return out
    for g in root.iter("gender"):
        out[g.get("Name")] = dict(g.attrib)
    return out


def genders():
    return _cached("genders", GENDERS_XML, _load_genders)


def _load_spice(path):
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        return {}
    # JSONC: Zeilenkommentare außerhalb von Strings entfernen
    out, i, n, in_str = [], 0, len(raw), False
    while i < n:
        c = raw[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(raw[i + 1])
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif raw.startswith("//", i):
            while i < n and raw[i] != "\n":
                i += 1
            continue
        elif raw.startswith("/*", i):
            j = raw.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        else:
            out.append(c)
        i += 1
    txt = re.sub(r",(\s*[}\]])", r"\1", "".join(out))
    try:
        return json.loads(txt).get("spice", {})
    except ValueError:
        return {}


def spice():
    return _cached("spice", SPICE_JSONC, _load_spice)


DEFAULT_SAMPLES = {
    "objects": {
        "player": {"label": "Spieler (du)", "name": "du", "player": True,
                   "game_gender": "male"},
        "snapjaw": {"label": "Schnappkiefer (m)", "name": "Schnappkiefer",
                    "blueprint": "Snapjaw", "game_gender": "neuter"},
        "croc": {"label": "Krokodil (n)", "name": "Krokodil", "blueprint": "Croc",
                 "game_gender": "neuter"},
        "goat": {"label": "Ziege (f)", "name": "Ziege", "blueprint": "Goat",
                 "game_gender": "neuter"},
        "glowfish": {"label": "Leuchtfisch (m)", "name": "Leuchtfisch",
                     "blueprint": "Glowfish", "game_gender": "neuter"},
        "glowfish_pl": {"label": "Leuchtfische (Plural)", "name": "Leuchtfische",
                        "plural": True, "game_gender": "plural"},
        "warden": {"label": "Warden Ualraig (Eigenname, m)", "name": "Warden Ualraig",
                   "proper": True, "game_gender": "male"},
        "mehmet": {"label": "Mehmet (Eigenname, f)", "name": "Mehmet",
                   "proper": True, "game_gender": "female"},
        "vineblade": {"label": "eiserne Rebenklinge (f)", "name": "eiserne Rebenklinge",
                      "game_gender": "neuter"},
        "torch": {"label": "Fackel (f)", "name": "Fackel", "blueprint": "Torch",
                  "game_gender": "neuter"},
        "right_hand": {"label": "rechte Hand (Körperteil)", "part": True,
                       "eng": "right hand", "lat": 2, "owner": "player"},
        "left_leg": {"label": "linkes Bein (Körperteil)", "part": True,
                     "eng": "left leg", "lat": 1},
    },
    "roles": {"subject": "snapjaw", "object": "croc", "player": "player",
              "item": "vineblade", "weapon": "vineblade", "part": "right_hand",
              "limb": "left_leg", "pronouns": "subject"},
    "tokens": {
        "name": "Ihr Name",
        "factionaddress": "Freund",
        "V0tinkeraddendum": "",
        "commandKey": "{{W|[Leer]}}",
        "village.sacred": "die heiligen Quellen",
        "villageZeroName": "Kyakukya",
        "sultan": "Resheph",
        "faction.name": "Barathrumiten",
        "faction.the.name": "den Barathrumiten",
        "faction.formattedName": "die Barathrumiten",
        "liquid.name": "Süßwasser",
        "amount.signed": "+2",
        "bonus.signed": "+1",
        "glyph": "@",
    },
}


def samples():
    """Stichproben: Defaults, überlagert von data/sample_values.json."""
    def load(path):
        data = json.loads(json.dumps(DEFAULT_SAMPLES))
        if path:
            try:
                with open(path, encoding="utf-8") as f:
                    user = json.load(f)
                for k in ("objects", "roles", "tokens"):
                    data[k].update(user.get(k, {}))
            except (OSError, ValueError):
                pass
        return data
    return _cached("samples", SAMPLES_PATH, load)


def save_samples(data):
    clean = {k: data.get(k, {}) for k in ("objects", "roles", "tokens")}
    os.makedirs(os.path.dirname(SAMPLES_PATH), exist_ok=True)
    tmp = SAMPLES_PATH + ".curator-tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, SAMPLES_PATH)


# ------------------------------------------------- Port: Grammatik-Kern (C#)

def visible_text(v):
    return german.visible_text(v)


def guess_gender(name):
    return german.guess_gender(name, lexicon())[0]


def cap(s, capitalize):
    if not capitalize or not s:
        return s
    return s[0].upper() + s[1:]


def definite(g, c):
    if g == M:
        return "des" if c == GEN else "dem" if c == DAT else "den" if c == ACC else "der"
    if g == F:
        return "der" if c in (DAT, GEN) else "die"
    if g == N:
        return "des" if c == GEN else "dem" if c == DAT else "das"
    return "den" if c == DAT else "der" if c == GEN else "die"


def indefinite(g, c):
    if g == M:
        return "einem" if c == DAT else "eines" if c == GEN else "einen" if c == ACC else "ein"
    if g == F:
        return "einer" if c in (DAT, GEN) else "eine"
    if g == N:
        return "einem" if c == DAT else "eines" if c == GEN else "ein"
    return ""


def genitive_noun(name, g):
    if g in (F, P) or not name:
        return name
    last = name[-1].lower()
    return name + ("es" if last in "sßxz" else "s")


def adj_ending(t, c, g):
    if t == WEAK:
        if c == NOM:
            return "en" if g == P else "e"
        if c == ACC:
            return "en" if g in (M, P) else "e"
        return "en"
    if t == MIXED:
        if c == NOM:
            return {M: "er", F: "e", N: "es"}.get(g, "en")
        if c == ACC:
            return {M: "en", F: "e", N: "es"}.get(g, "en")
        return "en"
    if c == NOM:
        return {M: "er", F: "e", N: "es"}.get(g, "e")
    if c == ACC:
        return {M: "en", F: "e", N: "es"}.get(g, "e")
    if c == DAT:
        return "er" if g == F else "en" if g == P else "em"
    return "er" if g in (F, P) else "en"


def adj_stem(word):
    w = word.lower()
    for suf in ("em", "en", "er", "es", "e"):
        if len(w) - len(suf) >= 3 and w.endswith(suf):
            return w[:len(w) - len(suf)]
    return w


FUNCTION_WORDS = {
    "aus", "mit", "von", "der", "die", "das", "dem", "den", "des", "ein", "eine",
    "einem", "einen", "einer", "eines", "und", "im", "in", "an", "auf", "für", "fuer",
    "zu", "zur", "zum", "voller", "ohne", "über", "ueber", "unter",
}
_COLOR_WRAP = re.compile(r"^(\{\{[^|{}]+\|)(.+?)(\}\})$")
_COLOR_PREFIX = re.compile(r"^((?:[&^].)+)(.+)$")


def split_color(w):
    pre, core, post = "", w, ""
    m = _COLOR_WRAP.match(core)
    if m:
        pre, core, post = m.group(1), m.group(2), m.group(3)
    p = _COLOR_PREFIX.match(core)
    if p:
        pre += p.group(1)
        core = p.group(2)
    return pre, core, post


def decline_adj(word, t, c, g):
    pre, core, post = split_color(word)
    return pre + adj_stem(core) + adj_ending(t, c, g) + post


def _fw(w):
    return w.lower() in FUNCTION_WORDS


def is_adj_noun_pattern(words):
    if not words:
        return False
    head = split_color(words[-1])[1]
    if not head or not head[0].isupper():
        return len(words) == 1
    for w in words[:-1]:
        core = split_color(w)[1]
        if not core or _fw(core):
            return False
        for ch in core:
            if not ch.isalpha() or ch.isupper():
                return False
    return True


def phrase_gender_head(words):
    for i in range(1, len(words)):
        if _fw(words[i]):
            return words[i - 1]
    return words[-1]


def _words(name):
    return [w for w in name.split(" ") if w]


def build_definite_phrase(name, c, plural, capitalize):
    words = _words(name)
    if not words:
        return name
    g = P if plural else guess_gender(phrase_gender_head(words))
    if not is_adj_noun_pattern(words):
        return cap(definite(g, c), capitalize) + " " + name
    parts = [cap(definite(g, c), capitalize)]
    parts += [decline_adj(w, WEAK, c, g) for w in words[:-1]]
    parts.append(genitive_noun(words[-1], g) if c == GEN else words[-1])
    return " ".join(parts)


def build_indefinite_phrase(name, c, plural, capitalize):
    words = _words(name)
    if not words:
        return name
    g = P if plural else guess_gender(phrase_gender_head(words))
    art = indefinite(g, c)
    if not is_adj_noun_pattern(words):
        return cap(name, capitalize) if not art else cap(art, capitalize) + " " + name
    decl = STRONG if not art else MIXED
    parts = [cap(art, capitalize)] if art else []
    parts += [decline_adj(w, decl, c, g) for w in words[:-1]]
    parts.append(genitive_noun(words[-1], g) if c == GEN else words[-1])
    if not art and capitalize and parts:
        parts[0] = cap(parts[0], True)
    return " ".join(parts)


def decline_poss(stem, g, c):
    if stem not in ("sein", "ihr", "euer", "mein", "dein", "unser"):
        return stem
    if c == NOM:
        end = "e" if g in (F, P) else ""
    elif c == ACC:
        end = "en" if g == M else ("" if g == N else "e")
    elif c == DAT:
        end = "er" if g == F else ("en" if g == P else "em")
    else:
        end = "er" if g in (F, P) else "es"
    if not end:
        return stem
    return ("eur" if stem == "euer" else stem) + end


def build_possessive_phrase(name, c, plural, capitalize, stem="dein"):
    words = _words(name)
    if not words:
        return name
    g = P if plural else guess_gender(phrase_gender_head(words))
    det = decline_poss(stem, g, c)
    if not is_adj_noun_pattern(words):
        return cap(det, capitalize) + " " + name
    parts = [cap(det, capitalize)]
    parts += [decline_adj(w, MIXED, c, g) for w in words[:-1]]
    parts.append(genitive_noun(words[-1], g) if c == GEN else words[-1])
    return " ".join(parts)


def decline_after_article(s, plural=False):
    allw = _words(s or "")
    if len(allw) < 3:
        return s
    art, rest = allw[0], allw[1:]
    if not is_adj_noun_pattern(rest):
        return s
    low = art.lower()
    if low == "der":
        g, decl = M, WEAK
    elif low == "das":
        g, decl = N, WEAK
    elif low == "die":
        g, decl = (P if plural else F), WEAK
    elif low == "eine":
        g, decl = F, MIXED
    elif low == "ein":
        g = guess_gender(phrase_gender_head(rest))
        if g == F:
            g = M
        decl = MIXED
    else:
        return s
    return " ".join([art] + [decline_adj(w, decl, NOM, g) for w in rest[:-1]] + [rest[-1]])


def german_possessive_suffix(s):
    if not s:
        return s
    wrap = 0
    while s.endswith("}}"):
        wrap += 1
        s = s[:-2]
    last = s[-1].lower() if s else " "
    s += "'" if last in "sßxz" else "s"
    return s + "}}" * wrap


def weak_conjugate(inf, person):
    return german.weak_conjugate(inf, person)


def try_german_verb(verb, person):
    """C# TryGermanVerb -> Form oder None."""
    if not verb:
        return None
    v = verb.strip()
    by_inf, by_en = verbs()
    f = by_inf.get(v.lower()) or by_en.get(v.lower())
    if f:
        return f[person] or None
    low = v.lower()
    if any(u in low for u in "äöüß") and low.endswith("en"):
        return weak_conjugate(low, person)
    return None


BODY_PART_TERMS = {
    "head": "Kopf", "face": "Gesicht", "eye": "Auge", "eyes": "Augen",
    "hand": "Hand", "hands": "Hände", "arm": "Arm", "arms": "Arme",
    "foot": "Fuß", "feet": "Füße", "leg": "Bein", "legs": "Beine",
    "tail": "Schwanz", "claw": "Klaue", "tongue": "Zunge", "wing": "Flügel",
    "body": "Körper", "head slot": "Kopf",
}
_LAT_WORDS = ("left", "right", "upper", "lower", "fore", "mid", "hind", "inner", "outer")


def laterality_adjectives(code, g):
    e = "e" if g in (F, P) else ("es" if g == N else "er")
    parts = []
    for flag, stem in ((4, "ober"), (8, "unter"), (16, "vorder"), (32, "mittler"),
                       (64, "hinter"), (512, "inner"), (1024, "äußer"),
                       (128, "inner"), (256, "äußer"), (1, "link"), (2, "recht")):
        if code & flag:
            parts.append(stem + e)
    return " ".join(parts)


def translate_body_part_name(eng):
    if not eng:
        return eng
    hit = BODY_PART_TERMS.get(eng.strip().lower())
    if hit:
        return hit
    return " ".join(BODY_PART_TERMS.get(w.lower(), w) for w in eng.split(" "))


def transform_body_part(eng, lat):
    if not eng:
        return eng
    if "{{" in eng or "[" in eng or "<" in eng:
        return translate_body_part_name(eng)
    suffix, core = "", eng
    m = re.search(r"\s*\((\d+)\)\s*$", eng)
    if m:
        suffix, core = " (%s)" % m.group(1), eng[:m.start()]
    upper = bool(core) and core[0].isupper()
    base = core
    if lat:  # Näherung von Laterality.StripLateralityAdjective
        base = " ".join(w for w in core.split(" ") if w.lower() not in _LAT_WORDS)
    base_de = translate_body_part_name(base.strip())
    g = guess_gender(base_de)
    adj = laterality_adjectives(lat, g) if lat else ""
    composed = ((adj + " ") if adj else "") + base_de + suffix
    if upper and composed:
        composed = composed[0].upper() + composed[1:]
    return composed


def demonstrative(g, c):
    """C# Demonstrative: dieser/diese/dieses/diese nach Genus + Kasus."""
    if g == M:
        return {ACC: "diesen", DAT: "diesem", GEN: "dieses"}.get(c, "dieser")
    if g == F:
        return "dieser" if c in (DAT, GEN) else "diese"
    if g == N:
        return "diesem" if c == DAT else "dieses"
    return {DAT: "diesen", GEN: "dieser"}.get(c, "diese")


def _keep_case(original, lower):
    if original[:1].isupper() and lower:
        return lower[0].upper() + lower[1:]
    return lower


def plural_word(word):
    """C# PluralWord: Lexikon (exakt, dann längstes Grundwort) -> Endungsregeln."""
    if not word:
        return word
    w = word.lower()
    lex = plurals()
    if w in lex:
        return _keep_case(word, lex[w])
    best = None
    for k in lex:
        if len(k) >= 3 and len(k) < len(w) and w.endswith(k) and (best is None or len(k) > len(best)):
            best = k
    if best is not None:
        return word[:len(word) - len(best)] + lex[best]
    if w.endswith(("chen", "lein", "er", "el", "en")):
        return word
    if w.endswith(("ung", "heit", "keit", "schaft", "ion", "tät", "ik")):
        return word + "en"
    if w.endswith("in"):
        return word + "nen"
    if w.endswith("um"):
        return word[:-2] + "en"
    if w.endswith("e"):
        return word + "n"
    if w[-1] in "aiouy":
        return word + "s"
    return word + ("en" if guess_gender(word) == F else "e")


def german_plural(name):
    """C# GermanPlural: Kopfwort in den Plural, Adjektive stark (-e)."""
    if not name:
        return name
    words = _words(name)
    if not words:
        return name
    head = len(words) - 1
    for i in range(1, len(words)):
        if _fw(words[i]):
            head = i - 1
            break
    pre, core, post = split_color(words[head])
    words[head] = pre + plural_word(core) + post
    if head == len(words) - 1 and is_adj_noun_pattern(words):
        words[:head] = [decline_adj(w, STRONG, NOM, P) for w in words[:head]]
    return " ".join(words)


# ------------------------------------------- Replacer auf Stichproben-Objekten

class Ctx:
    def __init__(self, role, key, params, arg, capitalize, roles):
        self.role = role            # "subject" | "object" | …
        self.key = key              # normalisierter Replacer-Name
        self.params = params
        self.arg = arg
        self.capitalize = capitalize
        self.roles = roles          # role -> Objekt-dict

    def has(self, p):
        return p in self.params


def is_player(o):
    return bool(o.get("player"))


def is_plural(o):
    return bool(o.get("plural"))


def is_proper(o):
    return bool(o.get("proper"))


def gname(o):
    return o.get("name") or ""


def case_of(ctx):
    return ACC if ctx.role == "object" else NOM


def definite_for(o, c):
    if is_plural(o):
        return "den" if c == DAT else "der" if c == GEN else "die"
    return definite(guess_gender(gname(o)), c)


def player_pronoun(c):
    """Spieler-Anrede du (Richtlinie 2026-10-22): du/dich/dir/deiner."""
    return {NOM: "du", ACC: "dich", DAT: "dir", GEN: "deiner"}[c]


def is_reflexive(ctx, o):
    subj = ctx.roles.get("subject")
    return ctx.role == "object" and subj is not None and subj is o


def holder_of(ctx, o):
    h = o.get("holder")
    return ctx.roles.get("_objects", {}).get(h) if h else None


def genitive_phrase(o):
    n = gname(o)
    if is_proper(o):
        return genitive_noun(n, M)
    return build_definite_phrase(n, GEN, is_plural(o), False)


def with_possessor(phrase, ctx, o):
    if ctx.has("itsPossessor") or ctx.has("itsSubjectPossessor"):
        h = holder_of(ctx, o)
        if h is not None and not is_player(h) and not h.get("part"):
            return phrase + " " + genitive_phrase(h)
    return phrase


def case_name(ctx, o, c):
    if is_player(o):
        return cap(player_pronoun(c), ctx.capitalize)
    if c in (ACC, DAT) and is_reflexive(ctx, o):
        return cap("sich", ctx.capitalize)
    name = gname(o)
    if ctx.has("asPossessed"):
        h = holder_of(ctx, o)
        if h is not None and is_player(h):
            return build_possessive_phrase(name, c, is_plural(o), ctx.capitalize, "dein")
        if h is not None:
            return build_definite_phrase(name, c, is_plural(o), ctx.capitalize) \
                + " " + genitive_phrase(h)
    if is_proper(o):
        return with_possessor(genitive_noun(name, M) if c == GEN else name, ctx, o)
    return with_possessor(build_definite_phrase(name, c, is_plural(o), ctx.capitalize), ctx, o)


def indef_case_name(ctx, o, c):
    if is_player(o):
        return cap(player_pronoun(c), ctx.capitalize)
    if is_proper(o):
        pn = gname(o)
        return with_possessor(genitive_noun(pn, M) if c == GEN else pn, ctx, o)
    return with_possessor(build_indefinite_phrase(gname(o), c, is_plural(o), ctx.capitalize), ctx, o)


def definite_name(ctx, o):
    if is_player(o):
        return cap(player_pronoun(case_of(ctx)), ctx.capitalize)
    if is_proper(o):
        return gname(o)
    return cap(definite_for(o, case_of(ctx)), ctx.capitalize) + " " + gname(o)


def verb_person(o):
    """0 = s3, 1 = p2 (ihr), 2 = p3, 3 = s2 (du, Spieler)."""
    if is_player(o):
        return 3
    if is_plural(o):
        return 2
    return 0


ADVERBS = {"already": "bereits", "just": "gerade", "merely": "lediglich",
           "still": "noch", "now": "jetzt", "then": "dann", "also": "auch",
           "no longer": "nicht mehr", "suddenly": "plötzlich"}


def _english_does(ctx, o, verb, adverb):
    """Englischer Fallback (Object.Does) — nur angenähert."""
    name = definite_name(ctx, o)
    v = verb or "do"
    if not is_player(o) and not is_plural(o):
        v = v + ("es" if v.endswith(("s", "sh", "ch", "x", "o")) else "s")
    return name + (" " + adverb if adverb else "") + " " + v


def does_de(ctx, o, verb, adverb):
    form = try_german_verb(verb, verb_person(o))
    if form is None:
        return _english_does(ctx, o, verb, adverb), "en"
    adv = None
    if adverb:
        adv = ADVERBS.get(adverb.strip().lower(), adverb)
    return definite_name(ctx, o) + " " + form + ("" if adv is None else " " + adv), "emu"


def poss_stem(o):
    if is_player(o):
        return "dein"
    gn = o.get("game_gender")
    if gn in ("male", "hindren male"):
        return "sein"
    if gn in ("female", "hindren female"):
        return "ihr"
    if gn in ("males", "females", "plural", "collective"):
        return "ihr"
    if is_proper(o):
        adj = (genders().get(gn) or {}).get("PossessiveAdjective")
        return adj.lower() if adj else "sein"
    g = P if is_plural(o) else guess_gender(gname(o))
    return "ihr" if g in (F, P) else "sein"


def case_param(ctx):
    if ctx.has("dativ") or ctx.has("dat"):
        return DAT
    if ctx.has("akkusativ") or ctx.has("akk"):
        return ACC
    if ctx.has("genitiv") or ctx.has("gen"):
        return GEN
    return NOM


def _arg_obj(ctx):
    """'#weapon' / '#part' -> Stichprobe dieser Rolle (Default: item/part)."""
    if ctx.arg and ctx.arg in ctx.roles:
        return ctx.roles[ctx.arg]
    return None


def r_the(ctx, o):
    if is_player(o) or is_proper(o):
        return ""
    return cap(definite_for(o, case_of(ctx)), ctx.capitalize) + " "


def r_the_name(ctx, o):
    return definite_name(ctx, o)


def r_a(ctx, o):
    if is_plural(o) or is_proper(o):
        return ""
    art = indefinite(guess_gender(gname(o)), case_of(ctx))
    return cap(art, ctx.capitalize) + " " if art else ""


def r_a_name(ctx, o):
    name = gname(o)
    if is_player(o):
        return cap(player_pronoun(case_of(ctx)), ctx.capitalize)
    if is_plural(o) or is_proper(o):
        return name
    art = indefinite(guess_gender(name), case_of(ctx))
    return cap(art, ctx.capitalize) + " " + name if art else name


def r_konjde(ctx, o):
    inf = ctx.params[0] if ctx.params else ""
    p = verb_person(o)
    f = verbs()[0].get(inf.lower())
    de = f[p] if f and f[p] else weak_conjugate(inf, p)
    return cap(de, ctx.capitalize)


def r_does(ctx, o):
    if ctx.arg is not None:  # DoesDeArg: Verb als #-Argument
        return does_de(ctx, o, ctx.arg, None)
    ps = ctx.params
    early_empty = len(ps) >= 2 and not ps[1]
    verbidx = 1 if (len(ps) >= 2 and not early_empty) else 0
    verb = ps[verbidx] if ps else "do"
    adverb = ps[0] if (len(ps) >= 2 and not early_empty) else None
    return does_de(ctx, o, verb, adverb)


def r_poss_definite(ctx, o):
    if is_player(o):
        return cap("dein", ctx.capitalize)
    n = gname(o)
    if is_proper(o):
        return cap(genitive_noun(n, M), ctx.capitalize)
    return build_definite_phrase(n, GEN, is_plural(o), ctx.capitalize)


def r_poss_bare(ctx, o):
    if is_player(o):
        return cap("dein", ctx.capitalize)
    n = gname(o)
    return cap(genitive_noun(n, P if is_plural(o) else guess_gender(n)), ctx.capitalize)


def r_poss_indef(ctx, o):
    if is_player(o):
        return cap("dein", ctx.capitalize)
    return indef_case_name(ctx, o, GEN)


def r_possessive_adj(ctx, o):
    stem = poss_stem(o)
    g = M if ctx.has("m") else F if ctx.has("f") else N if ctx.has("n") else \
        P if ctx.has("pl") else None
    de = decline_poss(stem, g, case_param(ctx)) if g else stem
    return cap(de, ctx.capitalize)


def r_its_item(ctx, o):
    item = _arg_obj(ctx) or ctx.roles.get("item")
    if item is None:
        return None
    n = gname(item)
    if is_proper(item):
        return cap(n, ctx.capitalize)
    return build_possessive_phrase(n, case_param(ctx), is_plural(item), ctx.capitalize, poss_stem(o))


def r_its_part(ctx, o):
    part = _arg_obj(ctx) or ctx.roles.get("part")
    if part is None or not part.get("part"):
        return None
    de = transform_body_part(part.get("eng", ""), part.get("lat", 0))
    return build_possessive_phrase(de, case_param(ctx), False, ctx.capitalize, poss_stem(o))


def r_this(ctx, o):
    if is_player(o):
        return cap(player_pronoun(case_param(ctx)), ctx.capitalize)
    g = P if is_plural(o) else guess_gender(gname(o))
    return cap(demonstrative(g, case_param(ctx)), ctx.capitalize)


def dative_from_accusative(acc, plural):
    low = (acc or "").lower()
    if low in ("ihn", "es"):
        return "ihm"
    if low == "sie":
        return "ihnen" if plural else "ihr"
    return {"dich": "dir", "mich": "mir"}.get(low, acc)


def r_objective(ctx, o):
    c = case_param(ctx)
    if is_player(o) and c != NOM:
        return cap(player_pronoun(c), ctx.capitalize)
    acc = "dich" if is_player(o) else game_gender_entry(o).get("Objective")
    if acc is None:
        return None
    return cap(dative_from_accusative(acc, is_plural(o)) if c == DAT else acc, ctx.capitalize)


def r_pluralize(ctx, o):
    if ctx.arg is not None or ctx.key == "pluralize.word":
        what = ctx.arg if ctx.arg is not None else (ctx.params[0] if ctx.params else "")
        return cap(german_plural(what) if is_plural(o) else what, ctx.capitalize)
    n = gname(o)
    return cap(n if is_plural(o) else german_plural(n), ctx.capitalize)


def r_ternary_plural(ctx, o):
    """TernaryPlural (Spiel-Replacer): Parameter 0 bei Mehrzahl, sonst 1.
    ifplayerplural fragt immer den Spieler, unabhängig von der Rolle."""
    if ctx.key == "ifplayerplural":
        o = ctx.roles.get("player") or o
    i = 0 if is_plural(o) else 1
    return ctx.params[i] if len(ctx.params) > i else ""


def part_name(o):
    return transform_body_part(o.get("eng", ""), o.get("lat", 0))


def r_part_case(ctx, o, c):
    return build_definite_phrase(part_name(o), c, bool(o.get("plural")), ctx.capitalize)


def r_part_poss(ctx, o):
    owner = ctx.roles.get("_objects", {}).get(o.get("owner") or "player") or ctx.roles.get("player")
    stem = poss_stem(owner) if owner else "sein"
    return build_possessive_phrase(part_name(o), case_param(ctx), bool(o.get("plural")), ctx.capitalize, stem)


PART_REPLACERS = {
    "nominativ": lambda c, o: r_part_case(c, o, NOM), "akkusativ": lambda c, o: r_part_case(c, o, ACC),
    "dativ": lambda c, o: r_part_case(c, o, DAT), "genitiv": lambda c, o: r_part_case(c, o, GEN),
    "poss": r_part_poss,
    "pluralize": lambda c, o: cap(german_plural(part_name(o)) if not o.get("plural") else part_name(o),
                                  c.capitalize),
}


def r_part_name(ctx, o):
    if not o.get("part"):
        return None  # GameObject-"name" ist ein Spiel-Replacer -> approx unten
    return transform_body_part(o.get("eng", ""), o.get("lat", 0))


# Mod-Replacer (VariableReplacers.de.cs) — Schlüssel klein, wie registriert
MOD_REPLACERS = {
    "the": r_the,
    "the.name": r_the_name, "t": r_the_name, "formattedname": r_the_name,
    "nominativ": lambda c, o: case_name(c, o, NOM),
    "akkusativ": lambda c, o: case_name(c, o, ACC),
    "dativ": lambda c, o: case_name(c, o, DAT),
    "genitiv": lambda c, o: case_name(c, o, GEN),
    "a.nominativ": lambda c, o: indef_case_name(c, o, NOM),
    "a.akkusativ": lambda c, o: indef_case_name(c, o, ACC),
    "a.dativ": lambda c, o: indef_case_name(c, o, DAT),
    "a.genitiv": lambda c, o: indef_case_name(c, o, GEN),
    "a": r_a, "a.name": r_a_name, "an": r_a_name,
    "konjde": r_konjde,
    "does": r_does, "did": r_does,
    "the.name's": r_poss_definite, "t's": r_poss_definite,
    "name's": r_poss_bare, "basename's": r_poss_bare, "refname's": r_poss_bare,
    "a.name's": r_poss_indef, "an's": r_poss_indef,
    "possessive": r_possessive_adj, "their": r_possessive_adj, "its": r_possessive_adj,
    "possessiveadjective": r_possessive_adj,
    "its.item": r_its_item, "its_": r_its_item,
    "its.part": r_its_part,
    "this": r_this, "indicativeproximal": r_this,
    "that": r_this, "indicativedistal": r_this,
    "objective": r_objective, "them": r_objective,
    "pluralize": r_pluralize, "plural": r_pluralize, "pluralize.word": r_pluralize,
    # Spiel-Replacer, exakt nachgebaut (keine Sprachlogik)
    "ifplayerplural": r_ternary_plural, "isplural": r_ternary_plural, "ifplural": r_ternary_plural,
}

# Spiel-Replacer, angenähert (Pronomen aus Genders.de.xml; Spieler = Ihr-Form)
_PLAYER_PRONOUNS = {  # = PronounSets.de.xml "player" (du)
    "subjective": "du", "they": "du", "it": "du",
    "objective": "dich", "them": "dich", "him": "dich",
    "reflexive": "dich selbst", "itself": "dich selbst", "themselves": "dich selbst",
    "substantivepossessive": "deins",
}
_PRONOUN_ATTR = {
    "subjective": "Subjective", "they": "Subjective", "it": "Subjective",
    "objective": "Objective", "them": "Objective", "him": "Objective",
    "reflexive": "Reflexive", "itself": "Reflexive", "themselves": "Reflexive",
    "substantivepossessive": "SubstantivePossessive",
    "formaladdressterm": "FormalAddressTerm", "personterm": "PersonTerm",
    "offspringterm": "OffspringTerm", "siblingterm": "SiblingTerm",
    "parentterm": "ParentTerm", "immaturepersonterm": "ImmaturePersonTerm",
}


def game_gender_entry(o):
    gn = o.get("game_gender")
    if not gn:
        g = P if is_plural(o) else guess_gender(gname(o))
        gn = {M: "male", F: "female", N: "neuter", P: "plural"}[g]
    return genders().get(gn) or {}


def approx_replacer(ctx, o):
    k = ctx.key
    if k in ("name", "refname", "basename", "displayname", "shortdisplayname"):
        return cap(gname(o), ctx.capitalize)
    if is_player(o) and k in _PLAYER_PRONOUNS:
        return cap(_PLAYER_PRONOUNS[k], ctx.capitalize)
    attr = _PRONOUN_ATTR.get(k)
    if attr:
        val = game_gender_entry(o).get(attr)
        if val is None and k == "formaladdressterm":
            val = "Freund"
        return cap(val, ctx.capitalize) if val is not None else None
    if k == "is":
        return "bist" if is_player(o) else "sind" if is_plural(o) else "ist"
    if k == "has":
        return "hast" if is_player(o) else "haben" if is_plural(o) else "hat"
    return None


# --------------------------------------------------------------- Gewürz-Texte

def _spice_get(node, key):
    if not isinstance(node, dict):
        return None
    if key in node:
        return node[key]
    return node.get(key + "=")


def spice_lookup(path, pick):
    """'villages.warden.introDialog.!random' -> (Text, Pfadknoten) oder None."""
    node = spice()
    parts = [p for p in path.split(".") if p]
    parent = None
    for p in parts:
        if p == "!random":
            if isinstance(node, list) and node:
                return node[pick % len(node)], parent
            return None
        parent = node
        node = _spice_get(node, p)
        if node is None:
            return None
    if isinstance(node, list) and node:
        return node[pick % len(node)], parent
    if isinstance(node, str):
        return node, parent
    return None


# ------------------------------------------------------------------ Resolver

POST_KNOWN = ("capitalize", "'s", "possessive", "makepossessive", "strip",
              "addparens", "lower", "upper", "pluralize", "plural")


def _apply_post(val, posts):
    how_ok = True
    for p in posts:
        pl = p.lower()
        if pl == "capitalize":
            val = cap(val, True)
        elif pl in ("'s", "possessive", "makepossessive"):
            val = german_possessive_suffix(val)
        elif pl in ("pluralize", "plural"):
            val = german_plural(val)
        elif pl == "strip":
            val = visible_text(val)
        elif pl == "addparens":
            val = "(" + val + ")" if val else val
        elif pl == "lower":
            val = val.lower()
        elif pl == "upper":
            val = val.upper()
        else:
            how_ok = False  # unbekannter Postprozessor -> Ausgabe ungefähr
    return val, how_ok


def parse_token(inner):
    """'subject.its.item:dat#weapon|capitalize' ->
    (target, key, params, arg, posts, capitalize)."""
    body, *posts = inner.split("|")
    arg = None
    if "#" in body:
        body, arg = body.split("#", 1)
    head, *params = body.split(":")
    segs = head.split(".")
    return segs, params, arg, posts


def _norm_key(s):
    return s[:1].lower() + s[1:] if s else s


def resolve_token(inner, ctx_roles, samples_tokens, pick=0, depth=0):
    """-> (Ausgabe, how)"""
    segs, params, arg, posts = parse_token(inner)
    target = None
    capitalize = False
    if len(segs) > 1 and _norm_key(segs[0]).lower() in ctx_roles:
        target = _norm_key(segs[0]).lower()
        capitalize = segs[0][:1].isupper()
        key_segs = segs[1:]
    else:
        key_segs = segs
    if key_segs and key_segs[0][:1].isupper():
        capitalize = True
    key = ".".join(_norm_key(s) for s in key_segs).lower()

    out, how = None, None
    # 1) Stichproben-Tabelle: exakter Token-Text gewinnt (bewusste Overrides)
    for k in (inner, inner.split("|")[0], ".".join(segs) + (":" + ":".join(params) if params else ""),
              ".".join(segs), (target + "." + key) if target else key):
        if k and k in samples_tokens:
            out, how = samples_tokens[k], "sample"
            break
    # 2) Gewürz
    if out is None and segs and segs[0].lower() == "spice" and (params or len(segs) > 1):
        path = ":".join(params) if params else ".".join(segs[1:])
        hit = spice_lookup(path, pick)
        if hit:
            txt = hit[0]
            if depth < 4:
                txt = _strip_markers(resolve(txt, ctx_roles=ctx_roles, pick=pick,
                                             depth=depth + 1)["text"])
            out, how = txt, "spice"
    # 3) Objekt-Replacer
    if out is None:
        o = ctx_roles.get(target or "subject")
        if isinstance(o, dict):
            ctx = Ctx(target or "subject", key, params, arg, capitalize, ctx_roles)
            fn = MOD_REPLACERS.get(key)
            if o.get("part") and key in ("name", "ordinalname"):
                out, how = r_part_name(ctx, o), "emu"
            elif o.get("part") and key in PART_REPLACERS:
                out, how = PART_REPLACERS[key](ctx, o), "emu"
            elif fn is not None:
                res = fn(ctx, o)
                if isinstance(res, tuple):
                    out, how = res
                elif res is not None:
                    out, how = res, "emu"
            if out is None:
                res = approx_replacer(ctx, o)
                if res is not None:
                    out, how = res, "approx"
    # Zahl + Wort ("=amount.pluralize:Punkt:Punkte=") — Rolle ist eine Zahl, kein Objekt;
    # Vorschau nimmt Mehrzahl an
    if out is None and params and len(segs) == 2 and segs[1].lower() == "pluralize" \
            and segs[0].lower() not in ctx_roles:
        out, how = (params[1] if len(params) > 1 else german_plural(params[0])), "approx"
    # Zahl/Kontextvariable + Plural-Weiche ("=number.ifPlural:Punkte:Punkt=") — Mehrzahl angenommen
    if out is None and params and len(segs) == 2 and segs[1].lower() in ("ifplural", "isplural") \
            and segs[0].lower() not in ctx_roles:
        out, how = params[0], "approx"
    if out is None:
        return None, "unknown"
    out, ok = _apply_post(out, posts)
    if not ok and how in ("emu", "approx"):
        how = "approx"
    return out, how


def _strip_markers(s):
    return s.replace(TOK_START, "").replace(TOK_END, "")


def build_roles(ctx=None):
    """ctx: {role: sample-id} (Overrides) -> role -> Objekt-dict."""
    s = samples()
    objs = s["objects"]
    roles = dict(s["roles"])
    roles.update(ctx or {})
    out = {"_objects": objs}
    for role, sid in roles.items():
        if sid in objs:
            out[role] = objs[sid]
    for role, sid in roles.items():  # Alias-Rollen ("pronouns": "subject")
        if role not in out and sid in out:
            out[role] = out[sid]
    return out


def resolve(template, ctx=None, ctx_roles=None, pick=0, depth=0):
    roles = ctx_roles if ctx_roles is not None else build_roles(ctx)
    stoks = samples()["tokens"]
    tokens = []
    out = []
    pos = 0
    for m in TOKEN_RE.finditer(template or ""):
        out.append(template[pos:m.start()])
        pos = m.end()
        val, how = resolve_token(m.group(1), roles, stoks, pick, depth)
        if val is None:
            val = m.group(0)
        tokens.append({"src": m.group(0), "out": val, "how": how})
        out.append(TOK_START + val + TOK_END)
    out.append((template or "")[pos:])
    return {"text": "".join(out), "tokens": tokens}


def resolve_plain(template, ctx=None, pick=0):
    """Ohne Marker — für Tests und Test-Vorschläge."""
    return _strip_markers(resolve(template, ctx=ctx, pick=pick)["text"])


def sample_for_blueprint(bp, store=None):
    """Blueprint-Name -> Stichprobe (deutscher DisplayName aus den Daten)."""
    s = samples()["objects"]
    for o in s.values():
        if o.get("blueprint") == bp:
            return dict(o)
    name = bp
    if store is not None:
        for u in store.all_units():
            if u.objname == bp and u.attr == "DisplayName":
                name = visible_text(u.display_value()) or bp
                break
    return {"label": bp, "name": name, "blueprint": bp, "game_gender": "neuter"}
