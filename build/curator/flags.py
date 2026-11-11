"""Markierungen aus der Szenen-Vorschau („passt nicht im Kontext").

Ein Prüfer markiert eine Einheit mit einer Notiz, wenn sie im Kontext nicht
passt (Ton, Kasus über Fragmentgrenzen, Länge …). Liegt in
build/curator/data/flags.json — committbar, wird nicht deployt. Anders als
geprüft-Marken verfallen Markierungen nicht bei Wertänderung; der Hash zum
Markierzeitpunkt zeigt nur an, ob seitdem nachgebessert wurde.

Optional mit Fehlerstelle (span: {start, end, text} im Display-Wert) und
Kategorie (CATEGORIES) — Grundlage für tools/review_fix.py, das genau diese
Stelle von einem Agenten korrigieren lässt.
"""
import json
import os
import threading
import time

from . import config
from .review import value_hash

PATH = os.path.join(config.DATA_DIR, "flags.json")
_lock = threading.Lock()

CATEGORIES = {
    "kasus-genus": "Kasus / Genus / Artikel",
    "verb": "Verbform / Konjugation",
    "anrede": "Anrede (du)",
    "bedeutung": "Bedeutung falsch / Fehlübersetzung",
    "stil": "Stil / Ton / holprig",
    "begriff": "Begriff / Terminologie",
    "tippfehler": "Tipp- / Rechtschreibfehler",
    "unuebersetzt": "Unübersetzt / englischer Rest",
    "sonstiges": "Sonstiges",
}


def check_span(value, span):
    """-> bereinigter span oder ValueError (Grenzen + Text müssen zum Wert passen)."""
    try:
        s, e = int(span["start"]), int(span["end"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("span braucht start und end.")
    if not 0 <= s < e <= len(value):
        raise ValueError("span liegt außerhalb des Werts.")
    if span.get("text") is not None and value[s:e] != span["text"]:
        raise ValueError("span-Text passt nicht zum aktuellen Wert — neu markieren.")
    return {"start": s, "end": e, "text": value[s:e]}


class Flags:
    def __init__(self, path=None):
        self.path = path or PATH

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f).get("flags", {})
        except (OSError, ValueError):
            return {}

    def _write(self, data):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        out = {"note": "Markierungen der Szenen-Vorschau (build/curator/). uid -> "
                       "{file, key, note, value_sha1, date}. Committbar, wird NICHT deployt.",
               "flags": {k: data[k] for k in sorted(data)}}
        tmp = self.path + ".curator-tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, self.path)

    STATES = ("open", "fixed", "wontfix")

    def set(self, unit, note, kind=None, span=None, category=None):
        """Markierung setzen/erneuern (Status wieder open). kind: z. B. "orphan"
        für verwaiste Einträge nach K1-Neuanlage (dürfen gelöscht werden)."""
        if category is not None and category not in CATEGORIES:
            raise ValueError("Kategorie muss eine von %s sein." % ", ".join(CATEGORIES))
        if span is not None:
            span = check_span(unit.display_value(), span)
        with _lock:
            data = self.load()
            data[unit.uid] = {"file": unit.file, "key": unit.key, "note": note or "",
                              "value_sha1": value_hash(unit.display_value()),
                              "date": time.strftime("%Y-%m-%d"), "status": "open"}
            if kind:
                data[unit.uid]["kind"] = kind
            if span:
                data[unit.uid]["span"] = span
            if category:
                data[unit.uid]["category"] = category
            self._write(data)
            return data[unit.uid]

    def set_status(self, uid, status):
        if status not in self.STATES:
            raise ValueError("Status muss open, fixed oder wontfix sein.")
        with _lock:
            data = self.load()
            if uid not in data:
                raise KeyError("Keine Markierung für diese Einheit.")
            data[uid]["status"] = status
            data[uid]["closed"] = time.strftime("%Y-%m-%d") if status != "open" else None
            self._write(data)
            return data[uid]

    def open_flags(self):
        return {k: v for k, v in self.load().items() if v.get("status", "open") == "open"}

    def clear(self, uid):
        with _lock:
            data = self.load()
            if data.pop(uid, None) is not None:
                self._write(data)

    def list(self, store):
        out = []
        for uid, e in sorted(self.load().items(), key=lambda kv: kv[1].get("date", "")):
            u = store.get(uid)
            out.append({**e, "uid": uid, "exists": u is not None,
                        "status": e.get("status", "open"),
                        "changed": bool(u) and value_hash(u.display_value()) != e.get("value_sha1"),
                        "value": u.display_value() if u else None,
                        "english": u.english if u else None})
        return out


FLAGS = Flags()
