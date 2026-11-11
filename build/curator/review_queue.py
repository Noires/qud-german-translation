"""Prüfrunde: alle Übersetzungen in Sichtbarkeits-Reihenfolge durchgehen.

Bereiche (Buckets) in der Reihenfolge, in der Spieler sie sehen — Start/Optionen,
Joppa & Allgemeines, Hauptquest, Spielmeldungen, übrige Gespräche, Dinge &
Kreaturen, Welt & Lore. Innerhalb eines Bereichs zuerst Einheiten mit offener
Markierung bzw. Prüf-Befunden, dann nach LLM-Triage-Schwere (data/triage.json,
falls vorhanden), dann Gesprächstiefe/Dateireihenfolge.

Stichproben-Modus: je Bereich eine feste Zufallsauswahl (Seed bleibt gleich,
damit der Fortschritt über Sitzungen erhalten bleibt). Fehlerquote =
markiert / (geprüft + markiert) — ohne Befunde in der Stichprobe gilt der
Bereich als vertretbar.
"""
import json
import os
import random
import re

from . import config, convtree
from .flags import FLAGS
from .review import REVIEW, value_hash

TRIAGE_PATH = os.path.join(config.DATA_DIR, "triage.json")
SAMPLE_SEED = "qudde-2026"

START_FILES = {"Options.de.xml", "EmbarkModules.de.xml", "Genotypes.de.xml", "Subtypes.de.xml",
               "TutorialStaging.de.xml", "Manual.de.xml"}
START_CTX = ("Chargen", "Tutorial", "Core", "Saving", "Popup", "MainMenu", "Options", "Tombstone")
JOPPA_CONV = {"Mehmet", "Argyve", "Irudad", "WardenYrame", "Tam", "Nima Ruda", "JoppaFarmer",
              "JoppaFarmerConvert", "BaseConversation", "GenericAskNameOption", "GenericMerchant",
              "GenericTradeOption", "SimpleGeneric", "DefaultTrader"}
MAIN_CONV = {"Otho", "Barathrum", "BarathrumHologram", "Q Girl", "PaxKlanq", "PaxKlanq2", "Mafeo",
             "Neek", "Une", "Asphodel", "AsphodelArrived", "AsphodelChaos", "AsphodelDone",
             "AsphodelWaiting", "Resheph", "ChavvahPrime", "ChavvahFrontChime", "Nuntu", "Euclid",
             "Tszappur", "Shem", "TauChime", "TauCompanion", "TauNoLonger", "TauSoft", "WanderingTau",
             "Gritgate Intercom", "Gritgate Mainframe Intercom", "Sixshrew", "Krka"}
MESSAGE_FILES = {"Strings.de.xml", "InventoryActions.de.xml", "ActivatedAbilities.de.xml",
                 "Skills.de.xml", "Mutations.de.xml", "Statistics.de.xml", "EffectsDetails.de.xml",
                 "Liquids.de.xml", "Strings.appendix.de.xml", "Strings.Extend.de.xml",
                 "TextConstants.de.xml", "Widgets.de.xml"}
THING_FILES = {"Items.de.xml", "Creatures.de.xml", "Furniture.de.xml", "Foods.de.xml", "Walls.de.xml",
               "HiddenObjects.de.xml", "Mods.de.xml", "Relics.de.xml", "HiddenMutations.de.xml",
               "PhysicalPhenomena.de.xml", "SparkingBaetyls.de.xml", "Templates.de.xml"}

BUCKETS = [
    ("start", "Start & Optionen"),
    ("joppa", "Joppa & allgemeine Gespräche"),
    ("main", "Hauptquest-Gespräche"),
    ("messages", "Spielmeldungen & Fähigkeiten"),
    ("conv", "Übrige Gespräche"),
    ("things", "Gegenstände & Kreaturen"),
    ("world", "Welt, Bücher & Lore"),
]
_ORDER = {b: i for i, (b, _) in enumerate(BUCKETS)}
_BOOL = {"true", "false"}


def _conv_id(context):
    m = re.match(r"Conversation ([^.]+)", context or "")
    return m.group(1) if m else None


def bucket_of(u):
    ctx = u.context or ""
    conv = _conv_id(ctx)
    if u.file in START_FILES or (u.file == "Strings.de.xml" and ctx.startswith(START_CTX)):
        return "start"
    if conv:
        if conv in JOPPA_CONV:
            return "joppa"
        if conv in MAIN_CONV:
            return "main"
        return "conv"
    if u.file in MESSAGE_FILES:
        return "messages"
    if u.file in THING_FILES:
        return "things"
    return "world"


