"""Abdeckungs-Messung gegen die ▶-Manifeste (coverage.py).

Sichert die Korrekturen gegen Mess-Artefakte: Container-Text vor Kind-Elementen,
übersetzte Namen von <zone>/<step> (positional), ID-/Command-Anker, leere Marker,
Booleans. Echte Lücken müssen offen bleiben.
"""
import os
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import coverage  # noqa: E402

M = coverage.MARK


def _units(ex_xml, de_xml):
    ex, de = ET.fromstring(ex_xml), ET.fromstring(de_xml)
    pos = coverage.positional_tags(ex)
    exu = coverage.units_example(ex, False, pos)
    deu = coverage.covered_de(de, False, pos)
    return exu, {k for k in exu if k not in deu}


class TestArtefacts(unittest.TestCase):
    def test_container_text_before_children(self):
        exu, missing = _units(
            '<mutations><mutation Name="A"><description>%s\n  <p>You regulate.</p>\n'
            '</description></mutation></mutations>' % M,
            '<mutations><mutation Name="A"><description>\n  <p>Du regulierst.</p>\n'
            '</description></mutation></mutations>')
        self.assertEqual(len(exu), 1)
        self.assertEqual(missing, set())

    def test_empty_marker_is_no_unit(self):
        exu, _ = _units('<mutations><mutation Name="A"><leveltext>%s</leveltext></mutation></mutations>' % M,
                        '<mutations/>')
        self.assertEqual(exu, {})

    def test_zone_with_translated_name_matches_by_position(self):
        exu, missing = _units(
            '<worlds><world Name="W"><cell Name="C"><zone Level="10" x="1" y="1" Name="%sControl pit" '
            'NameContext="%sGolem" ProperName="%strue"/></cell></world></worlds>' % (M, M, M),
            '<worlds><world Name="W"><cell Name="C"><zone Level="10" x="1" y="1" Name="Kontrollgrube" '
            'NameContext="Golem"/></cell></world></worlds>')
        self.assertEqual(len(exu), 1, "ProperName (Boolean) darf keine Einheit sein")
        self.assertEqual(missing, set())

    def test_options_anchor_on_id(self):
        exu, missing = _units(
            '<options><option ID="A" DisplayText="%sShow A"/><option ID="B" DisplayText="%sShow B"/></options>' % (M, M),
            '<options><option ID="A" DisplayText="Zeige A"/></options>')
        self.assertEqual(len(exu), 2)
        self.assertEqual({k[2] for k in missing}, {"B"})


@unittest.skipUnless(coverage.Coverage().available(), "Spiel-Manifeste nicht gefunden")
class TestCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = coverage.Coverage().compute()

    def _missing(self, name):
        return {tuple(m["key"]) for m in self.r["files"][name]["missing"]}

    def test_artefact_files_clean(self):
        for name in ("Worlds", "HiddenMutations", "Quests"):
            self.assertEqual(self._missing(name), set(), name)
        self.assertNotIn(("Adrenal Control", "description", "", "#text"), self._missing("Mutations"))

    def test_positional_list_complete(self):
        """Jeder Tag mit ▶-markiertem Name in einem Manifest steht in POSITIONAL_TAGS."""
        import glob
        from curator import config, xmlscan
        for p in glob.glob(os.path.join(config.CFG["game_example_dir"], "*.example.xml")):
            if os.path.basename(p).startswith("Naming."):
                continue  # Naming fließt nicht in die Abdeckung ein
            root = coverage._parse(p)
            marked = {el.tag for el in root.iter() if (el.get("Name") or "").startswith(coverage.MARK)}
            self.assertLessEqual(marked, set(xmlscan.POSITIONAL_TAGS), os.path.basename(p))

    def test_covkey_parity_with_xmlscan(self):
        """Abdeckungs-Schlüssel == xmlscan.covkey (Geprüft-Statistik, Manifest-Englisch)."""
        from curator.store import Store
        st = Store()
        st.refresh()
        for fn, res in st.files.items():
            if res.root_tag in ("strings", "json"):
                continue
            de = coverage.covered_de(coverage._parse(st.path(fn)), False)
            orphan = [u for u in res.units if tuple(u.covkey) not in de and u.display_value().strip()]
            self.assertEqual(orphan, [], fn)

    def test_snapshot_diff(self):
        import json
        import tempfile
        c = coverage.Coverage()
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "snap.json")
            info = c.save_snapshot(p)
            self.assertTrue(info["build"])
            self.assertEqual(c.diff_snapshot(p)["counts"], {"added": 0, "removed": 0, "changed": 0})
            with open(p, encoding="utf-8") as f:
                snap = json.load(f)
            items = snap["files"]["Items"]
            k1, k2 = sorted(items)[:2]
            del items[k1]                     # im Snapshot fehlend -> „neu"
            items[k2] = items[k2] + " (alt)"  # englischer Text geändert
            snap["files"]["Items"]["[\"Fake\", \"part\", \"X\", \"Y\"]"] = "weg"  # -> „entfernt"
            with open(p, "w", encoding="utf-8") as f:
                json.dump(snap, f)
            self.assertEqual(c.diff_snapshot(p)["counts"], {"added": 1, "removed": 1, "changed": 1})

    def test_closed_blueprint_gaps(self):
        """Die per tools/insert_blueprint.py geschlossenen Lücken bleiben geschlossen
        (offene Lücken prüfen die synthetischen Tests oben)."""
        self.assertNotIn(("Gaslight Chisel", "part", "Gaslight", "ChargedName"), self._missing("Items"))
        for name in ("Items", "Options", "EffectsDetails", "ZoneTerrain"):
            self.assertEqual(self._missing(name), set(), name)


if __name__ == "__main__":
    unittest.main()
