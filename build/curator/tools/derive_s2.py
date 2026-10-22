"""Verbs.json: "du"-Form (s2) für alle Einträge ableiten (Anrede-Richtlinie du).

Regel = C# DeriveS2 (VariableReplacers.de.cs) bzw. german.derive_s2:
  sieht->siehst, trägt->trägst, lässt->lässt, hält->hältst, lädt->lädst
Echte Unregelmäßige kommen aus IRREGULAR. Bestehende s2-Einträge bleiben.

  py build/curator/tools/derive_s2.py          # Vorschau (Tabelle)
  py build/curator/tools/derive_s2.py --write  # Verbs.json schreiben
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import german, verbs  # noqa: E402

IRREGULAR = {
    "sein": "bist", "haben": "hast", "werden": "wirst", "wissen": "weißt",
    "können": "kannst", "wollen": "willst", "müssen": "musst", "dürfen": "darfst",
    "sollen": "sollst", "mögen": "magst",
}


def main():
    v = verbs.Verbs()
    data = v.load()
    rows = []
    for e in data.get("verbs", []):
        inf = e.get("inf", "")
        if e.get("s2"):
            rows.append((inf, e.get("s3"), e["s2"], "vorhanden"))
            continue
        s2 = IRREGULAR.get(inf.lower()) or german.derive_s2(e.get("s3"), inf)
        e["s2"] = s2
        rows.append((inf, e.get("s3"), s2, "unregelmäßig" if inf.lower() in IRREGULAR else "abgeleitet"))
    for inf, s3, s2, how in rows:
        print("%-16s %-12s -> %-14s %s" % (inf, s3, s2, how))
    if "--write" in sys.argv:
        v._emit(data)
        print("Verbs.json geschrieben (%d Einträge)." % len(rows))


if __name__ == "__main__":
    main()
