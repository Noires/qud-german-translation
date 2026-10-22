"""Parität der Python-Emulation (grammar_emu) gegen die C#-Vektoren.

Quellen werden LIVE aus VariableReplacers.de.cs geparst ([VariableExample],
[VariableParametrizedExample], SelfTestPipeline-Tabellen) — neue C#-Vektoren
landen also automatisch hier. Rein funktionale Vektoren (Possessiv-Selbsttest)
sind gespiegelt, weil sie Funktionsaufrufe statt Daten sind.
"""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import config, grammar_emu as g  # noqa: E402

with open(config.CODE_CS, encoding="utf-8") as _f:
    CS = _f.read()

# Blueprint -> Stichprobe (wie die Spiel-Objekte der C#-Selbsttests)
BP = {"Croc": "croc", "Glowfish": "glowfish", "Goat": "goat", "Snapjaw": "snapjaw",
      "Torch": "torch"}


def _replacer_blocks():
    """-> [(replacer_names, [(attr_kind, args...)])] für jede Methode."""
    rx = re.compile(r"((?:[ \t]*\[Variable\w+\(.*\)\][ \t]*\r?\n)+)[ \t]*public static string")
    out = []
    for m in rx.finditer(CS):
        block = m.group(1)
        names = re.search(r"\[VariableReplacer\(new string\[\] \{([^}]*)\}", block)
        if not names:
            continue
        nm = re.findall(r'"([^"]*)"', names.group(1))
        ex = re.findall(r'\[VariableExample\("([^"]*)", "([^"]*)"\)\]', block)
        pex = re.findall(r'\[VariableParametrizedExample\("([^"]*)", "([^"]*)", "([^"]*)"\)\]', block)
        out.append((nm, ex, pex))
    return out


class TestVariableExamples(unittest.TestCase):
    def test_examples_exist(self):
        self.assertTrue(any(ex for _, ex, _ in _replacer_blocks()),
                        "keine [VariableExample]-Attribute gefunden — Parser kaputt?")

    def test_variable_examples(self):
        for names, ex, pex in _replacer_blocks():
            for expected, bp in ex:
                low, upper = expected.split(":", 1)
                name = names[0]
                with self.subTest(name=name, bp=bp):
                    ctx = {"object": BP[bp]}
                    self.assertEqual(g.resolve_plain("=object.%s=" % name, ctx), low)
                    capname = name[0].upper() + name[1:]
                    self.assertEqual(g.resolve_plain("=object.%s=" % capname, ctx), upper)
            for param, expected, bp in pex:
                low, upper = expected.split(":", 1)
                name = names[0]
                with self.subTest(name=name, param=param):
                    ctx = {"subject": BP[bp]}
                    self.assertEqual(g.resolve_plain("=subject.%s:%s=" % (name, param), ctx), low)
                    capname = name[0].upper() + name[1:]
                    self.assertEqual(g.resolve_plain("=subject.%s:%s=" % (capname, param), ctx), upper)


class TestSelfTestPipeline(unittest.TestCase):
    def _vectors(self, table):
        m = re.search(r"string\[\]\[\] %s = \{(.*?)\};" % table, CS, re.S)
        self.assertIsNotNone(m, table)
        return re.findall(r'new\[\] \{ "([^"]*)",\s*"([^"]*)",\s*"([^"]*)" \}', m.group(1))

    def test_case_pipeline(self):
        vecs = self._vectors("tests")
        self.assertGreater(len(vecs), 5)
        for bp, tpl, want in vecs:
            with self.subTest(tpl=tpl, bp=bp):
                # C#: VariableReplace(t, other=Snapjaw, o) -> o ist object
                self.assertEqual(g.resolve_plain(tpl, {"object": BP[bp], "subject": "warden"}), want)

    def test_verb_pipeline(self):
        vecs = self._vectors("vtests")
        self.assertGreater(len(vecs), 5)
        for bp, tpl, want in vecs:
            with self.subTest(tpl=tpl):
                self.assertEqual(g.resolve_plain(tpl, {"subject": BP[bp]}), want)


