"""Szenen-Vorschau: Gesprächsbaum gegen das ▶-Manifest + Szenenaufbau.

Braucht die Spieldateien (Base/Conversations.xml, ExampleLanguage) — fehlen
sie, werden die Tests übersprungen.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import config, convtree, scenes  # noqa: E402
from curator.store import Store  # noqa: E402

MANIFEST = os.path.join(config.CFG["game_example_dir"], "Strings.Conversations.example.xml")
HAVE_GAME = convtree.TREE.available() and os.path.exists(MANIFEST)


@unittest.skipUnless(HAVE_GAME, "Spieldateien nicht gefunden")
class TestConvTree(unittest.TestCase):
    def test_context_ids_match_manifest(self):
        with open(MANIFEST, encoding="utf-8") as f:
            ctx = set(re.findall(r'Context="([^"]*)"', f.read()))
        mine = set(convtree.TREE.all_paths())
        rate = len(ctx & mine) / len(ctx)
        # Rest sind C#-dynamische Knoten (Thah, KithAndKin …) -> ID-Fallback
        self.assertGreater(rate, 0.97, "ID-Vergabe weicht vom Spiel ab: %.3f" % rate)

    def test_node_dedupe_and_choice_ids(self):
        _, n = convtree.TREE.node("Otho", "Start2")
        self.assertIsNotNone(n)
        self.assertEqual([c["id"] for c in n["choices"]], ["EndChoice"])
        _, n = convtree.TREE.node("Otho", "Start")
        self.assertEqual([c["id"] for c in n["choices"]], ["EndChoice", "EndChoice2"])

    def test_text_normalization(self):
        _, n = convtree.TREE.node("Otho", "Signal")
        self.assertTrue(n["texts"][0]["en"].startswith("The signal is a repeat transmission"))
        self.assertIn("\n\nWe've long known", n["texts"][0]["en"])


@unittest.skipUnless(HAVE_GAME, "Spieldateien nicht gefunden")
class TestSceneBuilder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = Store()
        cls.store.refresh()
        cls.b = scenes.SceneBuilder(cls.store)

    def test_otho_path(self):
        sc = self.b.conversation("Otho", "Start5")
        self.assertEqual(sc["npc"]["match"], "context")
        self.assertIn("Signal", sc["npc"]["de"])
        self.assertEqual([c["target"] for c in sc["choices"] if c["origin"] == "node"],
                         ["Signal", "End"])
        sc = self.b.conversation("Otho", "Signal")
        targets = [c["target"] for c in sc["choices"] if c["origin"] == "node"]
        self.assertEqual(targets, ["Baetyl?"])
        nxt = self.b.conversation("Otho", "Baetyl?")
        self.assertTrue(nxt["choices"])

    def test_stale_id_is_reported(self):
        # Spieltext geändert, deutscher Eintrag hat noch die alte ID -> greift nie
        u, match = self.b.lookup("Conversation Otho.Signal.Text", "geänderter englischer Text")
        self.assertEqual(match, "staleid")
        self.assertIsNotNone(u)

    def test_end_tag_and_globals(self):
        sc = self.b.conversation("Otho", "Start")
        end = [c for c in sc["choices"] if c["target"] == "End"]
        self.assertTrue(end and end[0]["tags"], "End-Tag ({{K|[End]}}) fehlt")
        self.assertTrue(any(c["origin"].startswith("global:") for c in sc["choices"]))

    def test_for_unit_focuses_conversation(self):
        u = next(x for x in self.store.all_units()
                 if x.context == "Conversation Otho.Signal.Baetyl?Choice.Text")
        sc = self.b.for_unit(u.uid)
        self.assertEqual(sc["layout"], "conversation")
        self.assertEqual(sc["node"], "Signal")
        self.assertIn(u.uid, [c["uid"] for c in sc["choices"]])

    def test_draft_rerenders(self):
        u = next(x for x in self.store.all_units()
                 if x.context == "Conversation Otho.Signal.Baetyl?Choice.Text")
        sc = self.b.for_unit(u.uid, drafts={u.uid: "Was ist =object.a.nominativ=?"})
        c = next(c for c in sc["choices"] if c["uid"] == u.uid)
        self.assertTrue(c["draft"])
        self.assertEqual(c["render"]["text"].replace("\x01", "").replace("\x02", ""),
                         "Was ist ein Krokodil?")

    def test_list_filters_and_counts(self):
        allc = {c["id"]: c for c in self.b.conversation_list()}
        self.assertIn("Otho", allc)
        o = allc["Otho"]
        self.assertGreaterEqual(o["texts"], o["translated"])
        self.assertGreaterEqual(o["translated"], o["checked"])
        self.assertLessEqual(len(self.b.conversation_list(filt="staleid")), len(allc))
        from curator.tests import fixtures
        import shutil
        d, st = fixtures.defect_copy()
        try:
            b = scenes.SceneBuilder(st)
            self.assertIn("Otho", {c["id"] for c in b.conversation_list(filt="staleid")})
        finally:
            shutil.rmtree(d)

    def test_next_scene_wraps_and_matches(self):
        first = self.b.next_scene("unchecked")
        self.assertIsNotNone(first)
        nxt = self.b.next_scene("unchecked", first["conversation"], first["node"])
        self.assertIsNotNone(nxt)
        self.assertNotEqual((nxt["conversation"], nxt["node"]),
                            (first["conversation"], first["node"]))

    def test_graph_reachability(self):
        g = self.b.graph("Otho")
        ids = {n["id"]: n for n in g["nodes"]}
        self.assertEqual(ids["Start"]["depth"], 0)
        self.assertEqual(ids["Signal"]["depth"], 1)
        self.assertEqual(ids["Baetyl?"]["depth"], 2)
        # Slynth-Knoten sind über geerbte Konversations-Antworten erreichbar
        self.assertIsNotNone(ids["SlynthRequest"]["depth"])
        self.assertTrue(any(e["global"] for e in g["edges"]))

    def test_card_binds_described_object(self):
        u = next(x for x in self.store.all_units() if x.objname == "Croc" and x.attr == "Short")
        sc = self.b.for_unit(u.uid)
        self.assertEqual(sc["layout"], "card")
        self.assertEqual(sc["title"]["de"], "Krokodil")
        self.assertTrue(sc["body"][0]["render"]["text"].startswith("\x01Sein\x02"))


if __name__ == "__main__":
    unittest.main()
