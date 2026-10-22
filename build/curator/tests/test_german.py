"""Paritätstests der Python-Ports gegen die C#-Selbsttest-Vektoren.

Vektoren aus VariableReplacers.de.cs (SelfTestCases/SelfTestPipeline) und
den dokumentierten Beispielen in docs/GRAMMAR_ENGINE.md.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import german  # noqa: E402


class TestWeakConjugate(unittest.TestCase):
    def test_regular(self):
        self.assertEqual(german.weak_conjugate("machen", 0), "macht")
        self.assertEqual(german.weak_conjugate("machen", 1), "macht")
        self.assertEqual(german.weak_conjugate("machen", 2), "machen")

    def test_dental_stem(self):
        self.assertEqual(german.weak_conjugate("waten", 0), "watet")
        self.assertEqual(german.weak_conjugate("landen", 0), "landet")

    def test_n_only_infinitive(self):
        self.assertEqual(german.weak_conjugate("lockern", 0), "lockert")

    def test_du_form(self):
        # Spiegel der C#-Selbsttest-Vektoren (SelfTestPipeline, Anrede du)
        self.assertEqual(german.weak_conjugate("machen", 3), "machst")
        self.assertEqual(german.weak_conjugate("waten", 3), "watest")
        self.assertEqual(german.weak_conjugate("reisen", 3), "reist")
        self.assertEqual(german.derive_s2("hält", "halten"), "hältst")
        self.assertEqual(german.derive_s2("lädt", "laden"), "lädst")
        self.assertEqual(german.derive_s2("lässt", "lassen"), "lässt")
        self.assertEqual(german.derive_s2("löst", "lösen"), "löst")
        self.assertEqual(german.derive_s2("zerbirst", "zerbersten"), "zerbirst")
        self.assertEqual(german.derive_s2("sieht", "sehen"), "siehst")

    def test_strong_verb_would_be_wrong_weakly(self):
        # beweist, warum "sehen" einen Verbs.json-Eintrag braucht
        self.assertEqual(german.weak_conjugate("sehen", 0), "seht")  # richtig: sieht


class TestGender(unittest.TestCase):
    def setUp(self):
        self.lex = german.load_lexicon()

    def test_exact_hits(self):
        self.assertEqual(german.guess_gender("Wand", self.lex)[0], "f")
        self.assertEqual(german.guess_gender("Käfer", self.lex)[0], "m")
        self.assertEqual(german.guess_gender("Schwert", self.lex)[0], "n")

    def test_suffix_inheritance(self):
        g, src = german.guess_gender("Langschwert", self.lex)
        self.assertEqual(g, "n")
        self.assertTrue(src.startswith("suffix:"))
        g, src = german.guess_gender("Werkbank", self.lex)
        self.assertEqual(g, "f", "werkbank muss von bank erben (bank->f)")

    def test_color_markup_stripped(self):
        self.assertEqual(german.guess_gender("{{r|blutiger}} Käfer", self.lex)[0], "m")

    def test_ending_heuristics(self):
        lex = {}
        self.assertEqual(german.guess_gender("Erfindung", lex)[0], "f")
        self.assertEqual(german.guess_gender("Mädchen", lex)[0], "n")
        self.assertEqual(german.guess_gender("Frühling", lex)[0], "m")
        self.assertEqual(german.guess_gender("Lampe", lex)[0], "f")

    def test_default_masc(self):
        self.assertEqual(german.guess_gender("Xyzzy", {})[0], "m")


class TestSeparable(unittest.TestCase):
    def test_separable(self):
        self.assertEqual(german.separable_prefix("angreifen"), ("an", False))
        self.assertEqual(german.separable_prefix("aufheben"), ("auf", False))

    def test_ambiguous(self):
        self.assertEqual(german.separable_prefix("umgeben"), ("um", True))

    def test_clean(self):
        self.assertEqual(german.separable_prefix("sehen"), (None, False))
        # "ansehen" wäre trennbar, aber "anen"-artige Kurzwörter nicht false-positiven:
        self.assertEqual(german.separable_prefix("anka"), (None, False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
