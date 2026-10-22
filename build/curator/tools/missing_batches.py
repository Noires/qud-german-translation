"""Fehlende String-Tabellen-Einträge (▶-Manifest ohne deutsche Abdeckung) in Batches.

  py build/curator/tools/missing_batches.py export         # Eingaben schreiben
  py build/curator/tools/missing_batches.py import NAME    # Ergebnis -> Vorschlags-Batch (op=create)

export: data/proposals/_work/new-<datei>-NN.input.json
  {batch, file, units: [{context, id, english, neighbors: [{english, value}]}]}
  (neighbors = bis zu 3 vorhandene deutsche Einträge mit gleichem Context-Präfix
   — für Ton und Terminologie)
Agent schreibt <NAME>.output.json: {items: [{context, id, new_value, note?}]}
import legt einen Batch mit rule "new" und op=create-Items an; angenommen wird
im Tab „Vorschläge“ (writer.create_string_entry).
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import coverage, proposals  # noqa: E402
from curator.store import Store  # noqa: E402

WORK = os.path.join(proposals.DIR, "_work")
SIZE = 130
# Manifest-Datei -> Ziel-String-Tabelle
TARGETS = {"Strings": "Strings.de.xml", "Strings.appendix": "Strings.appendix.de.xml"}


def _prefix(ctx):
    return (ctx or "").split(" ")[0]


def export():
    store = Store()
    store.refresh()
    cov = coverage.Coverage().compute()
    os.makedirs(WORK, exist_ok=True)
    by_prefix = {}
    for u in store.all_units():
        if u.kind == "string" and u.file in TARGETS.values():
            by_prefix.setdefault((u.file, _prefix(u.context)), []).append(u)
    names = []
    for man, target in TARGETS.items():
        f = cov["files"].get(man)
        if not f:
            continue
        units = []
        for m in f["missing"]:
            sid = m["key"][1]
            near = by_prefix.get((target, _prefix(m.get("context"))), [])[:3]
            units.append({"context": m.get("context") or "", "id": sid, "english": m["english"],
                          "neighbors": [{"english": n.english, "value": n.display_value()} for n in near]})
        short = man.replace("Strings.", "").replace("Strings", "strings").lower()
        for i in range(0, len(units), SIZE):
            name = "new-%s-%02d" % (short, i // SIZE + 1)
            with open(os.path.join(WORK, name + ".input.json"), "w", encoding="utf-8", newline="\n") as fh:
                json.dump({"batch": name, "file": target, "units": units[i:i + SIZE]}, fh,
                          ensure_ascii=False, indent=1)
            names.append((name, len(units[i:i + SIZE])))
    for n, c in names:
        print("%-24s %4d" % (n, c))


def do_import(name):
    with open(os.path.join(WORK, name + ".input.json"), encoding="utf-8") as fh:
        inp = json.load(fh)
    want = {(u["context"], u["id"]) for u in inp["units"]}
    with open(os.path.join(WORK, name + ".output.json"), encoding="utf-8") as fh:
        out = json.load(fh).get("items", [])
    items, skipped = [], []
    for it in out:
        k = (it.get("context") or "", it.get("id"))
        if k not in want:
            skipped.append(k)
            continue
        if not (it.get("new_value") or "").strip():
            continue
        items.append({"op": "create", "file": inp["file"], "context": k[0], "id": k[1],
                      "new_value": it["new_value"], "note": it.get("note", "")})
    proposals.PROPOSALS.create(name, "new", items, "Neue Einträge (%s)" % name)
    store = Store()
    store.refresh()
    b = proposals.PROPOSALS.load(name, store)
    gate = sum(1 for i in b["items"] if i["gate"])
    print("%s: %d Neuanlagen, %d mit Prüfbefund, %d übersprungen (ID/Context unbekannt)"
          % (name, len(items), gate, len(skipped)))


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "export":
        export()
    elif len(sys.argv) >= 3 and sys.argv[1] == "import":
        do_import(sys.argv[2])
    else:
        print(__doc__)
