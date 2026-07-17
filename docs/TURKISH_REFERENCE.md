# Der türkische Referenz-Mod — Extrakt für unsere Zwecke

_Erstellt 2026-07-17 aus dem Quellstand des offiziellen türkischen Mods (Freehold Games
and Community Contributors). **Das Archiv `docs/archive/caves-of-qud-turkish-main/` ist
gitignoriert** und existiert nur lokal — dieses Dokument ist die dauerhafte Aufzeichnung.
Wenn das Archiv vorliegt, sind deren `Notes/README.md` (Engine-Guide) und
`Notes/TranslatorsGuide.md` (Onboarding) die Primärquellen._

## 1. Warum dieser Mod die Referenz ist

Es ist die einzige offizielle, 100 % native Lokalisierung (kein Harmony, keine DLL) —
derselbe Rahmen, in dem wir arbeiten. Wo sie eine Wand dokumentiert haben (z. B. das
geschelfte Body-Part-Experiment in `UnusedDelegates.tr.cs`), ist das für uns ein
verlässliches „dort ist wirklich eine Wand".

## 2. Architektur-Kontrast: Suffixe vs. Artikel

Türkisch ist agglutinierend: Grammatik passiert als Suffix AM WORTENDE (ev → evde „im
Haus"), mit Vokalharmonie und Konsonantenerweichung. Deutsch flektiert VOR dem Nomen
(Artikel + Adjektivendungen). Daraus folgen spiegelbildliche Architekturen:

| | Türkisch | Wir (Deutsch) |
|---|---|---|
| Schwerpunkt | ~60 **Postprocessors** (`\|dative`, `\|yor`, `\|possessive` …) + Kasus-Replacer | **Replacer** (Kasus-/Artikel-/Possessiv-Phrasen), 1 Postprocessor |
| Kern-Engine | `CaserHandler` + Vokalharmonie (`TurkishVowelHarmonizerSimple/Complex`) + Erweichung (`SoftenWord`, k→ğ/p→b/t→d/ç→c) | `BuildDefinitePhrase`-Familie + `GuessGender` + `AdjEnding`-Tabellen |
| Kasus-Aufruf | dreifach: `.dative` / `\|dative` / `.caser:dative` | `=X.dativ=` (+ `a.`-Variante, + Parameter) |
| Tempora | yor (kontinuierlich), di (Vergangenheit), ecek (Futur), ar (Präsens) je als Postprocessor-Familie inkl. Personenformen (yorum/dim/cagim …) | nur Präsens (`konjde`, `does`) — siehe Lückenliste in GRAMMAR_ENGINE |
| Zahlwörter | `TranslatorTurkish`: GetCultureInfo/Ordinal/Cardinal/Multiplicative | identisches Muster (`TranslatorDeutsch`), plus unsere Artikel-/DisplayName-Hooks, die sie NICHT haben |

Ihre Replacer-Familien (Namen sind zugleich türkische Suffixe): Kasus `dative/ya`,
`genitive/nin`, `ablative/dan`, `locative/da`, `accusative/yi`, `instrumental/yle`;
Possessive `possessive/si` (vier Overloads inkl. Possessor-Objekt); Tempora
`di/past`, `ar/er`, `yor/continuous`, `ecek/future`, `sa/wish`; dazu Utilities wie
`maybePronoun` (redundantes Subjekt fallen lassen), `suffixer`, `nounEnd`,
`its.item`-Override (unser Vorbild), `countable.name`, `andList`.

## 3. Das PUA-Marker-System (vollständig festgehalten)

Das Spiel reserviert `U+E700–U+E7FF` als beim Rendern **unsichtbare** Flag-Zone
(`QUD_PUA_FLAG_START/END` in TextConstants). Der türkische Mod nutzt sie als
Metadaten-Kanal DURCH die Text-Pipeline (Konstanten in `Translator.tr.cs`):

| Konstante | Zeichen | Zweck |
|---|---|---|
| `COMPOUND_MARK` | U+E70C | „Suffix bereits angefügt" — Idempotenz-Schutz. Alle Helfer prüfen `Contains(COMPOUND_MARK)` vor erneutem Anfügen/Erweichen |
| `DATIVE_MARK` | U+E7DA | Kasus-Metadatum am Wort |
| `ACCUSATIVE_MARK` | U+E7AC | dito (Default-Kasus für Verben ist Akkusativ → unmarkiert) |
| `LOCATIVE_MARK` | U+E7DE | dito |
| `ABLATIVE_MARK` | U+E7AB | dito |
| `INSTRUMENTAL_MARK` | U+E711 | dito |

**Schreibweisen:** XML `&#xE70C;`, JSON/C# `\uE70C`. **Tamlanan-Regel** (aus ihrem
Notes/README): Bei bereits possessiv-markierten Komposita steht die Compound-Mark nach dem
Wortstamm — „kazı alanı" wird zu `kazı alan\uE70Cı` (JSON) bzw. `kazı alan&#xE70C;ı` (XML).
Ein Postprocessor liest später `Verb.Contains(DATIVE_MARK)` und wählt die passende
Suffix-Behandlung — so wandert Kasus-Information durch Stellen, an denen kein
Token-Parameter durchgereicht werden kann.

