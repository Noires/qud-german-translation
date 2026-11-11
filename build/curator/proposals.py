"""Vorschlags-Warteschlange: Wert-Änderungen, die ein Mensch annimmt.

Batches liegen in build/curator/data/proposals/<batch>.json (committbar, nicht
deployt). Sie entstehen durch Assistenten (K3-Regel, du-Umstellung durch
Subagenten …); geschrieben wird AUSSCHLIESSLICH beim Annehmen, und zwar über
writer.save (Alt-Wert-Prüfung, Schlüsselmengen-Schutz, Byte-Erhalt).

Batch-Format:
  {batch, rule, note, created,
   items: [{uid, file, key, old_value, new_value, note, status}]}
  status: open | accepted | rejected
Abgeleitet beim Laden (nicht gespeichert):
  gate  — Liste der Prüfprobleme (Tokens verändert, {{ }} unausgewogen,
          Anrede noch nicht nach Richtlinie …); Items mit gate sind nicht annehmbar
  stale — der aktuelle Wert entspricht nicht mehr old_value
"""
import json
import os
import re
import threading
import time
from collections import Counter

from . import config, writer

DIR = os.path.join(config.DATA_DIR, "proposals")
TOKEN_RE = re.compile(r"=([^=\s][^=]*?)=")
_NAME_RE = re.compile(r"^[\w.-]{1,80}$")
_lock = threading.Lock()


# review-fix: so viele Zeichen links/rechts der markierten Stelle dürfen mitgeändert
# werden (Artikel/Endung vor einem Nomen, Satzzeichen)
SPAN_SLACK = 16


def span_problem(old, new, span):
    """Änderung muss innerhalb der markierten Stelle (± SPAN_SLACK) liegen."""
    if not span or old == new:
        return None
    pre = 0
    while pre < min(len(old), len(new)) and old[pre] == new[pre]:
        pre += 1
    suf = 0
    while suf < min(len(old), len(new)) - pre and old[-1 - suf] == new[-1 - suf]:
        suf += 1
    if pre < span["start"] - SPAN_SLACK or len(old) - suf > span["end"] + SPAN_SLACK:
        return ("Änderung reicht über die markierte Stelle „%s“ hinaus (geändert: Zeichen %d–%d)"
                % (span.get("text", ""), pre, len(old) - suf))
    return None


