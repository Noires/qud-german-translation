"""HTTP-Routen für den Geprüft-Status."""
from curator.review import REVIEW
from curator.server import STORE, route


@route("POST", r"/api/review")
def api_review_set(m, q, body):
    body = body or {}
    uid = body.get("uid", "")
    STORE.refresh()
    u = STORE.get(uid)
    if u is None:
        return 404, {"error": "Einheit nicht gefunden — Index neu laden."}
    status, entry = REVIEW.set_checked(u, bool(body.get("checked")))
    return 200, {"review": status, "review_entry": entry,
                 "summary": REVIEW.summary(STORE)}


@route("GET", r"/api/review/summary")
def api_review_summary(m, q, body):
    STORE.refresh()
    return 200, REVIEW.summary(STORE)