class TestPureFunctions(unittest.TestCase):
    """Spiegel des Possessiv-/Deklinations-Selbsttests (SelfTestPipeline)."""

    def test_possessive(self):
        self.assertEqual(g.german_possessive_suffix("Krokodil"), "Krokodils")
        self.assertEqual(g.german_possessive_suffix("Marx"), "Marx'")
        self.assertEqual(g.german_possessive_suffix("{{M|Resheph}}"), "{{M|Reshephs}}")
        self.assertEqual(g.build_possessive_phrase("rostiger Wischmopp", g.DAT, False, False),
                         "deinem rostigen Wischmopp")
        self.assertEqual(g.build_possessive_phrase("Flammenpistole", g.DAT, False, False),
                         "deiner Flammenpistole")
        self.assertEqual(g.build_possessive_phrase("Biss", g.DAT, False, False, "sein"), "seinem Biss")
        self.assertEqual(g.build_possessive_phrase("rechte Hand", g.DAT, False, False, "ihr"),
                         "ihrer rechten Hand")
        self.assertEqual(g.decline_poss("euer", g.N, g.ACC), "euer")
        self.assertEqual(g.decline_poss("sein", g.F, g.ACC), "seine")
        self.assertEqual(g.decline_poss("ihr", g.P, g.DAT), "ihren")
        self.assertEqual(g.decline_poss("hir", g.M, g.DAT), "hir")

    def test_verbs(self):
        self.assertEqual(g.try_german_verb("see", 1), "seht")
        self.assertEqual(g.try_german_verb("see", 3), "siehst")
        self.assertEqual(g.try_german_verb("Sehen", 3), "siehst")
        self.assertEqual(g.try_german_verb("Sehen", 0), "sieht")
        self.assertIsNone(g.try_german_verb("open", 0))

    def test_declension(self):
        self.assertEqual(g.decline_after_article("Der nass Leuchtfisch"), "Der nasse Leuchtfisch")
        self.assertEqual(g.decline_after_article("ein nass Leuchtfisch"), "ein nasser Leuchtfisch")
        self.assertEqual(g.decline_after_article("das Zahnrad aus der Großen Maschine"),
                         "das Zahnrad aus der Großen Maschine")
        self.assertEqual(g.build_definite_phrase("Phiole mit Wasser", g.NOM, False, False),
                         "die Phiole mit Wasser")
        self.assertEqual(g.build_definite_phrase("Phiole mit Wasser", g.DAT, False, False),
                         "der Phiole mit Wasser")
        self.assertEqual(g.build_definite_phrase("nass Leuchtfisch", g.NOM, False, False),
                         "der nasse Leuchtfisch")
        self.assertEqual(g.decline_after_article("Der {{r|blutig}} Issachari-Raider"),
                         "Der {{r|blutige}} Issachari-Raider")
        self.assertEqual(g.decline_after_article("Der &rblutig Leuchtfisch"), "Der &rblutige Leuchtfisch")

    def test_demonstrative_and_plural(self):
        # Spiegel der C#-SelfTestPipeline-Vektoren (Demonstrativ, PluralWord, GermanPlural)
        self.assertEqual(g.demonstrative(g.M, g.DAT), "diesem")
        self.assertEqual(g.demonstrative(g.F, g.NOM), "diese")
        self.assertEqual(g.plural_word("Klinge"), "Klingen")
        self.assertEqual(g.plural_word("Rüstung"), "Rüstungen")
        self.assertEqual(g.plural_word("Käfer"), "Käfer")
        self.assertEqual(g.plural_word("Museum"), "Museen")
        self.assertEqual(g.german_plural("rostiger Wischmopp"), "rostige Wischmoppe")

    def test_part_case_and_possessive(self):
        self.assertEqual(g.resolve_plain("an =part.poss:dat=", {"part": "right_hand"}), "an deiner rechten Hand")
        self.assertEqual(g.resolve_plain("=part.Dativ=", {"part": "left_leg"}), "Dem linken Bein")
        self.assertEqual(g.resolve_plain("=object.This:dat=", {"object": "glowfish"}), "Diesem")

    def test_body_parts(self):
        self.assertEqual(g.transform_body_part("right hand", 2), "rechte Hand")
        self.assertEqual(g.transform_body_part("left leg", 1), "linkes Bein")
        self.assertEqual(g.transform_body_part("hand", 0), "Hand")


