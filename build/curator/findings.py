"""Playtest-Befunde: was im Spiel auffällt, bis zur Bestätigung im nächsten Lauf.

Ein Befund = Beschreibung + optional Einheit (uid) + optional Screenshot. Status:
  open      gemeldet, noch nicht behoben
  verify    behoben (Wert-Hash beim Beheben gespeichert) — im nächsten Spiel-Lauf prüfen
  closed    im Spiel bestätigt
  regressed nach dem Beheben wieder aufgetaucht (Hand-Rückmeldung oder String-Miss im Log)
  wontfix   bewusst so gelassen
Automatik: Ist ein „verify“-Befund an eine Einheit gebunden und meldet ein Player.log,
das NACH dem Beheben geschrieben wurde, einen String-Miss für deren Context, wird er
„regressed“. Bestätigen (closed) bleibt Handarbeit — das Log kann nicht sagen, ob ein
Text gut aussah.

Ablage: build/curator/data/findings/findings.json (committbar); Screenshots daneben
als <id>.png (gitignoriert, bleiben lokal).
"""
import base64
import json
import os
import re
import threading
import time

from . import config
from .review import value_hash

DIR = os.path.join(config.DATA_DIR, "findings")
PATH = os.path.join(DIR, "findings.json")
STATES = ("open", "verify", "closed", "regressed", "wontfix")
MAX_SHOT = 6 * 1024 * 1024
_lock = threading.Lock()


class Findings:
    def __init__(self, path=None):
        self.path = path or PATH

    @property
    def dir(self):
        return os.path.dirname(self.path)

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f).get("findings", {})
        except (OSError, ValueError):
            return {}

    def _write(self, data):
        os.makedirs(self.dir, exist_ok=True)
        out = {"note": "Playtest-Befunde der Kurator-UI. id -> {text, where, uid, status, "
                       "history[], screenshot, fixed_value_sha1, fixed_at}. Committbar; "
                       "Screenshots (*.png) bleiben lokal.",
               "findings": {k: data[k] for k in sorted(data)}}
        tmp = self.path + ".curator-tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, self.path)

    def _shot(self, fid, data_url):
        m = re.match(r"data:image/png;base64,(.+)$", data_url or "", re.S)
        if not m:
            raise ValueError("Screenshot muss ein PNG (data:image/png;base64,…) sein.")
        raw = base64.b64decode(m.group(1))
        if len(raw) > MAX_SHOT:
            raise ValueError("Screenshot größer als 6 MB.")
        os.makedirs(self.dir, exist_ok=True)
        name = fid + ".png"
        with open(os.path.join(self.dir, name), "wb") as f:
            f.write(raw)
        return name

    def create(self, text, where="", uid=None, screenshot=None):
        if not (text or "").strip():
            raise ValueError("Beschreibung fehlt.")
        with _lock:
            data = self.load()
            fid = time.strftime("%Y%m%d-%H%M%S")
            while fid in data:
                fid += "x"
            e = {"text": text.strip(), "where": (where or "").strip(), "uid": uid or None,
                 "status": "open", "created": time.strftime("%Y-%m-%d %H:%M"),
                 "history": [{"date": time.strftime("%Y-%m-%d %H:%M"), "status": "open"}]}
            if screenshot:
                e["screenshot"] = self._shot(fid, screenshot)
            data[fid] = e
            self._write(data)
            return dict(e, id=fid)

    def update(self, fid, store, status=None, uid=None, note=""):
        with _lock:
            data = self.load()
            if fid not in data:
                raise KeyError("Befund nicht gefunden.")
            e = data[fid]
            if uid is not None:
                e["uid"] = uid or None
            if status:
                if status not in STATES:
                    raise ValueError("Status muss einer von %s sein." % ", ".join(STATES))
                e["status"] = status
                if status == "verify":
                    u = store.get(e["uid"]) if e.get("uid") else None
                    e["fixed_value_sha1"] = value_hash(u.display_value()) if u else None
                    e["fixed_at"] = time.time()
                e.setdefault("history", []).append(
                    {"date": time.strftime("%Y-%m-%d %H:%M"), "status": status, "note": note or ""})
            self._write(data)
            return dict(e, id=fid)

    def auto_regress(self, store, log):
        """verify-Befunde mit String-Miss im Log, das nach dem Beheben entstand -> regressed."""
        if not log or not log.get("exists") or not log.get("mtime"):
            return []
        misses = {m["context"] for m in log.get("misses", [])}
        changed = []
        with _lock:
            data = self.load()
            for fid, e in data.items():
                if e.get("status") != "verify" or not e.get("uid"):
                    continue
                if (e.get("fixed_at") or 0) >= log["mtime"]:
                    continue  # Log stammt von vor dem Beheben
                u = store.get(e["uid"])
                if u is not None and u.context and u.context in misses:
                    e["status"] = "regressed"
                    e["history"].append({"date": time.strftime("%Y-%m-%d %H:%M"),
                                         "status": "regressed",
                                         "note": "String-Miss im Player.log nach dem Beheben"})
                    changed.append(fid)
            if changed:
                self._write(data)
        return changed

    def list(self, store, log=None):
        out = []
        log_mtime = (log or {}).get("mtime")
        for fid, e in sorted(self.load().items(), reverse=True):
            u = store.get(e["uid"]) if e.get("uid") else None
            out.append(dict(e, id=fid, english=u.english if u else None,
                            value=u.display_value() if u else None,
                            changed_since_fix=bool(u and e.get("fixed_value_sha1")
                                                   and value_hash(u.display_value()) != e["fixed_value_sha1"]),
                            played_since_fix=bool(log_mtime and e.get("fixed_at")
                                                  and log_mtime > e["fixed_at"])))
        return out


FINDINGS = Findings()
