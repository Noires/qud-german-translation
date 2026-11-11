"""Phase-1-Prüfungen: K7 Konsistenz, P1 Parität, Schwere-Übersteuerung je Regel
und das Speicher-Gate für „error“-Regeln (auf Kopien bzw. temporärem Glossar)."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import config, context_lint, lint, writer  # noqa: E402
from curator.glossary import GLOSSARY, Glossary  # noqa: E402
from curator.store import Store  # noqa: E402


class TempGlossary:
    """Leitet das globale GLOSSARY für die Dauer eines Tests auf eine Kopie um."""

    def __enter__(self):
        self.d = tempfile.mkdtemp()
        self.saved = GLOSSARY.path
        path = os.path.join(self.d, "glossary.json")
        if os.path.exists(self.saved):
            shutil.copy(self.saved, path)
        GLOSSARY.path, GLOSSARY._cache = path, None
        return GLOSSARY

    def __exit__(self, *a):
        GLOSSARY.path, GLOSSARY._cache = self.saved, None
        shutil.rmtree(self.d)


class TestParity(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(lint.parity_findings("u", "Costs 5 drams.", "Kostet 5 Dram."), [])
        self.assertEqual(lint.parity_findings("u", "1.5 times", "1,5-mal"), [])
        f = lint.parity_findings("u", "In 901, the villagers", "Im Jahre 979")
        self.assertEqual([x["rule"] for x in f], ["P1"])
        # Zahlen in Tokens/Farbcodes zählen nicht
        self.assertEqual(lint.parity_findings("u", "=amount.pluralize:dram=", "=amount.pluralize:Dram:Dram="), [])

    def test_whitespace_and_brackets(self):
        msgs = [x["message"] for x in lint.parity_findings("u", "clue. ", "Hinweis.")]
        self.assertTrue(any("Ende" in m for m in msgs))
        self.assertTrue(lint.parity_findings("u", "a (b)", "a (b"))
        self.assertEqual(lint.parity_findings("u", "a  b", "a  b"), [])


class TestLevels(unittest.TestCase):
    def test_apply_levels(self):
        fs = [{"uid": "x", "rule": "K7", "severity": "warning", "message": "m"},
              {"uid": "y", "rule": "T3", "severity": "info", "message": "n"}]
        out = lint.apply_levels(fs, {"K7": "error", "T3": "off"})
        self.assertEqual([(f["rule"], f["severity"]) for f in out], [("K7", "error")])
        self.assertEqual(fs[0]["severity"], "warning")  # Original unverändert

    def test_glossary_rules_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            g = Glossary(os.path.join(d, "g.json"))
            g.set_term({"en": "baetyl", "de": "Baetyl", "gender": "n"})
            g.set_rule("k5", "error")
            g.set_ignore_inconsistent("skill")
            self.assertEqual(g.rules(), {"K5": "error"})
            self.assertEqual(g.ignore_inconsistent(), {"skill"})
            self.assertEqual(len(g.terms()), 1)  # Begriffe bleiben erhalten
            g.set_rule("K5", None)
            self.assertEqual(g.rules(), {})
            with self.assertRaises(ValueError):
                g.set_rule("K5", "fatal")


class TestConsistencyAndGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        shutil.copy(os.path.join(config.LANG_DE, "Strings.de.xml"), os.path.join(self.tmp, "Strings.de.xml"))
        self.store = Store(self.tmp)
        self.store.refresh()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _pair(self):
        by_en = {}
        for u in self.store.all_units():
            if u.english and len(u.english) > 12 and "=" not in u.english:
                by_en.setdefault(u.english, []).append(u)
        return next(us for us in by_en.values() if len(us) >= 2
                    and len({x.display_value() for x in us}) == 1)

    def test_k7_finds_and_ignores(self):
        a, b = self._pair()[:2]
        writer.save(self.store, b.uid, b.display_value(), b.display_value() + " (abweichend)")
        with TempGlossary() as g:
            hits = {f["uid"] for f in context_lint._k7(self.store)}
            self.assertTrue({a.uid, b.uid} <= hits)
            g.set_ignore_inconsistent(a.english)
            hits = {f["uid"] for f in context_lint._k7(self.store)}
            self.assertFalse({a.uid, b.uid} & hits)

    def test_error_level_blocks_new_findings_only(self):
        u = next(x for x in self.store.all_units() if x.english and "drams" in x.english
                 and any(ch.isdigit() for ch in x.display_value()) is False)
        bad = u.display_value() + " 42"
        with TempGlossary() as g:
            g.set_rule("P1", "error")
            lint._engine = None
            with self.assertRaises(writer.WriteError):
                writer.save(self.store, u.uid, u.display_value(), bad)
            g.set_rule("P1", None)
            lint._engine = None
            writer.save(self.store, u.uid, u.display_value(), bad)  # Standard: nur warning
        lint._engine = None


if __name__ == "__main__":
    unittest.main()
