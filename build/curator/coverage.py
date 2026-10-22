"""Unübersetzt-Filter: Manifest-Diff gegen ExampleLanguage/*.example.xml.

Repliziert exakt die Key-Logik von build/tools/coverage_audit.py (▶-Marker =
übersetzbare Einheit). Fehlt der Spielpfad, degradiert alles zu leeren
Ergebnissen + Hinweis.
"""
import glob
import json
import time
import os
import xml.etree.ElementTree as ET

from . import config
from .xmlscan import POSITIONAL_TAGS, SCOPE_TAGS

MARK = "▶"  # ▶


def _parse(p):
    try:
        return ET.parse(p).getroot()
    except Exception:
        return None


BOOL_VALUES = {"true", "false"}


def _child_text(el):
    """Sichtbarer Text der Kind-Elemente (für Container wie <description><p>…)."""
    return " ".join(t.strip() for ch in el for t in ch.itertext() if t.strip()).replace(MARK, "")


def positional_tags(root=None):
    """Tags mit übersetztem (▶-markiertem) Name — auf BEIDEN Seiten über die
    Position identifiziert. Feste Liste, geteilt mit xmlscan (covkey-Gleichheit);
    tests/test_coverage.py prüft, dass sie alle Manifeste abdeckt."""
    return POSITIONAL_TAGS


def _children(el, positional):
    """Kinder mit stabiler Identität: Name-Attribut, sonst Position."""
    seen = {}
    for ch in el:
        # Anker wie xmlscan: Name, sonst ID (Optionen), sonst Command (Fähigkeiten)
        name = ch.get("Name") or ch.get("ID") or ch.get("Command") or ""
        if ch.tag in positional:
            n = seen.get(ch.tag, 0)
            seen[ch.tag] = n + 1
            yield ch, "#%d" % n
        else:
            yield ch, name


def units_example(root, is_strings, positional=POSITIONAL_TAGS):
    """Key -> (englischer Manifest-Text ohne ▶, Context oder None)."""
    U = {}
    if is_strings:
        for s in root.iter("string"):
            txts = []
            if s.text and MARK in s.text:
                txts.append(s.text.replace(MARK, "").strip())
            for v in s.attrib.values():
                if v and v.startswith(MARK):
                    txts.append(v[len(MARK):])
            if txts:
                U[("S", s.get("ID"))] = (txts[0], s.get("Context", ""))
        return U

    def walk(el, on, ident):
        if el.tag in SCOPE_TAGS:
            on = el.get("Name") or on
        for a, v in el.attrib.items():
            if a != "Name" and isinstance(v, str) and v.startswith(MARK):
                if v[len(MARK):].strip().lower() in BOOL_VALUES:
                    continue  # Booleans bleiben englisch (Kontrakt B1) -> keine Einheit
                U[(on, el.tag, ident, a)] = (v[len(MARK):], None)
        if el.text and MARK in el.text:
            txt = el.text.replace(MARK, "").strip()
            # Container mit Marker nur vor Kind-Elementen (<description>▶<p>…): die Kinder
            # tragen den Text -> Einheit gilt als abgedeckt, sobald die deutschen Kinder Text haben
            full = txt or _child_text(el)
            if full:  # leerer Marker (<leveltext>▶</leveltext>) = nichts zu übersetzen
                U[(on, el.tag, ident, "#text")] = (full, None)
        for ch, cid in _children(el, positional):
            walk(ch, on, cid)
    walk(root, None, "")
    return U


def covered_de(root, is_strings, positional=POSITIONAL_TAGS):
    if root is None:
        return set()
    C = set()
    if is_strings:
        return {("S", s.get("ID")) for s in root.iter("string") if s.get("ID")}

    def walk(el, on, ident):
        if el.tag in SCOPE_TAGS:
            on = el.get("Name") or on
        for a, v in el.attrib.items():
            if a != "Name" and isinstance(v, str) and v.strip():
                C.add((on, el.tag, ident, a))
        if (el.text and el.text.strip()) or (len(el) and _child_text(el)):
            C.add((on, el.tag, ident, "#text"))
        for ch, cid in _children(el, positional):
            walk(ch, on, cid)
    walk(root, None, "")
    return C


