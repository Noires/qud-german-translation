"""Markierte Fehlerstellen gezielt korrigieren lassen (Mensch markiert, Agent korrigiert).

  py build/curator/tools/review_fix.py export        # offene Markierungen -> Agenten-Eingaben
  py build/curator/tools/review_fix.py import NAME   # Agenten-Ergebnis -> Vorschlags-Batch

Forschungslage: Korrekturen an MENSCHLICH markierten Stellen sind zuverlässiger als
freies automatisches Nachbearbeiten. Darum bekommt der Agent je Eintrag die
markierte Stelle (span), Kategorie und Notiz und darf nur dort ändern; das
Prüf-Gate „review-fix“ (proposals.span_problem) lehnt Änderungen außerhalb der
Stelle (± SPAN_SLACK Zeichen) ab. Annehmen setzt die Markierung auf „erledigt“.

export schreibt _work/reviewfix-NN.input.json:
  {batch, units: [{uid, context, english, value, span, category, note}]}
Agent (nach _work/REVIEWFIX_RULES.md) schreibt <NAME>.output.json:
  {items: [{uid, new_value, note}]}
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import proposals  # noqa: E402
from curator.flags import CATEGORIES, FLAGS  # noqa: E402
from curator.review import value_hash  # noqa: E402
from curator.store import Store  # noqa: E402

WORK = os.path.join(proposals.DIR, "_work")
SIZE = 60


def open_marks(store):
    out = []
    for uid, e in FLAGS.open_flags().items():
        u = store.get(uid)
        if u is None or e.get("kind") == "orphan":
            continue
        if e.get("value_sha1") != value_hash(u.display_value()):
            continue  # seit dem Markieren geändert -> erst neu ansehen
        out.append((u, e))
    return out


def export():
    st = Store()
    st.refresh()
    marks = open_marks(st)
    os.makedirs(WORK, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M")
    names = []
    for k in range(0, len(marks), SIZE):
        name = "reviewfix-%s-%02d" % (stamp, k // SIZE + 1)
        data = {"batch": name, "units": [
            {"uid": u.uid, "context": u.context or u.key, "english": u.english,
             "value": u.display_value(), "span": e.get("span"),
             "category": CATEGORIES.get(e.get("category"), e.get("category") or ""),
             "note": e.get("note", "")} for u, e in marks[k:k + SIZE]]}
        with open(os.path.join(WORK, name + ".input.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        names.append((name, len(data["units"])))
    for n, c in names:
        print("%-36s %4d" % (n, c))
    print("%d offene Markierungen in %d Batches -> %s" % (len(marks), len(names), WORK))


def do_import(name):
    st = Store()
    st.refresh()
    with open(os.path.join(WORK, name + ".input.json"), encoding="utf-8") as f:
        inp = {u["uid"]: u for u in json.load(f)["units"]}
    with open(os.path.join(WORK, name + ".output.json"), encoding="utf-8") as f:
        out = json.load(f).get("items", [])
    items, skipped = [], []
    for it in out:
        src, u = inp.get(it.get("uid")), st.get(it.get("uid", ""))
        if src is None or u is None:
            skipped.append((it.get("uid"), "unbekannte uid"))
            continue
        if u.display_value() != src["value"]:
            skipped.append((u.uid, "Wert seit Export geändert"))
            continue
        if it.get("new_value") in (None, src["value"]):
            continue
        items.append({"uid": u.uid, "file": u.file, "key": u.key, "old_value": src["value"],
                      "new_value": it["new_value"], "span": src.get("span"),
                      "category": src.get("category"),
                      "note": (src.get("note") or "") + (" → " + it["note"] if it.get("note") else "")})
    proposals.PROPOSALS.create(name, "review-fix", items, "Korrektur markierter Stellen (%s)" % name)
    gate = sum(1 for i in items if proposals.gate_problems(i, "review-fix"))
    print("%s: %d Vorschläge, %d mit Prüfbefund, %d übersprungen" % (name, len(items), gate, len(skipped)))
    for s in skipped[:10]:
        print("  übersprungen:", s)


if __name__ == "__main__":
    if sys.argv[1:2] == ["export"]:
        export()
    elif sys.argv[1:2] == ["import"] and len(sys.argv) > 2:
        do_import(sys.argv[2])
    else:
        print(__doc__)
