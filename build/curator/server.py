"""QudDE Kurator — lokaler Server.

Start:  py build/curator/server.py   ->  http://127.0.0.1:8371
Nur Stdlib; alle Endpoints liefern JSON. Statische UI aus static/.
"""
import json
import mimetypes
import os
import re
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from curator import config, coverage, store, xmlscan  # noqa: E402

STORE = store.Store()
COVERAGE = coverage.Coverage()
ROUTES = []  # (method, compiled_pattern, handler(match, query, body) -> (status, obj))


def route(method, pattern):
    rx = re.compile("^" + pattern + "$")

    def deco(fn):
        ROUTES.append((method, rx, fn))
        return fn
    return deco


# ---------------------------------------------------------------- Endpoints

@route("GET", r"/api/units")
def api_units(m, q, body):
    STORE.refresh()
    uids = None
    flag = q.get("flag")
    if flag == "untranslated":
        # Unübersetzt = Manifest-Keys ohne deutsche Abdeckung -> eigene Antwortform
        return 200, _untranslated(q)
    if flag == "lint":
        uids = _lint_uids(q)
    predicate = _review_predicate(q.get("review"))
    total, units = STORE.search(
        q=q.get("q", ""), mode=q.get("mode", "de"),
        file=q.get("file") or None, category=q.get("category") or None,
        has_token=flag == "hastoken",
        offset=int(q.get("offset", 0)), limit=min(int(q.get("limit", 100)), 500),
        uids=uids, predicate=predicate)
    out = []
    for u in units:
        d = u.to_json()
        if not d["english"] and u.kind in ("attr", "text"):
            d["english"] = _manifest_english(u)
        d["review"] = _review_status(u)
        out.append(d)
    return 200, {"total": total, "units": out, "files": STORE.data_files()}


def _review_status(u):
    try:
        from curator.review import REVIEW
        return REVIEW.status(u)[0]
    except ImportError:
        return None


def _review_predicate(want):
    if want not in ("checked", "unchecked", "stale", "open"):
        return None
    try:
        from curator.review import REVIEW
    except ImportError:
        return None
    if want == "open":  # ungeprüft ODER veraltet geprüft
        return lambda u: REVIEW.status(u)[0] != "checked"
    return lambda u: REVIEW.status(u)[0] == want


def _lint_uids(q):
    try:
        from curator import lint
        return lint.get_engine(STORE).uids_with_findings(severity=q.get("sev") or None)
    except ImportError:
        return []


def _untranslated(q):
    res = COVERAGE.compute()
    items = []
    fileq = (q.get("file") or "").replace(".de.xml", "")
    needle = (q.get("q") or "").lower()
    for name, f in sorted(res["files"].items()):
        if fileq and name != fileq:
            continue
        for miss in f["missing"]:
            if needle and needle not in miss["english"].lower():
                continue
            items.append({"file": name + ".de.xml", "key": miss["key"],
                          "english": miss["english"], "context": miss.get("context"),
                          "is_strings": f["is_strings"]})
    off = int(q.get("offset", 0))
    lim = min(int(q.get("limit", 100)), 500)
    return {"total": len(items), "untranslated": items[off:off + lim],
            "available": res["available"], "files": STORE.xml_files()}


@route("GET", r"/api/units/(?P<uid>[0-9a-f]{16})")
def api_unit(m, q, body):
    STORE.refresh()
    u = STORE.get(m.group("uid"))
    if not u:
        return 404, {"error": "Einheit nicht gefunden (Index veraltet? Neu laden.)"}
    d = u.to_json()
    d["category"] = STORE.category(u)
    # Nachbarn: gleicher Context (Strings) bzw. gleiches Objekt (Blueprints)
    neigh = []
    for other in STORE.all_units():
        if other.uid == u.uid or other.file != u.file:
            continue
        if (u.context and other.context == u.context) or \
           (u.objname and other.objname == u.objname):
            neigh.append(other.to_json())
        if len(neigh) >= 20:
            break
    d["neighbors"] = neigh
    d["english_manifest"] = _manifest_english(u)
    try:
        from curator.review import REVIEW
        st_r, entry = REVIEW.status(u)
        d["review"] = st_r
        d["review_entry"] = entry
    except ImportError:
        d["review"] = None
    try:
        from curator import lint
        d["lint"] = lint.get_engine(STORE).findings_for(u)
    except ImportError:
        d["lint"] = []
    return 200, d


_manifest_cache = {}
_AMBIGUOUS = object()


def _manifest_tables(name):
    """Beispieldatei mit DEMSELBEN Scanner indizieren wie die deutschen Dateien:
    primär Pfad-Schlüssel (Unit.key, ankert auf Name/ID/Command — eindeutig),
    sekundär coverage-covkey (mehrdeutige Keys werden als AMBIGUOUS markiert,
    damit nie der Text eines FALSCHEN Eintrags angezeigt wird)."""
    ex = os.path.join(COVERAGE.game_dir, name + ".example.xml")
    if not os.path.exists(ex):
        return None
    st = os.stat(ex)
    sig = (st.st_mtime_ns, st.st_size)
    cached = _manifest_cache.get(name)
    if cached and cached[0] == sig:
        return cached[1]
    try:
        res = xmlscan.scan(ex, name + ".example.xml")
    except Exception:
        return None
    by_path, by_cov = {}, {}
    for u in res.units:
        val = u.display_value().replace(coverage.MARK, "").strip()
        if not val:
            continue
        by_path[u.key] = val
        ck = tuple(u.covkey)
        by_cov[ck] = _AMBIGUOUS if ck in by_cov else val
    # Pfad-Root angleichen: /<root>#0/… ist in Beispiel- und de-Datei identisch,
    # weil beide dieselbe Root-Struktur haben — Keys sind direkt vergleichbar.
    tables = (by_path, by_cov)
    _manifest_cache[name] = (sig, tables)
    return tables


