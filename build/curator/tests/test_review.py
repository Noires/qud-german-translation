"""Geprüft-Status: Marke setzen, Wert-Änderung degradiert zu stale, aufheben."""
import glob
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import review, store, writer  # noqa: E402

LANG_DE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "languages", "lang-de"))


class TestReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="qudde-review-")
        shutil.copy2(os.path.join(LANG_DE, "Items.de.xml"),
                     os.path.join(self.tmp, "Items.de.xml"))
        self.store = store.Store(lang_dir=self.tmp)
        self.store.refresh()
        self.review = review.Review(path=os.path.join(self.tmp, "reviewed.json"))
        self.unit = next(u for u in self.store.all_units() if u.kind == "attr")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_lifecycle(self):
        u = self.unit
        self.assertEqual(self.review.status(u)[0], "unchecked")

        st, entry = self.review.set_checked(u, True)
        self.assertEqual(st, "checked")
        self.assertEqual(entry["file"], u.file)
        self.assertEqual(entry["key"], u.key)

        # Wert ändern -> Marke degradiert zu stale
        writer.save(self.store, u.uid, u.display_value(),
                    u.display_value() + " (geändert)")
        fresh = self.store.get(u.uid)
        self.assertEqual(self.review.status(fresh)[0], "stale")

        # erneut prüfen -> wieder checked (mit neuem Hash)
        st, _ = self.review.set_checked(fresh, True)
        self.assertEqual(st, "checked")

        # aufheben -> unchecked
        st, entry = self.review.set_checked(fresh, False)
        self.assertEqual(st, "unchecked")
        self.assertIsNone(entry)

    def test_summary_counts(self):
        units = [u for u in self.store.all_units() if u.kind == "attr"][:3]
        for u in units:
            self.review.set_checked(u, True)
        writer.save(self.store, units[0].uid, units[0].display_value(),
                    units[0].display_value() + " (neu)")
        s = self.review.summary(self.store)
        self.assertEqual(s["checked"], 2)
        self.assertEqual(s["stale"], 1)
        self.assertEqual(s["orphaned"], 0)

    def test_file_is_diff_friendly(self):
        self.review.set_checked(self.unit, True)
        with open(self.review.path, encoding="utf-8") as f:
            text = f.read()
        self.assertIn('"file": "Items.de.xml"', text)
        self.assertIn(self.unit.key, text)
        self.assertTrue(text.endswith("\n"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
