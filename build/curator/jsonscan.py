"""Positions-genauer Scanner für JSON(C)-Datenquellen (HistorySpice.jsonc).

Liefert dieselben Unit-/ScanResult-Strukturen wie xmlscan: jede String-WERT-
Position (Objektwerte und Array-Elemente, keine Schlüssel) wird eine Einheit
kind="json" mit exakter Spanne des Inhalts zwischen den Anführungszeichen —
der Writer splict byte-genau hinein (JSON-Escaping, Rest der Datei unberührt).

key   = JSON-Pfad ("/spice/elements/glass/materials=/0")
context = Pfad ohne Array-Indizes und ohne "="-Suffixe (für Suche/Gruppierung)
english = Wert am selben Pfad in Base/HistorySpice.jsonc (übersetzte deutsche
          Blatt-Schlüssel tragen ein "="-Suffix, das englische Original nicht)

LibraryCorpus.de.json ist ABSICHTLICH nicht dabei: generiert von
build/tools/build_library_corpus.py aus Books/Beschreibungen/Gesprächen.
"""
import json
import os

from . import xmlscan

JSON_FILES = ("HistorySpice.jsonc",)


class _Parser:
    def __init__(self, text):
        self.t = text
        self.i = 0
        self.leaves = []  # (path tuple, start, end) Inhalt ohne Anführungszeichen

    def ws(self):
        t, n = self.t, len(self.t)
        while self.i < n:
            c = t[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif t.startswith("//", self.i):
                j = t.find("\n", self.i)
                self.i = n if j < 0 else j + 1
            elif t.startswith("/*", self.i):
                j = t.find("*/", self.i + 2)
                self.i = n if j < 0 else j + 2
            else:
                break

    def string(self):
        assert self.t[self.i] == '"', "Zeichenkette erwartet bei %d" % self.i
        start = self.i + 1
        j = start
        t = self.t
        while True:
            c = t[j]
            if c == "\\":
                j += 2
                continue
            if c == '"':
                break
            j += 1
        self.i = j + 1
        return start, j

    def value(self, path):
        self.ws()
        c = self.t[self.i]
        if c == "{":
            self.i += 1
            self.ws()
            if self.t[self.i] == "}":
                self.i += 1
                return
            while True:
                self.ws()
                ks, ke = self.string()
                key = json.loads('"' + self.t[ks:ke] + '"')
                self.ws()
                assert self.t[self.i] == ":", "':' erwartet bei %d" % self.i
                self.i += 1
                self.value(path + (key,))
                self.ws()
                if self.t[self.i] == ",":
                    self.i += 1
                    self.ws()
                    if self.t[self.i] == "}":  # JSONC: Komma vor }
                        self.i += 1
                        return
                    continue
                assert self.t[self.i] == "}", "'}' erwartet bei %d" % self.i
                self.i += 1
                return
        if c == "[":
            self.i += 1
            k = 0
            self.ws()
            if self.t[self.i] == "]":
                self.i += 1
                return
            while True:
                self.value(path + (k,))
                k += 1
                self.ws()
                if self.t[self.i] == ",":
                    self.i += 1
                    self.ws()
                    if self.t[self.i] == "]":
                        self.i += 1
                        return
                    continue
                assert self.t[self.i] == "]", "']' erwartet bei %d" % self.i
                self.i += 1
                return
        if c == '"':
            s, e = self.string()
            self.leaves.append((path, s, e))
            return
        # Zahl / true / false / null
        j = self.i
        while j < len(self.t) and self.t[j] not in ",}] \t\r\n":
            j += 1
        self.i = j


def _path_key(path):
    return "/" + "/".join(str(p) for p in path)


def _context(path):
    return ".".join(str(p).rstrip("=") for p in path if not isinstance(p, int))


def _english_lookup(base_root, path):
    node = base_root
    for p in path:
        if isinstance(p, int):
            if not isinstance(node, list) or p >= len(node):
                return None
            node = node[p]
        else:
            if not isinstance(node, dict):
                return None
            k = p.rstrip("=")
            node = node.get(k, node.get(p))
            if node is None:
                return None
    return node if isinstance(node, str) else None


_base_cache = {}


def load_base(filename):
    """Englisches Original aus dem Spiel (Base/<filename>), JSONC-tolerant."""
    from . import convtree
    p = os.path.join(convtree.base_dir(), filename)
    try:
        st = os.stat(p)
    except OSError:
        return None
    sig = (st.st_mtime_ns, st.st_size)
    hit = _base_cache.get(filename)
    if hit and hit[0] == sig:
        return hit[1]
    from . import grammar_emu
    root = {"spice": grammar_emu._load_spice(p)} if filename == "HistorySpice.jsonc" else None
    _base_cache[filename] = (sig, root)
    return root


def scan_text(text, filename, bom=b"", digest=None):
    p = _Parser(text)
    p.ws()
    p.value(())
    lines = xmlscan._Lines(text)
    base = load_base(filename)
    units = []
    for path, s, e in p.leaves:
        key = _path_key(path)
        units.append(xmlscan.Unit(
            uid=xmlscan._mkuid(filename, "json", key), file=filename, kind="json",
            key=key, covkey=(key,), context=_context(path),
            english=_english_lookup(base, path) if base else None,
            value=text[s:e], span=(s, e), quote='"', line=lines.line(s),
            objname=None, elem="json", elemname=str(path[-2]) if len(path) > 1 else "",
            attr="json", eol="\n"))
    return xmlscan.ScanResult(units, text, bom, digest, "json")


def scan(path, filename):
    text, bom, digest = xmlscan.read_file(path)
    return scan_text(text, filename, bom, digest)


def verify(new_text, filename, expect_keys):
    """Kandidat muss gültiges JSON(C) bleiben und dieselben Wert-Pfade haben."""
    res = scan_text(new_text, filename)
    got = sorted(("json", u.key) for u in res.units)
    return res, got == expect_keys
