"""HTTP-Routen: Manifest-Versionsvergleich (Spiel-Update -> neue/entfernte/geänderte Einträge)."""
import os

from curator import config
from curator.server import COVERAGE, route

SNAPSHOT = os.path.join(config.DATA_DIR, "manifest_snapshot.json")


@route("GET", r"/api/coverage/diff")
def api_coverage_diff(m, q, body):
    if not COVERAGE.available():
        return 200, {"available": False}
    return 200, dict(COVERAGE.diff_snapshot(SNAPSHOT), available=True)


@route("POST", r"/api/coverage/snapshot")
def api_coverage_snapshot(m, q, body):
    if not COVERAGE.available():
        return 422, {"error": "Spiel-Manifeste nicht gefunden."}
    return 200, COVERAGE.save_snapshot(SNAPSHOT)
