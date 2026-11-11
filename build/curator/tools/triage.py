"""LLM-Triage für die Prüfrunde (MQM-Stil) — NUR Sortierhilfe, keine Korrekturliste.

  py build/curator/tools/triage.py export [BEREICH] [--limit N]   # Agenten-Eingaben je 100
  py build/curator/tools/triage.py import NAME                    # Ergebnis -> data/triage.json
  py build/curator/tools/triage.py calibrate                      # Abgleich mit menschlichen Urteilen

export: noch ungeprüfte Einheiten in Prüfrunden-Reihenfolge nach
  data/proposals/_work/triage-<bereich>-NN.input.json  {batch, units: [{uid, context, english, value}]}
Ein Agent bewertet nach _work/TRIAGE_RULES.md und schreibt <NAME>.output.json:
  {items: [{uid, errors: [{text, category, severity, note}]}]}   (errors leer = in Ordnung)
import speichert je uid {value_sha1, errors, batch} — das Urteil gilt nur, solange
der Wert unverändert ist (review_queue.triage_weight).

calibrate: Forschungslage (GEMBA-MQM u. a.): LLM-Richter finden viel, melden aber
noch mehr Falsches. Bevor die Triage Gewicht bekommt, gegen menschliche Urteile
messen: Präzision = Anteil der LLM-Fehlermeldungen, die der Mensch auch markiert
hat; Trefferquote = Anteil der menschlichen Markierungen, die das LLM fand.
Grundlage sind Einheiten, die Mensch UND LLM beurteilt haben (geprüft oder markiert).
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import proposals  # noqa: E402
from curator.flags import FLAGS  # noqa: E402
from curator.review import REVIEW, value_hash  # noqa: E402
from curator.review_queue import BUCKETS, TRIAGE_PATH, ReviewQueue, load_triage  # noqa: E402
from curator.store import Store  # noqa: E402

WORK = os.path.join(proposals.DIR, "_work")
SIZE = 100
SEVERITIES = ("critical", "major", "minor")


def export(bucket=None, limit=None):
    st = Store()
    st.refresh()
    q = ReviewQueue(st)
    items = q.pending(q.items(), bucket)
    done = load_triage()
    todo = [i for i in items if i["uid"] not in done
            or done[i["uid"]].get("value_sha1") != value_hash(i["_u"].display_value())]
    if limit:
        todo = todo[:limit]
    os.makedirs(WORK, exist_ok=True)
    names = []
    for b, _ in BUCKETS:
        mine = [i for i in todo if i["bucket"] == b]
        for k in range(0, len(mine), SIZE):
            name = "triage-%s-%02d" % (b, k // SIZE + 1)
            path = os.path.join(WORK, name + ".input.json")
            if os.path.exists(path):
                name += "-" + time.strftime("%H%M%S")
                path = os.path.join(WORK, name + ".input.json")
            data = {"batch": name, "units": [
                {"uid": i["uid"], "context": i["_u"].context or i["_u"].key,
                 "english": i["_u"].english, "value": i["_u"].display_value()}
                for i in mine[k:k + SIZE]]}
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            names.append((name, len(data["units"])))
    for n, c in names:
        print("%-32s %4d" % (n, c))
    print("%d Batches, %d Einheiten -> %s" % (len(names), sum(c for _, c in names), WORK))


def _save(data):
    out = {"note": "LLM-Triage (MQM-Stil) — nur Sortierhilfe der Prüfrunde. uid -> "
                   "{value_sha1, errors[{text, category, severity, note}], batch}. "
                   "Committbar, wird NICHT deployt.",
           "triage": {k: data[k] for k in sorted(data)}}
    tmp = TRIAGE_PATH + ".curator-tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, TRIAGE_PATH)


def do_import(name):
    st = Store()
    st.refresh()
    with open(os.path.join(WORK, name + ".input.json"), encoding="utf-8") as f:
        inp = {u["uid"]: u for u in json.load(f)["units"]}
    with open(os.path.join(WORK, name + ".output.json"), encoding="utf-8") as f:
        out = json.load(f).get("items", [])
    data = load_triage()
    n = bad = flagged = 0
    for it in out:
        src, u = inp.get(it.get("uid")), st.get(it.get("uid", ""))
        if src is None or u is None or u.display_value() != src["value"]:
            bad += 1
            continue
        errs = [e for e in it.get("errors") or [] if e.get("severity") in SEVERITIES]
        data[u.uid] = {"value_sha1": value_hash(src["value"]), "errors": errs, "batch": name}
        n += 1
        flagged += bool(errs)
    _save(data)
    print("%s: %d bewertet, %d mit Fehlermeldung, %d übersprungen (Wert geändert/unbekannt)"
          % (name, n, flagged, bad))


def calibrate():
    st = Store()
    st.refresh()
    tri, flags = load_triage(), FLAGS.load()
    tp = fp = fn = tn = 0
    for u in st.all_units():
        t = tri.get(u.uid)
        if not t or t.get("value_sha1") != value_hash(u.display_value()):
            continue
        human_bad = u.uid in flags and flags[u.uid].get("status", "open") == "open"
        human_ok = REVIEW.status(u)[0] == "checked" and not human_bad
        if not (human_bad or human_ok):
            continue
        llm_bad = bool(t.get("errors"))
        tp += llm_bad and human_bad
        fp += llm_bad and human_ok
        fn += (not llm_bad) and human_bad
        tn += (not llm_bad) and human_ok
    n = tp + fp + fn + tn
    print("Einheiten mit Mensch- UND LLM-Urteil: %d" % n)
    if not n:
        print("Noch keine Grundlage — erst ~100 Einträge in der Prüfrunde prüfen/markieren.")
        return
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    print("LLM meldet Fehler: %d (davon vom Menschen bestätigt %d)" % (tp + fp, tp))
    print("Präzision: %s · Trefferquote: %s" % (
        "%.0f %%" % (100 * prec) if prec is not None else "–",
        "%.0f %%" % (100 * rec) if rec is not None else "–"))
    if n < 100:
        print("Hinweis: weniger als 100 Vergleichsfälle — Werte noch wenig belastbar.")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["export"]:
        lim = int(a[a.index("--limit") + 1]) if "--limit" in a else None
        rest = [x for x in a[1:] if not x.startswith("--") and not x.isdigit()]
        export(rest[0] if rest else None, lim)
    elif a[:1] == ["import"] and len(a) > 1:
        do_import(a[1])
    elif a[:1] == ["calibrate"]:
        calibrate()
    else:
        print(__doc__)