class Coverage:
    """Cached gegen mtimes von Manifest + de-Dateien."""

    def __init__(self, lang_dir=None, game_dir=None):
        self.lang_dir = lang_dir or config.LANG_DE
        self.game_dir = game_dir or config.CFG["game_example_dir"]
        self._sig = None
        self._result = None
        self._file_keys = {}  # name -> frozenset(Manifest-Keys)

    def available(self):
        return os.path.isdir(self.game_dir)

    def _signature(self):
        sig = []
        for pat in (os.path.join(self.game_dir, "*.example.xml"),
                    os.path.join(self.lang_dir, "*.de.xml")):
            for p in sorted(glob.glob(pat)):
                st = os.stat(p)
                sig.append((p, st.st_mtime_ns, st.st_size))
        return tuple(sig)

    def compute(self):
        """-> {"files": {name: {units, covered, missing:[{key, english}]}}, "totals": ...}"""
        if not self.available():
            return {"available": False, "game_dir": self.game_dir, "files": {},
                    "totals": {"units": 0, "covered": 0}}
        sig = self._signature()
        if sig == self._sig and self._result is not None:
            return self._result
        files = {}
        tu = tc = 0
        for ex in sorted(glob.glob(os.path.join(self.game_dir, "*.example.xml"))):
            name = os.path.basename(ex).replace(".example.xml", "")
            if name == "Naming":
                continue
            exroot = _parse(ex)
            if exroot is None:
                continue
            is_strings = exroot.tag == "strings"
            pos = positional_tags(exroot)
            exu = units_example(exroot, is_strings, pos)
            if not exu:
                continue
            deroot = _parse(os.path.join(self.lang_dir, "%s.de.xml" % name))
            deu = covered_de(deroot, is_strings, pos)
            self._file_keys[name] = frozenset(exu.keys())
            missing = [{"key": list(k), "english": v[0], "context": v[1]}
                       for k, v in sorted(exu.items(), key=lambda kv: str(kv[0]))
                       if k not in deu]
            tu += len(exu)
            tc += len(exu) - len(missing)
            files[name] = {"units": len(exu), "covered": len(exu) - len(missing),
                           "missing": missing, "is_strings": is_strings}
        self._sig = sig
        self._result = {"available": True, "game_dir": self.game_dir, "files": files,
                        "totals": {"units": tu, "covered": tc}}
        return self._result

    def manifest_keys(self, name):
        """Alle Manifest-Keys (▶-markiert) einer Datei — nach compute()."""
        self.compute()
        return self._file_keys.get(name)

    # ------------------------------------------------ Versions-Snapshot

    def build_version(self):
        """Spiel-Build aus dem Manifest-Kopf ("… Generated Localizable XML 2.0.212.31")."""
        import re
        for name in ("Strings", "Creatures"):
            p = os.path.join(self.game_dir, name + ".example.xml")
            try:
                with open(p, encoding="utf-8-sig") as f:
                    head = f.read(600)
            except OSError:
                continue
            m = re.search(r"\b(\d+\.\d+\.\d+(?:\.\d+)?)\b", head)
            if m:
                return m.group(1)
        return None

    def current_manifest(self):
        """{datei: {json-key: englischer Text}} aller ▶-Einheiten (Naming ausgenommen)."""
        out = {}
        for ex in sorted(glob.glob(os.path.join(self.game_dir, "*.example.xml"))):
            name = os.path.basename(ex).replace(".example.xml", "")
            if name == "Naming":
                continue
            root = _parse(ex)
            if root is None:
                continue
            units = units_example(root, root.tag == "strings")
            out[name] = {json.dumps(list(k), ensure_ascii=False): v[0] for k, v in units.items()}
        return out

    def save_snapshot(self, path):
        data = {"build": self.build_version(), "created": time.strftime("%Y-%m-%d %H:%M"),
                "files": self.current_manifest()}
        tmp = path + ".curator-tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=0, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
        return {"build": data["build"], "created": data["created"],
                "units": sum(len(v) for v in data["files"].values())}

    def diff_snapshot(self, path, limit=200):
        """Neu / entfernt / Englisch geändert seit dem Snapshot."""
        try:
            with open(path, encoding="utf-8") as f:
                snap = json.load(f)
        except (OSError, ValueError):
            return {"snapshot": None, "build": self.build_version()}
        cur = self.current_manifest()
        added, removed, changed = [], [], []
        for name in sorted(set(cur) | set(snap.get("files", {}))):
            a, b = snap["files"].get(name, {}), cur.get(name, {})
            for k in b.keys() - a.keys():
                added.append({"file": name, "key": json.loads(k), "english": b[k]})
            for k in a.keys() - b.keys():
                removed.append({"file": name, "key": json.loads(k), "english": a[k]})
            for k in a.keys() & b.keys():
                if a[k] != b[k]:
                    changed.append({"file": name, "key": json.loads(k), "old": a[k], "new": b[k]})
        return {"snapshot": {"build": snap.get("build"), "created": snap.get("created")},
                "build": self.build_version(),
                "counts": {"added": len(added), "removed": len(removed), "changed": len(changed)},
                "added": added[:limit], "removed": removed[:limit], "changed": changed[:limit]}

    def missing_covkeys(self, filename_de):
        """Set der Manifest-Keys ohne deutsche Abdeckung für eine .de.xml-Datei."""
        name = filename_de.replace(".de.xml", "")
        res = self.compute()
        f = res["files"].get(name)
        if not f:
            return set()
        return {tuple(m["key"]) for m in f["missing"]}
