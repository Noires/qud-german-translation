"""Plausibilitätsregeln (plausi.py): jede Regel muss den Defekt finden, für den
sie gebaut wurde (Fälle aus dem Spieler-Feedback 2026-11-11), und der echte
Korpus muss frei von error-Befunden sein."""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import plausi, store  # noqa: E402
from curator.xmlscan import Unit  # noqa: E402


def unit(**kw):
    base = dict(uid="u", file="Items.de.xml", kind="attr", key="", context=None,
                english=None, value="", objname=None, elem=None, attr=None)
    base.update(kw)
    return Unit(**base)


def rules(findings):
    return sorted(f["rule"] for f in findings)


class TestHelpers(unittest.TestCase):
    def test_plain_nested(self):
        self.assertEqual(plausi.plain("{{K|makellose {{crysteel|Kristallstahl}}-Stiefel}}"),
                         "makellose Kristallstahl-Stiefel")

    def test_repeated_words(self):
        self.assertEqual(plausi.repeated_words("{{Y|Stahlstulpen}} Stahlstulpen"), "stahlstulpen")
        self.assertEqual(plausi.repeated_words(
            "Makellose Aigis {{crysteel|Makellose Aigis}} Makellose Aigis"), "makellose aigis")
        self.assertIsNone(plausi.repeated_words("{{K|Fullerit}}-Dolch"))

    def test_glued_suffix(self):
        self.assertTrue(plausi.glued_suffix_dup("{{c|Chrommantel}}mantel"))
        self.assertTrue(plausi.glued_suffix_dup("{{plastifer|Plastifer-Wams}}Wams"))
        self.assertIsNone(plausi.glued_suffix_dup("{{c|Chrom}}mantel"))
        self.assertIsNone(plausi.glued_suffix_dup("{{Y|Stahl}}helm"))


class TestUnitRules(unittest.TestCase):
    def test_h1_hotkey_ein(self):
        u = unit(file="InventoryActions.de.xml", kind="text", elem="key", attr="#text",
                 key="/inventoryActions#0/inventoryAction[Eat]/key", value="ein")
        self.assertEqual(rules(plausi.unit_findings(u)), ["H1"])

    def test_h2_tutorial_display_capitalized(self):
        u = unit(file="InventoryActions.de.xml", kind="text", elem="display", attr="#text",
                 key="/inventoryActions#0/inventoryAction[CommandAutoEquipObject]/display",
                 value="Ausrüsten (auto)")
        self.assertEqual(rules(plausi.unit_findings(u)), ["H2"])
        u.value = "ausrüsten (auto)"
        self.assertEqual(plausi.unit_findings(u), [])

    def test_h2_other_actions_free(self):
        u = unit(file="InventoryActions.de.xml", kind="text", elem="display", attr="#text",
                 key="/inventoryActions#0/inventoryAction[Chat]/display", value="Gespräch")
        self.assertEqual(plausi.unit_findings(u), [])

    def test_d_rules_on_names(self):
        names = {"Dagger7": "{{K|flawless {{crysteel|crysteel}} dagger}}",
                 "Crysteel Boots": "{{K|{{crysteel|crysteel}} boots}}"}
        orig = plausi.base_display_names
        plausi.base_display_names = lambda: names
        try:
            u = unit(attr="DisplayName", objname="Dagger7", value="{{K|{{crysteel|Dolch VII}}}}")
            self.assertEqual(rules(plausi.unit_findings(u)), ["D2"])
            u = unit(attr="DisplayName", objname="Crysteel Boots",
                     value="{{K|{{crysteel|Crysteel Stiefel}}}}")
            self.assertEqual(rules(plausi.unit_findings(u)), ["D3"])
            u = unit(attr="DisplayName", objname="Crysteel Boots",
                     value="{{K|{{crysteel|Kristallstahl}}-Stiefel}}")
            self.assertEqual(plausi.unit_findings(u), [])
        finally:
            plausi.base_display_names = orig


class _Res:
    def __init__(self, text):
        self.text = text
        self.digest = str(hash(text))


class _FakeStore:
    def __init__(self, files, units=()):
        self.files = files
        self._units = list(units)

    def all_units(self):
        return self._units


class TestCorpusRules(unittest.TestCase):
    def test_l1_reward_without_merge(self):
        st = _FakeStore({"SparkingBaetyls.de.xml": _Res(
            '<sparkingbaetyls><rewards>'
            '<reward Name="Armor" Description="X" />'
            '<reward Name="MeleeWeapon" Load="Merge" Description="Y" />'
            '</rewards></sparkingbaetyls>')})
        fs = plausi._loader_rules(st)
        self.assertEqual(len(fs), 1)
        self.assertEqual(fs[0]["rule"], "L1")
        self.assertIn("Armor", fs[0]["message"])

    def test_s_rules(self):
        man = {"Ctx A": {"new text"}, "Ctx B": {"b"}, None: {"free"}}
        orig = plausi.manifest_strings
        plausi.manifest_strings = lambda: man
        try:
            us = [unit(uid="1", file="Strings.de.xml", kind="string", context="Ctx A", english="old text"),
                  unit(uid="2", file="Strings.de.xml", kind="string", context="", english="b"),
                  unit(uid="3", file="Strings.de.xml", kind="string", context="", english="free")]
            fs = plausi._strings_rules(_FakeStore({}, us))
            got = sorted((f["rule"], f["uid"]) for f in fs)
            # 1: veraltet (neue Fassung fehlt) / 2: kontextlos, Spiel fragt nur „Ctx B“ /
            # S3: „new text“ und „Ctx B|b“ fehlen
            self.assertEqual(got, [("S1", "1"), ("S2", "2"), ("S3", None), ("S3", None)])
        finally:
            plausi.manifest_strings = orig


class TestCorpusBaseline(unittest.TestCase):
    def test_no_errors_in_corpus(self):
        s = store.Store()
        s.refresh()
        errors = [f for f in plausi.findings(s) if f["severity"] == "error"]
        self.assertEqual(errors, [], "\n".join(f["message"] for f in errors[:20]))


if __name__ == "__main__":
    unittest.main()
