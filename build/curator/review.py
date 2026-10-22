"""Prüf-Status („geprüft") für Übersetzungseinheiten.

Marken liegen in build/curator/data/reviewed.json — im Repo committbar,
außerhalb des Deploy-Manifests (wird nicht mit ins Spiel kopiert). Eine Marke
speichert den Hash des Werts ZUM PRÜFZEITPUNKT: wird der Wert später geändert,
degradiert die Marke automatisch zu „stale" (veraltet geprüft), bis jemand neu
prüft. Die Datei ist sortiert und diff-freundlich (Review im Git möglich).

Status je Einheit: "checked" | "stale" | "unchecked".
"""
import hashlib
import json
import os
import threading
import time

from . import config

PATH = os.path.join(config.DATA_DIR, "reviewed.json")
_lock = threading.Lock()


def value_hash(display_value):
    return hashlib.sha1(display_value.encode("utf-8")).hexdigest()[:12]


class Review:
    def __init__(self, path=None):
        self.path = path or PATH
        self._cache = None  # (mtime_sig, data)

    def _load(self):
        try:
            st = os.stat(self.path)
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            self._cache = (None, {})
            return {}
        if self._cache and self._cache[0] == sig:
            return self._cache[1]
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f).get("reviewed", {})
        except Exception:
            data = {}
        self._cache = (sig, data)
        return data

    def _write(self, data):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        out = {
            "note": "Geprüft-Marken der Kurator-UI (build/curator/). uid -> "
                    "{file, key, value_sha1, date}. value_sha1 = Wert zum "
                    "Prüfzeitpunkt; weicht der aktuelle Wert ab, gilt die Marke "
                    "als veraltet. Datei ist committbar, wird NICHT deployt.",
            "reviewed": {k: data[k] for k in sorted(data)},
        }
        tmp = self.path + ".curator-tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, self.path)
        self._cache = None

    def entry(self, uid):
        return self._load().get(uid)

    def status(self, unit):
        """-> ("checked"|"stale"|"unchecked", entry|None)"""
        e = self._load().get(unit.uid)
        if not e:
            return "unchecked", None
        if e.get("value_sha1") == value_hash(unit.display_value()):
            return "checked", e
        return "stale", e

    def set_checked(self, unit, checked):
        with _lock:
            data = dict(self._load())
            if checked:
                data[unit.uid] = {
                    "file": unit.file,
                    "key": unit.key,
                    "value_sha1": value_hash(unit.display_value()),
                    "date": time.strftime("%Y-%m-%d"),
                }
            else:
                data.pop(unit.uid, None)
            self._write(data)
        return self.status(unit)

    def summary(self, store_obj):
        data = self._load()
        checked = stale = 0
        seen = set()
        for u in store_obj.all_units():
            e = data.get(u.uid)
            if not e:
                continue
            seen.add(u.uid)
            if e.get("value_sha1") == value_hash(u.display_value()):
                checked += 1
            else:
                stale += 1
        return {
            "checked": checked,
            "stale": stale,
            "orphaned": len(data) - len(seen),  # uid existiert nicht mehr
            "total_units": len(store_obj.units),
        }


REVIEW = Review()
