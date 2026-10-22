"""Szenen für die In-Kontext-Vorschau: mehrere Übersetzungseinheiten, so
zusammengesetzt, wie das Spiel sie gemeinsam zeigt.

Szenentypen (layout):
  conversation  NPC-Text eines Gesprächsknotens + nummerierte Antworten
  popup         Meldungsfenster mit Tasten-Leiste
  messagelog    Nachrichtenlog: Zeile + verwandte Zeilen derselben Quelle
  card          Look-/Tooltip-/Fähigkeits-Karte: Name + Beschreibung(en)

Jeder Baustein ist ein Slot {role, uid, en, de, status, match, render}; render
ist die emulierte Ausgabe (grammar_emu) mit Token-Markern — das Frontend
(static/qudrender.js) setzt Farbcodes, Umbruch und Klickziele darauf.
"""
import re

from . import config, convtree, grammar_emu

# Erste Schätzwerte — gegen Spiel-Screenshots kalibrieren (config.json
# "preview_cols": {...}). Die Breite des Classic-UI ist nicht belegt.
DEFAULT_COLS = {"conversation": 74, "popup": 66, "messagelog": 62, "card": 48,
                "book": 62, "journal": 64, "spicelist": 70}

LAYOUTS = ("conversation", "popup", "messagelog", "card", "book", "journal", "spicelist")

_POPUP_HINT = re.compile(r"popup|title|prompt|confirm|dialog|question|error", re.I)
_LOG_HINT = re.compile(r"message|log|addplayermessage|ignore|combat|xdidy|death", re.I)
_GROUP_RE = re.compile(r"^(/[^/]+/[^/@]+)")
_LAST_NAMED = re.compile(r"^(.*\])(?=[/@])")
_QUEST_RE = re.compile(r"^(/[^/]+/quest\[[^\]]*\])")
_OBJECT_RE = re.compile(r"^(/[^/]+/object\[[^\]]*\])")

# Datei -> Layout für Nicht-String-Einheiten (sonst "card")
FILE_LAYOUTS = {"Books.de.xml": "book", "Quests.de.xml": "journal", "HistorySpice.jsonc": "spicelist"}


def group_key(u):
    """Zusammengehörige Einheiten: ein Buch, eine Quest (mit Schritten), das
    innerste benannte Element (Mutation, Fähigkeit, Kreatur …) bzw. bei JSON
    die Eltern-Liste (alle Varianten eines Gewürz-Eintrags)."""
    key = u.key or ""
    if u.kind == "json":
        return key.rsplit("/", 1)[0]
    if u.file == "Quests.de.xml":
        m = _QUEST_RE.match(key)
        if m:
            return m.group(1)
    # Blueprints: das ganze Objekt (Name aus part[Render] + Beschreibung aus part[Description])
    m = _OBJECT_RE.match(key)
    if m:
        return m.group(1)
    m = _LAST_NAMED.match(key)
    if m:
        return m.group(1)
    m = _GROUP_RE.match(key)
    return m.group(1) if m else None


def load_colors():
    """Base/Colors.xml -> {"solid": {name: letter}, "shaders": {name: {type, colors}}}."""
    import os
    import xml.etree.ElementTree as ET
    path = os.path.join(convtree.base_dir(), "Colors.xml")
    out = {"solid": {}, "shaders": {}}
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return out
    for c in root.iter("solidcolor"):
        out["solid"][c.get("Name")] = c.get("Color")
    for sh in root.iter("shader"):
        out["shaders"][sh.get("Name")] = {"type": sh.get("Type"),
                                          "colors": (sh.get("Colors") or "").split("-")}
    return out


def cols():
    out = dict(DEFAULT_COLS)
    out.update(config.CFG.get("preview_cols") or {})
    return out


