"""HTTP-Routen für den Kurator-Test-Korpus (Phase 6)."""
from curator import testcorpus
from curator.server import STORE, route

CORPUS = testcorpus.TestCorpus()


@route("GET", r"/api/tests")
def api_tests(m, q, body):
    st = CORPUS.status()
    st["blueprints"] = STORE.blueprint_names()
    return 200, st


@route("POST", r"/api/tests")
def api_tests_set(m, q, body):
    try:
        t = CORPUS.set_test(body or {})
    except ValueError as ex:
        return 422, {"error": str(ex)}
    return 200, {"test": t}


@route("DELETE", r"/api/tests")
def api_tests_delete(m, q, body):
    body = body or {}
    try:
        CORPUS.delete_test(body.get("id", ""))
    except KeyError as ex:
        return 404, {"error": str(ex.args[0])}
    return 200, {"ok": True}


@route("POST", r"/api/tests/auto")
def api_tests_auto(m, q, body):
    """„Emulation prüfen": ctx-auto-Tests aus den häufigsten Token-Mustern (ersetzt alte)."""
    from curator import autotests
    STORE.refresh()
    made = autotests.generate(STORE, CORPUS, int((body or {}).get("n") or 20))
    return 200, {"count": len(made), "tests": made}
