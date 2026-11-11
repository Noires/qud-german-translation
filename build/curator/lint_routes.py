"""HTTP-Routen der Prüf-Engine (Phase 3)."""
from curator import lint, tokens
from curator.glossary import GLOSSARY
from curator.server import STORE, route


@route("POST", r"/api/lint/level")
def api_lint_level(m, q, body):
    """{rule, level: off|info|warning|error|null} — null = Standard-Schwere."""
    body = body or {}
    try:
        GLOSSARY.set_rule(body.get("rule"), body.get("level") or None)
    except ValueError as ex:
        return 422, {"error": str(ex)}
    return 200, {"levels": GLOSSARY.rules()}


@route("POST", r"/api/lint/ignore-inconsistent")
def api_lint_ignore_inconsistent(m, q, body):
    """K7-Ausnahme: {english, ignore: true|false}."""
    body = body or {}
    try:
        GLOSSARY.set_ignore_inconsistent(body.get("english"), bool(body.get("ignore", True)))
    except ValueError as ex:
        return 422, {"error": str(ex)}
    return 200, {"ok": True}


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