class SceneBuilder:
    def __init__(self, store, english_fn=None, review=None, lint_uids=None):
        self.store = store
        self.english_fn = english_fn or (lambda u: None)
        self.review = review
        self.lint_uids = lint_uids or (lambda: set())
        self.flags_fn = lambda: {}
        self.findings_fn = lambda: {}   # uid -> [{rule, severity, message}] (K*/G*)
        self._flags = {}
        self._finds = {}
        self._idx_sig = None
        self._by_ctx = {}
        self._by_en = {}
        self._by_group = {}

    # ------------------------------------------------------------ Indizes

    def _index(self):
        sig = id(self.store.units)
        if sig == self._idx_sig:
            return
        by_ctx, by_en, by_group, ctx_only = {}, {}, {}, {}
        for u in self.store.all_units():
            if u.kind in ("string", "string-text"):
                by_ctx[(u.context or "", u.english or "")] = u
                if u.context:
                    ctx_only.setdefault(u.context, u)
                by_en.setdefault(u.english or "", []).append(u)
            else:
                g = group_key(u)
                if g:
                    by_group.setdefault((u.file, g), []).append(u)
        for us in by_group.values():
            us.sort(key=lambda x: x.line or 0)
        self._by_ctx, self._by_en, self._by_group = by_ctx, by_en, by_group
        self._ctx_only = ctx_only
        self._idx_sig = sig

    def lookup(self, context, english):
        """(Context, ID) wie das Spiel; sonst ID allein (anderer Context)."""
        self._index()
        u = self._by_ctx.get((context or "", english))
        if u is not None:
            return u, "context"
        cands = self._by_en.get(english) or []
        if cands:
            return cands[0], "id"
        # Eintrag mit diesem Context, aber anderer ID: das Spiel hat den
        # englischen Text geändert -> der deutsche Wert greift nie (Spiel zeigt EN)
        u = self._ctx_only.get(context or "")
        if u is not None:
            return u, "staleid"
        return None, "none"

    # -------------------------------------------------------------- Slots

    def _status(self, u, lint, match=None):
        if u is None:
            return "untranslated"
        if match == "staleid":
            return "staleid"
        if u.uid in lint:
            return "lint"
        if self.review is not None:
            st = self.review.status(u)[0]
            if st in ("checked", "stale"):
                return st
        return "translated"

    def slot(self, role, u, en, opts, lint, match="context", path=None, drafts=None):
        de = None
        if u is not None:
            de = (drafts or {}).get(u.uid, u.display_value())
        # veraltete ID: das Spiel findet den Eintrag nicht und zeigt Englisch
        src = de if (opts["lang"] == "de" and de is not None and match != "staleid") else en
        if opts["lang"] == "en" or de is None or match == "staleid":
            render = _raw_render(src or "")
        elif opts.get("ctx_roles"):
            render = grammar_emu.resolve(src, ctx_roles=opts["ctx_roles"], pick=opts["pick"])
        else:
            render = grammar_emu.resolve(src, ctx=opts["roles"], pick=opts["pick"])
        return {
            "role": role, "uid": u.uid if u else None, "file": u.file if u else None,
            "en": en, "de": de, "status": self._status(u, lint, match), "match": match,
            "id_en": u.english if (u is not None and match == "staleid") else None,
            "path": path, "render": render, "draft": bool(u and drafts and u.uid in drafts),
            "flag": self._flags.get(u.uid) if u else None,
            "findings": self._finds.get(u.uid, []) if u else [],
        }

    # ------------------------------------------------------ Konversation

    # ---------------------------------------------- Review-Workflow

    def node_stats(self, n, lint, flags, finds):
        """Zählwerte eines Knotens (NPC-Texte + eigene Antworten)."""
        st = {"texts": 0, "translated": 0, "checked": 0, "flagged": 0, "staleid": 0,
              "lint": 0, "rules": set()}
        for t in _node_texts(n):
            st["texts"] += 1
            u, match = self.lookup(t["path"], t["en"])
            if u is None:
                continue
            if match == "staleid":
                st["staleid"] += 1
                st["rules"].add("K1")
                continue
            st["translated"] += 1
            if u.uid in lint:
                st["lint"] += 1
            if u.uid in flags:
                st["flagged"] += 1
            st["rules"].update(f["rule"] for f in finds.get(u.uid, ()))
            if self.review is not None and self.review.status(u)[0] == "checked":
                st["checked"] += 1
        return st

    def _ctx(self):
        self._index()
        return set(self.lint_uids()), self.flags_fn(), self.findings_fn()

    def conversation_list(self, q="", filt=""):
        lint, flags, finds = self._ctx()
        ql = (q or "").lower()
        out = []
        for cid, c in sorted(convtree.TREE.load().items()):
            if ql and ql not in cid.lower():
                continue
            agg = {"texts": 0, "translated": 0, "checked": 0, "flagged": 0, "staleid": 0,
                   "lint": 0, "rules": set()}
            for n in c["nodes"]:
                st = self.node_stats(n, lint, flags, finds)
                for k in agg:
                    agg[k] = agg[k] | st[k] if k == "rules" else agg[k] + st[k]
            if not agg["texts"] or not matches_filter(agg, filt):
                continue
            agg["rules"] = sorted(agg["rules"])
            out.append({"id": cid, "nodes": len(c["nodes"]), "source": c["source"],
                        "open": open_count(agg), **agg})
        return out

    def next_scene(self, filt, from_conv=None, from_node=None):
        """Erster Knoten nach (from_conv, from_node), der zum Filter passt."""
        lint, flags, finds = self._ctx()
        seq = []
        for cid, c in sorted(convtree.TREE.load().items()):
            for n in c["nodes"]:
                seq.append((cid, n))
        start = 0
        for i, (cid, n) in enumerate(seq):
            if cid == from_conv and n["id"] == from_node:
                start = i + 1
                break
        for cid, n in seq[start:] + seq[:start]:
            st = self.node_stats(n, lint, flags, finds)
            if st["texts"] and matches_filter(st, filt or "open"):
                return {"conversation": cid, "node": n["id"]}
        return None

    def graph(self, cid):
        """Knotenkarte: Knoten + Kanten (GotoID/Target), Status, Erreichbarkeit."""
        lint, flags, finds = self._ctx()
        chain = convtree.TREE.chain(cid)
        if not chain:
            return None
        conv = chain[0]
        by_raw = {}
        for n in conv["nodes"]:
            by_raw.setdefault(n["raw_id"], []).append(n["id"])
        nodes, edges = [], []
        for n in conv["nodes"]:
            st = self.node_stats(n, lint, flags, finds)
            choices = list(n["choices"])
            if n.get("inherits"):
                _, base = convtree.TREE.node(cid, n["inherits"])
                if base is not None:
                    choices += base["choices"]
            own = len(choices)
            if n["start"] or n["raw_id"] == "Start":
                for c in chain:  # Konversations-Antworten gehen an Startknoten (wie im Spiel)
                    choices += c["choices"]
            targets = []
            for i, ch in enumerate(choices):
                for tid in by_raw.get(ch["target"], []):
                    if tid not in targets:
                        targets.append(tid)
                        edges.append({"from": n["id"], "to": tid, "global": i >= own})
            st["rules"] = sorted(st["rules"])
            nodes.append({"id": n["id"], "raw_id": n["raw_id"], "cond": n["cond"],
                          "start": n["start"] or n["raw_id"] == "Start",
                          "status": node_status(st), "ends": any(ch["target"] == "End" for ch in choices),
                          **st})
        # Tiefe per BFS von den Startknoten; Unerreichbares bekommt depth=None
        depth = {n["id"]: 0 for n in nodes if n["start"]}
        queue = list(depth)
        adj = {}
        for e in edges:
            adj.setdefault(e["from"], []).append(e["to"])
        while queue:
            cur = queue.pop(0)
            for nxt in adj.get(cur, []):
                if nxt not in depth:
                    depth[nxt] = depth[cur] + 1
                    queue.append(nxt)
        for n in nodes:
            n["depth"] = depth.get(n["id"])
        return {"conversation": cid, "nodes": nodes, "edges": edges}

    def conversation(self, cid, nid=None, opts=None, drafts=None):
        opts = _opts(opts)
        lint = set(self.lint_uids())
        self._flags = self.flags_fn()
        self._finds = self.findings_fn()
        tree = convtree.TREE
        chain = tree.chain(cid)
        if not chain:
            return None
        conv = chain[0]
        if not nid:
            starts = [n for n in conv["nodes"] if n["raw_id"] == "Start" or n["start"]]
            nid = (starts or conv["nodes"] or [{"id": None}])[0]["id"]
        owner, node = tree.node(cid, nid)
        if node is None:
            return None
        variants = node["texts"]
        vi = min(max(opts["variant"], 0), max(len(variants) - 1, 0))
        npc = None
        if variants:
            t = variants[vi]
            u, match = self.lookup(t["path"], t["en"])
            npc = self.slot("npc", u, t["en"], opts, lint, match, t["path"], drafts)
            npc["cond"] = t["cond"]

        choices = [dict(c, origin="node") for c in node["choices"]]
        if node.get("inherits"):  # Knoten-Vererbung: Antworten des Basisknotens
            _, base = tree.node(cid, node["inherits"])
            if base is not None:
                choices += [dict(c, origin="inherited") for c in base["choices"]]
        if node["start"] or node["raw_id"] == "Start":
            for c in chain:  # Konversations-Antworten gehen an Startknoten
                choices += [dict(ch, origin="global:" + c["id"]) for ch in c["choices"]]
        choices.sort(key=lambda c: (c["ordinal"] if c["ordinal"] is not None else 0))

        end_tag = self._end_tag(opts, lint, drafts)
        out_choices = []
        for c in choices:
            if not c["texts"]:
                continue
            ci = opts["choice_variants"].get(c["id"], 0) % len(c["texts"])
            t = c["texts"][ci]
            u, match = self.lookup(t["path"], t["en"])
            s = self.slot("choice", u, t["en"], opts, lint, match, t["path"], drafts)
            s.update({"id": c["id"], "target": c["target"], "cond": {**c["cond"], **t["cond"]},
                      "origin": c["origin"], "variants": len(c["texts"]), "variant": ci})
            tags = []
            for p in c["parts"]:
                pu, pm = self.lookup(p["path"], p["en"])
                tags.append(self.slot("tag", pu, p["en"], opts, lint, pm, p["path"], drafts))
            if c["target"] == "End" and end_tag:
                tags.append(end_tag)
            s["tags"] = tags
            out_choices.append(s)

        siblings = [{"id": n["id"], "cond": n["cond"]}
                    for n in owner["nodes"] if n["raw_id"] == node["raw_id"]]
        return {
            "layout": "conversation", "cols": cols()["conversation"],
            "conversation": cid, "node": node["id"], "raw_id": node["raw_id"],
            "owner": owner["id"], "speaker": cid, "cond": node["cond"],
            "variants": [{"path": v["path"], "cond": v["cond"]} for v in variants],
            "variant": vi, "npc": npc, "choices": out_choices, "siblings": siblings,
            "nodes": [n["id"] for n in conv["nodes"]],
        }

    def _end_tag(self, opts, lint, drafts):
        u, match = self.lookup("Conversation Choice - End tag", "{{K|[End]}}")
        if u is None:
            return None
        return self.slot("tag", u, "{{K|[End]}}", opts, lint, match, None, drafts)

    # --------------------------------------------- Strings / Blueprints

    def for_unit(self, uid, opts=None, layout=None, drafts=None):
        """Szene, die die Einheit enthält (Kontext-Panel im Editor)."""
        self.store.refresh()
        u = self.store.get(uid)
        if u is None:
            return None
        opts = _opts(opts)
        self._flags = self.flags_fn()
        self._finds = self.findings_fn()
        if u.kind in ("string", "string-text") and (u.context or "").startswith("Conversation ") \
                and layout in (None, "conversation"):
            cid, segs = convtree.context_conversation(u.context)
            if cid and segs and convtree.TREE.chain(cid):
                sc = self.conversation(cid, segs[0], opts, drafts)
                if sc is not None:
                    _choose_variant(sc, u, self, cid, segs, opts, drafts)
                    sc["focus"] = uid
                    return sc
        if u.kind in ("string", "string-text"):
            return self.string_scene(u, opts, layout, drafts)
        return self.card_scene(u, opts, drafts)

    def string_scene(self, u, opts, layout=None, drafts=None):
        lint = set(self.lint_uids())
        layout = layout if layout in ("popup", "messagelog") else guess_layout(u)
        main = self.slot("main", u, u.english, opts, lint, "context", u.context, drafts)
        sc = {"layout": layout, "cols": cols()[layout], "focus": u.uid,
              "context": u.context, "main": main, "lines": []}
        if layout == "messagelog":
            # verwandte Zeilen derselben Quelle (gleiches Context-Präfix) als Umgebung
            prefix = (u.context or "").split(" ")[0]
            near = [o for o in self.store.all_units()
                    if o.file == u.file and o.uid != u.uid and o.kind == u.kind
                    and prefix and (o.context or "").split(" ")[0] == prefix]
            near.sort(key=lambda o: abs((o.line or 0) - (u.line or 0)))
            lines = [self.slot("context", o, o.english, opts, lint, "context", o.context, drafts)
                     for o in near[:4]]
            lines.sort(key=lambda s: self.store.get(s["uid"]).line or 0)
            before = [s for s in lines if self.store.get(s["uid"]).line < u.line]
            after = [s for s in lines if self.store.get(s["uid"]).line >= u.line]
            sc["lines"] = before + [main] + after
        return sc

    def card_scene(self, u, opts, drafts=None):
        self._index()
        lint = set(self.lint_uids())
        gk = group_key(u)
        group = self._by_group.get((u.file, gk), [u]) if gk else [u]
        layout = FILE_LAYOUTS.get(u.file, "card")
        if layout == "spicelist" and len(group) > 14:  # lange Listen: Fenster um den Fokus
            i = next((k for k, o in enumerate(group) if o.uid == u.uid), 0)
            lo = max(0, min(i - 6, len(group) - 14))
            group = group[lo:lo + 14]
        if u.objname:  # beschriebenes Objekt ist subject/pronouns (=pronouns.Possessive=)
            roles = grammar_emu.build_roles(opts["roles"])
            obj = grammar_emu.sample_for_blueprint(u.objname, self.store)
            roles["subject"] = roles["pronouns"] = obj
            opts = dict(opts, ctx_roles=roles)
        title, body = None, []
        for o in group:
            s = self.slot(_card_role(o), o, self.english_fn(o), opts, lint, "path", o.key, drafts)
            if s["role"] == "title" and title is None:
                title = s
            elif s["role"] != "skip":
                body.append(s)
        name = (gk or "").rsplit("/", 1)[-1] or u.objname
        if layout == "spicelist":
            name = (u.context or name)
        for s, o in zip([x for x in body], [o for o in group if _card_role(o) not in ("title", "skip")]):
            s["label"] = _label(o)
        return {"layout": layout, "cols": cols()[layout], "focus": u.uid,
                "group": name, "file": u.file, "title": title, "body": body}


