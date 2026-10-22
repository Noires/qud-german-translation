"""„Emulation prüfen": In-Game-Tests aus den häufigsten Token-Mustern des Korpus.

Für die N häufigsten Mod-Replacer-Tokens (alles, was grammar_emu als "emu"
auflöst und ohne #-Argument auskommt — CuratorTests übergeben nur subject und
object) entsteht je Blueprint-Paar ein CuratorTest mit der EMULIERTEN Ausgabe
als expected. Läuft das Spiel, zeigt der Tests-Tab jede Abweichung
Emulation ↔ Spiel als FAIL. Ids: ctx-auto-<n>; ein neuer Lauf ersetzt alle.
"""
from collections import Counter

from . import grammar_emu

PREFIX = "ctx-auto-"
# Blueprint-Stichproben mit verschiedenem Genus (n, f, m) — alle per
# GameObjectFactory im Spiel erzeugbar (SelfTestPipeline nutzt dieselben)
BLUEPRINTS = (("Snapjaw", "Croc"), ("Croc", "Goat"), ("Goat", "Glowfish"))


def frequent_tokens(store, n=20):
    roles_ok = {"subject", "object"}
    cnt = Counter()
    for u in store.all_units():
        for m in grammar_emu.TOKEN_RE.finditer(u.display_value()):
            inner = m.group(1)
            if "#" in inner or "|" in inner:
                continue
            segs, params, arg, posts = grammar_emu.parse_token(inner)
            if len(segs) < 2 or segs[0].lower() not in roles_ok:
                continue
            key = ".".join(s[:1].lower() + s[1:] for s in segs[1:]).lower()
            if key in grammar_emu.MOD_REPLACERS and key not in ("its.item", "its_", "its.part"):
                cnt[m.group(0)] += 1
    return [t for t, _ in cnt.most_common(n)]


def generate(store, corpus, n=20):
    """Ersetzt alle ctx-auto-Tests. -> Liste der angelegten Tests."""
    for t in corpus.load().get("tests", []):
        if t.get("id", "").startswith(PREFIX):
            corpus.delete_test(t["id"])
    made = []
    k = 0
    for tok in frequent_tokens(store, n):
        for subj_bp, obj_bp in BLUEPRINTS:
            roles = grammar_emu.build_roles()
            roles["subject"] = grammar_emu.sample_for_blueprint(subj_bp, store)
            roles["object"] = grammar_emu.sample_for_blueprint(obj_bp, store)
            r = grammar_emu.resolve(tok, ctx_roles=roles)
            if not r["tokens"] or r["tokens"][0]["how"] != "emu":
                continue
            k += 1
            test = {"id": "%s%03d" % (PREFIX, k),
                    "description": "Emulation prüfen: %s (%s/%s)" % (tok, subj_bp, obj_bp),
                    "template": tok, "subject": subj_bp, "object": obj_bp,
                    "expected": grammar_emu._strip_markers(r["text"]), "enabled": True,
                    "sourceUnit": ""}
            corpus.set_test(test)
            made.append(test)
    return made