def gate_problems(item, rule):
    """Prüfungen, die ein Vorschlag bestehen muss, bevor er annehmbar ist."""
    old, new = item.get("old_value") or "", item.get("new_value") or ""
    out = []
    if rule == "review-fix":
        sp = span_problem(old, new, item.get("span"))
        if sp:
            out.append(sp)
    if not new.strip():
        out.append("leerer Wert")
    told = Counter(m.group(0) for m in TOKEN_RE.finditer(old))
    tnew = Counter(m.group(0) for m in TOKEN_RE.finditer(new))
    if rule == "fix-plural":
        # nur die Parameter von pluralize/isPlural/ifPlural-Tokens dürfen sich ändern
        norm = lambda c: Counter(re.sub(r"(\.(?:pluralize|isplural|ifplural)):[^=]*=$", r"\1=", t, flags=re.I)  # noqa: E731
                                 for t in c.elements())
        told, tnew = norm(told), norm(tnew)
    elif rule == "fix-part":
        # Körperteil-Phrase umgebaut: part-Tokens frei; Besitzer-Tokens (…the.name's / their /
        # genitiv) dürfen wechseln, solange die ROLLE erhalten bleibt
        def norm(c):
            out = Counter()
            for t in c.elements():
                low = t.lower()
                if low.startswith("=part."):
                    out["=part="] += 1
                elif re.match(r"=\w+\.(the\.name's|their|its|possessive|genitiv)", low):
                    continue  # Besitzer steckt jetzt in =part.poss= bzw. =X.genitiv=
                else:
                    out[re.sub(r"(\.(?:pluralize|isplural|ifplural)):[^=]*=$", r"=", t, flags=re.I)] += 1
            return out
        told, tnew = norm(told), norm(tnew)
    elif rule == "fix-case":
        # nur ein Kasus-Parameter an Objektpronomen darf dazukommen (=X.them= -> =X.them:dat=)
        norm = lambda c: Counter(re.sub(r"\.(them|objective):(?:dat|dativ|akk)=$", r".\1=", t, flags=re.I)  # noqa: E731
                                 for t in c.elements())
        told, tnew = norm(told), norm(tnew)
    elif rule == "fix-ifplural":
        # nur die (Text-)Argumente der Weichen-Tokens dürfen sich ändern
        norm = lambda c: Counter(re.sub(r"(ifplayerplural|isplural|ifplural):[^=]*=$", r"\1=", t, flags=re.I)  # noqa: E731
                                 for t in c.elements())
        told, tnew = norm(told), norm(tnew)
    if rule == "k3":
        # K3 darf genau ein Namens-Token ergänzen und konjde klein schreiben
        told = Counter(t.lower() for t in told.elements())
        tnew = Counter(t.lower() for t in tnew.elements())
        extra = tnew - told
        if (told - tnew) or sum(extra.values()) > 1:
            out.append("Tokens verändert")
    elif told != tnew:
        missing = list((told - tnew).elements())
        added = list((tnew - told).elements())
        out.append("Tokens verändert: %s%s" % (
            ("fehlt " + " ".join(missing)) if missing else "",
            (" neu " + " ".join(added)) if added else ""))
    if new.count("{{") != new.count("}}"):
        out.append("{{ }} unausgewogen")
    from . import context_lint
    key = item.get("key") or ""
    english = item.get("id") or (key.split("|", 1)[1] if "|" in key else "")
    k5_new = context_lint.untranslated_token_args(english, new)
    if len(k5_new) > len(context_lint.untranslated_token_args(english, old)) \
            or (rule == "fix-ifplural" and k5_new):
        out.append("K5: " + k5_new[0])
    if rule in ("du", "fix-ifplural"):
        forms = context_lint.address_forms(new)
        left = sorted(f for f in forms if f in ("Ihr", "Sie"))
        if left:
            out.append("noch %s-Form („%s“)" % ("/".join(left), forms[left[0]]))
    return out


ROLE_RE = re.compile(r"=([A-Za-z]\w*)\.")


def gate_create(item):
    """Prüfung für NEUE Einträge (op=create): kein Wert-Vergleich möglich, also
    gegen die englische Vorlage (ID) — jede Token-Rolle der Vorlage muss im
    Deutschen vorkommen, Markup ausgewogen, Anrede du, kein konjde ohne Subjekt."""
    from . import context_lint
    en, new = item.get("id") or "", item.get("new_value") or ""
    out = []
    if not new.strip():
        out.append("leerer Wert")
    def roles(text):
        toks = " ".join(m.group(0) for m in TOKEN_RE.finditer(text))
        found = {m.group(1).lower() for m in ROLE_RE.finditer(toks)}
        # Rolle als #-Argument („=subject.its.part:dat#part=“) zählt mit
        found |= {a.lower() for a in re.findall(r"#([A-Za-z]\w*)", toks)}
        return found
    roles_en, roles_de = roles(en), roles(new)
    lost = sorted(roles_en - roles_de)
    if lost:
        out.append("Token-Rolle fehlt: " + ", ".join(lost))
    if new.count("{{") != new.count("}}"):
        out.append("{{ }} unausgewogen")
    if new.count("=") % 2 != en.count("=") % 2:  # manche Vorlagen sind selbst ungerade
        out.append("'='-Anzahl passt nicht zur Vorlage (Token offen?)")
    forms = context_lint.address_forms(new)
    left = sorted(f for f in forms if f in ("Ihr", "Sie"))
    if left:
        out.append("noch %s-Form („%s“)" % ("/".join(left), forms[left[0]]))
    k3 = context_lint.konjde_without_subject(en, new)
    if k3:
        out.append("konjde ohne Subjekt (%s)" % ", ".join(k3))
    return out