# ---------------------------------------------------------------- Helfer

FILTERS = ("", "open", "untranslated", "unchecked", "flagged", "staleid", "address", "findings")


def open_count(st):
    return (st["texts"] - st["translated"]) + (st["translated"] - st["checked"])


def matches_filter(st, filt):
    if not filt:
        return True
    if filt == "open":
        return open_count(st) > 0
    if filt == "untranslated":
        return st["translated"] < st["texts"]
    if filt == "unchecked":
        return st["checked"] < st["translated"]
    if filt == "flagged":
        return st["flagged"] > 0
    if filt == "staleid":
        return st["staleid"] > 0
    if filt == "address":
        return "K2" in st["rules"]
    if filt == "findings":
        return bool(st["rules"]) or st["lint"] > 0
    return True


def node_status(st):
    if st["translated"] + st["staleid"] < st["texts"]:
        return "untranslated"
    if st["staleid"]:
        return "staleid"
    if st["lint"] or st["rules"]:
        return "lint"
    if st["checked"] < st["translated"]:
        return "translated"
    return "checked"


def _opts(opts):
    o = {"lang": "de", "roles": {}, "pick": 0, "variant": 0, "choice_variants": {}}
    o.update({k: v for k, v in (opts or {}).items() if v is not None})
    return o


