"""HTTP-Routen der Prüf-Engine (Phase 3)."""
from curator import lint, tokens
from curator.server import STORE, route


@route("GET", r"/api/lint/summary")
def api_lint_summary(m, q, body):
    STORE.refresh()
    return 200, lint.get_engine(STORE).summary()


@route("GET", r"/api/lint")
def api_lint(m, q, body):
    STORE.refresh()
    eng = lint.get_engine(STORE)
    if q.get("file"):
        finds = eng.lint_file(q["file"])
    else:
        finds = eng.all_findings()
    if q.get("sev"):
        finds = [f for f in finds if f["severity"] == q["sev"]]
    return 200, {"findings": finds[:1000], "total": len(finds)}


@route("GET", r"/api/tokens")
def api_tokens(m, q, body):
    return 200, {"palette": tokens.Registry().palette()}