_CODE_ATTRS = {"Class", "Part", "Load", "ID", "Command"}  # Klassennamen/Schlüssel, kein Text
_TOKEN = re.compile(r"=[^=\s][^=]*=")


def reviewable(u):
    v = u.display_value()
    if not v or not v.strip() or v.strip().lower() in _BOOL or u.attr in _CODE_ATTRS:
        return False
    # nur Tokens/Satzzeichen ("...", "=spice:…=") -> nichts zu lesen
    return bool(re.search(r"[A-Za-zÄÖÜäöüß]{2,}", _TOKEN.sub(" ", v)))


def load_triage():
    try:
        with open(TRIAGE_PATH, encoding="utf-8") as f:
            return json.load(f).get("triage", {})
    except (OSError, ValueError):
        return {}


def triage_weight(entry, u):
    """MQM-Gewicht des LLM-Urteils — nur gültig, solange der Wert gleich ist."""
    if not entry or entry.get("value_sha1") != value_hash(u.display_value()):
        return 0
    w = {"critical": 25, "major": 5, "minor": 1}
    return min(25, sum(w.get(e.get("severity"), 0) for e in entry.get("errors") or []))


class ReviewQueue:
    def __init__(self, store):
        self.store = store

    def _depths(self):
        out = {}
        if not convtree.TREE.available():
            return out
        for path in convtree.TREE.all_paths():
            # "Conversation X.Node.Choice.Text" -> Tiefe grob über die Pfadlänge
            out[path] = path.count(".")
        return out

    def items(self, lint_uids=None):
        """Alle prüfbaren Einheiten mit Bereich, Status, Sortierschlüssel."""
        flags = FLAGS.load()
        triage = load_triage()
        depths = self._depths()
        lint_uids = lint_uids or set()
        out = []
        for u in self.store.all_units():
            if not reviewable(u):
                continue
            status, _ = REVIEW.status(u)
            fl = flags.get(u.uid)
            flagged = bool(fl) and fl.get("status", "open") == "open"
            tw = triage_weight(triage.get(u.uid), u)
            b = bucket_of(u)
            key = (_ORDER[b], 0 if flagged else 1, 0 if u.uid in lint_uids else 1, -tw,
                   depths.get(u.context or "", 99), u.file, u.line or 0)
            out.append({"uid": u.uid, "bucket": b, "status": status, "flagged": flagged,
                        "lint": u.uid in lint_uids, "triage": tw, "_key": key, "_u": u})
        out.sort(key=lambda x: x["_key"])
        return out

    @staticmethod
    def sample_uids(items, bucket, n):
        pool = sorted(i["uid"] for i in items if i["bucket"] == bucket)
        rnd = random.Random("%s-%s" % (SAMPLE_SEED, bucket))
        return set(rnd.sample(pool, min(n, len(pool))))

    def summary(self, items, n_sample=50):
        out = []
        for b, label in BUCKETS:
            mine = [i for i in items if i["bucket"] == b]
            samp = self.sample_uids(items, b, n_sample)
            s_items = [i for i in mine if i["uid"] in samp]
            s_checked = sum(1 for i in s_items if i["status"] == "checked" and not i["flagged"])
            s_flagged = sum(1 for i in s_items if i["flagged"])
            done = s_checked + s_flagged
            out.append({
                "id": b, "label": label, "total": len(mine),
                "checked": sum(1 for i in mine if i["status"] == "checked"),
                "stale": sum(1 for i in mine if i["status"] == "stale"),
                "flagged": sum(1 for i in mine if i["flagged"]),
                "lint": sum(1 for i in mine if i["lint"]),
                "triaged": sum(1 for i in mine if i["triage"]),
                "sample": {"n": len(s_items), "checked": s_checked, "flagged": s_flagged,
                           "error_rate": round(s_flagged / done, 3) if done else None},
            })
        return out

    def pending(self, items, bucket=None, mode="priority", n_sample=50):
        """Noch zu prüfen: ungeprüft/veraltet oder offen markiert, in Reihenfolge."""
        sel = [i for i in items if bucket in (None, "", i["bucket"])]
        if mode == "sample":
            samp = set()
            for b, _ in BUCKETS:
                if bucket in (None, "", b):
                    samp |= self.sample_uids(items, b, n_sample)
            sel = [i for i in sel if i["uid"] in samp]
        return [i for i in sel if i["status"] != "checked" or i["flagged"]]

    @staticmethod
    def public(i):
        u = i["_u"]
        return {"uid": i["uid"], "bucket": i["bucket"], "status": i["status"],
                "flagged": i["flagged"], "lint": i["lint"], "triage": i["triage"],
                "file": u.file, "context": u.context or u.key, "english": u.english,
                "value": u.display_value()}
