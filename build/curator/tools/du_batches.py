"""Agenten-Batches aus Lint-Befunden: du-Umstellung (K2) und Weichen-Token-
Argumente (K5, ifplayerplural/isplural mit englischem Text).

  py build/curator/tools/du_batches.py export [K5]   # Eingaben je Datei/150 (K5: 50) Einheiten
  py build/curator/tools/du_batches.py import NAME   # Agenten-Ergebnis -> Vorschlags-Batch

export schreibt build/curator/data/proposals/_work/<NAME>.input.json:
  {batch, file, units: [{uid, context, english, value}]}
Ein Agent schreibt dazu <NAME>.output.json:
  {items: [{uid, new_value, note?}]}   (unveränderte Einheiten weglassen)
import prüft uid/Alt-Wert gegen den aktuellen Stand und legt den Batch mit
rule "du" (bzw. "fix-ifplural" für ifplural-*) an — die Prüfung (gate_problems) läuft beim Laden in der UI.
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import context_lint, proposals  # noqa: E402
from curator.store import Store  # noqa: E402

WORK = os.path.join(proposals.DIR, "_work")
SIZE = 150
# Reihenfolge: Gespräche zuerst (dort fällt die Anrede am meisten auf)
ORDER = ["Strings.Conversations.de.xml", "Strings.de.xml"]


# Lint-Regel -> (Batch-Präfix, Batch-Größe, Vorschlags-Regel)
KINDS = {"K2": ("du", SIZE, "du"), "K5": ("ifplural", 50, "fix-ifplural")}


def k2_units(store, rule="K2"):
    uids = {f["uid"] for f in context_lint.findings(store)
            if f["rule"] == rule and f["severity"] == "warning"}
    us = [store.get(u) for u in uids if store.get(u) is not None]
    rank = {f: i for i, f in enumerate(ORDER)}
    us.sort(key=lambda u: (rank.get(u.file, 99), u.file, u.line or 0))
    return us


def export(rule="K2"):
    prefix, size, _ = KINDS[rule]
    store = Store()
    store.refresh()
    os.makedirs(WORK, exist_ok=True)
    by_file = {}
    for u in k2_units(store, rule):
        by_file.setdefault(u.file, []).append(u)
    names = []
    for fn in sorted(by_file, key=lambda f: ORDER.index(f) if f in ORDER else 99):
        us = by_file[fn]
        short = fn.replace(".de.xml", "").replace("Strings.", "").replace(".", "-").lower()
        for i in range(0, len(us), size):
            name = "%s-%s-%02d" % (prefix, short, i // size + 1)
            data = {"batch": name, "file": fn, "units": [
                {"uid": u.uid, "context": u.context or u.key, "english": u.english,
                 "value": u.display_value()} for u in us[i:i + size]]}
            with open(os.path.join(WORK, name + ".input.json"), "w", encoding="utf-8", newline="\n") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            names.append((name, len(data["units"])))
    for n, c in names:
        print("%-28s %4d" % (n, c))
    print("%d Batches, %d Einheiten -> %s" % (len(names), sum(c for _, c in names), WORK))


def do_import(name):
    store = Store()
    store.refresh()
    with open(os.path.join(WORK, name + ".input.json"), encoding="utf-8") as f:
        inp = {u["uid"]: u for u in json.load(f)["units"]}
    with open(os.path.join(WORK, name + ".output.json"), encoding="utf-8") as f:
        out = json.load(f).get("items", [])
    items, skipped = [], []
    for it in out:
        src = inp.get(it.get("uid"))
        u = store.get(it.get("uid", ""))
        if src is None or u is None:
            skipped.append((it.get("uid"), "unbekannte uid"))
            continue
        if u.display_value() != src["value"]:
            skipped.append((u.uid, "Wert seit Export geändert"))
            continue
        if it.get("new_value") in (None, src["value"]):
            continue
        items.append({"uid": u.uid, "file": u.file, "key": u.key, "old_value": src["value"],
                      "new_value": it["new_value"], "note": it.get("note", "")})
    rule = KINDS["K5"][2] if name.startswith(KINDS["K5"][0] + "-") else "du"
    note = "Weichen-Token-Argumente deutsch" if rule != "du" else "Anrede Ihr/Sie → du"
    proposals.PROPOSALS.create(name, rule, items, "%s (%s)" % (note, name))
    gate = sum(1 for i in items if proposals.gate_problems(i, rule))
    print("%s: %d Vorschläge, %d mit Prüfbefund, %d übersprungen" % (name, len(items), gate, len(skipped)))
    for s in skipped[:10]:
        print("  übersprungen:", s)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "export":
        export(sys.argv[2] if len(sys.argv) >= 3 else "K2")
    elif len(sys.argv) >= 3 and sys.argv[1] == "import":
        do_import(sys.argv[2])
    else:
        print(__doc__)
