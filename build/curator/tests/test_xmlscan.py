"""Scanner-Parität: xmlscan-Einheiten == ElementTree-Einheiten für alle Dateien.

Regel-Duplikat auf ET-Seite:
  - strings-Dateien: Value-Attribute + Textform-<string>
  - Blueprint-Dateien: alle Attribute außer Name/Load (nicht auf dem Root),
    Text nur für Leaf-Elemente (keine Kinder), nicht auf dem Root.
Vergleich auf (kind, covkey-artiger Schlüssel, entschärfter Wert) als Multiset.
"""
import collections
import glob
import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import xmlscan  # noqa: E402

LANG_DE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "languages", "lang-de"))


def et_units(path):
    root = ET.parse(path).getroot()
    out = collections.Counter()
    if root.tag == "strings":
        for s in root.iter("string"):
            if "Value" in s.attrib:
                out[("string", s.get("Context", ""), s.get("ID", ""), s.get("Value"))] += 1
            elif s.text and s.text.strip():
                out[("string-text", s.get("Context", ""), s.get("ID", ""), s.text)] += 1
        return out

    def walk(el, on, is_root):
        if el.tag in ("object", "mutation"):
            on = el.get("Name") or on
        if not is_root:
            for a, v in el.attrib.items():
                if a in ("Name", "ID", "Load", "Command"):
                    continue
                out[("attr", on, el.tag, el.get("Name") or "", a, v)] += 1
            if len(el) == 0 and el.text and el.text.strip():
                out[("text", on, el.tag, el.get("Name") or "", el.text)] += 1
        for ch in el:
            walk(ch, on, False)
    walk(root, None, True)
    return out


def scan_units(path, fn):
    res = xmlscan.scan(path, fn)
    out = collections.Counter()
    for u in res.units:
        if u.kind == "string":
            out[("string", u.context, u.english, u.display_value())] += 1
        elif u.kind == "string-text":
            ctx = u.key.split("|", 1)[0]
            out[("string-text", ctx, u.english, u.display_value())] += 1
        elif u.kind == "attr":
            out[("attr", u.objname, u.elem, u.elemname, u.attr, u.display_value())] += 1
        else:
            out[("text", u.objname, u.elem, u.elemname, u.display_value())] += 1
    return out, res


class TestScannerParity(unittest.TestCase):
    def test_all_files(self):
        files = sorted(glob.glob(os.path.join(LANG_DE, "*.de.xml")))
        self.assertGreater(len(files), 40, "erwarte ~44 .de.xml-Dateien")
        for p in files:
            fn = os.path.basename(p)
            with self.subTest(file=fn):
                expected = et_units(p)
                actual, res = scan_units(p, fn)
                missing = expected - actual
                extra = actual - expected
                self.assertFalse(
                    missing or extra,
                    "%s:\n  fehlt im Scanner: %s\n  zuviel im Scanner: %s" % (
                        fn,
                        list(missing.items())[:5],
                        list(extra.items())[:5]))

    def test_spans_reproduce_values(self):
        """Der Span muss exakt den gespeicherten Roh-Wert ausschneiden."""
        for p in sorted(glob.glob(os.path.join(LANG_DE, "*.de.xml"))):
            fn = os.path.basename(p)
            res = xmlscan.scan(p, fn)
            for u in res.units:
                s, e = u.span
                self.assertEqual(res.text[s:e], u.value,
                                 "%s uid=%s span!=value" % (fn, u.uid))

    def test_no_uid_collisions(self):
        for p in sorted(glob.glob(os.path.join(LANG_DE, "*.de.xml"))):
            fn = os.path.basename(p)
            res = xmlscan.scan(p, fn)
            seen = {}
            for u in res.units:
                self.assertNotIn(u.uid, seen,
                                 "%s: uid-Kollision %s <-> %s" % (fn, u.key, seen.get(u.uid)))
                seen[u.uid] = u.key


if __name__ == "__main__":
    unittest.main(verbosity=2)
