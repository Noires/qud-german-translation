"""HTTP-Routen der Vorschlags-Warteschlange (Annehmen schreibt über writer.save)."""
from curator import proposals, writer
from curator.proposals import PROPOSALS
from curator.server import STORE, route

GENERATORS = {
    "k3": ("k3-auto", "K3: Subjekt-Token vor konjde ergänzt (Does → Name + Verb)", proposals.k3_items),
}


@route("GET", r"/api/proposals")
def api_proposals(m, q, body):
    STORE.refresh()
    return 200, {"batches": PROPOSALS.batches(STORE), "generators": {
        k: v[1] for k, v in GENERATORS.items()}}


@route("GET", r"/api/proposals/(?P<batch>[\w.-]+)")
def api_proposal_batch(m, q, body):
    STORE.refresh()
    try:
        return 200, PROPOSALS.load(m.group("batch"), STORE)
    except (OSError, ValueError):
        return 404, {"error": "Batch nicht gefunden."}


@route("POST", r"/api/proposals/(?P<batch>[\w.-]+)/decide")
def api_proposal_decide(m, q, body):
    body = body or {}
    STORE.refresh()
    try:
        it = PROPOSALS.decide(m.group("batch"), body.get("uid", ""), body.get("action", ""),
                              STORE, body.get("new_value"), bool(body.get("force")))
    except KeyError as ex:
        return 404, {"error": str(ex.args[0])}
    except ValueError as ex:
        return 422, {"error": str(ex)}
    except writer.WriteError as ex:
        return ex.status, {"error": str(ex)}
    except OSError:
        return 404, {"error": "Batch nicht gefunden."}
    return 200, {"item": {k: it[k] for k in ("uid", "status", "new_value") if k in it}}


@route("POST", r"/api/proposals/generate")
def api_proposal_generate(m, q, body):
    rule = (body or {}).get("rule", "")
    if rule not in GENERATORS:
        return 422, {"error": "Unbekannter Assistent."}
    STORE.refresh()
    name, note, fn = GENERATORS[rule]
    items = fn(STORE)
    PROPOSALS.create(name, rule, items, note)
    return 200, {"batch": name, "count": len(items)}
