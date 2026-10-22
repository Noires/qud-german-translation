"""CuratorTests.json: CRUD + Abgleich mit Player.log-Ergebnissen + Staleness.

Staleness-Logik (Player.log hat keine Zeilen-Timestamps):
  - Der C#-Runner loggt beim Lauf `file-mtime=<Ticks>` der GELADENEN (deployten)
    Testdatei. Weicht das vom aktuellen mtime der deployten Datei ab, stammen
    die Ergebnisse von einem alten Stand -> "Spiel neu starten".
  - Weichen Repo- und Deploy-Datei ab (Hash) -> "noch nicht abgeglichen".
  - Test-Id ohne Log-Zeile -> "noch nicht ausgeführt".
"""
import hashlib
import json
import os
import threading

from . import config, playerlog

_lock = threading.Lock()

# .NET-Ticks: 100ns seit 0001-01-01; Unix-Epoche = 621355968000000000 Ticks
_EPOCH_TICKS = 621355968000000000


def ticks_to_unix(ticks):
    return (ticks - _EPOCH_TICKS) / 10_000_000


def _sha(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


class TestCorpus:
    def __init__(self, path=None):
        self.path = path or config.CURATOR_TESTS

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except OSError:
            return {"version": 1, "note": "", "tests": []}

    def _write(self, data):
        tmp = self.path + ".curator-tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, self.path)

    def set_test(self, test):
        tid = (test.get("id") or "").strip()
        if not tid:
            raise ValueError("id ist erforderlich (kurz, eindeutig, kebab-case).")
        if not test.get("template"):
            raise ValueError("template ist erforderlich.")
        if test.get("expected") is None:
            raise ValueError("expected ist erforderlich (erwarteter deutscher Output).")
        clean = {
            "id": tid,
            "description": test.get("description", ""),
            "template": test["template"],
            "subject": test.get("subject") or "Snapjaw",
            "object": test.get("object") or "Snapjaw",
            "expected": test["expected"],
            "enabled": bool(test.get("enabled", True)),
            "sourceUnit": test.get("sourceUnit", ""),
        }
        with _lock:
            data = self.load()
            tests = data.setdefault("tests", [])
            for i, t in enumerate(tests):
                if t.get("id") == tid:
                    tests[i] = clean
                    break
            else:
                tests.append(clean)
            self._write(data)
        return clean

    def delete_test(self, tid):
        with _lock:
            data = self.load()
            tests = data.get("tests", [])
            keep = [t for t in tests if t.get("id") != tid]
            if len(keep) == len(tests):
                raise KeyError("Test „%s“ nicht gefunden." % tid)
            data["tests"] = keep
            self._write(data)

    def deployed_path(self):
        return os.path.join(config.CFG["deploy_dir"], "languages", "lang-de",
                            "COQDE", "CuratorTests.json")

    def status(self):
        """Tests + Log-Ergebnisse + Staleness-Diagnose."""
        data = self.load()
        log = playerlog.parse_log(config.CFG["player_log"])
        results = {r["id"]: r for r in log["curator"]["results"]}
        header = log["curator"]["header"]

        dep = self.deployed_path()
        deployed_exists = os.path.exists(dep)
        synced = deployed_exists and _sha(dep) == _sha(self.path)

        run_stale = False
        if header and deployed_exists:
            logged_mtime = ticks_to_unix(header["file_mtime_ticks"])
            actual = os.stat(dep).st_mtime
            run_stale = abs(logged_mtime - actual) > 2.0  # FS-Rundung tolerieren

        tests = []
        for t in data.get("tests", []):
            r = results.get(t.get("id"))
            tests.append(dict(t, result=r["status"] if r else None,
                              detail=r["detail"] if r else None))
        return {
            "tests": tests,
            "note": data.get("note", ""),
            "log_has_run": header is not None or bool(results),
            "run_stale": run_stale,
            "synced": synced,
            "deployed_exists": deployed_exists,
            "log_mtime": log["mtime"],
        }
