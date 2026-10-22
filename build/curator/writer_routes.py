"""HTTP-Routen für das Schreiben (Phase 2) — von server.register_optional_routes geladen."""
from curator import writer
from curator.server import STORE, route


def _handle(fn):
    try:
        u = fn()
    except writer.WriteError as ex:
        return ex.status, {"error": str(ex)}
    d = u.to_json()
    try:
        from curator import lint
        d_lint = lint.get_engine(STORE).findings_for(u)
    except ImportError:
        d_lint = []
    return 200, {"unit": d, "lint": d_lint}


@route("POST", r"/api/units/(?P<uid>[0-9a-f]{16})")
def api_save_unit(m, q, body):
    body = body or {}
    if "old_value" not in body or "new_value" not in body:
        return 400, {"error": "old_value und new_value sind erforderlich."}
    return _handle(lambda: writer.save(
        STORE, m.group("uid"), body["old_value"], body["new_value"]))


@route("POST", r"/api/units")
def api_create_unit(m, q, body):
    body = body or {}
    if not body.get("file") or not body.get("id"):
        return 400, {"error": "file und id sind erforderlich."}
    return _handle(lambda: writer.create_string_entry(
        STORE, body["file"], body.get("context", ""), body["id"],
        body.get("value", "")))
