"""Daten-Korrekturen als Vorschlags-Batches (nach der du-Umstellung ausführen —
arbeitet auf den AKTUELLEN Werten).

  py build/curator/tools/fix_batches.py            # alle Batches erzeugen, Bericht

Batches (rule):
  fix-plural   =X.pluralize:<engl. Wort>= -> =X.pluralize:<Singular>:<Plural>=  (Zahl-Pluralisierung)
  fix-part     <Possessiv/Artikel> =part.ordinalName= -> =part.poss:<kasus>= / =part.<kasus>=
  fix-spice    HistorySpice instancesOf.desire= / wouldLikeTo= auf 1. Person
  fix-terms    Terminologie-Entscheidungen (Rückspuler, Elektroresistenz, Gaslicht-*, Fiber)
"""
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import proposals  # noqa: E402
from curator.store import Store  # noqa: E402

# Zahl-Pluralisierung: englisches Wort (bzw. Paar) -> deutsches Singular:Plural
PLURAL_WORDS = {
    "dram": "Dram:Dram", "point": "Punkt:Punkte", "item": "Gegenstand:Gegenstände",
    "follower": "Anhänger:Anhänger", "serving": "Portion:Portionen", "square": "Feld:Felder",
    "level": "Stufe:Stufen", "hit point": "Trefferpunkt:Trefferpunkte", "round": "Runde:Runden",
    "day": "Tag:Tage", "Portion": "Portion:Portionen", "turn": "Zug:Züge", "lair": "Versteck:Verstecke",
    "a psychic presence:psychic presences": "eine psychische Präsenz:psychische Präsenzen",
    "secret": "Geheimnis:Geheimnisse", "was:were": "war:waren", "Attribute Point": "Attributpunkt:Attributpunkte",
    "mark": "Zeichen:Zeichen", "bit": "Bit:Bits", "cooldown": "Abklingzeit:Abklingzeiten",
    "is": "ist:sind", "poison": "Gift:Gifte", "serving:servings": "Portion:Portionen", "is:are": "ist:sind",
    "mod": "Modifikation:Modifikationen", "rank": "Rang:Ränge",
    "an engraving:engravings": "eine Gravur:Gravuren", "a tattoo:tattoos": "eine Tätowierung:Tätowierungen",
}
OBJ_ROLES = {"subject", "object", "player", "item", "part"}

# =X.isPlural:<plural>:<singular>= / ifPlural mit englischen Parametern -> deutsch
ISPLURAL_WORDS = {
    "points:point": "Punkte:Punkt", "are:is": "sind:ist", "were:was": "waren:war",
    "cooldowns of the abilities:cooldown of the ability": "Abklingzeiten der Fähigkeiten:Abklingzeit der Fähigkeit",
    "artifacts:artifact": "Artefakte:Artefakt", "objects:object": "Objekte:Objekt",
    "These:This": "Diese:Dies", "These items are:This item is": "Diese Gegenstände sind:Dieser Gegenstand ist",
    "Those items aren't:That item isn't": "Diese Gegenstände sind nicht:Dieser Gegenstand ist nicht",
    "they aren't:it isn't": "sie sind nicht:es ist nicht", "they don't:it doesn't": "sie haben kein:es hat kein",
}

# Körperteil: Bestimmer vor =part.ordinalName= -> Kasus
_PART_RE = re.compile(r"\b(Deine[mnrs]?|deine[mnrs]?|Eure[mnrs]?|eure[mnrs]?|Ihre[mnrs]?|"
                      r"[Dd]er|[Dd]ie|[Dd]en|[Dd]em|[Dd]es)\s+=part\.ordinalName=")
_POSS = re.compile(r"^(?:[Dd]ein|[Ee]ur|[Ii]hr)(e[mnrs]?)?$")


def _case(det, before):
    low = det.lower()
    if low.endswith("em") or low in ("dem",):
        return "dat"
    if low.endswith("er") and low != "der":
        return "dat"
    if low in ("der",):
        return "dat"  # vor Körperteil fast immer Dativ fem. („an der rechten Hand“)
    if low.endswith("es") or low == "des":
        return "gen"
    if low.endswith("en") or low == "den":
        return "akk"
    # -e / die: Satzanfang -> Nominativ, sonst Akkusativ
    return "nom" if re.search(r"(^|[.!?:]\s*)$", before) else "akk"


_SENT = re.compile(r"(^|[.!?:]\s*)$")
_DAT_PREP = re.compile(r"\b(auf|an|in|mit|von|zu|bei|aus|unter|über)\s*$", re.I)
CASE_NAMES = {"nom": "nominativ", "akk": "akkusativ", "dat": "dativ", "gen": "genitiv"}
# vorangestellter Genitiv vor Körperteil: =X.the.name's(:p)= =part.ordinalName=
_GEN_PART = re.compile(r"=([A-Za-z]\w*)\.([Tt])he\.name's(?::[^=]*)?=\s+=part\.ordinalName=")
# Possessiv-Token des Spielers vor Körperteil: =player.their= =part.ordinalName=
_TOK_POSS_PART = re.compile(r"=([A-Za-z]\w*)\.(?:their|its|possessive)=\s+=part\.ordinalName=")


