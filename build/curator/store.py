"""Index über alle Übersetzungseinheiten + Suche.

Refresh ist lazy: refresh() statet alle Datendateien (mtime+size) und scannt
nur geänderte Dateien neu — korrekt auch bei externen Edits während der
Server läuft.
"""
import glob
import os
import re
import threading

from . import config, jsonscan, xmlscan

TOKEN_RE = re.compile(r"=([A-Za-z][\w']*)((?:[.:#][^=\s][^=]*)?)=")


class Store:
    def __init__(self, lang_dir=None):
        self.lang_dir = lang_dir or config.LANG_DE
        self.lock = threading.RLock()
        self.files = {}        # filename -> ScanResult
        self.stats = {}        # filename -> (mtime, size)
        self.units = {}        # uid -> Unit
        self.dup_uids = set()  # kollidierende uids (sollten leer sein)

    def xml_files(self):
        return sorted(os.path.basename(p)
                      for p in glob.glob(os.path.join(self.lang_dir, "*.de.xml")))

    def data_files(self):
        """XML-Dateien + JSON-Datenquellen (jsonscan.JSON_FILES), sofern vorhanden."""
        js = [f for f in jsonscan.JSON_FILES if os.path.exists(self.path(f))]
        return self.xml_files() + js

    def path(self, filename):
        return os.path.join(self.lang_dir, filename)

    def refresh(self, force=False):
        with self.lock:
            changed = []
            seen = set()
            for fn in self.data_files():
                seen.add(fn)
                p = self.path(fn)
                st = os.stat(p)
                sig = (st.st_mtime_ns, st.st_size)
                if force or self.stats.get(fn) != sig:
                    scanner = jsonscan if fn in jsonscan.JSON_FILES else xmlscan
                    self.files[fn] = scanner.scan(p, fn)
                    self.stats[fn] = sig
                    changed.append(fn)
            for fn in list(self.files):
                if fn not in seen:
                    del self.files[fn], self.stats[fn]
                    changed.append(fn)
            if changed:
                self._rebuild_unit_map()
            return changed

    def _rebuild_unit_map(self):
        self.units = {}
        self.dup_uids = set()
        for res in self.files.values():
            for u in res.units:
                if u.uid in self.units:
                    self.dup_uids.add(u.uid)
                self.units[u.uid] = u

    def get(self, uid):
        return self.units.get(uid)

    def all_units(self):
        return self.units.values()

    def category(self, u):
        if u.kind == "json":
            return "HistorySpice"
        if u.kind in ("string", "string-text"):
            return "Strings"
        if u.attr == "#text":
            return "Beschreibungstext"
        if u.attr == "DisplayName":
            return "DisplayName"
        if u.attr in ("Short", "Long"):
            return "Beschreibung"
        if u.elem == "tag" and u.elemname in ("PetResponse", "SimpleConversation"):
            return "Ambient"
        if (u.elem or "").startswith("xtag"):
            return "xtag-Flavor"
        return "Sonstiges"

    def search(self, q="", mode="de", file=None, category=None,
               has_token=False, offset=0, limit=100, uids=None, predicate=None):
        """-> (total, [Unit]) — einfache Substring-Suche, case-insensitiv."""
        ql = (q or "").lower()
        out = []
        with self.lock:
            pool = (self.units[i] for i in uids if i in self.units) if uids is not None \
                else self.all_units()
            for u in pool:
                if file and u.file != file:
                    continue
                if category and self.category(u) != category:
                    continue
                if predicate is not None and not predicate(u):
                    continue
                disp = u.display_value()
                if has_token and not TOKEN_RE.search(disp):
                    continue
                if ql:
                    if mode == "de":
                        hay = disp.lower()
                    elif mode == "en":
                        hay = (u.english or "").lower()
                    elif mode == "context":
                        hay = ((u.context or "") + " " + (u.objname or "") + " "
                               + (u.elemname or "")).lower()
                    elif mode == "token":
                        hay = " ".join(m.group(0) for m in TOKEN_RE.finditer(
                            (u.english or "") + " " + disp)).lower()
                    else:
                        hay = disp.lower()
                    if ql not in hay:
                        continue
                out.append(u)
        out.sort(key=lambda u: (u.file, u.line))
        return len(out), out[offset:offset + limit]

    def blueprint_names(self):
        names = set()
        with self.lock:
            for u in self.all_units():
                if u.objname:
                    names.add(u.objname)
        return sorted(names)
