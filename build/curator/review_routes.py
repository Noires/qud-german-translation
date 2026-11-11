"""HTTP-Routen für den Geprüft-Status."""
from curator import lint
from curator.flags import CATEGORIES
from curator.review import REVIEW
from curator.review_queue import ReviewQueue
from curator.server import STORE, route


def _queue_items():
    STORE.refresh()
    eng = lint.get_engine(STORE)
    lint_uids = {f["uid"] for f in eng.all_findings()
                 if f["uid"] and f["severity"] in ("error", "warning")}
    q = ReviewQueue(STORE)
    return q, q.items(lint_uids)


@route("GET", r"/api/review/queue")
def api_review_queue(m, q, body):
    """?bucket=&mode=priority|sample&n=50&offset=0&limit=50"""
    rq, items = _queue_items()
    n = int(q.get("n") or 50)
    pend = rq.pending(items, q.get("bucket") or None, q.get("mode") or "priority", n)
    off, lim = int(q.get("offset") or 0), int(q.get("limit") or 50)
    return 200, {"buckets": rq.summary(items, n), "pending": len(pend),
                 "items": [rq.public(i) for i in pend[off:off + lim]],
                 "categories": CATEGORIES}


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