def create_uid(item):
    import hashlib
    raw = "%s|%s|%s" % (item.get("file"), item.get("context") or "", item.get("id"))
    return "new-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def is_address_problem(problem):
    return problem.startswith("noch ") and "-Form" in problem


class Proposals:
    def __init__(self, dirpath=None):
        self.dir = dirpath or DIR

    def _p(self, batch):
        if not _NAME_RE.match(batch or ""):
            raise ValueError("Ungültiger Batch-Name.")
        return os.path.join(self.dir, batch + ".json")

    def batches(self, store):
        out = []
        if not os.path.isdir(self.dir):
            return out
        for fn in sorted(os.listdir(self.dir)):
            if not fn.endswith(".json"):
                continue
            try:
                b = self.load(fn[:-5], store)
            except (OSError, ValueError):
                continue
            c = Counter(i["state"] for i in b["items"])
            out.append({"batch": b["batch"], "rule": b.get("rule"), "note": b.get("note", ""),
                        "created": b.get("created"), "total": len(b["items"]), "counts": dict(c)})
        return out

    def load(self, batch, store):
        with open(self._p(batch), encoding="utf-8") as f:
            b = json.load(f)
        b.setdefault("batch", batch)
        rule = b.get("rule")
        for it in b.get("items", []):
            it.setdefault("status", "open")
            if it.get("op") == "create":
                self._load_create(it, store)
                continue
            u = store.get(it.get("uid", "")) if store is not None else None
            it["gate"] = gate_problems(it, rule)
            it["current"] = u.display_value() if u else None
            it["english"] = u.english if u else None
            it["context"] = u.context if u else None
            it["stale"] = u is None or (it["status"] == "open" and it["current"] != it["old_value"])
            if it["status"] != "open":
                it["state"] = it["status"]
            elif it["stale"]:
                it["state"] = "stale"
            elif it["gate"]:
                it["state"] = "gate"
            else:
                it["state"] = "open"
        return b

    @staticmethod
    def _load_create(it, store):
        """Neuanlage: Zustand daraus, ob (Context, ID) in der Datei schon existiert."""
        it["uid"] = it.get("uid") or create_uid(it)
        it["gate"] = gate_create(it)
        it["english"] = it.get("id")
        it["old_value"] = ""
        existing = None
        res = store.files.get(it.get("file")) if store is not None else None
        if res is not None:
            key = "%s|%s" % (it.get("context") or "", it.get("id"))
            existing = next((x for x in res.units if x.kind in ("string", "string-text")
                             and x.key == key), None)
        it["current"] = existing.display_value() if existing else None
        it["created_uid"] = existing.uid if existing else it.get("created_uid")
        it["stale"] = it["status"] == "open" and existing is not None
        if it["status"] != "open":
            it["state"] = it["status"]
        elif it["stale"]:
            it["state"] = "stale"  # inzwischen anderweitig angelegt
        elif it["gate"]:
            it["state"] = "gate"
        else:
            it["state"] = "open"

    def save_batch(self, b):
        os.makedirs(self.dir, exist_ok=True)
        keep = ("uid", "op", "file", "key", "context", "id", "old_value", "new_value", "note",
                "status", "created_uid", "span", "category")
        out = {"batch": b["batch"], "rule": b.get("rule"), "note": b.get("note", ""),
               "created": b.get("created") or time.strftime("%Y-%m-%d %H:%M"),
               "items": [{k: it[k] for k in keep if k in it} for it in b["items"]]}
        p = self._p(b["batch"])
        tmp = p + ".curator-tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, p)

    def create(self, batch, rule, items, note=""):
        """Neuen Batch anlegen (bestehender Batch gleichen Namens wird ersetzt)."""
        b = {"batch": batch, "rule": rule, "note": note,
             "created": time.strftime("%Y-%m-%d %H:%M"),
             "items": [dict(it, status="open") for it in items]}
        with _lock:
            self.save_batch(b)
        return b

    def decide(self, batch, uid, action, store, new_value=None, force=False):
        """action: accept | reject | reopen. accept schreibt über writer.save.
        force übergeht NUR Anrede-Befunde (z. B. „Ihr Licht“ = 3. Person) —
        Token-/Markup-Probleme bleiben harte Sperren."""
        with _lock:
            b = self.load(batch, store)
            it = next((i for i in b["items"] if i["uid"] == uid), None)
            if it is None:
                raise KeyError("Vorschlag nicht im Batch.")
            create = it.get("op") == "create"
            if new_value is not None:
                it["new_value"] = new_value
                it["gate"] = gate_create(it) if create else gate_problems(it, b.get("rule"))
            if action == "accept":
                if it["status"] != "open":
                    raise ValueError("Vorschlag ist nicht offen (%s)." % it["status"])
                hard = [g for g in it["gate"] if not (force and is_address_problem(g))]
                if hard:
                    raise ValueError("Prüfung nicht bestanden: " + "; ".join(hard))
                if create:
                    if it.get("stale"):
                        raise ValueError("Eintrag existiert inzwischen schon.")
                    u = writer.create_string_entry(store, it["file"], it.get("context") or "",
                                                   it["id"], it["new_value"])
                    it["created_uid"] = u.uid
                else:
                    writer.save(store, uid, it["old_value"], it["new_value"])
                it["status"] = "accepted"
                if b.get("rule") == "review-fix":
                    # Markierung ist behoben; die geprüft-Marke setzt der Mensch neu
                    from .flags import FLAGS
                    try:
                        FLAGS.set_status(uid, "fixed")
                    except KeyError:
                        pass
            elif action == "reject":
                it["status"] = "rejected"
            elif action == "reopen":
                it["status"] = "open"
            else:
                raise ValueError("Unbekannte Aktion.")
            self.save_batch(b)
            return it


