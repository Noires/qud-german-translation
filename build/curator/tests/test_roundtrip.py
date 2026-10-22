"""Round-Trip-Suite für den chirurgischen Writer — das Phase-2-Gate.

Arbeitet ausschließlich auf Temp-KOPIEN des echten Korpus (nie am Repo):
  1. No-op-Save jeder Einheit -> Datei byte-identisch (BOM, EOL, alles).
  2. Mutationstest: Sentinel schreiben -> genau eine zusammenhängende
     Byte-Region geändert, Rescan findet den Sentinel unter unverändertem
     Key; Original zurückschreiben -> byte-identisch (bei kanonischem
     Original-Escaping) bzw. semantisch identisch.
  3. Schutzprüfungen: ID-Manipulation über den Wert ist unmöglich
     (Escaping), externer Edit -> 409, Naming-Kontrakt blockt.
  4. Neuanlage: Key-Set = alt + neu, Nachbarzeilen unangetastet.
"""
import glob
import os
import random
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import store, writer, xmlscan  # noqa: E402

LANG_DE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "languages", "lang-de"))


def make_temp_corpus(files=None):
    tmp = tempfile.mkdtemp(prefix="qudde-roundtrip-")
    for p in sorted(glob.glob(os.path.join(LANG_DE, "*.de.xml"))):
        fn = os.path.basename(p)
        if files and fn not in files:
            continue
        shutil.copy2(p, os.path.join(tmp, fn))
    return tmp


def read_bytes(p):
    with open(p, "rb") as f:
        return f.read()


class TestNoOpSaves(unittest.TestCase):
    """No-op-Save jeder Einheit aller Dateien -> byte-identisch."""

    def test_noop_all_units(self):
        tmp = make_temp_corpus()
        try:
            st = store.Store(lang_dir=tmp)
            st.refresh()
            before = {fn: read_bytes(os.path.join(tmp, fn)) for fn in st.xml_files()}
            for uid in list(st.units.keys()):
                u = st.units[uid]
                writer.save(st, uid, u.display_value(), u.display_value())
            for fn, data in before.items():
                self.assertEqual(read_bytes(os.path.join(tmp, fn)), data,
                                 "%s nach No-op-Saves nicht byte-identisch" % fn)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestMutation(unittest.TestCase):
    SENTINEL = "KURATOR-SENTINEL äöü {{r|rot}} & <kein-tag> =object.dativ="

    def test_mutate_and_restore(self):
        tmp = make_temp_corpus()
        try:
            st = store.Store(lang_dir=tmp)
            st.refresh()
            rng = random.Random(42)
            by_kind = {}
            for u in st.all_units():
                by_kind.setdefault(u.kind, []).append(u.uid)
            sample = []
            for kind, uids in by_kind.items():
                rng.shuffle(uids)
                sample += uids[:50]
            self.assertGreaterEqual(len(by_kind), 4, "erwarte alle 4 Einheiten-Arten")

            for uid in sample:
                u = st.get(uid)
                fn, key, kind = u.file, u.key, u.kind
                orig_bytes = read_bytes(os.path.join(tmp, fn))
                orig_value = u.display_value()
                if (u.context or "").endswith(writer.NAMING_CTX_SUFFIX):
                    continue  # Kontrakt blockt frei erfundene Sentinels — eigener Test unten

                fresh = writer.save(st, uid, orig_value, self.SENTINEL)
                self.assertEqual(fresh.key, key)
                self.assertEqual(fresh.kind, kind)
                self.assertEqual(fresh.display_value(), self.SENTINEL)

                # genau eine zusammenhängende Region geändert
                mut = read_bytes(os.path.join(tmp, fn))
                pre = common_prefix(orig_bytes, mut)
                suf = common_suffix(orig_bytes, mut)
                self.assertLessEqual(pre + suf, min(len(orig_bytes), len(mut)),
                                     "%s: Änderung nicht zusammenhängend" % fn)

                # zurückschreiben
                writer.save(st, fresh.uid, self.SENTINEL, orig_value)
                back = read_bytes(os.path.join(tmp, fn))
                if canonical(u):
                    self.assertEqual(back, orig_bytes,
                                     "%s (%s): Rückschreiben nicht byte-identisch" % (fn, key))
                else:
                    st.refresh()
                    self.assertEqual(st.get(uid).display_value(), orig_value)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def canonical(u):
    """Original-Escaping entspricht dem des Writers -> Byte-Identität erwartbar."""
    return u.escape_back(u.display_value()) == u.value


