"""Kontext-Prüfregeln K1–K4, G1/G2 (context_lint.py).

Fixtures sind die Befunde, die die Szenen-Vorschau zuerst sichtbar gemacht
hat — die Regeln müssen sie korpusweit wiederfinden.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import context_lint as cl, convtree  # noqa: E402
from curator.glossary import Glossary  # noqa: E402
from curator.store import Store  # noqa: E402


class TestHeuristics(unittest.TestCase):
    def test_address_forms(self):
        self.assertEqual(set(cl.address_forms("Kehre zurück, wenn du bereit bist.")), {"du"})
        self.assertEqual(set(cl.address_forms("Leben Sie und trinken Sie.")), {"Sie"})
        self.assertEqual(set(cl.address_forms("Euer Durst ist meiner, mein Wasser ist eures.")), {"Ihr"})
        self.assertEqual(set(cl.address_forms("Ihr habt nicht genug Reputation.")), {"Ihr"})
        # kleines ihr/euch ohne Höflichkeits-Gegenstück = Gruppen-Anrede
        self.assertEqual(set(cl.address_forms("Kommt, ihr habt lange genug gewartet.")), {"ihr"})
        self.assertEqual(set(cl.address_forms("Ihr werdet Kleidung brauchen, um euch zu schützen.")), {"Ihr"})
        # Satzanfang-„Sie" = 3. Person, kein Sie-Form-Beleg
        self.assertEqual(cl.address_forms("Q Girl tüftelt. Sie wird ihre Anweisungen codieren."), {})
        # Tokens zählen nicht
        self.assertEqual(cl.address_forms("=player.subjective= =subject.konjde:sehen="), {})

    def test_choice_context(self):
        self.assertTrue(cl.is_choice_context("Conversation Otho.Signal.Baetyl?Choice.Text"))
        self.assertTrue(cl.is_choice_context("Conversation Otho.Start.EndChoice2.Text"))
        self.assertFalse(cl.is_choice_context("Conversation Otho.Signal.Text"))

    def test_konjde_without_subject(self):
        self.assertEqual(cl.konjde_without_subject(
            "=subject.Does:ignore= =object.the.name=.",
            "=subject.Konjde:ignorieren= =object.the.name=."), ["subject"])
        self.assertEqual(cl.konjde_without_subject(
            "=subject.Does:ignore= =object.the.name=.",
            "=subject.The.name= =subject.konjde:ignorieren= =object.akkusativ=."), [])
        self.assertEqual(cl.konjde_without_subject(
            "=subject.Does:ignore= it.", "=subject.Does:ignorieren= es."), [])

    def test_unannotated_possessive(self):
        self.assertEqual(cl.unannotated_possessive(
            "=pronouns.Possessive= ergraute, rissige Schuppen"),
            [("=pronouns.Possessive=", "ergraute")])
        self.assertEqual(cl.unannotated_possessive("=subject.its:akk:f= Energiezelle"), [])
        self.assertEqual(cl.unannotated_possessive("Das ist =subject.its=."), [])

    def test_untranslated_token_args(self):
        en = "=ifplayerplural:Ye have:Thou hast= changed the world."
        self.assertTrue(cl.untranslated_token_args(en, "=ifplayerplural:Ye have:Thou hast= die Welt verändert."))
        self.assertEqual(cl.untranslated_token_args(en, "=ifplayerplural:Ihr habt:Du hast= die Welt verändert."), [])
        self.assertIn("doppelt", cl.untranslated_token_args(en, "=ifplayerplural:ihr:du= du hast")[0])
        # identische Argumente wie in der Vorlage = unübersetzt, auch ohne Archaismus
        self.assertTrue(cl.untranslated_token_args("They =faction.ifPlural:despise:despises= you.",
                                                   "Sie =faction.ifPlural:despise:despises= dich."))

    def test_object_pronoun_without_dative(self):
        self.assertEqual(cl.object_pronoun_without_dative("aus =subject.them= trinken"),
                         [("aus", "=subject.them=")])
        self.assertEqual(cl.object_pronoun_without_dative("aus =subject.them:dat= trinken"), [])
        self.assertTrue(cl.object_pronoun_without_dative("=head.isPlural:helfen:hilft= =subject.them="))
        self.assertEqual(cl.object_pronoun_without_dative("für =subject.them="), [])

    def test_ihr_seid_is_polite(self):
        self.assertIn("Ihr", cl.address_forms("Ihr seid gelähmt!"))

    def test_article_mismatch(self):
        term = {"en": "baetyl", "de": "Baetyl", "gender": "n"}
        self.assertEqual(cl.article_mismatches("das Baetyl leuchtet", term), [])
        self.assertTrue(cl.article_mismatches("eines voll funktionierenden Baetyl in", term))
        self.assertEqual(cl.article_mismatches("eines voll funktionierenden Baetyls in", term), [])
        self.assertTrue(cl.article_mismatches("die Baetyl leuchtet", term))

    def test_term_missing(self):
        term = {"en": "baetyl", "de": "Baetyl", "plural": "Baetyle", "gender": "n",
                "variants_forbidden": ["Bätyl"]}
        self.assertIsNone(cl.term_missing("What is a baetyl?", "Was ist ein Baetyl?", term))
        self.assertIn("fehlt", cl.term_missing("What is a baetyl?", "Was ist ein Stein?", term))
        self.assertIn("verbotene", cl.term_missing("a baetyl", "ein Bätyl", term))
        self.assertIsNone(cl.term_missing("No term here.", "Kein Begriff.", term))


class TestGlossaryFile(unittest.TestCase):
    def test_roundtrip_and_validation(self):
        with tempfile.TemporaryDirectory() as d:
            g = Glossary(os.path.join(d, "glossary.json"))
            self.assertEqual(g.policy()["player_address"], "Ihr")
            g.set_term({"en": "baetyl", "de": "Baetyl", "gender": "n"})
            g.set_term({"en": "Baetyl", "de": "Baetyl", "gender": "n", "plural": "Baetyle"})
            self.assertEqual(len(g.terms()), 1)  # en case-insensitiv eindeutig
            self.assertEqual(g.terms()[0]["plural"], "Baetyle")
            with self.assertRaises(ValueError):
                g.set_term({"en": "x", "de": "y", "gender": "q"})
            with self.assertRaises(ValueError):
                g.set_policy({"player_address": "Euch"})
            g.set_policy({"choice_address": "du"})
            self.assertEqual(g.policy()["choice_address"], "du")
            g.delete_term("BAETYL")
            self.assertEqual(g.terms(), [])


@unittest.skipUnless(convtree.TREE.available(), "Spieldateien nicht gefunden")
class TestCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = Store()
        cls.store.refresh()
        cls.findings = cl.findings(cls.store)
        cls.by_ctx = {}
        for f in cls.findings:
            u = cls.store.get(f["uid"])
            cls.by_ctx.setdefault((u.context or u.objname, f["rule"]), []).append(f)

    def test_k4_croc_description(self):
        self.assertIn(("Croc", "K4"), self.by_ctx)


@unittest.skipUnless(convtree.TREE.available(), "Spieldateien nicht gefunden")
class TestInjectedDefects(unittest.TestCase):
    """Die Regeln finden die typischen Defekte (eingebaut in eine Kopie)."""

    @classmethod
    def setUpClass(cls):
        from curator.tests import fixtures
        cls.fx = fixtures
        cls.tmp, cls.store = fixtures.defect_copy()
        cls.by_ctx = {}
        for f in cl.findings(cls.store):
            u = cls.store.get(f["uid"])
            cls.by_ctx.setdefault((u.context or u.objname, f["rule"]), []).append(f)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp)

    def test_k1_stale(self):
        self.assertIn((self.fx.K1_CONTEXT, "K1"), self.by_ctx)

    def test_k2_address_policy(self):
        self.assertIn((self.fx.K2_CONTEXT, "K2"), self.by_ctx)

    def test_k3_konjde_without_subject(self):
        self.assertIn((self.fx.K3_CONTEXT, "K3"), self.by_ctx)

    def test_k5_english_token_args(self):
        self.assertIn((self.fx.K5_CONTEXT, "K5"), self.by_ctx)

    def test_k1_rekey(self):
        """Neuanlage mit aktueller ID: genau eine neue Zeile, danach kein K1 mehr."""
        st = self.store
        old = next(u for u in st.all_units() if u.context == self.fx.K1_CONTEXT)
        path = st.path(old.file)
        before = open(path, encoding="utf-8").read().splitlines()
        new, o = cl.rekey(st, old.uid)
        after = open(path, encoding="utf-8").read().splitlines()
        self.assertEqual(len(after), len(before) + 1)
        self.assertEqual(new.context, old.context)
        self.assertEqual(new.display_value(), old.display_value())
        self.assertIn("=V0tinkeraddendum=", new.english)
        st.refresh()
        from curator.scenes import SceneBuilder
        u, match = SceneBuilder(st).lookup(old.context, new.english)
        self.assertEqual((u.uid, match), (new.uid, "context"))
        with self.assertRaises(ValueError):
            cl.rekey(st, new.uid)  # aktuelle ID -> nichts zu tun


@unittest.skipUnless(convtree.TREE.available(), "Spieldateien nicht gefunden")
class TestCorpusClean(TestCorpus):
    """Regression: der bereinigte Korpus bleibt sauber."""

    def test_corpus_has_no_stale_ids_or_k3(self):
        rules = [k[1] for k in self.by_ctx]
        self.assertNotIn("K1", rules)
        self.assertNotIn("K5", rules)
        self.assertNotIn("K6", rules)

    def test_no_error_severity(self):
        self.assertFalse([f for f in self.findings if f["severity"] == "error"])


if __name__ == "__main__":
    unittest.main()
