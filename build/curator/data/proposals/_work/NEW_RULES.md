# Neue Einträge übersetzen — Regeln für Übersetzungs-Agenten

Projekt: deutsche Übersetzung von Caves of Qud (Mod „CavesOfQudGermanLang").
Die Einträge fehlen bisher; du lieferst den deutschen Wert (`Value`) zu einer
englischen Vorlage (`id`, byte-exakt = Lookup-Schlüssel).

## Ein-/Ausgabe
- Eingabe `<batch>.input.json`: `{batch, file, units:[{context, id, english, neighbors:[{english, value}]}]}`.
  `neighbors` = vorhandene deutsche Einträge derselben Quelle — Ton/Terminologie übernehmen.
- Ausgabe `<batch>.output.json` im selben Ordner:
  `{"items":[{"context":"…","id":"…","new_value":"…","note":"optional"}]}` —
  `context` und `id` EXAKT aus der Eingabe kopieren (nicht verändern!). UTF-8, gültiges JSON.
- Keine anderen Dateien ändern. Hilfsskripte nur mit eindeutigem Namen im Scratchpad
  `C:\Users\dusti\AppData\Local\Temp\claude\C--Users-dusti-Documents-CavesOfQudGermanLang\b1fc90e0-5c5f-4530-95e4-36209e040c2a\scratchpad`.

## Sprache & Ton
- Qud-Ton: leicht archaisch, poetisch, aber klar. Spielmeldungen knapp.
- **Anrede: „du"** (Richtlinie). Spieler: du/dich/dir/dein; Verben 2. Sg.
- Begriffe aus `C:\Users\dusti\Documents\CavesOfQudGermanLang\build\curator\data\glossary.json`
  (z. B. Baetyl n.) und aus den `neighbors` übernehmen.

## Tokens (Grammatik-Engine, siehe docs/GRAMMAR_ENGINE.md)
`=…=`-Tokens werden zur Laufzeit ersetzt. Regeln:
1. **Jede Rolle** der Vorlage (`subject`, `object`, `player`, `item` …, der Teil vor dem
   ersten Punkt) muss im Deutschen wieder vorkommen. Nicht-grammatische Tokens
   (`=amount.signed=`, `=stat.narration=`, `=commandKey:…=`, `=spice:…=` …) unverändert übernehmen.
2. **Namen mit Kasus** statt englischer Artikel-Tokens, wo die Satzstellung es verlangt:
   `=object.the.name=` → `=object.akkusativ=` / `=object.dativ=` (nach mit/von/zu/aus/bei)
   / `=object.genitiv=` / `=object.nominativ=`; unbestimmt `=object.a.dativ=` usw.
   Großschreibung am Satzanfang: erster Buchstabe groß (`=subject.The.name=`, `=object.Dativ=`).
3. **Verben:** `=X.Does:verb=` (englisch: Name + Verb) wird zu
   `=X.The.name= =X.konjde:<deutscher Infinitiv>=` (am Satzanfang `The` groß).
   Kleingeschrieben `=X.does:verb=` → `=X.the.name= =X.konjde:<inf>=`.
   Nur NICHT-trennbare Verben verwenden (kein „angreifen" → „attackieren"; kein „aufheben").
   `=X.Doesly:adverb:verb=` → `=X.The.name= =X.konjde:<inf>= <Adverb>`.
   `=X.it.does:verb=`/`=X.It.does:…=` → `=X.subjective= =X.konjde:<inf>=` bzw. großes `Subjective`.
4. **Possessiv:** `=X.its=` vor einem Nomen mit Kasus/Genus annotieren: `=X.its:akk:f= Klinge`;
   `=X.the.name's= Y` → `=X.the.name's= Y` (vorangestellter Genitiv) ist ok.
5. Pronomen-Tokens (`=X.subjective=`, `=X.objective=`, `=X.reflexive=`) übernehmen.
6. Farbcodes `{{X|…}}`, `&X`, `^X` und Zeilenumbrüche aus der Vorlage übernehmen
   (Text darin übersetzen, Begrenzer erhalten).

## Abschlussprüfung (Python, Pflicht)
- Ausgabe parst; jedes `(context, id)` existiert in der Eingabe; keine Duplikate.
- Rollen-Menge (Teil vor dem ersten Punkt in `=…=`) der Vorlage ⊆ Rollen im Deutschen.
- `{{`/`}}` ausgewogen, Anzahl `=` gerade.
- Keine Ihr/Euch/Euer/Sie-Anrede des Spielers.
- Kein `konjde` für eine Rolle ohne Namens-/Pronomen-Token derselben Rolle, wenn die Vorlage `Does` hatte.

Bericht: Anzahl übersetzt / ausgelassen (mit Grund), unsichere Fälle kurz.
