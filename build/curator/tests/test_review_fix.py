"""Phase 3: Span-Gate „review-fix“, Annehmen schließt die Markierung, Triage-Gewicht."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import config, flags as flags_mod, proposals, review_queue as rq  # noqa: E402
from curator.review import value_hash  # noqa: E402
from curator.store import Store  # noqa: E402

NAME = "Strings.de.xml"


class TestSpanGate(unittest.TestCase):
    SP = {"start": 10, "end": 13, "text": "ihn"}

    def test_inside_span_ok(self):
        it = {"old_value": "Du siehst ihn nicht.", "new_value": "Du siehst ihm nicht.", "span": self.SP}
        self.assertEqual(proposals.gate_problems(it, "review-fix"), [])

    def test_outside_span_blocked(self):
        old = "Du siehst ihn nicht, und das ist ein ziemlich langer Satz hier."
        it = {"old_value": old, "new_value": old.replace("hier", "dort").replace("ihn", "ihm"),
              "span": self.SP}
        self.assertTrue(any("markierte Stelle" in p for p in proposals.gate_problems(it, "review-fix")))

    def test_slack_allows_article(self):
        old = "Er gibt den Krokodil das Wasser."
        sp = {"start": 12, "end": 20, "text": "Krokodil"}
        it = {"old_value": old, "new_value": "Er gibt dem Krokodil das Wasser.", "span": sp}
        self.assertEqual(proposals.gate_problems(it, "review-fix"), [])


class TestAcceptClosesFlag(unittest.TestCase):
    def test_accept(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "lang"))
            shutil.copy(os.path.join(config.LANG_DE, NAME), os.path.join(d, "lang", NAME))
            st = Store(os.path.join(d, "lang"))
            st.refresh()
            saved = flags_mod.FLAGS.path
            flags_mod.FLAGS.path = os.path.join(d, "flags.json")
            try:
                u = next(x for x in st.all_units() if x.display_value() == "Du bist gelähmt!")
                v = u.display_value()
                flags_mod.FLAGS.set(u, "Test", span={"start": 3, "end": 7, "text": "bist"},
                                    category="verb")
                q = proposals.Proposals(os.path.join(d, "proposals"))
                q.create("rf", "review-fix", [{"uid": u.uid, "file": u.file, "key": u.key,
                                               "old_value": v, "new_value": "Du wirst gelähmt!",
                                               "span": {"start": 3, "end": 7, "text": "bist"}}])
                q.decide("rf", u.uid, "accept", st)
                self.assertEqual(st.get(u.uid).display_value(), "Du wirst gelähmt!")
                self.assertEqual(flags_mod.FLAGS.load()[u.uid]["status"], "fixed")
            finally:
                flags_mod.FLAGS.path = saved


class TestTriageWeight(unittest.TestCase):
    def test_weight_only_for_current_value(self):
        class U:
            def display_value(self):
                return "Hallo"
        e = {"value_sha1": value_hash("Hallo"),
             "errors": [{"severity": "major"}, {"severity": "minor"}]}
        self.assertEqual(rq.triage_weight(e, U()), 6)
        self.assertEqual(rq.triage_weight(dict(e, value_sha1="x"), U()), 0)
        self.assertEqual(rq.triage_weight({"value_sha1": value_hash("Hallo"),
                                           "errors": [{"severity": "critical"}] * 3}, U()), 25)


if __name__ == "__main__":
    unittest.main()