# ------------------------------------------------------------- Assistenten

# Satzanfang: Textbeginn, nach .!?: oder Zeilenumbruch, nach einer geschlossenen
# Farbspanne oder direkt hinter einem öffnenden {{X|
_SENT_START = re.compile(r"(?:^|[.!?:]\s+|\n\s*|\}\}\s*|^\{\{[^|{}]+\|)$")


def k3_items(store):
    """K3-Assistent: konjde ohne Subjekt am Satzanfang -> Namens-Token davor.
    "=subject.Konjde:spüren= X." -> "=subject.The.name= =subject.konjde:spüren= X."
    Fälle mitten im Satz (Verb-zweit nach Adverb o. ä.) bleiben K3-Befunde für Handarbeit."""
    from . import context_lint
    items = []
    for u in store.all_units():
        value = u.display_value()
        roles = context_lint.konjde_without_subject(u.english or "", value)
        if not roles:
            continue
        new = value
        ok = True
        for role in roles:
            rx = re.compile(r"=(%s)\.([Kk])onjde:([^=]*)=" % re.escape(role), re.I)
            m = rx.search(new)
            if not m or not _SENT_START.search(new[:m.start()]):
                ok = False
                break
            name = "=%s.The.name=" % m.group(1)
            new = new[:m.start()] + name + " =" + m.group(1) + ".konjde:" + m.group(3) + "=" + new[m.end():]
        if ok and new != value:
            items.append({"uid": u.uid, "file": u.file, "key": u.key, "old_value": value,
                          "new_value": new, "note": "Subjekt-Token ergänzt (Does → Name + konjde)"})
    return items


PROPOSALS = Proposals()
