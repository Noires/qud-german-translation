# du-Umstellung — Regeln für Konvertierungs-Agenten

Ziel: Deutsche Übersetzungswerte (Caves of Qud, Mod „CavesOfQudGermanLang") von der
Höflichkeitsanrede des Spielers („Ihr"/„Sie") auf „du" umstellen. Anrede-Richtlinie
seit 2026-10-22: NPCs duzen den Spieler, der Spieler duzt NPCs.

## Ein-/Ausgabe
- Eingabe: `<batch>.input.json` = `{batch, file, units:[{uid, context, english, value}]}`
  (`english` = englisches Original, `value` = aktueller deutscher Wert).
- Ausgabe: `<batch>.output.json` im selben Ordner, exakt
  `{"items":[{"uid":"…","new_value":"…","note":"optional, kurz"}]}` — UTF-8, gültiges JSON.
  Nur geänderte Einheiten aufnehmen. KEINE anderen Dateien ändern.
- Hilfsskripte nur mit eindeutigem Namen (z. B. `du_<batch>.py`) im Scratchpad
  `C:\Users\dusti\AppData\Local\Temp\claude\C--Users-dusti-Documents-CavesOfQudGermanLang\b1fc90e0-5c5f-4530-95e4-36209e040c2a\scratchpad`.

## Regeln
1. **Pronomen nach Kasus:** Ihr→du (Nom.), Euch→dich (Akk.) oder dir (Dat.) — nach
   regierendem Verb/Präposition entscheiden: mit/zu/von/aus/bei/nach/seit/gegenüber → dir;
   für/durch/gegen/ohne/um → dich; Dativ-Verben (empfehlen, sagen, geben, danken, helfen,
   folgen, gehören, verkaufen, zeigen, fehlen, gelingen, erlauben, vertrauen) → dir;
   reflexiv „Ihr … Euch" → „du … dich/dir". Euer/Eure/Eurem/Euren/Eurer/Eures →
   dein/deine/deinem/deinen/deiner/deines. „Sie"-Form (Sie/Ihnen/Ihr(e) als höfliches
   Possessiv) → du/dir/dich/dein ebenso.
2. **Verben** mit dem Spieler als Subjekt in die 2. Sg.: habt→hast, seid→bist, könnt→kannst,
   wollt→willst, müsst→musst, dürft→darfst, sollt→sollst, werdet→wirst, wisst→weißt,
   tut→tust, seht→siehst, nehmt→nimmst, gebt→gibst, esst→isst, lest→liest, tragt→trägst,
   haltet→hältst, lasst→lässt, fallt→fällst, schlaft→schläfst, wärt→wärst, hättet→hättest,
   würdet→würdest, konntet→konntest; regelmäßig -t → -st (macht→machst, findet→findest,
   reist→reist); Präteritum -tet → -test. **Imperative** → Singular („Lebt und trinkt" /
   „Leben Sie und trinken Sie" → „Lebe und trinke"; Nehmt→Nimm, Seht→Sieh, Gebt→Gib,
   Kommt→Komm, Sprecht→Sprich, Kehrt zurück→Kehre zurück, Lasst uns→Lass uns,
   Drückt→Drück, Wählt→Wähle).
3. **Kleinschreibung:** du/dich/dir/dein klein, außer am Satz-/Zeilenanfang.
4. **Nicht anfassen:** 3. Person „Sie/ihr/ihre/Ihre" = she/her/they/their/it (am Englischen
   prüfen; z. B. „Ihr Licht" = die Göttin). Echte Gruppen-Anrede („you all", „you lot") →
   kleines Plural „ihr/euch/euer".
5. **KRITISCH:** Nichts innerhalb von `=…=`-Tokens ändern (=subject.T=, =player.reflexive=,
   =verb:…=, =subject.konjde:…= …), keine `{{X|…}}`-Begrenzer, keine `&X`/`^X`-Codes,
   keine Zeilenumbrüche. Die Multimenge der `=tokens=` muss byte-identisch bleiben.
   Wenn ein Token das Verb des Spielers erzeugt (=subject.konjde:sein=, =subject.Does:…=),
   das Token lassen — die Engine gibt bereits die du-Form aus. Nur wörtlichen Text ändern.
   Keine sonstigen Umformulierungen, keine Tippfehler-Korrekturen (alte Schreibung wie
   „daß/müßt" beibehalten: „mußt").
6. Einheiten ohne nötige Änderung weglassen. Unsicher → trotzdem umstellen + kurze `note`.

## Vorgehen
Jede Einheit selbst entscheiden (Kasus, Verbkongruenz, Imperative) — rein mechanisches
Regex-Ersetzen ist NICHT zulässig. Entscheidungen als exakte Teilstring-Ersetzungen
anwenden, damit der Rest byte-identisch bleibt.

## Abschlussprüfung (Python, Pflicht)
- Ausgabe parst; jede uid existiert in der Eingabe, keine doppelt.
- `=token=`-Multimengen (Regex `=([^=\s][^=]*?)=`) identisch zur Eingabe.
- Zeilenumbruch-Anzahl unverändert.
- Kein großgeschriebenes Ihr/Euch/Euer/Eure* mehr, das den Spieler anspricht.

Bericht: Anzahl geschrieben / ausgelassen, zweifelhafte Fälle kurz.
