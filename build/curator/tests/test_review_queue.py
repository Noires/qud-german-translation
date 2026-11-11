"""Prüfrunde: Bereiche, Reihenfolge, Stichprobe; Markierungen mit Fehlerstelle."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import flags as flags_mod, review as review_mod, review_queue as rq  # noqa: E402
from curator.store import Store  # noqa: E402
from curator.xmlscan import Unit  # noqa: E402


def unit(**kw):
    base = dict(uid="u1", file="Strings.de.xml", kind="string", key="k", context="",
                english="Hello there", value="Hallo du", attr="Value")
    base.update(kw)
    return Unit(**base)


class TestBuckets(unittest.TestCase):
    def test_bucket_of(self):
        self.assertEqual(rq.bucket_of(unit(context="Chargen Pick Genotype")), "start")
        self.assertEqual(rq.bucket_of(unit(file="Strings.Conversations.de.xml",
                                           context="Conversation Mehmet.Start.Text")), "joppa")
        self.assertEqual(rq.bucket_of(unit(file="Strings.Conversations.de.xml",
                                           context="Conversation Otho.Signal.Text")), "main")
        self.assertEqual(rq.bucket_of(unit(file="Strings.Conversations.de.xml",
                                           context="Conversation Doyoba.Start.Text")), "conv")
        self.assertEqual(rq.bucket_of(unit(context="Stomach TooFamishedToTravel")), "messages")
        self.assertEqual(rq.bucket_of(unit(file="Items.de.xml", context=None)), "things")
        self.assertEqual(rq.bucket_of(unit(file="Books.de.xml", context=None)), "world")

    def test_reviewable(self):
        self.assertTrue(rq.reviewable(unit()))
        self.assertFalse(rq.reviewable(unit(value="...")))
        self.assertFalse(rq.reviewable(unit(value="=spice:history.x=")))
        self.assertFalse(rq.reviewable(unit(value="true", attr="Hidden")))
        self.assertFalse(rq.reviewable(unit(value="XRL.Foo.Bar", attr="Class")))


class TestQueueOnCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = Store()
        cls.store.refresh()

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.saved = (review_mod.REVIEW.path, flags_mod.FLAGS.path)
        review_mod.REVIEW.path = os.path.join(self.d, "reviewed.json")
        review_mod.REVIEW._cache = None
        flags_mod.FLAGS.path = os.path.join(self.d, "flags.json")

    def tearDown(self):
        review_mod.REVIEW.path, flags_mod.FLAGS.path = self.saved
        review_mod.REVIEW._cache = None
        import shutil
        shutil.rmtree(self.d)

    def test_order_flag_and_lint_first(self):
        q = rq.ReviewQueue(self.store)
        items = q.items()
        joppa = [i for i in items if i["bucket"] == "joppa"]
        last = joppa[-1]["_u"]
        flags_mod.FLAGS.set(last, "Test", category="stil")
        lint_uid = joppa[-2]["uid"]
        items = q.items({lint_uid})
        joppa = [i["uid"] for i in items if i["bucket"] == "joppa"]
        self.assertEqual(joppa[:2], [last.uid, lint_uid])
        # Bereiche in Sichtbarkeits-Reihenfolge
        order = [i["bucket"] for i in items]
        self.assertEqual(order, sorted(order, key=lambda b: rq._ORDER[b]))

    def test_sample_is_stable_and_progress_counts(self):
        q = rq.ReviewQueue(self.store)
        items = q.items()
        s1 = q.sample_uids(items, "joppa", 20)
        self.assertEqual(s1, q.sample_uids(q.items(), "joppa", 20))
        pend = q.pending(items, "joppa", "sample", 20)
        self.assertEqual(len(pend), 20)
        a, b = pend[0]["_u"], pend[1]["_u"]
        review_mod.REVIEW.set_checked(a, True)
        flags_mod.FLAGS.set(b, "falsch", category="kasus-genus")
        summ = {s["id"]: s for s in q.summary(q.items(), 20)}["joppa"]["sample"]
        self.assertEqual((summ["checked"], summ["flagged"], summ["error_rate"]), (1, 1, 0.5))
        self.assertEqual(len(q.pending(q.items(), "joppa", "sample", 20)), 19)  # b bleibt (markiert)


class TestFlagSpan(unittest.TestCase):
    def test_span_and_category_validation(self):
        with tempfile.TemporaryDirectory() as d:
            f = flags_mod.Flags(os.path.join(d, "flags.json"))
            u = unit(value="Du siehst ihn nicht.")
            e = f.set(u, "Dativ?", span={"start": 10, "end": 13, "text": "ihn"}, category="kasus-genus")
            self.assertEqual(e["span"], {"start": 10, "end": 13, "text": "ihn"})
            with self.assertRaises(ValueError):
                f.set(u, "", span={"start": 10, "end": 13, "text": "ihm"})  # Text passt nicht
            with self.assertRaises(ValueError):
                f.set(u, "", span={"start": 5, "end": 99})
            with self.assertRaises(ValueError):
                f.set(u, "", category="quatsch")


if __name__ == "__main__":
    unittest.main()
