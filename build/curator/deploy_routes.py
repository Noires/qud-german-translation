"""HTTP-Routen für den Deploy-Abgleich (Phase 7)."""
from curator import deploy
from curator.server import route


@route("GET", r"/api/deploy/status")
def api_deploy_status(m, q, body):
    st = deploy.status()
    return 200, {
        "deploy_dir": st["deploy_dir"], "exists": st["exists"],
        "in_sync": st.get("in_sync", False),
        "identical": len(st["identical"]),
        "changed": st["changed"], "missing": st["missing"],
        "surplus": st["surplus"],
    }


@route("POST", r"/api/deploy/sync")
def api_deploy_sync(m, q, body):
    try:
        stamp = deploy.sync()
    except RuntimeError as ex:
        return 422, {"error": str(ex)}
    return 200, stamp
