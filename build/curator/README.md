# QudDE Kurator

Lokale Web-UI zum Kuratieren der deutschen Übersetzung: durchsuchen, prüfen,
anpassen, Tests anlegen und In-Game-Ergebnisse einsehen — mit den harten
Projekt-Kontrakten by construction erzwungen.

## Start

```
py build/curator/server.py
```

Öffnet automatisch `http://127.0.0.1:8371`. Nur Python-3-Stdlib, keine
Installation. Pfade (Spiel, Player.log, Deploy-Ordner, Port) lassen sich über
`build/curator/config.json` übersteuern (Vorlage: Schlüssel `game_example_dir`,
`player_log`, `deploy_dir`, `port`; für die Szenen-Vorschau zusätzlich
`game_base_dir` — Default: Elternordner von `game_example_dir` — und
`preview_cols`, z. B. `{"conversation": 74, "popup": 66}`).

## Tabs

| Tab | Zweck |
|---|---|
| **Übersetzungen** | Suchen/Filtern über ~28.700 Einheiten aus 44 `*.de.xml` + `HistorySpice.jsonc`; Editieren mit unveränderlicher ID, Token-Palette, Live-Prüfbefunden; „Nur unübersetzt" = Manifest-Diff; **Geprüft-Marken** je Eintrag (Filter: ungeprüft/veraltet/geprüft) |
| **Vorschläge** | Warteschlange für Assistenten-Änderungen (du-Umstellung, K3-Behebung): Wort-Diff + Szenen-Vorschau mit neuem Wert, Annehmen/Ablehnen/Bearbeiten — geschrieben wird NUR beim Annehmen, über den Writer |
| **Szenen** | In-Kontext-Vorschau: Übersetzungen in nachgebauten Qud-Fenstern (Gespräch, Popup, Nachrichtenlog, Look-Karte) zusammen mit ihren Nachbar-Bausteinen, Grammatik-Tokens emuliert — siehe unten |
| **Prüfungen** | Lint über den ganzen Korpus (T1–T6 Token-Regeln, B1 Boolean, N1 Naming-Substring, X1 Entity, X2 Schema, K1–K7 Kontext, G1/G2 Glossar, S/L/H/D Plausibilität); Klick öffnet den Eintrag |
| **Glossar** | Begriffe (EN → DE, Genus, Plural, verbotene Varianten) + Anrede-Richtlinie (**du/du** seit 2026-10-22); Vorschläge aus Kreatur-/Gegenstandsnamen (mit „belegt"-Quote, Mehrfach-Übernahme) und eingefärbten Begriffen; Abgleich mit dem Genus-Lexikon |
| **Tests** | CuratorTests.json pflegen; Ergebnisse des letzten Spiel-Laufs mit Staleness-Diagnose; **„Emulation prüfen"** erzeugt `ctx-auto-*`-Tests aus den häufigsten Grammatik-Tokens (FAIL = Vorschau weicht vom Spiel ab) |
| **Lexikon** | GenderLexicon.tsv mit Konsequenz-Vorschau (Suffix-Vererbung!) und L1/L2-Prüfung |
| **Verben** | Verbs.json mit Schwach-Konjugations-Vorschau („Eintrag nötig ja/nein") und Trennbar-Guard |
| **Protokoll & Abgleich** | Player.log-Dashboard (Misses, MODWARN, Selbsttests, Kurator-Tests) + Deploy-Sync |
| **Abdeckung** | Coverage je Datei gegen die ▶-Manifeste des Spiels; **Versionsvergleich** gegen `data/manifest_snapshot.json` (nach Spiel-Updates: neue / entfernte / geänderte Einträge) |

## Kontrakte, die der Writer erzwingt

1. `ID="…"`/`Context`/`Name` werden nie verändert — kein Codepfad schreibt in
   Schlüssel, und jeder Save verifiziert Key-Set-Invarianz auf dem Kandidaten.
2. XML bleibt wohlgeformt (Parse vor dem Persistieren).
3. Naming ⊇ Strings als **Regressions-Gate**: nur *neu entstehende*
   Verletzungen blockieren; Bestandsfälle meldet die Prüf-Engine (N1).
4. Byte-Erhalt: Splice in den Originaltext, BOM/EOL pro Datei unangetastet,
   No-op-Saves schreiben nicht. `git diff` zeigt nur die geänderte Stelle.

## Geprüft-Marken

„Als geprüft markieren" im Editor setzt eine Marke in
`build/curator/data/reviewed.json` — **im Repo committbar** (diff-freundlich:
eine Zeile Datei/Schlüssel/Datum je Marke), wird NICHT ins Spiel deployt.
Jede Marke speichert den Hash des Werts zum Prüfzeitpunkt: wird der Wert
später geändert, degradiert sie automatisch zu „✓? veraltet", bis jemand neu
prüft. Kopfzeile zeigt den Fortschritt („Geprüft: X/Y"); Filter in der
Suchleiste: *noch zu prüfen / nur ungeprüfte / nur veraltet / nur geprüfte*.

## Szenen-Vorschau (In-Kontext-Prüfung)

Beantwortet „passt die Übersetzung *im Spiel*?" — Ton/Anrede über Antworten
hinweg (du/Ihr/Sie), Kasus über Fragmentgrenzen, Länge und Umbruch.

- **Gespräche** kommen aus dem englischen Baum des Spiels
  (`Base/Conversations.xml` + `HiddenConversations.xml`, `convtree.py`). Die
  Context-IDs (`Otho.Start2.EndChoice.Text`) werden wie im Spiel vergeben
  (≈ 98,6 % Treffer gegen das ▶-Manifest; Rest = C#-dynamische Knoten).
  Deutsche Werte: Lookup per (Context, ID) wie das Spiel, sonst nur ID
  („nur ID"-Badge). Stimmt die ID nicht mehr mit dem Spieltext überein, heißt
  der Baustein **„ID veraltet"** — das Spiel zeigt dort Englisch.
  `[n]` wählt die Antwort (folgt GotoID/Target), ↻ wechselt Antwort-Varianten,
  „Knoten" wechselt zwischen gleichnamigen Knoten (Start, Start2 … mit ihren
  Bedingungen), „Basis-Antworten" blendet geerbte Antworten (Handel,
  Wasserritual …) ein.
- **Andere Einheiten** (Übersetzungen-Tab → Panel „Im Kontext", oder
  „In Szenen öffnen"): Strings als Popup oder Nachrichtenlog (Heuristik über
  den Context, umschaltbar), Blueprint-Texte als Look-/Fähigkeitskarte
  (Name + Beschreibungen desselben Objekts; `=pronouns.*=` bezieht sich auf
  das beschriebene Objekt).
- **Tokens** löst `grammar_emu.py` auf: 1:1-Port der Mod-Replacer aus
  `VariableReplacers.de.cs` (Paritätstest gegen alle `[VariableExample]` und
  Selbsttest-Vektoren), Spiel-Replacer angenähert (Pronomen aus
  `Genders.de.xml`), Gewürz aus `HistorySpice.jsonc` (⟳ würfelt neu), Rest aus
  der Stichproben-Tabelle `data/sample_values.json` (Defaults in
  `grammar_emu.DEFAULT_SAMPLES`; Datei überschreibt). Unterstreichung zeigt die
  Herkunft; **unbekannt** und **englischer Fallback** sind Warnsignale.
  subject/object/Spieler sind umschaltbar (Krokodil n., Leuchtfisch m.,
  Ziege f., Plural, Eigenname, Spieler-Ihr …).
- **Live-Entwurf:** Tippen im Editor rendert die Szene sofort neu, ohne zu
  speichern. **Im Spiel bestätigen** legt aus der aktuellen Vorschau einen
  CuratorTest an (erwartet = emulierte Ausgabe) — PASS im Spiel bestätigt die
  Emulation, FAIL zeigt eine Abweichung Emulation ↔ Spiel.
- **Prüfen:** „Szene als geprüft markieren" setzt Geprüft-Marken für alle
  Bausteine der Ansicht. „⚑ Passt nicht" speichert eine Notiz in
  `data/flags.json` (committbar, nicht deployt); Liste im Tab „Prüfungen".
- **Breite:** Spaltenbreiten sind Schätzwerte (Modern UI bricht nach
  Pixelbreite um, nicht nach Spalten) — gegen Spiel-Screenshots kalibrieren
  und in `preview_cols` eintragen. Roter Rand = Wort länger als die Zeile.
- **Review-Workflow:** Gesprächsliste filtern (offen, unübersetzt,
  ungeprüft, mit Befund, Anrede-Mix, ID veraltet, markiert) und nach „meiste
  offen" sortieren; Balken = übersetzt (grün) / geprüft (cyan).
  **Nächste ▶** springt zum nächsten Knoten, der zum Filter passt.
  **Knotenkarte:** Spalten = Schritte ab Start (BFS über GotoID/Target inkl.
  geerbter Antworten, blasse Kanten = Konversations-Antworten), Farbe =
  Status, gestrichelt = kein Weg vom Start; Klick öffnet den Knoten.
  Tasten: `1–9` Antwort · `←/→` Text-Variante · `N` nächste · `R` Szene
  geprüft · `F` markieren.
- **Deep-Links:** `#szenen/conv/<Gespräch>/<Knoten>`, `#szenen/unit/<uid>`,
  `#unit/<uid>`, `#tab/<tab>`.

## Kontext- und Glossar-Regeln (`context_lint.py`)

| Regel | Schwere | Was |
|---|---|---|
| K1 | warning | ID veraltet: Context steht im Spiel-Gesprächsbaum, der englische Text hat sich geändert — der Wert greift nie. **Behebung per Klick** („Neu anlegen mit aktueller ID", Prüfungen-Tab oder Szenen-Editor): legt einen Eintrag mit aktueller ID, gleichem Context und altem Wert an; der alte bleibt (der Writer löscht nie) und wird als verwaist markiert |
| K2 | warning | Anrede weicht von der Richtlinie im Glossar ab (du/Sie/Ihr-Heuristik; NPC-Texte und Antworten getrennt) |
| K3 | warning | `=X.Does:…=` (Name + Verb) wurde zu `=X.konjde:…=` ohne Namen — im Spiel fehlt das Subjekt |
| K4 | info | Possessiv-Token ohne Kasus/Genus vor einem Wort — wird undekliniert ausgegeben |
| K5 | warning | Weichen-Token (`=ifplayerplural:…:…=`, `=X.isPlural:…=`, `=X.ifPlural:…=`) mit englischen Argumenten (Archaismen, Funktionswörter oder wörtlich wie in der Vorlage) bzw. doppelter Anrede direkt dahinter — die Argumente sind Text und werden im Spiel wörtlich ausgegeben. Batches: `tools/du_batches.py export K5` → Agenten nach `_work/IFPLURAL_RULES.md` → `import ifplural-…` (Regel `fix-ifplural`); jedes Gate sperrt neue K5-Befunde |
| K6 | warning | `=X.them=`/`=X.objective=` direkt nach Dativ-Präposition/-Verb ohne `:dat` — im Spiel „von ihn“. Wechselpräpositionen (an/in/unter/über) prüft die Regel bewusst nicht (Bewegung = Akkusativ); Gate-Regel `fix-case` erlaubt nur das Ergänzen des Kasus |
| K7 | warning | Gleicher englischer Text, verschiedene deutsche Fassungen (Weblate „inconsistent“; Groß-/Kleinschreibung am Satzanfang zählt nicht). Gewollte Kontext-Varianten per „Varianten erlauben“ → `glossary.json` `ignore_inconsistent` |
| P1 | warning/info | Parität zur Vorlage: Ziffernfolgen (außerhalb von Tokens/Farbcodes; 1.5 ≙ 1,5), Leerraum am Anfang/Ende (wichtig bei zusammengesetzten Texten), doppelte Leerzeichen, unausgewogene `()`/`[]` |
| G1 | warning | Glossar-Begriff im Englischen, deutsche Festlegung fehlt / verbotene Variante |
| G2 | warning | Artikel direkt vor dem Begriff passt in keinem Kasus zum Glossar-Genus; Genitiv m/n ohne -s |

## Plausibilitätsprüfungen (`plausi.py`)

Fehlerklassen aus dem Spieler-Feedback 2026-11-11; laufen im Prüfungen-Tab mit und als
Gate von der Kommandozeile: `cd build && py -m curator.plausi` (Exit 1 bei error).

| Regel | Schwere | Was |
|---|---|---|
| S1 | warning | String-ID veraltet: Context existiert im Manifest, der englische Text nicht mehr (Upstream-Update) — bzw. toter Alteintrag, wenn die neue Fassung schon übersetzt ist |
| S2 | warning | Kontextloser String, den das Spiel nur mit Context abfragt — greift nie |
| S3 | warning | Manifest-String fehlt bei uns (zeigt Englisch) |
| L1 | error | Eigener Loader ohne `Load="Merge"` (`REPLACE_BY_NAME_LOADERS`, z. B. Baetyl-`<reward>`) — ersetzt Base-Daten komplett |
| H1 | error | InventoryAction-Hotkey nicht genau ein Zeichen (`ein` statt `a`) |
| H2 | error | `<display>` von Aktionen, die C# per `.Display` vergleicht (`CODE_READ_ACTIONS`), nicht kleingeschrieben — blockiert das Tutorial |
| D1 | warning | Wortdopplung im Anzeigenamen („X X“, `{{c|A-B}}B`) |
| D2 | warning | Stufen-Ziffer (I–VIII) im Namen, die das Englische nicht hat („Dolch VII“) |
| D3 | warning | Englisches Material-/Attributwort im deutschen Namen (crysteel, flawless …) |

**Schwere je Regel** (Prüfungen-Tab, Auswahl neben jeder Regel): Standard / off /
info / warning / error, gespeichert in `glossary.json` → `rules`. `off` blendet die
Regel aus; `error` blockt zusätzlich das Speichern (Editor, Vorschlag-Annehmen,
Werkzeuge) — aber nur, wenn die Änderung einen NEUEN Befund dieser Regel erzeugt;
Bestandsbefunde blockieren nicht.

Glossar und Richtlinie liegen in `data/glossary.json` (committbar, nicht
deployt). Pronomen-Bezüge („um ihn herum") prüft G2 bewusst nicht.

## Vorschlags-Warteschlange & du-Umstellung

- Batches: `data/proposals/<batch>.json` (committbar, nicht deployt). Jeder
  Vorschlag durchläuft beim Laden eine **Prüfung** (Token-Multimenge unverändert,
  `{{ }}` ausgewogen, bei du-Batches keine Ihr/Sie-Form mehr). Annehmen =
  `writer.save` mit Alt-Wert-Prüfung; hat sich der Wert inzwischen geändert, wird
  der Vorschlag „veraltet". Reine Anrede-Befunde (z. B. „Ihr Licht" = die Göttin)
  lassen sich per „Trotzdem annehmen" übergehen — Token-Probleme nie.
- **K3-Assistent** (Tab Vorschläge → „Erzeugen"): ergänzt `=X.The.name=` vor
  satzinitialem `konjde` (313 der 322 Fälle); Rest bleibt K3-Befund.
- **du-Umstellung** (Anrede-Richtlinie du/du): `py build/curator/tools/du_batches.py export`
  schreibt K2-Einheiten je Datei/150 nach `data/proposals/_work/<batch>.input.json`;
  Subagenten konvertieren nach `data/proposals/_work/DU_RULES.md` in
  `<batch>.output.json`; `… du_batches.py import <batch>` legt den Batch an.
  Engine-Seite: `PlayerPronoun` du/dich/dir/deiner, Possessiv „dein",
  Verbperson **s2** (`Verbs.json` Feld `s2`, Ableitung `DeriveS2`/`derive_s2`,
  `tools/derive_s2.py`), `PronounSets.de.xml` player = du.
- **Verwaiste Einträge** nach K1-„Neu anlegen" sind als `orphan` markiert und
  lassen sich im Szenen-Editor löschen (`writer.delete_string_entry`,
  byte-genau, Schlüsselmengen-Prüfung). Markierungen haben Status
  offen / erledigt / verworfen.
- **K1 im Spiel bestätigt:** Erscheint die aktuelle englische ID unter dem
  Context als String-Miss in `Player.log`, trägt der Befund „✓ im Spiel bestätigt".
- **Korrektur-Batches:** `py build/curator/tools/fix_batches.py <art>` mit
  `fix-plural` (`=X.pluralize:wort=` → `Singular:Plural`-Paar), `fix-part`
  (`=part.ordinalName=` nach Possessiv/Artikel → `=part.poss:dat=`/`=part.dativ=`),
  `fix-spice` (HistorySpice-Listen in 1. Person), `fix-terms` (Glossar-Varianten →
  Vorzugsbegriff). Gate-Regeln gleichnamig: nur die jeweiligen Token-Parameter
  dürfen sich ändern.
- **Engine-Ergänzungen (2026-10-22):** Demonstrativ `=X.this=` (dieser/diese/dieses),
  deutscher Plural (`COQDE/PluralLexicon.tsv` + Endungsregeln) für alle
  `pluralize`-Pfade, Körperteil-Kasus `=part.dativ=` und Possessiv
  `=part.poss:<kasus>=` — gespiegelt in `grammar_emu.py`, Details in
  `docs/GRAMMAR_ENGINE.md` (Abschnitte 7/7a).
- **Nach angenommenen du-Batches** `py build/tools/build_library_corpus.py`
  laufen lassen (`LibraryCorpus.de.json` ist aus Büchern/Beschreibungen/Gesprächen
  generiert und enthält sonst weiter Ihr-Formen).

## Kuratieren: Prüfrunde, Triage, Korrektur, Playtest

Empfohlener Ablauf (Begründung: Deep-Research 2026-10-22 — LLM-Richter finden viel,
melden aber noch mehr Falsches; Korrekturen an menschlich markierten Stellen sind
zuverlässiger als freies Nachbearbeiten):

1. **Regeln** (Prüfungen-Tab) bis keine Warnungen mehr offen sind.
2. **Triage** (optional): `py build/curator/tools/triage.py export [bereich] [--limit N]` →
   Agenten nach `_work/TRIAGE_RULES.md` → `triage.py import <batch>` → `data/triage.json`.
   Wirkt NUR als Sortierschlüssel der Prüfrunde. Vorher kalibrieren: ~100 Einträge selbst
   prüfen/markieren, dann `triage.py calibrate` (Präzision/Trefferquote gegen deine Urteile).
3. **Prüfrunde** (Tab): Bereiche in Sichtbarkeits-Reihenfolge (Start/Optionen → Joppa →
   Hauptquest → Meldungen → Gespräche → Dinge → Welt/Lore); je Bereich zuerst offene
   Markierungen, Prüf-Befunde, Triage-Schwere. Tasten **G**/Enter geprüft · **M** markieren
   (vorher die fehlerhafte Stelle im deutschen Wert mit der Maus auswählen, Kategorie +
   Notiz) · **N**/→ weiter · **B**/← zurück · **E** Editor. Modus **Stichprobe**: feste
   Zufallsauswahl (50 je Bereich, Seed bleibt) mit Fehlerquote = markiert/bearbeitet —
   ohne Befunde gilt ein Bereich mit wenig Sichtbarkeit als vertretbar.
4. **Korrektur**: `py build/curator/tools/review_fix.py export` → Agenten nach
   `_work/REVIEWFIX_RULES.md` → `review_fix.py import <batch>` → Vorschläge-Tab. Gate
   `review-fix` lässt nur Änderungen an der markierten Stelle (± 16 Zeichen) zu; Annehmen
   setzt die Markierung auf erledigt — danach in der Prüfrunde erneut „geprüft“.
5. **Playtest** (Tab): Befund mit Screenshot (Strg+V) und optional uid → „Behoben“ =
   zu verifizieren → nach dem nächsten Spiel-Lauf „bestätigt“ oder „weiterhin falsch“.
   String-Miss im neueren Player.log setzt automatisch „wieder aufgetaucht“.
   Ablage `data/findings/findings.json` (committbar), Screenshots gitignoriert.

Außerdem: **Verlauf** je Eintrag im Editor (Git-Commits der Zeile + Vorschlags-Batches)
und **Konkordanz** im Glossar-Tab (englischer Begriff → alle deutschen Fassungen).

## Abdeckung, fehlende Einträge, Spiel-Updates

- **Messung** (`coverage.py`) ist auf die Manifest-Struktur abgestimmt: Container-
  Text vor Kind-Elementen (`<description>▶<p>…`) zählt als abgedeckt, wenn die
  deutschen Kinder Text haben; Elemente mit übersetztem Namen (`zone`, `step`,
  `quest`, `location`, `pregen`, `relictypemapping` — `xmlscan.POSITIONAL_TAGS`)
  werden über ihre Position identifiziert; Anker Name/ID/Command wie `xmlscan`;
  leere Marker und Booleans sind keine Einheiten. `xmlscan.covkey` folgt demselben
  Schema (Test `test_covkey_parity_with_xmlscan`).
- **Fehlende String-Einträge:** `py build/curator/tools/missing_batches.py export`
  → `data/proposals/_work/new-*.input.json` (mit deutschen Nachbarn derselben Quelle),
  Agenten übersetzen nach `_work/NEW_RULES.md`, `… import <batch>` legt
  **Neuanlage-Vorschläge** (`op: create`) an; Annehmen = `writer.create_string_entry`.
  Prüfung für Neuanlagen: jede Token-Rolle der Vorlage im Deutschen, Markup
  ausgewogen, Anrede du, kein konjde ohne Subjekt.
- **Fehlende Nicht-String-Einträge** (EffectsDetails-Templates, Blueprint-Attribute,
  Optionen): `py build/curator/tools/insert_blueprint.py <batch> [--write]` fügt
  byte-erhaltend ein (Trockenlauf zuerst; jede bestehende Einheit behält uid + Wert).
- **gnarf/caves-of-qud-example-language** ist nur ein versionierter Spiegel von
  `StreamingAssets/Base/ExampleLanguage` (keine Code-/Setup-Referenz). Der lokale
  Versionsvergleich im Tab Abdeckung ersetzt ihn: nach einem Spiel-Update zeigt er,
  was neu/entfernt/geändert ist; danach „Snapshot übernehmen".

## Weitere Quellen & Layouts

- `HistorySpice.jsonc` ist als Datenquelle eingebunden (`jsonscan.py`):
  jede Zeichenkette eine Einheit mit JSON-Pfad, Englisch aus dem Spiel-Original,
  Schreiben byte-genau mit JSON-Escaping. Vorschau als **Gewürz-Liste** (alle
  Varianten des Eintrags).
- Weitere Layouts: **Buch** (Books.de.xml, blättern ◀ ▶), **Quest-Journal**
  (Erfolg, Hagiograph, Schritte), Karte gruppiert jetzt das innerste benannte
  Element (Mutation, Fähigkeit, Kreatur).
- **Kalibrieren** (Szenen-Werkzeugleiste): Spiel-Screenshot als halbtransparente
  Ebene über die Vorschau legen, Breite angleichen, je Layout in `config.json`
  speichern.

## Test-Loop (Tests laufen IM SPIEL)

1. Test im Tab „Tests" anlegen (oder im Editor „Test aus Eintrag erstellen").
2. Tab „Protokoll & Abgleich" → **Abgleichen** (kopiert auch CuratorTests.json
   in den Mod-Ordner).
3. Spiel starten (lang-experimental, Mod aktiv) — `VariableReplacers.CuratorTests()`
   läuft beim Mod-Load und loggt `[QudDE] curator-test <id> PASS/FAIL`.
4. Tab „Tests" neu laden: Ergebnisse + Staleness-Badges.

## Tool-Selbsttests

```
py -m unittest discover -s build/curator/tests
```

- `test_xmlscan.py` — Scanner ≙ ElementTree über alle 44 Dateien (Parität,
  Spans, uid-Eindeutigkeit)
- `test_roundtrip.py` — No-op-Saves byte-identisch über JEDE Einheit;
  Mutations-/Restore-Test; Ausbruchs-, 409- und Naming-Guards; Neuanlage
- `test_german.py` — WeakConjugate/GuessGender-Parität mit den C#-Vektoren
- `test_plausi.py` — jede Plausibilitätsregel findet ihren Original-Defekt; Korpus 0 error
- `test_lint.py` — Lint-Baseline (0 error-Befunde im Korpus) + Registry
- `test_grammar_emu.py` — Token-Emulation gegen `[VariableExample]`,
  Pipeline-/Verb-Vektoren und CuratorTests.json (live aus dem C# geparst)
- `test_scenes.py` — Context-ID-Vergabe gegen das ▶-Manifest, Szenenaufbau,
  Listenfilter/Nächste/Knotenkarte (braucht die Spieldateien, sonst übersprungen)
- `test_context_lint.py` — K1–K4/G1/G2-Heuristiken, Glossar-Datei, Korpus-
  Fixtures (Otho, AIWiring, Croc), K1-Neuanlage auf einer Dateikopie
- `test_proposals.py` — Prüf-Gate, K3-Assistent, Annehmen/veraltet auf einer
  Kopie, Neuanlagen (op=create), Löschen verwaister Einträge, JSON-Writer
- `test_coverage.py` — Mess-Artefakte (Container, Zonen/Schritte, ID-Anker, leere
  Marker, Booleans), covkey-Parität mit xmlscan, Versions-Snapshot-Diff
- `fixtures.py` — `defect_copy()`: Kopie der String-Tabellen mit gezielt
  eingebauten K1/K2/K3-Defekten (der echte Korpus ist bereinigt, die Regeln
  brauchen trotzdem Testfälle)
- `test_levels.py` — K7 Konsistenz + Ausnahmen, P1 Parität, Schwere je Regel,
  error blockt nur NEUE Befunde beim Speichern
- `test_review_queue.py` — Bereiche, Reihenfolge, stabile Stichprobe, Markierung mit Stelle
- `test_review_fix.py` — Span-Gate review-fix, Annehmen schließt Markierung, Triage-Gewicht
- `test_findings.py` — Playtest-Statusfluss, Auto-Regression, Verlauf, Konkordanz
- `qudrender.test.js` — Markup-Parser/Umbruch der Vorschau:
  `node build/curator/tests/qudrender.test.js`

Nach Änderungen an `CODE/*.cs` zusätzlich das Smoke-Gate:
`dotnet build build/smoke/smoke.csproj -c Release` (0 Fehler Pflicht).

## Manuelle E2E-Checkliste

1. Server starten → „Fackel" suchen → Beschreibung editieren → Speichern →
   `git diff` zeigt genau eine geänderte Zeile → per UI zurücksetzen +
   Speichern → `git diff` leer.
2. Tab Lexikon → Nomen + Genus eingeben → „Konsequenzen prüfen" listet
   betroffene Komposita.
3. Tab Tests → Seed-Test `torch-a-dativ` sichtbar → Abgleichen → Spiel
   starten → Tab Tests zeigt PASS.
4. Tab Protokoll: exakt 7 benigne Misses ✓, 4 Compiler-MODWARNs (benigne,
   CS0618), Selbsttests PASS.
