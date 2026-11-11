---
name: qud-de-grammatik
description: Arbeitsverfahren für die deutsche Caves-of-Qud-Lokalisierung — nutzen bei Playtest-Findings (falsche/englische Zeile im Spiel), Arbeit an Grammatik-Replacern/Translator-Provider, Übersetzungs-Values, Genus-/Kasus-Fragen und vor jedem Commit/Deploy in diesem Repo. Enthält den Finding-Diagnose-Baum, die Kontrakt-Checkliste und die Erweiterungs-Prozedur.
---

# QudDE-Grammatik: Arbeitsverfahren

**Fakten stehen in den Docs, hier stehen Verfahren.** Vor inhaltlichen Fragen zuerst lesen:
- `docs/GRAMMAR_ENGINE.md` — wie unsere Engine funktioniert, Kontrakte mit Begründung,
  Liste der nicht behandelten deutschen Grammatik.
- `docs/TURKISH_REFERENCE.md` — Techniken des offiziellen Referenz-Mods (PUA-Marker etc.).
- `docs/OPEN_ISSUES.md` — Wait-Liste (KEINE Shims bauen!), bekannt-benigne Log-Einträge,
  Diagnostik-Baseline.

## 1. Diagnose-Baum für Playtest-Findings

Eingang: „Zeile X ist englisch / falsch dekliniert / gemischt." Log:
`%USERPROFILE%\AppData\LocalLow\Freehold Games\CavesOfQud\Player.log`.

1. **Erst den Lauf-Zeitpunkt prüfen:** Ist `Player.log` NEUER als der letzte Deploy?
   Findings stammen oft aus einem Lauf VOR dem letzten Fix. `[QudDE] pipeline-test
   summary` bestätigt, welcher Code-Stand lief.
2. **String-Miss?** `Select-String Player.log -Pattern 'String table miss'`.
   Baseline: **exakt 7 benigne Startup-Misses** (siehe OPEN_ISSUES) — die ignorieren.
   Neuer Miss → Context/ID ablesen, Eintrag in `Strings*.de.xml` ergänzen
   (ID = byte-exaktes englisches Template!).
3. **Kein Miss, aber Token-Ergebnis falsch** (z. B. „mit die X", „ihr Biss")?
   → `[QudDE]`-Selbsttests im Log prüfen. Alle PASS ⇒ der Fehler liegt im VALUE
   (fehlende `:dativ`-Annotation, falsches Token), nicht im Code. FAIL ⇒ Code.