def _raw_render(s):
    """Englisch/unübersetzt: Tokens bleiben sichtbar (Marker ohne Auflösung)."""
    tokens = []

    def rep(m):
        tokens.append({"src": m.group(0), "out": m.group(0), "how": "raw"})
        return grammar_emu.TOK_START + m.group(0) + grammar_emu.TOK_END
    return {"text": grammar_emu.TOKEN_RE.sub(rep, s), "tokens": tokens}


def _node_texts(n):
    out = list(n["texts"])
    for c in n["choices"]:
        out += c["texts"]
    return out


def _choose_variant(sc, u, builder, cid, segs, opts, drafts):
    """Für eine Variante (Text2 …) oder eine Antwort-Variante dieselbe Szene
    so umschalten, dass die fokussierte Einheit sichtbar ist."""
    if sc["npc"] and sc["npc"]["uid"] == u.uid:
        return
    for i, v in enumerate(sc["variants"]):
        if v["path"] == u.context and i != sc["variant"]:
            opts = dict(opts, variant=i)
            sc.update(builder.conversation(cid, segs[0], opts, drafts))
            return
    for c in sc["choices"]:
        if c["uid"] == u.uid:
            return


def guess_layout(u):
    ctx = u.context or ""
    if _LOG_HINT.search(ctx):
        return "messagelog"
    if _POPUP_HINT.search(ctx):
        return "popup"
    if (u.english or "").lstrip().startswith(("=subject.", "=object.")):
        return "messagelog"
    return "popup"


def _label(u):
    """Kurzer Abschnittsname im Karten-/Journal-/Buch-Layout."""
    key = u.key or ""
    if u.kind == "json":
        return "#" + key.rsplit("/", 1)[-1]
    m = re.search(r"/step\[([^\]]*)\]", key)
    if m:
        return "Schritt: " + m.group(1)
    m = re.search(r"/page#(\d+)", key)
    if m:
        return "Seite " + m.group(1)
    return u.attr if u.attr not in ("#text", "Short") else ""


def _card_role(u):
    if u.attr in ("DisplayName", "DisplayText", "Title"):
        return "title"
    if u.kind == "json":
        return "body"
    if u.attr in ("Short", "Long", "Description", "BehaviorDescription", "Snippet", "#text",
                  "Accomplishment", "Hagiograph", "Gospel"):
        return "body"
    if u.attr in ("Value", "Proper", "x", "y", "Level", "NameContext", "Category"):
        return "skip"
    return "body"