**Farb-Markup:** zentrale Funktion `ModifyColoredText(input, transform, SuffixOutside)` —
zerlegt `{{farbe|text}}` AM WORTENDE, transformiert den Innentext. `SuffixOutside=true`
bei Eigennamen: Suffix landet AUSSERHALB des Tags (`{{M|Mehmet}}'i` — Name bleibt farbig,
Suffix neutral); Gattungswörter bekommen es innen (`{{c|çiçeği}}`). **Eingestandene
Grenzen** (Kommentar im Code): Tags MITTEN im String werden nicht behandelt, `&X`-Kurzcodes
gar nicht. Unser wortweises `SplitColor`/`DeclineAdj` deckt beides ab — hier sind wir
weiter. Großschreibung durch Tags delegieren beide an die Engine (`InitUpper`), sie mit
tr-Culture-Sonderfällen (ı/İ).

## 4. Das Ausnahme-Wörterbuch-Muster

Ihre Heuristiken (Vokalharmonie, Erweichung) sind IMMER mit Override-Tabellen gepaart,
die beim Übersetzen wachsen: `SofteningExceptions` (nicht erweichen),
`SofteningNonExceptions` (trotz Kürze erweichen), `NKSofteningWords` (k→g-Klasse),
`HarmonyExceptions` (v. a. arabische Lehnwörter, suffigieren „als ob auf e endend"),
`NarrowVowelDroppingWords`, `PresentTenseExceptions`. Deren Anweisung an Übersetzer:
*„Keep them in mind when translating and add to them when necessary."*

Das ist strukturell exakt unser `GenderLexicon.tsv`-Ansatz (Heuristik + Suffix-Vererbung +
Ausnahme-Einträge wie gewand≠wand). **Gemeinsame Lehre: nie reine Heuristik — Heuristik
plus lebende Override-Tabelle, deren Pflege Teil des Übersetzungs-Workflows ist.**

## 5. Konventionen aus ihren Notes (übertragbar)

- **Spice-Schlüssel:** Eltern-Keys bleiben identisch, übersetzte Blatt-Keys bekommen ein
  `=`-Suffix (`"fate"` → `"fate="`). Bei Mehrdeutigkeit eines englischen Worts wird der
  Schlüssel GESPALTEN (Beispiel „crowned" → `crowned` + `crownedPast`) — direkt relevant
  für unsere HistorySpice-Arbeit (Verb-vs-Adjektiv-Ambiguitäten wie „hold", „killed").
- **Token-Syntax-Regeln** (gelten auch für uns): Replacer ketten NICHT —
  `wort.r1.r2.r3` ist EIN Replacer namens `r1.r2.r3`; `:` = Parameter, `#` = GameObject-
  Argument, `|` = Postprocessor (die ketten, sehen aber nur den aktuellen String).
- **Test-Wishes im Spiel:** `testlangreplacers`, `testreplacers`, `sultanhistory` —
  nützlich zusätzlich zu unseren Load-Selbsttests. Ihre
  `VariableStativeExampleAttributes.cs` definiert die Attribut-Typen, die diese Wishes
  speisen.
- **Buchhaltung:** `Untranslated.tr.xml` mit absichtlich ungültigem `Lang`-Attribut für
  bewusst identische Templates — haben wir als `Untranslated.de.xml` übernommen.
- **Konsistenz-Glossar:** `Notes/dictionary.md` hält vereinbarte Begriffe fest
  (Snapjaw→Çatçene …), inkl. `??`-Markierung für Unentschiedenes. Unser Pendant sind die
  etablierten Begriffe im Bestand (Schnappkiefer, Ziegenvolk, …) — ein eigenes Glossar
  wäre ein sinnvoller Ausbau.
- **Eigennamen nach KLANG transliterieren**, nicht nach Schreibung (einsprachige Spieler
  sprechen sonst falsch aus) — für Deutsch weniger kritisch, aber dieselbe Denkweise gilt
  für unsere frei eingedeutschten Kunstwörter (Schrott-Papasan, Elektrodikus).
- **`maybePronoun`:** lässt redundante Subjektpronomen fallen (Türkisch ist pro-drop).
  Für Deutsch nicht anwendbar, aber das Muster „Kontext-Zustand über
  `Context.State`/`Invocation` statt Parameter-Threading" ist merkenswert.
- **Ihr geschelftes Body-Part-Experiment** (`UnusedDelegates.tr.cs`) und ihre nur 4
  Translator-Overrides bestätigen zwei unserer Entscheidungen: Paperdoll = warten, und
  der Translator-Provider ist bewusst schmal zu halten.
- **Ihre Skripte** (Node): `findMissingIds.js` (Strings-Manifest-Diff mit
  Ähnlichkeits-Matching für umbenannte IDs), `findMissingKeys.js` (HistorySpice-Key-Diff),
  `checkHotkeys.js` (Hotkey-Kollisionen). Unser Pendant: `build/tools/coverage_audit.py`;
  ein ID-Diff-Tool nach ihrem Vorbild wäre bei Spiel-Updates nützlich.

## 6. Verdikt-Tabelle (Stand 2026-07-17)

| Technik | Verdikt | Begründung |
|---|---|---|
| `its.item`-Override mit Besitzer+Item | **übernommen** | Unser `ItsItemDe` folgt dem Muster, plus Kasus-Parameter |
| Untranslated-Buchhaltungsdatei | **übernommen** | `Untranslated.de.xml` |
| Translator-Provider für Zahlen/Kultur | **übernommen** | `TranslatorDeutsch`, erweitert um Artikel-/DisplayName-Hooks |
| Heuristik + Ausnahme-Tabellen | **übernommen** | `GenderLexicon.tsv` + Suffix-Vererbung |
| Statische Kasus-Suffix-Postprocessors (`\|dative` …) | **angepasst** | Deutsch braucht Phrasen VOR dem Nomen → Kasus-REPLACER mit Parametern statt Postprocessors |
| `ModifyColoredText`/`SuffixOutside` | **angepasst** | wortweises `SplitColor` (deckt auch Mittel-Tags und `&X`-Codes ab); Eigennamen-Genitiv-`s` außen entspricht `SuffixOutside` |
| PUA-Marker (U+E70x) | **notiert, nicht umgesetzt** | Explizite `:kasus`-Parameter sind lesbarer; PUA nur falls Kasus durch parameterlose Pfade muss oder Idempotenz-Schutz nötig wird (OPEN_ISSUES „Technik-Option") |
| Spice-Key-Splitting bei Ambiguität | **bei Bedarf übernehmen** | Werkzeug für HistorySpice-Mehrdeutigkeiten |
| Tempus-Postprocessor-Familien (yor/di/ecek) | **nicht anwendbar** | Deutsche Tempora sind analytisch (haben/werden + Partizip) — kein Suffix-Problem; siehe Lückenliste in GRAMMAR_ENGINE |
| Vokalharmonie-Maschinerie | **nicht anwendbar** | Deutsch hat keine Vokalharmonie |
| `maybePronoun` (Subjekt-Drop) | **nicht anwendbar** | Deutsch ist nicht pro-drop |
| Node-Skripte (ID-Diff) | **Kandidat** | Bei Spiel-Updates: umbenannte/neue IDs finden; Python-Port neben `coverage_audit.py` |

## Verwandte Dokumente

- `docs/GRAMMAR_ENGINE.md` — unsere Engine im Detail.
- `docs/OPEN_ISSUES.md` — Wait-Liste inkl. der PUA-Technik-Option.
