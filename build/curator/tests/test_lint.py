"""Lint-Baseline über den echten Korpus (Regressions-Schnappschuss 2026-07-18).

Der Korpus ist vertragskonform: 0 error-Befunde (B1 Boolean, X1 Entity,
X2 Schema-Platzierung, N1-error). Warn-/Info-Befunde existieren (echte
Delimiter-Defekte + Ermessensfälle) und dürfen durch Kuratieren sinken,
aber nicht neu auf error springen.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import lint, store, tokens  # noqa: E402


class TestLintBaseline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = store.Store()
        cls.store.refresh()
        cls.engine = lint.LintEngine(cls.store)
        cls.findings = cls.engine.all_findings()

    def test_no_errors_in_corpus(self):
        errors = [f for f in self.findings if f["severity"] == "error"]
        units = {u.uid: u for u in self.store.all_units()}
        msg = "\n".join("%s %s: %s" % (
            f["rule"],
            "%s:%s" % (units[f["uid"]].file, units[f["uid"]].line)
            if f.get("uid") in units else "?",
            f["message"]) for f in errors[:20])
        self.assertEqual(len(errors), 0,
                         "Korpus hat error-Befunde (Kontraktverletzung?):\n" + msg)

    def test_engine_finds_known_defects(self):
        """Die bekannten '=. ='-Defekte (Strings.de.xml ~3181) müssen gefunden
        werden — beweist, dass T1 nicht leerläuft."""
        t1 = [f for f in self.findings if f["rule"] == "T1"]
        self.assertTrue(any("=. =" in f["message"] for f in t1),
                        "bekannter =. =-Defekt nicht gefunden")

    def test_finding_volume_sane(self):
        # nur Token-/Kontrakt-Regeln; K*/G* (context_lint) sind korpusweite
        # Inhaltsbefunde mit eigener Größenordnung (test_context_lint.py)
        core = [f for f in self.findings if f["rule"][0] in "TBNX"]
        self.assertLess(len(core), 200,
                        "Befund-Flut deutet auf kaputte Regel hin")


class TestTokenRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = tokens.Registry()
        self.reg.add_corpus(["=subject.the.name= sees =object.a.name=."])

    def test_cs_parse_found_replacers(self):
        self.assertGreaterEqual(len(self.reg.cs_names), 25,
                                "zu wenige [VariableReplacer]-Namen geparst")
        self.assertIn("konjde", self.reg.cs_names)
        self.assertIn("a.genitiv", self.reg.cs_names)

    def test_known_variants(self):
        self.assertTrue(self.reg.known("subject.konjde:sehen"))
        self.assertTrue(self.reg.known("object.dativ"))
        self.assertTrue(self.reg.known("Konjde:machen"))       # Kapitalisierung
        self.assertTrue(self.reg.known("pronouns.subjective"))  # Prefix
        self.assertTrue(self.reg.known("commandKey:CmdGet"))    # Prefix mit ':'
        self.assertTrue(self.reg.known("the.name"))             # aus Korpus
        self.assertFalse(self.reg.known("voelligUnbekannt"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