def fix_part(value):
    def rep(m):
        det = m.group(1)
        before = value[:m.start()]
        case = _case(det, before)
        cap = bool(_SENT.search(before))  # groß nur am Satzanfang (altes „Eurem“ war Höflichkeitsform)
        if _POSS.match(det):
            return "=part.%s:%s=" % ("Poss" if cap else "poss", case)
        name = CASE_NAMES[case]
        return "=part.%s=" % (name.capitalize() if cap else name)
    value = _PART_RE.sub(rep, value)

    def rep_gen(m):
        before = value_gen[:m.start()]
        if _SENT.search(before):
            case, cap = "nom", True
        elif _DAT_PREP.search(before):
            case, cap = "dat", False
        else:
            case, cap = "akk", False
        name = CASE_NAMES[case]
        return "=part.%s= =%s.genitiv=" % (name.capitalize() if cap else name, m.group(1))
    value_gen = value
    value = _GEN_PART.sub(rep_gen, value)

    def rep_tok(m):
        before = value_tok[:m.start()]
        case = "dat" if _DAT_PREP.search(before) else ("nom" if _SENT.search(before) else "akk")
        return "=part.%s:%s=" % ("Poss" if case == "nom" else "poss", case)
    value_tok = value
    return _TOK_POSS_PART.sub(rep_tok, value)


def fix_plural(value):
    def rep(m):
        role, param = m.group(1), m.group(2)
        if role in OBJ_ROLES or param not in PLURAL_WORDS:
            return m.group(0)
        return "=%s.pluralize:%s=" % (role, PLURAL_WORDS[param])

    def rep_is(m):
        role, kind, param = m.group(1), m.group(2), m.group(3)
        if param not in ISPLURAL_WORDS:
            return m.group(0)
        return "=%s.%s:%s=" % (role, kind, ISPLURAL_WORDS[param])
    value = re.sub(r"=([A-Za-z]\w*)\.pluralize:([^=|#]+)=", rep, value)
    return re.sub(r"=([A-Za-z]\w*)\.(isplural|isPlural|ifplural|ifPlural):([^=|#]+)=", rep_is, value)


SPICE_LISTS = {
    "/spice/instancesOf/desire=": ["brauche", "brauche dringend", "begehre", "verlange nach",
                                   "sehne mich nach", "benötige", "brauche", "könnte gebrauchen"],
    "/spice/instancesOf/wouldLikeTo=": ["würde gerne", "würde nur allzu gerne", "müsste", "möchte"],
}

# Terminologie: (Regex auf deutschen Wert, Ersatz, Bedingung auf englischen Text oder None)
TERMS = [
    (re.compile(r"Rekorder|Rückstoßgerät|Rückstoßer"), "Rückspuler", re.compile(r"recoiler", re.I)),
    (re.compile(r"Elektrische Widerstandsfähigkeit"), "Elektroresistenz", None),
    (re.compile(r"Gaslicht Chisel"), "Gaslicht-Meißel", None),
    (re.compile(r"Gaslicht Dolch"), "Gaslicht-Kris", re.compile(r"kris", re.I)),
    (re.compile(r"Gaslicht Schwert"), "Gaslicht-Flyssa", re.compile(r"flyssa", re.I)),
]


def _item(u, new, note):
    return {"uid": u.uid, "file": u.file, "key": u.key, "old_value": u.display_value(),
            "new_value": new, "note": note}


def build(store):
    batches = {"fix-plural": [], "fix-part": [], "fix-spice": [], "fix-terms": []}
    for u in store.all_units():
        v = u.display_value()
        if not v:
            continue
        nv = fix_plural(v)
        pv = fix_part(nv) if "=part.ordinalName=" in v else nv
        if pv != nv:  # Körperteil-Umbau (inkl. evtl. Plural-Korrektur derselben Einheit)
            batches["fix-part"].append(_item(u, pv, "Körperteil mit Kasus-/Possessiv-Token"))
        elif nv != v:
            batches["fix-plural"].append(_item(u, nv, "Zahl-Pluralisierung mit deutschem Singular:Plural"))
        nv = v
        for rx, new, cond in TERMS:
            if cond is not None and not cond.search(u.english or "") and not cond.search(u.objname or ""):
                continue
            nv = rx.sub(new, nv)
        if u.file == "ZoneTerrain.de.xml" and u.elemname == "Fiber" and nv == "ausziehen":
            nv = "Streifen"
        if nv != v:
            batches["fix-terms"].append(_item(u, nv, "Terminologie (Entscheidung 2026-10-22)"))
    js = store.files.get("HistorySpice.jsonc")
    if js is not None:
        for u in js.units:
            base = u.key.rsplit("/", 1)[0]
            if base in SPICE_LISTS:
                idx = int(u.key.rsplit("/", 1)[1])
                lst = SPICE_LISTS[base]
                if idx < len(lst) and lst[idx] != u.display_value():
                    batches["fix-spice"].append(_item(u, lst[idx], "1. Person (wird in loveToHave nach „ich“ eingesetzt)"))
    return batches


RULES = {"fix-plural": "fix-plural", "fix-part": "fix-part", "fix-spice": "fix", "fix-terms": "fix"}


def main():
    store = Store()
    store.refresh()
    for name, items in build(store).items():
        proposals.PROPOSALS.create(name, RULES[name], items, name)
        b = proposals.PROPOSALS.load(name, store)
        gate = [i for i in b["items"] if i["gate"]]
        print("%-12s %3d Vorschläge, %d mit Prüfbefund" % (name, len(items), len(gate)))
        for i in gate[:5]:
            print("    ", i["gate"], "|", i["new_value"][:90])


if __name__ == "__main__":
    main()
