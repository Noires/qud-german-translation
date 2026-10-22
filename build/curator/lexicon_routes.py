"""HTTP-Routen für GenderLexicon.tsv- und Verbs.json-Editor (Phase 4)."""
from curator import lexicon, verbs
from curator.server import STORE, route

LEX = lexicon.Lexicon()
VERBS = verbs.Verbs()


@route("GET", r"/api/lexicon")
def api_lexicon(m, q, body):
    return 200, {"entries": LEX.entries(), "lint": LEX.lint()}


@route("GET", r"/api/lexicon/preview")
def api_lexicon_preview(m, q, body):
    noun = q.get("noun", "").strip()
    gender = q.get("gender", "").strip()
    if not noun or gender not in lexicon.VALID:
        return 400, {"error": "noun und gender (m/f/n/p) sind erforderlich."}
    STORE.refresh()
    return 200, LEX.preview(noun, gender, STORE)


@route("POST", r"/api/lexicon")
def api_lexicon_set(m, q, body):
    body = body or {}
    try:
        LEX.set_entry(body.get("noun", ""), body.get("gender", ""))
    except ValueError as ex:
        return 422, {"error": str(ex)}
    return 200, {"entries": LEX.entries(), "lint": LEX.lint()}


@route("DELETE", r"/api/lexicon")
def api_lexicon_delete(m, q, body):
    body = body or {}
    try:
        LEX.delete_entry(body.get("noun", ""))
    except KeyError as ex:
        return 404, {"error": str(ex.args[0])}
    return 200, {"entries": LEX.entries(), "lint": LEX.lint()}


@route("GET", r"/api/verbs")
def api_verbs(m, q, body):
    return 200, {"entries": VERBS.entries()}


@route("GET", r"/api/verbs/weak")
def api_verbs_weak(m, q, body):
    inf = q.get("inf", "").strip()
    if not inf:
        return 400, {"error": "inf ist erforderlich."}
    return 200, VERBS.weak_preview(inf)


@route("POST", r"/api/verbs")
def api_verbs_set(m, q, body):
    body = body or {}
    try:
        entry = VERBS.set_entry(body, allow_separable=bool(body.get("allow_separable")))
    except ValueError as ex:
        return 422, {"error": str(ex)}
    return 200, {"entry": entry, "entries": VERBS.entries()}


@route("DELETE", r"/api/verbs")
def api_verbs_delete(m, q, body):
    body = body or {}
    try:
        VERBS.delete_entry(body.get("inf", ""))
    except KeyError as ex:
        return 404, {"error": str(ex.args[0])}
    return 200, {"entries": VERBS.entries()}