def common_prefix(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def common_suffix(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[len(a) - 1 - i] == b[len(b) - 1 - i]:
        i += 1
    return i


class TestGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = make_temp_corpus({"Strings.de.xml", "Naming.de.xml", "Items.de.xml"})
        self.st = store.Store(lang_dir=self.tmp)
        self.st.refresh()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _first_string_unit(self):
        for u in self.st.all_units():
            if u.kind == "string" and u.file == "Strings.de.xml" \
               and not (u.context or "").endswith(writer.NAMING_CTX_SUFFIX):
                return u
        self.fail("keine String-Einheit gefunden")

    def test_value_cannot_break_out(self):
        """Ein Wert mit Quote/Tag-Syntax darf die Struktur nicht ändern können."""
        u = self._first_string_unit()
        evil = 'x" ID="HACKED" Value="y'
        fresh = writer.save(self.st, u.uid, u.display_value(), evil)
        self.assertEqual(fresh.display_value(), evil)  # escaped gespeichert
        self.assertEqual(fresh.english, u.english)     # ID unverändert

    def test_stale_old_value_conflicts(self):
        u = self._first_string_unit()
        with self.assertRaises(writer.WriteError) as cm:
            writer.save(self.st, u.uid, u.display_value() + "-veraltet", "neu")
        self.assertEqual(cm.exception.status, 409)

    def test_naming_contract_blocks(self):
        victim = None
        for u in self.st.all_units():
            if (u.context or "").endswith(writer.NAMING_CTX_SUFFIX) \
               and "=" not in u.display_value():
                victim = u
                break
        if victim is None:
            self.skipTest("kein token-freier Naming-Kontrakt-Eintrag")
        with self.assertRaises(writer.WriteError) as cm:
            writer.save(self.st, victim.uid, victim.display_value(),
                        "FreiErfundenerTitelXYZ")
        self.assertEqual(cm.exception.status, 422)
        self.assertIn("Naming", str(cm.exception))

    def test_create_string_entry(self):
        before = read_bytes(os.path.join(self.tmp, "Strings.de.xml"))
        n_before = len(self.st.files["Strings.de.xml"].units)
        fresh = writer.create_string_entry(
            self.st, "Strings.de.xml", "Kurator Test Context",
            'A "new" <string> & more =object.the.name=', "Ein Wert")
        self.assertEqual(fresh.english, 'A "new" <string> & more =object.the.name=')
        self.assertEqual(fresh.display_value(), "Ein Wert")
        self.assertEqual(len(self.st.files["Strings.de.xml"].units), n_before + 1)
        after = read_bytes(os.path.join(self.tmp, "Strings.de.xml"))
        # genau eine Zeile eingefügt: ohne sie ist die Datei byte-identisch
        idx = after.find(b"Kurator Test Context")
        self.assertGreater(idx, 0)
        line_start = after.rfind(b"\n", 0, idx) + 1
        line_end = after.find(b"\n", idx) + 1
        self.assertEqual(after[:line_start] + after[line_end:], before)
        with self.assertRaises(writer.WriteError) as cm:
            writer.create_string_entry(
                self.st, "Strings.de.xml", "Kurator Test Context",
                'A "new" <string> & more =object.the.name=', "Doppelt")
        self.assertEqual(cm.exception.status, 409)


if __name__ == "__main__":
    unittest.main(verbosity=2)