4. **Nur Artikel/Genus falsch** („das Puma")? → Zeile in
   `languages/lang-de/COQDE/GenderLexicon.tsv`, NIE Code. Komposita erben per Suffix;
   falsche Erbschaft (gewand≠wand) braucht einen exakten Eintrag.
5. **Englischer Satzrahmen + deutsche Token-Ergebnisse** („The X hits … with seiner Y")?
   Quelle in dieser Reihenfolge suchen:
   a. **REKURSIV** über die Spieldaten greppen — `StreamingAssets/Base/**` inkl.
      `ObjectBlueprints/` (nicht-rekursive Scans haben hier schon Funde verpasst!) und
      `StreamingAssets/DLC/**`. Treffer in einem Part-Attribut (PrepMessageOther,
      Message, …) → per `Load="Merge"` in unserer entsprechenden `.de.xml` übersetzen.
   b. ExampleLanguage-Manifest prüfen (existiert ein übersehenes Template?).
   c. Assembly-Literal-Scan: Python, `data.count(s.encode("utf-16-le"))` über
      `CoQ_Data/Managed/Assembly-CSharp.dll`. Wortlaut kann zur Laufzeit flektiert sein —
      auch Stamm-Formen suchen („widen" statt „widens").
   d. Voll-Decompile-Grep: `ilspycmd <dll> -o <scratchpad>` einmal cachen, dann rg.
      Gezielte Typen: `ilspycmd -t <Typname>`; Typen finden via `ilspycmd --list c`.
   e. Echtes C#-Literal ohne Hook → **KEIN Shim** (gesperrte Entscheidung 2026-07-17):
      in OPEN_ISSUES-Wait-Liste dokumentieren. Vorher prüfen, ob ein Provider-Hook
      existiert (TranslatorBase-Virtuals, `DefaultDefiniteArticle`-Kanal) — mehrere
      „unerreichbare" Fragmente waren doch erreichbar.
6. **Prozedurale Namen** (Helden-Titel, Orte, Dorf-Rollen)? → `Naming.de.xml`.
   **Substring-Kontrakt:** Werte müssen die zugehörigen
   `"<X> Naming.xml Context"`-Strings-Werte als Teilstring enthalten — beide Dateien im
   selben Commit ändern.
7. **HistorySpice/Reputations-Texte?** → `HistorySpice.jsonc` (übersetzte Blatt-Keys
   tragen `=`-Suffix). Achtung: Reasons/Titel sind **savegame-persistiert** — Fix wirkt
   nur auf neue Kreaturen; im Bericht erwähnen.
8. Quelle partout unauffindbar → exakten Wortlaut/Screenshot vom User erbitten und als
   offen dokumentieren statt zu raten.

## 2. Kontrakt-Checkliste vor JEDEM Commit

- [ ] Kein `ID="…"`-Attribut angefasst (byte-exaktes englisches Lookup-Key).
- [ ] Naming⊇Strings-Substring-Kontrakt gewahrt (falls Naming/Strings-Naming-Context berührt).
- [ ] Replacer/Postprocessor geben **string zurück** — keine TextBuilder-Schreib-Overloads
      (Append/Insert brechen den net48-Smoke mit CS0518).
- [ ] **Smoke-Gate:** `dotnet build build/smoke/smoke.csproj -c Release` → 0 Fehler.
- [ ] **Plausi-Gate:** `cd build && py -m curator.plausi` → 0 error (S/L/H/D-Regeln;
      nach jedem Spiel-Update zusätzlich S1/S3 = 0, sonst sind IDs veraltet/fehlen).
- [ ] XML-Validierung geänderter `.de.xml` (python ElementTree).
- [ ] Buch-/Beschreibungs-/Konversationstexte geändert? →
      `python build/tools/build_library_corpus.py` neu laufen lassen.
- [ ] **Deploy-Sync:** geänderte Dateien nach
      `%USERPROFILE%\AppData\LocalLow\Freehold Games\CavesOfQud\Mods\CavesOfQudGermanLang`
      kopieren und per Get-FileHash-Schleife über `git ls-files 'languages/*'` verifizieren
      (Ziel: „out-of-sync: 0").
- [ ] Erwartete Log-Baseline nach nächstem Lauf: alle `[QudDE]`-Selbsttests PASS,
      0 eigene MODWARN, exakt 7 Misses.
- [ ] Lücke aus GRAMMAR_ENGINE „Nicht behandelte deutsche Grammatik" geschlossen?
      → Checkbox dort im selben Commit abhaken.

## 3. Replacer erweitern / neu bauen

1. **Original zuerst lesen:** das Spiel-Delegat in `docs/archive/coqcode/Delegates/`
   (Signatur, Parameter, Beispiele). Override-Dispatch läuft auf **Name + Parametertyp**,
   nicht Return-Typ — ein string-Override ersetzt ein void-Original sauber.
2. Parameter-Konventionen einhalten: Kasus `:nom/:akk/:dat/:gen` (+ Langformen), Genus
   `:m/:f/:n/:pl`; Display-Parameter (`:single/:long/:withTitles/:asIfKnown`) über
   `GermanName(obj, ctx)` durchreichen.
3. **Pflicht: Selbsttest-Zeile** in `SelfTestPipeline` (bzw. `TranslatorDeutsch.SelfTest`
   für Zahlen) — das ist Doku und Test in einem; plus `[VariableExample]`-Attribut, wo
   sinnvoll.
4. Wenn Logik offline testbar ist (pure Funktionen): zusätzlich einen schnellen
   Python-Port mit Kantenfällen laufen lassen, bevor der Code als fertig gilt.
5. Smoke → Deploy → Commit (Checkliste oben).

## 4. Bestehendes hinterfragen (bei jedem Fix mitdenken)

- Gehört das ins **Lexikon/Verbs.json statt in Code**? (Eine Datenzeile schlägt eine
  Codeänderung.)
- Deckt der Fix **alle vier Deklinationspfade** ab: definit, indefinit, possessiv,
  `DeclineAfterArticle`-Nachdeklination?
- **Beide Farbcode-Formen** getestet: `{{x|wort}}` UND `&x`-Präfix?
- Verweigert `IsAdjNounPattern` ein Muster, das sicher behandelbar wäre — oder umgekehrt:
  lässt eine Lockerung Verstümmelung zu („Zahnrad aus der Großen Maschine")?
- Ist die Kasus-/Genus-Heuristik hier eine dokumentierte Wette (GRAMMAR_ENGINE,
  „Possessive")? Dann Gegenbeispiel als Ein-Zeilen-Justierung behandeln, nicht als Redesign.
- Wäre ein **PUA-Marker** (TURKISH_REFERENCE, „PUA-Marker-System") besser als ein weiterer
  durchgereichter Parameter? (Bisher: Parameter sind erste Wahl.)
- Ist das Finding vielleicht schon gefixt und der Playtest lief auf altem Stand?

## 5. Zeiger

- Code: `languages/lang-de/CODE/VariableReplacers.de.cs` (Token-Engine + Selbsttests),
  `languages/lang-de/CODE/Translator.de.cs` (Provider).
- Daten: `languages/lang-de/COQDE/GenderLexicon.tsv`, `Verbs.json`;
  Buchhaltung `languages/lang-de/Untranslated.de.xml`.
- Werkzeuge: `build/smoke/` (Pflicht-Gate), `build/tools/coverage_audit.py`,
  `build/tools/build_library_corpus.py`; `ilspycmd` (global installiert);
  In-Game-Wishes `testlangreplacers`/`testreplacers`.
- Diagnostik: `OptionDebugStringTableMisses` ist AN; Miss-Zeilen und `MODWARN [Caves of
  Qud German Translation]` in `Player.log` sind die Ground Truth.
