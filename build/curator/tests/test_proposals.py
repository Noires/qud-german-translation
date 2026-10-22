"""Vorschlags-Warteschlange, K3-Assistent und Löschen verwaister Einträge.

Schreibende Tests laufen IMMER auf einer Kopie der String-Tabelle.
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import config, proposals, writer  # noqa: E402
from curator.store import Store  # noqa: E402

NAME = "Strings.de.xml"


class TestGate(unittest.TestCase):
    def test_tokens_must_survive(self):
        it = {"old_value": "=subject.T= sieht =object.a.akkusativ=.",
              "new_value": "=subject.T= sieht etwas."}
        self.assertTrue(any("Tokens" in p for p in proposals.gate_problems(it, "du")))

    def test_du_rule_rejects_remaining_ihr(self):
        it = {"old_value": "Ihr habt nicht genug Reputation.", "new_value": "Ihr habt nicht genug Ruf."}
        self.assertTrue(any("Ihr" in p for p in proposals.gate_problems(it, "du")))
        it["new_value"] = "Du hast nicht genug Reputation."
        self.assertEqual(proposals.gate_problems(it, "du"), [])

    def test_k3_allows_one_added_name_token(self):
        it = {"old_value": "=subject.Konjde:scheinen= neu zu sein.",
              "new_value": "=subject.The.name= =subject.konjde:scheinen= neu zu sein."}
        self.assertEqual(proposals.gate_problems(it, "k3"), [])
        it["new_value"] = "=subject.The.name= =object.the.name= =subject.konjde:scheinen= neu."
        self.assertTrue(proposals.gate_problems(it, "k3"))

    def test_fix_ifplural(self):
        key = "Conversation X.Text|=ifplayerplural:Ye have:Thou hast= changed =subject.the.name=."
        it = {"key": key, "old_value": "=ifplayerplural:Ye have:Thou hast= =subject.the.name= verändert.",
              "new_value": "=ifplayerplural:Ihr habt:Du hast= =subject.the.name= verändert."}
        self.assertEqual(proposals.gate_problems(it, "fix-ifplural"), [])
        it["new_value"] = "=ifplayerplural:Ihr habt:Du hast= alles verändert."  # anderes Token weg
        self.assertTrue(proposals.gate_problems(it, "fix-ifplural"))
        it["new_value"] = "=ifplayerplural:Ye have:Du hast= =subject.the.name= verändert."
        self.assertTrue(any("K5" in p for p in proposals.gate_problems(it, "fix-ifplural")))
        # andere Regeln: ein NEUER K5-Befund sperrt ebenfalls
        it2 = {"key": key, "old_value": "Du hast es verändert.",
               "new_value": "=ifplayerplural:ye have:thou hast= es verändert."}
        self.assertTrue(any("K5" in p for p in proposals.gate_problems(it2, None)))

    def test_fix_case(self):
        it = {"old_value": "aus =subject.them= trinken", "new_value": "aus =subject.them:dat= trinken"}
        self.assertEqual(proposals.gate_problems(it, "fix-case"), [])
        it["new_value"] = "aus =subject.it:dat= trinken"
        self.assertTrue(proposals.gate_problems(it, "fix-case"))

    def test_markup_balance(self):
        it = {"old_value": "{{W|Gold}}", "new_value": "{{W|Gold"}
        self.assertIn("{{ }} unausgewogen", proposals.gate_problems(it, None))


class TestQueueOnCopy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "lang"))
        shutil.copy(os.path.join(config.LANG_DE, NAME), os.path.join(self.tmp, "lang", NAME))
        self.store = Store(os.path.join(self.tmp, "lang"))
        self.store.refresh()
        self.q = proposals.Proposals(os.path.join(self.tmp, "proposals"))
        self.path = os.path.join(self.tmp, "lang", NAME)
        # K3-Defekte einbauen (der echte Korpus ist bereinigt)
        defects = {
            "AIWiring - Ignore Conversation Message": "=subject.Konjde:ignorieren= =object.the.name=.",
            "PsychicHunterSystem Sense Presence Message":
                "=subject.Konjde:spüren= =number.pluralize:eine psychische Präsenz:psychische Präsenzen=.",
        }
        for ctx, bad in defects.items():
            u = next(x for x in self.store.all_units() if x.context == ctx)
            writer.save(self.store, u.uid, u.display_value(), bad)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _lines(self):
        with open(self.path, encoding="utf-8") as f:
            return f.read().splitlines()

    def test_k3_batch_accept_writes_one_line(self):
        items = proposals.k3_items(self.store)
        self.assertTrue(items, "K3-Assistent findet nichts — Korpus geändert?")
        self.q.create("k3-test", "k3", items[:3])
        b = self.q.load("k3-test", self.store)
        self.assertTrue(all(i["state"] == "open" for i in b["items"]))
        before = self._lines()
        first = b["items"][0]
        self.q.decide("k3-test", first["uid"], "accept", self.store)
        after = self._lines()
        self.assertEqual(len(before), len(after))
        changed = [i for i, (a, c) in enumerate(zip(before, after)) if a != c]
        self.assertEqual(len(changed), 1)
        self.assertEqual(self.store.get(first["uid"]).display_value(), first["new_value"])
        b = self.q.load("k3-test", self.store)
        self.assertEqual(b["items"][0]["state"], "accepted")
        with self.assertRaises(ValueError):
            self.q.decide("k3-test", first["uid"], "accept", self.store)  # schon angenommen

    def test_stale_when_value_changed_elsewhere(self):
        items = proposals.k3_items(self.store)[:1]
        self.q.create("k3-stale", "k3", items)
        uid = items[0]["uid"]
        u = self.store.get(uid)
        writer.save(self.store, uid, u.display_value(), u.display_value() + " ")
        b = self.q.load("k3-stale", self.store)
        self.assertEqual(b["items"][0]["state"], "stale")
        with self.assertRaises(writer.WriteError):
            self.q.decide("k3-stale", uid, "accept", self.store)

    def test_gate_blocks_accept(self):
        u = next(x for x in self.store.all_units() if "=subject." in x.display_value())
        self.q.create("bad", "du", [{"uid": u.uid, "file": u.file, "key": u.key,
                                      "old_value": u.display_value(), "new_value": "kaputt"}])
        with self.assertRaises(ValueError):
            self.q.decide("bad", u.uid, "accept", self.store)

    def test_delete_string_entry(self):
        u = next(x for x in self.store.all_units() if x.kind == "string" and x.context)
        others = {x.uid: x.display_value() for x in self.store.all_units() if x.uid != u.uid}
        before = self._lines()
        key = writer.delete_string_entry(self.store, u.uid, u.display_value())
        self.assertEqual(key, u.key)
        self.assertEqual(len(self._lines()), len(before) - 1)
        self.assertIsNone(self.store.get(u.uid))
        now = {x.uid: x.display_value() for x in self.store.all_units()}
        self.assertEqual(now, others)


if __name__ == "__main__":
    unittest.main()


class TestJsonWriter(unittest.TestCase):
    """HistorySpice.jsonc: Wert-Splice byte-genau, JSON bleibt gültig (auf einer Kopie)."""

    def test_json_save_on_copy(self):
        import json
        name = "HistorySpice.jsonc"
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(os.path.join(config.LANG_DE, name), os.path.join(d, name))
            st = Store(d)
            st.refresh()
            us = st.files[name].units
            u = next(x for x in us if x.display_value() == "Glas")
            with open(os.path.join(d, name), encoding="utf-8") as f:
                before = f.read()
            tricky = 'Glas "klar" ' + chr(92) + ' ä'  # Anführungszeichen + Backslash + Umlaut
            writer.save(st, u.uid, "Glas", tricky)
            with open(os.path.join(d, name), encoding="utf-8") as f:
                after = f.read()
            json.loads(after)  # weiterhin gültiges JSON
            self.assertEqual(st.get(u.uid).display_value(), tricky)
            diff = [i for i, (a, b) in enumerate(zip(before.splitlines(), after.splitlines())) if a != b]
            self.assertEqual(len(diff), 1)
            # Ausbruchsversuch über Anführungszeichen bleibt ein Wert (escaped)
            writer.save(st, u.uid, tricky, 'x", "y')
            self.assertEqual(len(st.files[name].units), len(us))


class TestCreateItems(unittest.TestCase):
    """Neuanlagen (op=create) über die Warteschlange — auf einer Kopie."""

    def test_create_accept_and_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "lang"))
            shutil.copy(os.path.join(config.LANG_DE, NAME), os.path.join(d, "lang", NAME))
            st = Store(os.path.join(d, "lang"))
            st.refresh()
            q = proposals.Proposals(os.path.join(d, "proposals"))
            item = {"op": "create", "file": NAME, "context": "Testkontext Neuanlage",
                    "id": "=subject.Does:don't= seem to understand you (test).",
                    "new_value": "=subject.The.name= =subject.konjde:scheinen= dich nicht zu verstehen."}
            bad = dict(item, id="Neu: =subject.T= test", new_value="Ihr versteht nichts.")
            q.create("new-test", "new", [item, bad])
            b = q.load("new-test", st)
            states = {i["id"]: i["state"] for i in b["items"]}
            self.assertEqual(states[item["id"]], "open")
            self.assertEqual(states[bad["id"]], "gate")
            path = os.path.join(d, "lang", NAME)
            n0 = len(open(path, encoding="utf-8").read().splitlines())
            uid = next(i["uid"] for i in b["items"] if i["id"] == item["id"])
            q.decide("new-test", uid, "accept", st)
            self.assertEqual(len(open(path, encoding="utf-8").read().splitlines()), n0 + 1)
            b = q.load("new-test", st)
            got = next(i for i in b["items"] if i["id"] == item["id"])
            self.assertEqual(got["state"], "accepted")
            self.assertEqual(st.get(got["created_uid"]).display_value(), item["new_value"])
            buid = next(i["uid"] for i in b["items"] if i["id"] == bad["id"])
            with self.assertRaises(ValueError):
                q.decide("new-test", buid, "accept", st)  # Gate sperrt
