"""Englischer Gesprächsbaum aus dem Spiel (Base/Conversations.xml +
HiddenConversations.xml) für die Szenen-Vorschau.

Liefert Knoten mit ihren Antworten in Spielreihenfolge, Ziel-Knoten
(GotoID/Target), Bedingungen und allen <text>-Varianten — und für jeden
Text den Context-Pfad, unter dem das Spiel ihn in der String-Tabelle
nachschlägt ("Conversation Otho.Start2.EndChoice.Text"). Die ID-Vergabe
(Duplikat-Zähler, "<Ziel>Choice", "Text2"…) ist dem Spiel nachgebaut und
wird in tests/test_scenes.py gegen das ▶-Manifest geprüft.

Nur lesend; die deutschen Werte kommen weiter ausschließlich aus dem Store.
"""
import os
import re
import threading
import xml.etree.ElementTree as ET

from . import config

COND_PREFIXES = ("If", "Unless")
_lock = threading.Lock()


def base_dir():
    cfg = config.CFG
    if cfg.get("game_base_dir"):
        return cfg["game_base_dir"]
    return os.path.dirname(cfg["game_example_dir"].rstrip("/\\"))


def normalize_text(s):
    """Wie das Spiel: Einrückung je Zeile weg, Absätze erhalten — Leerzeichen am
    ZEILENENDE bleiben (das Spiel behält sie: „I... \\n\\nNo matter“). Gegen das
    ▶-Manifest geprüft: lstrip trifft 4494/4501, strip nur 4488 (Rest = echte Textänderungen)."""
    if s is None:
        return ""
    lines = [ln.lstrip() for ln in s.replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()


def conditions(el):
    return {k: v for k, v in el.attrib.items() if k.startswith(COND_PREFIXES)}


class Counter:
    """ID-Vergabe mit Duplikat-Zähler: X, X2, X3 …"""

    def __init__(self):
        self.seen = {}

    def take(self, base):
        n = self.seen.get(base, 0) + 1
        self.seen[base] = n
        return base if n == 1 else "%s%d" % (base, n)


def _texts(el, path, ctr=None):
    """<text>-Kinder eines Elements -> [{en, path, cond}] (Gruppen flach)."""
    out = []
    ctr = ctr or Counter()
    for t in el.findall("text"):
        kids = t.findall("text")
        if kids:
            # Gruppen-<text>: an erster Stelle "Text", danach ohne ID (Spiel-Verhalten,
            # z. B. "AmoebaFarmer.Start.Text.Text2" vs. "WaterRitualChoice..Text2")
            gid = t.get("ID") or ("" if ctr.seen else ctr.take("Text"))
            sub = path + "." + gid
            for v in _texts(t, sub, Counter()):
                v["cond"] = {**conditions(t), **v["cond"]}
                out.append(v)
            continue
        tid = ctr.take(t.get("ID") or "Text")
        raw = "".join(t.itertext())
        out.append({"en": normalize_text(raw), "path": path + "." + tid,
                    "cond": conditions(t)})
    # Element ohne <text>: der Elementtext ist der Text
    if not out and el.tag in ("choice", "node", "start"):
        raw = (el.text or "").strip()
        if raw:
            out.append({"en": normalize_text(raw), "path": path + ".Text", "cond": {}})
    return out


def _parts(el, path):
    out = []
    for p in el.findall("part"):
        txt = normalize_text("".join(p.itertext()))
        if txt:
            out.append({"name": p.get("Name"), "en": txt, "path": path + "." + (p.get("Name") or "")})
    return out


def _choice(el, node_path, ctr):
    target = el.get("GotoID") or el.get("Target")
    cid = el.get("ID") or ctr.take((target or "") + "Choice")
    path = node_path + "." + cid
    return {
        "id": cid,
        "target": target,
        "ordinal": _int(el.get("Ordinal")),
        "cond": conditions(el),
        "texts": _texts(el, path),
        "parts": _parts(el, path),
    }


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _parse_conversation(el, source):
    cid = el.get("ID") or el.get("Name") or "?"
    root = "Conversation " + cid
    nodes, globals_ = [], []
    nctr = Counter()
    for child in el:
        if child.tag in ("node", "start"):
            nid = nctr.take(child.get("ID") or "")
            path = root + "." + nid
            cctr = Counter()
            nodes.append({
                "id": nid, "raw_id": child.get("ID"), "start": child.tag == "start",
                "inherits": child.get("Inherits"),
                "cond": conditions(child),
                "texts": _texts(child, path),
                "choices": [_choice(c, path, cctr) for c in child.findall("choice")],
                "parts": _parts(child, path),
            })
        elif child.tag == "choice":
            globals_.append(_choice(child, root, Counter()))
    inherits = el.get("Inherits")
    if inherits is None:
        inherits = "" if cid == "BaseConversation" else "BaseConversation"
    return {"id": cid, "inherits": inherits, "source": source,
            "nodes": nodes, "choices": globals_}


class ConvTree:
    def __init__(self, dirpath=None):
        self.dir = dirpath
        self._sig = None
        self.convs = {}

    def _files(self):
        d = self.dir or base_dir()
        return [os.path.join(d, n) for n in ("Conversations.xml", "HiddenConversations.xml")]

    def available(self):
        return any(os.path.exists(p) for p in self._files())

    def load(self):
        files = [p for p in self._files() if os.path.exists(p)]
        sig = tuple((p, os.stat(p).st_mtime_ns) for p in files)
        with _lock:
            if sig == self._sig:
                return self.convs
            convs = {}
            for p in files:
                try:
                    root = ET.parse(p).getroot()
                except ET.ParseError:
                    continue
                for el in root.findall("conversation"):
                    c = _parse_conversation(el, os.path.basename(p))
                    if c["id"] in convs:  # Load=Merge späterer Dateien: anhängen
                        convs[c["id"]]["nodes"] += c["nodes"]
                        convs[c["id"]]["choices"] += c["choices"]
                    else:
                        convs[c["id"]] = c
            self.convs = convs
            self._sig = sig
            return convs

    # -------------------------------------------------------------- Abfragen

    def chain(self, cid):
        """Konversation + Vererbungskette (nächste zuerst)."""
        convs = self.load()
        out, seen = [], set()
        while cid and cid in convs and cid not in seen:
            seen.add(cid)
            out.append(convs[cid])
            cid = convs[cid]["inherits"]
        return out

    def node(self, cid, nid):
        """Knoten per (deduplizierter) ID; Vererbung wird durchsucht."""
        for c in self.chain(cid):
            for n in c["nodes"]:
                if n["id"] == nid:
                    return c, n
        return None, None

    def nodes_by_raw(self, cid, raw):
        for c in self.chain(cid):
            hits = [n for n in c["nodes"] if n["raw_id"] == raw]
            if hits:
                return c, hits
        return None, []

    def all_paths(self):
        """Alle Text-Context-Pfade (für den Manifest-Abgleich)."""
        out = []
        for c in self.load().values():
            for n in c["nodes"]:
                out += [t["path"] for t in n["texts"]]
                out += [p["path"] for p in n["parts"]]
                for ch in n["choices"]:
                    out += [t["path"] for t in ch["texts"]]
                    out += [p["path"] for p in ch["parts"]]
            for ch in c["choices"]:
                out += [t["path"] for t in ch["texts"]]
                out += [p["path"] for p in ch["parts"]]
        return out


TREE = ConvTree()


def context_conversation(context):
    """'Conversation Otho.Start2.EndChoice.Text' -> ('Otho', ['Start2', 'EndChoice', 'Text'])"""
    m = re.match(r"^Conversation ([^.]+)\.(.*)$", context or "")
    if not m:
        return None, []
    return m.group(1), m.group(2).split(".")