def _manifest_english(u):
    name = u.file.replace(".de.xml", "")
    tables = _manifest_tables(name)
    if not tables:
        return None
    by_path, by_cov = tables
    hit = by_path.get(u.key)
    if hit is not None:
        return hit
    hit = by_cov.get(tuple(u.covkey))
    return None if hit is _AMBIGUOUS else hit


@route("GET", r"/api/coverage")
def api_coverage(m, q, body):
    res = COVERAGE.compute()
    out = {"available": res["available"], "game_dir": res["game_dir"],
           "totals": dict(res["totals"]), "files": {}}
    for name, f in res["files"].items():
        out["files"][name] = {"units": f["units"], "covered": f["covered"],
                              "missing": len(f["missing"])}
    _add_review_coverage(out)
    return 200, out


def _add_review_coverage(out):
    """Geprüft-Statistik gegen das ▶-Manifest: eine Manifest-Einheit zählt als
    geprüft, wenn ALLE deutschen Einheiten mit ihrem Coverage-Key geprüft sind
    (kollidierende #text-Keys erfordern also alle Absätze)."""
    try:
        from curator.review import REVIEW
    except ImportError:
        return
    STORE.refresh()
    total_checked = total_stale = 0
    for name, f in out["files"].items():
        keys = COVERAGE.manifest_keys(name)
        res = STORE.files.get(name + ".de.xml")
        f["checked"] = f["stale"] = 0
        if not keys or res is None:
            continue
        by_cov = {}
        for u in res.units:
            by_cov.setdefault(tuple(u.covkey), []).append(u)
        for k, us in by_cov.items():
            if k not in keys:
                continue
            statuses = [REVIEW.status(u)[0] for u in us]
            if all(s == "checked" for s in statuses):
                f["checked"] += 1
            elif any(s == "stale" for s in statuses):
                f["stale"] += 1
        total_checked += f["checked"]
        total_stale += f["stale"]
    out["totals"]["checked"] = total_checked
    out["totals"]["stale"] = total_stale


@route("GET", r"/api/meta")
def api_meta(m, q, body):
    STORE.refresh()
    cats = sorted({STORE.category(u) for u in STORE.all_units()})
    try:
        from curator.review import REVIEW
        review = REVIEW.summary(STORE)
    except ImportError:
        review = None
    return 200, {"files": STORE.data_files(), "categories": cats,
                 "unit_count": len(STORE.units),
                 "blueprints": STORE.blueprint_names(),
                 "review": review}


@route("POST", r"/api/reload")
def api_reload(m, q, body):
    changed = STORE.refresh(force=True)
    return 200, {"reloaded": changed}


# ------------------------------------------------------------- HTTP-Gerüst

class Handler(BaseHTTPRequestHandler):
    server_version = "QudDEKurator/1.0"

    def _dispatch(self, method):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if method == "GET" and not path.startswith("/api/"):
            return self._static(path)
        query = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}
        body = None
        if method in ("POST", "PUT", "DELETE"):
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            if raw:
                try:
                    body = json.loads(raw.decode("utf-8"))
                except Exception:
                    return self._json(400, {"error": "Ungültiges JSON im Request-Body."})
        for m_, rx, fn in ROUTES:
            if m_ != method:
                continue
            mo = rx.match(path)
            if mo:
                try:
                    status, obj = fn(mo, query, body)
                except Exception as ex:  # Fehler als JSON, Server läuft weiter
                    import traceback
                    traceback.print_exc()
                    status, obj = 500, {"error": "Interner Fehler: %s" % ex}
                return self._json(status, obj)
        return self._json(404, {"error": "Unbekannter Endpoint: %s" % path})

    def _static(self, path):
        if path in ("/", ""):
            path = "/index.html"
        fp = os.path.normpath(os.path.join(config.STATIC_DIR, path.lstrip("/")))
        if not fp.startswith(config.STATIC_DIR) or not os.path.isfile(fp):
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(fp)[0] or "application/octet-stream"
        with open(fp, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text") or ctype.endswith("javascript") else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def log_message(self, fmt, *args):
        pass  # Konsole ruhig halten


def register_optional_routes():
    """Routen späterer Phasen — Module fehlen ggf. noch, dann ohne sie starten."""
    for mod in ("writer_routes", "lint_routes", "lexicon_routes",
                "tests_routes", "log_routes", "deploy_routes", "review_routes",
                "scene_routes", "glossary_routes", "proposal_routes", "coverage_routes"):
        try:
            __import__("curator." + mod)
        except ImportError as ex:
            if ("curator." + mod) not in str(ex):
                print("WARNUNG: %s nicht geladen: %s" % (mod, ex))
        except Exception as ex:
            print("WARNUNG: %s nicht geladen: %s" % (mod, ex))


def main():
    register_optional_routes()
    STORE.refresh()
    port = int(config.CFG["port"])
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = "http://127.0.0.1:%d" % port
    print("QudDE Kurator: %s  (%d Einheiten indiziert, Strg+C beendet)"
          % (url, len(STORE.units)))
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")


if __name__ == "__main__":
    # Als Skript gestartet (py build/curator/server.py): NICHT das __main__-
    # Modul verwenden, sondern die Paket-Instanz — sonst registrieren die
    # Routen-Module ihre Routen in einer zweiten ROUTES-Liste.
    from curator.server import main as _pkg_main
    _pkg_main()
