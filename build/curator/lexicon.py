"""GenderLexicon.tsv-Modell: zeilenerhaltender Editor + Konsequenz-Vorschau.

Die Datei ist die einzige Genus-Quelle (Kontrakt: Genus-Fixes hierhin, nie in
Code). Kommentare/Leerzeilen bleiben byte-genau erhalten; Edits sind
Zeilen-Splices, Neueinträge werden am Dateiende angefügt.
"""
import os
import threading

from . import config, german

_lock = threading.Lock()
VALID = ("m", "f", "n", "p")

UMLAUT_FOLD = (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"))


def fold(noun):
    out = noun
    for u, f in UMLAUT_FOLD:
        out = out.replace(u, f)
    return out


def has_umlaut(noun):
    return any(u in noun for u, _ in UMLAUT_FOLD)


class Lexicon:
    def __init__(self, path=None):
        self.path = path or config.GENDER_LEXICON

    def _read(self):
        with open(self.path, "r", encoding="utf-8", newline="") as f:
            return f.read()

    def entries(self):
        """-> [{noun, gender, line}] in Dateireihenfolge (nur Datenzeilen)."""
        out = []
        text = self._read()
        for i, raw in enumerate(text.split("\n")):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = raw.split("\t")
            if len(parts) < 2:
                continue
            noun = parts[0].strip().lower()
            g = parts[1].strip().lower()
            if noun and g in VALID:
                out.append({"noun": noun, "gender": g, "line": i + 1})
        return out

    def lint(self):
        """L1 (fehlender/abweichender Faltungs-Zwilling) und L2 (Duplikat)."""
        entries = self.entries()
        seen = {}
        finds = []
        for e in entries:
            if e["noun"] in seen and seen[e["noun"]] != e["gender"]:
                finds.append({"rule": "L2", "severity": "error", "noun": e["noun"],
                              "message": "Duplikat „%s“ mit abweichendem Genus "
                                         "(%s vs. %s) — der letzte gewinnt still im C#!"
                                         % (e["noun"], seen[e["noun"]], e["gender"])})
            elif e["noun"] in seen:
                finds.append({"rule": "L2", "severity": "warning", "noun": e["noun"],
                              "message": "Doppelter Eintrag „%s“ (gleiches Genus) — "
                                         "einen entfernen." % e["noun"]})
            seen[e["noun"]] = e["gender"]
        for e in entries:
            n = e["noun"]
            if has_umlaut(n):
                twin = fold(n)
                if twin not in seen:
                    finds.append({"rule": "L1", "severity": "warning", "noun": n,
                                  "twin": twin, "gender": e["gender"],
                                  "message": "Faltungs-Zwilling „%s“ fehlt "
                                             "(Datei-Konvention: beide Schreibweisen)."
                                             % twin})
                elif seen[twin] != e["gender"]:
                    finds.append({"rule": "L1", "severity": "error", "noun": n,
                                  "message": "Zwilling „%s“ hat anderes Genus (%s vs. %s)."
                                             % (twin, e["gender"], seen[twin])})
        return finds

    def set_entry(self, noun, gender):
        """Fügt hinzu oder ändert (Zeilen-Splice; Anfügen ans Dateiende)."""
        noun = (noun or "").strip().lower()
        if not noun or "\t" in noun or "\n" in noun:
            raise ValueError("Ungültiges Nomen.")
        if gender not in VALID:
            raise ValueError("Genus muss m/f/n/p sein.")
        with _lock:
            text = self._read()
            eol = "\r\n" if "\r\n" in text else "\n"
            lines = text.split("\n")
            changed = False
            for i, raw in enumerate(lines):
                parts = raw.split("\t")
                if len(parts) >= 2 and parts[0].strip().lower() == noun:
                    keep_eolr = raw.endswith("\r")
                    lines[i] = "%s\t%s%s" % (noun, gender, "\r" if keep_eolr else "")
                    changed = True
            if not changed:
                # ans Dateiende anfügen
                if not text.endswith("\n"):
                    text += eol
                text += "%s\t%s%s" % (noun, gender, eol)
                self._write(text)
                return
            self._write("\n".join(lines))

    def delete_entry(self, noun):
        noun = (noun or "").strip().lower()
        with _lock:
            text = self._read()
            lines = text.split("\n")
            out = []
            removed = False
            for raw in lines:
                parts = raw.split("\t")
                if len(parts) >= 2 and parts[0].strip().lower() == noun:
                    removed = True
                    continue
                out.append(raw)
            if not removed:
                raise KeyError("Eintrag „%s“ nicht gefunden." % noun)
            self._write("\n".join(out))

    def _write(self, text):
        tmp = self.path + ".curator-tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, self.path)

    def preview(self, noun, gender, store_obj):
        """Konsequenz-Vorschau: welche sichtbaren Namen ändern ihr Genus, wenn
        noun->gender in die Datei kommt?"""
        noun = (noun or "").strip().lower()
        lex = german.load_lexicon(self.path)
        heads = {}
        for u in store_obj.all_units():
            if u.attr not in ("DisplayName",):
                continue
            name = u.display_value()
            h = german.head_noun(name).lower()
            if h:
                heads.setdefault(h, set()).add(german.visible_text(name))
        changes = german.suffix_consequences(noun, gender, lex, heads.keys())
        out = []
        for head, old, new in changes:
            out.append({
                "head": head,
                "old": {"gender": old[0], "source": old[1]},
                "new": {"gender": new[0], "source": new[1]},
                "examples": sorted(heads[head])[:6],
            })
        exact_before = lex.get(noun)
        return {
            "noun": noun, "gender": gender,
            "replaces": exact_before,
            "twin": fold(noun) if has_umlaut(noun) else None,
            "twin_present": fold(noun) in lex if has_umlaut(noun) else None,
            "changes": sorted(out, key=lambda c: c["head"]),
        }
