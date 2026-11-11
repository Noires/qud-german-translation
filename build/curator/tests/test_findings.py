"""Phase 4: Playtest-Befunde (Statusfluss, Auto-Regression), Verlauf, Konkordanz."""
import base64
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import findings as fmod, history  # noqa: E402
from curator.store import Store  # noqa: E402

PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()


class TestFindings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = Store()
        cls.store.refresh()
        cls.unit = next(u for u in cls.store.all_units()
                        if (u.context or "").startswith("Conversation Agyra.Start.Text"))

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.f = fmod.Findings(os.path.join(self.d.name, "findings.json"))

    def tearDown(self):
        self.d.cleanup()

    def test_flow_and_screenshot(self):
        e = self.f.create("Thou hast im Gespräch", "Bey Lah", self.unit.uid, PNG)
        self.assertTrue(os.path.exists(os.path.join(self.d.name, e["screenshot"])))
        e = self.f.update(e["id"], self.store, status="verify")
        self.assertTrue(e["fixed_value_sha1"])
        self.assertEqual([h["status"] for h in e["history"]], ["open", "verify"])
        with self.assertRaises(ValueError):
            self.f.update(e["id"], self.store, status="quatsch")
        with self.assertRaises(ValueError):
            self.f.create("x", screenshot="data:image/jpeg;base64,AAAA")

    def test_auto_regress_only_after_fix(self):
        e = self.f.create("Miss", uid=self.unit.uid)
        self.f.update(e["id"], self.store, status="verify")
        fixed_at = self.f.load()[e["id"]]["fixed_at"]
        old_log = {"exists": True, "mtime": fixed_at - 10, "misses": [{"context": self.unit.context}]}
        self.assertEqual(self.f.auto_regress(self.store, old_log), [])
        new_log = dict(old_log, mtime=time.time() + 10)
        self.assertEqual(self.f.auto_regress(self.store, new_log), [e["id"]])
        self.assertEqual(self.f.load()[e["id"]]["status"], "regressed")


class TestHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = Store()
        cls.store.refresh()

    def test_proposal_history_and_git(self):
        u = next(x for x in self.store.all_units() if x.context == "Conversation Agyra.Start.Text")
        h = history.history(self.store, u.uid)
        self.assertTrue(any(p["rule"] == "fix-ifplural" for p in h["proposals"]))
        self.assertTrue(h["git"], "git log -L liefert nichts")

    def test_concordance(self):
        c = history.concordance(self.store, "baetyl")
        self.assertGreater(c["total"], 5)
        self.assertTrue(all("baetyl" in i["english"].lower() for i in c["items"]))
        self.assertEqual(history.concordance(self.store, "x")["total"], 0)


if __name__ == "__main__":
    unittest.main()
