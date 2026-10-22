"""Verbs.json-Modell: Editor mit stilerhaltendem Emitter + Schwach-Vorschau.

Nur STARKE (unregelmäßige) Verben gehören in die Datei; die Vorschau zeigt,
was die schwache Fallback-Konjugation ergäbe, damit der Kurator entscheiden
kann, ob ein Eintrag nötig ist. Trennbare Präfix-Verben werden abgewehrt
(Datei-Kontrakt: brechen die Wortstellung).
"""
import json
import os
import threading

from . import config, german

_lock = threading.Lock()
FIELDS = ("en", "inf", "s3", "s2", "p2", "p3")


class Verbs:
    def __init__(self, path=None):
        self.path = path or config.VERBS_JSON

    def load(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def entries(self):
        return self.load().get("verbs", [])

    def _emit(self, data):
        """Stil der bestehenden Datei: 2-Space-Indent, Key-Reihenfolge
        version/note/verbs, Verb-Keys in FIELDS-Reihenfolge, LF."""
        verbs = []
        for v in data.get("verbs", []):
            verbs.append({k: v[k] for k in FIELDS if k in v})
        ordered = {"version": data.get("version", 2),
                   "note": data.get("note", ""),
                   "verbs": verbs}
        text = json.dumps(ordered, ensure_ascii=False, indent=2) + "\n"
        tmp = self.path + ".curator-tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp, self.path)

    def weak_preview(self, inf):
        low = (inf or "").strip().lower()
        pref, ambig = german.separable_prefix(low)
        return {
            "inf": low,
            "weak": {"s3": german.weak_conjugate(low, 0), "s2": german.weak_conjugate(low, 3),
                     "p2": german.weak_conjugate(low, 1),
                     "p3": german.weak_conjugate(low, 2)},
            "separable": {"prefix": pref, "ambiguous": ambig} if pref else None,
            "exists": any(v.get("inf", "").lower() == low for v in self.entries()),
        }

    def set_entry(self, entry, allow_separable=False):
        inf = (entry.get("inf") or "").strip()
        if not inf:
            raise ValueError("inf (deutscher Infinitiv) ist erforderlich.")
        if not entry.get("s3"):
            raise ValueError("s3 ist erforderlich — Verben ohne s3 sind schwach "
                             "und brauchen keinen Eintrag.")
        pref, ambig = german.separable_prefix(inf.lower())
        if pref and not ambig and not allow_separable:
            raise ValueError(
                "„%s“ beginnt mit trennbarem Präfix „%s-“ — trennbare Verben "
                "brechen die Wortstellung im Einzel-Token (Datei-Kontrakt). "
                "Untrennbares Synonym wählen (z. B. attackieren statt angreifen) "
                "oder bewusst mit allow_separable=true speichern." % (inf, pref))
        with _lock:
            data = self.load()
            verbs = data.setdefault("verbs", [])
            new = {k: entry[k] for k in FIELDS if entry.get(k)}
            for i, v in enumerate(verbs):
                if v.get("inf", "").lower() == inf.lower():
                    verbs[i] = new
                    break
            else:
                verbs.append(new)
            self._emit(data)
            return new

    def delete_entry(self, inf):
        low = (inf or "").strip().lower()
        with _lock:
            data = self.load()
            verbs = data.get("verbs", [])
            keep = [v for v in verbs if v.get("inf", "").lower() != low]
            if len(keep) == len(verbs):
                raise KeyError("Verb „%s“ nicht gefunden." % inf)
            data["verbs"] = keep
            self._emit(data)
