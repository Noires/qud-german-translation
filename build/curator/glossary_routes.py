"""HTTP-Routen für Glossar + Anrede-Richtlinie (Terminologie-Konsistenz)."""
from curator import german, grammar_emu
from curator.glossary import GLOSSARY
from curator.server import STORE, route


def _payload():
    data = GLOSSARY.load()
    terms = []
    for t in data["terms"]:
        # Abweichung zum Genus-Lexikon (Token-Ebene nutzt das Lexikon!)
        lex_g = german.guess_gender(t["de"], grammar_emu.lexicon())
        terms.append({**t, "lexicon_gender": lex_g[0], "lexicon_source": lex_g[1]})
    return {"policy": data["policy"], "terms": terms}


@route("GET", r"/api/glossary")
def api_glossary(m, q, body):
    return 200, _payload()


@route("POST", r"/api/glossary")
def api_glossary_set(m, q, body):
    body = body or {}
    try:
        if "policy" in body:
            GLOSSARY.set_policy(body["policy"] or {})
        if "term" in body:
            GLOSSARY.set_term(body["term"] or {})
        for t in body.get("terms") or []:  # Mehrfach-Übernahme aus den Vorschlägen
            GLOSSARY.set_term(t)
    except ValueError as ex:
        return 422, {"error": str(ex)}
    return 200, _payload()


@route("DELETE", r"/api/glossary")
def api_glossary_delete(m, q, body):
    try:
        GLOSSARY.delete_term((body or {}).get("en", ""))
    except KeyError as ex:
        return 404, {"error": str(ex.args[0])}
    return 200, _payload()


@route("GET", r"/api/glossary/suggest")
def api_glossary_suggest(m, q, body):
    STORE.refresh()
    from curator.server import _manifest_english
    return 200, {"suggestions": GLOSSARY.suggest(STORE),
                 "names": GLOSSARY.suggest_names(STORE, _manifest_english)}