class TestResolver(unittest.TestCase):
    def test_player_second_person(self):
        # Anrede-Richtlinie du (2026-10-22)
        self.assertEqual(g.resolve_plain("=object.dativ=", {"object": "player"}), "dir")
        self.assertEqual(g.resolve_plain("=object.akkusativ=", {"object": "player"}), "dich")
        self.assertEqual(g.resolve_plain("=subject.konjde:sehen=", {"subject": "player"}), "siehst")
        self.assertEqual(g.resolve_plain("=subject.konjde:machen=", {"subject": "player"}), "machst")
        self.assertEqual(g.resolve_plain("=subject.The.name= =subject.konjde:sein= hier.",
                                         {"subject": "player"}), "Du bist hier.")
        self.assertEqual(g.resolve_plain("=subject.Does:see= =object.a.akkusativ=.",
                                         {"subject": "player", "object": "croc"}), "Du siehst ein Krokodil.")
        self.assertEqual(g.resolve_plain("mit =subject.its.item:dat#weapon=",
                                         {"subject": "player", "weapon": "vineblade"}),
                         "mit deiner eisernen Rebenklinge")

    def test_ternary_plural(self):
        # TernaryPlural: Parameter 0 bei Mehrzahl, sonst 1; ifplayerplural fragt den Spieler
        self.assertEqual(g.resolve_plain("=ifplayerplural:Ihr habt:Du hast= es.", {"subject": "croc"}),
                         "Du hast es.")
        self.assertEqual(g.resolve_plain("=ifplayerplural:ihr:du=", {"player": "glowfish_pl"}), "ihr")
        self.assertEqual(g.resolve_plain("=subject.isplural:sind:ist=", {"subject": "glowfish_pl"}), "sind")
        r = g.resolve("=number.isplural:Objekte:Objekt=")
        self.assertEqual((r["tokens"][0]["out"], r["tokens"][0]["how"]), ("Objekte", "approx"))

    def test_objective_dative_and_distal(self):
        self.assertEqual(g.resolve_plain("von =subject.them:dat=", {"subject": "croc"}), "von ihm")
        self.assertEqual(g.resolve_plain("von =subject.them:dat=", {"subject": "glowfish_pl"}), "von ihnen")
        self.assertEqual(g.resolve_plain("mit =subject.them:dat=", {"subject": "player"}), "mit dir")
        self.assertEqual(g.resolve_plain("=subject.them=", {"subject": "player"}), "dich")
        self.assertEqual(g.dative_from_accusative("sie", False), "ihr")
        self.assertEqual(g.dative_from_accusative("xem", False), "xem")  # Neopronomen unverändert
        self.assertEqual(g.resolve_plain("um =object.indicativeDistal:akk= zu laden", {"object": "croc"}),
                         "um dieses zu laden")

    def test_reflexive(self):
        self.assertEqual(g.resolve_plain("=object.dativ=", {"subject": "croc", "object": "croc"}), "sich")

    def test_its_item_and_part(self):
        self.assertEqual(g.resolve_plain("mit =subject.its.item:dat#weapon=",
                                         {"subject": "croc", "weapon": "vineblade"}),
                         "mit seiner eisernen Rebenklinge")
        self.assertEqual(g.resolve_plain("von =subject.its.part:dat#part=",
                                         {"subject": "goat", "part": "right_hand"}),
                         "von ihrer rechten Hand")

    def test_markers_and_unknown(self):
        r = g.resolve("Hallo =totally.unknownThing=, =subject.T=.", {"subject": "croc"})
        self.assertEqual(r["tokens"][0]["how"], "unknown")
        self.assertEqual(r["tokens"][1]["out"], "Das Krokodil")
        self.assertIn(g.TOK_START + "Das Krokodil" + g.TOK_END, r["text"])

    def test_postprocessors(self):
        self.assertEqual(g.resolve_plain("=subject.name|'s=", {"subject": "croc"}), "Krokodils")

    def test_curator_tests_json(self):
        try:
            with open(config.CURATOR_TESTS, encoding="utf-8") as f:
                tests = json.load(f).get("tests", [])
        except OSError:
            self.skipTest("keine CuratorTests.json")
        from curator.store import Store
        store = Store()
        store.refresh()
        for t in tests:
            if not t.get("enabled", True):
                continue
            with self.subTest(id=t["id"]):
                roles = g.build_roles()
                roles["subject"] = g.sample_for_blueprint(t.get("subject") or "Snapjaw", store)
                roles["object"] = g.sample_for_blueprint(t.get("object") or "Snapjaw", store)
                got = g._strip_markers(g.resolve(t["template"], ctx_roles=roles)["text"])
                self.assertEqual(got, t["expected"])


if __name__ == "__main__":
    unittest.main()
