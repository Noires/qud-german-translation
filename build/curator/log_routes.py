"""HTTP-Route für das Player.log-Dashboard (Phase 5)."""
from curator import playerlog
from curator.server import STORE, route


@route("GET", r"/api/playerlog")
def api_playerlog(m, q, body):
    return 200, playerlog.dashboard(STORE)
