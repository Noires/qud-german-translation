"""HTTP-Routen: Playtest-Befunde, Verlauf je Eintrag, Konkordanz."""
import os

from curator import config, history, playerlog
from curator.findings import FINDINGS
from curator.server import STORE, route


def _log():
    try:
        return playerlog.parse_log(config.CFG["player_log"])
    except OSError:
        return None


@route("GET", r"/api/findings")
def api_findings(m, q, body):
    STORE.refresh()
    log = _log()
    auto = FINDINGS.auto_regress(STORE, log)
    return 200, {"findings": FINDINGS.list(STORE, log), "auto_regressed": auto,
                 "log_mtime": (log or {}).get("mtime")}


@route("POST", r"/api/findings")
def api_findings_create(m, q, body):
    body = body or {}
    try:
        return 200, {"finding": FINDINGS.create(body.get("text", ""), body.get("where", ""),
                                                body.get("uid") or None, body.get("screenshot"))}
    except ValueError as ex:
        return 422, {"error": str(ex)}


@route("POST", r"/api/findings/update")
def api_findings_update(m, q, body):
    body = body or {}
    STORE.refresh()
    if body.get("uid") and STORE.get(body["uid"]) is None:
        return 404, {"error": "Einheit nicht gefunden."}
    try:
        return 200, {"finding": FINDINGS.update(body.get("id", ""), STORE, body.get("status"),
                                                body.get("uid"), body.get("note", ""))}
    except KeyError as ex:
        return 404, {"error": str(ex.args[0])}
    except ValueError as ex:
        return 422, {"error": str(ex)}


@route("GET", r"/api/findings/shot/([\w-]+\.png)")
def api_findings_shot(m, q, body):
    path = os.path.join(FINDINGS.dir, m.group(1))
    if not os.path.isfile(path):
        return 404, {"error": "Screenshot nicht gefunden."}
    with open(path, "rb") as f:
        return 200, ("image/png", f.read())


@route("GET", r"/api/history")
def api_history(m, q, body):
    STORE.refresh()
    h = history.history(STORE, q.get("uid", ""))
    if h is None:
        return 404, {"error": "Einheit nicht gefunden."}
    return 200, h


@route("GET", r"/api/concordance")
def api_concordance(m, q, body):
    STORE.refresh()
    return 200, history.concordance(STORE, q.get("q", ""))
