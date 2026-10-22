# Regeln: Weichen-Token-Argumente übersetzen (Lint K5)

Eingabe `<batch>.input.json`: `{batch, file, units: [{uid, context, english, value}]}`.
`english` = Spiel-Vorlage (byte-exakte ID, nie anfassen), `value` = aktuelle deutsche Übersetzung.
Ausgabe `<batch>.output.json`: `{"items": [{"uid": ..., "new_value": ..., "note": "..."}]}` —
für JEDE Einheit genau ein Eintrag (uid exakt übernehmen).

## Das Problem
Weichen-Tokens geben eines ihrer Argumente WÖRTLICH aus:
`=ifplayerplural:<Mehrzahl>:<Einzahl>=` (Spieler), `=X.isPlural:<Mehrzahl>:<Einzahl>=` /
`=X.ifPlural:…=` (Objekt/Fraktion X). Die Übersetzung hat die englischen Argumente stehen
lassen — im Spiel steht dann „Thou hast die Welt verändert" bzw. „Die Mopango despises …".

## Was du tust
1. Jedes Argument jedes Weichen-Tokens ins Deutsche übertragen. Reihenfolge bleibt:
   **erst Mehrzahl, dann Einzahl**. Der Spieler ist fast immer Einzahl.
2. **Anrede-Richtlinie du/du**: Spieler-Einzahl = du, Spieler-Mehrzahl = ihr (klein).
   `=ifplayerplural:Ye have:Thou hast=` → `=ifplayerplural:Ihr habt:Du hast=`;
   `=ifplayerplural:ye:thee=` → je nach Kasus im deutschen Satz `=ifplayerplural:euch:dich=`
   oder `=ifplayerplural:euch:dir=`; `=ifplayerplural:your:thy=` → mit Endung passend zum
   Nomen, z. B. `=ifplayerplural:eure:deine=`.
3. Deutsche Wortstellung: Wenn das Verb im deutschen Satz woanders steht, Satz so umbauen,
   dass er für BEIDE Zweige grammatisch ist; ggf. Verb mit in das Token nehmen
   (`=ifplayerplural:Braucht ihr:Brauchst du=`), oder Verb-Teil auslagern, wenn er gleich ist.
   Großschreibung am Satzanfang im Argument selbst.
4. **Doppelungen entfernen**: Hat die bisherige Übersetzung die Anrede zusätzlich ausgeschrieben
   („=ifplayerplural:ye have:thou hast= du eines der Kinder befreit hast"), nur EINE Fassung
   behalten (das Token mit deutschen Argumenten).
5. Englische Reste im übrigen Satz, die in den Weichen-Kontext gehören („Wouldst",
   „Needest thou") mit übersetzen. Den Rest des Satzes nur anfassen, wo nötig — kein
   Neu-Übersetzen ganzer Absätze; offensichtliche grobe Fehler im selben Satz darfst du
   mitkorrigieren (in `note` erwähnen).
6. Ton: Die Mopango sprechen altertümlich-feierlich. Das darf in der Wortwahl bleiben
   („wohlan", „gewiss"), aber die Anrede ist du/ihr, NIE Ihr/Euch/Sie.
7. Objekt-/Fraktions-Weichen in Spielmeldungen (`=faction.ifPlural:despise:despises=`):
   deutsche Verbform passend zum Subjekt — Mehrzahl zuerst
   (`=faction.ifPlural:verachten:verachtet=`). Bei Mengen-/Artikel-Weichen
   (`=object.isplural:one of :=`, `=object.isplural:these:this one=`) den deutschen Satz so
   bauen, dass beide Zweige grammatisch sind (Genus des Objekts ist unbekannt —
   neutrale Formen wie „eines von" / „diese:dieses" oder Umformulierung).
   Kontext/Englisch genau lesen, was die Weiche im Satz bewirkt.

## Harte Regeln (das Prüf-Gate lehnt sonst ab)
- Alle anderen Tokens (`=…=`) bleiben exakt erhalten (gleiche Anzahl, gleicher Text).
  Nur die Argumente der Weichen-Tokens ändern sich. Tokens nicht hinzufügen/entfernen.
- Kein englisches Wort (ye, thou, thee, thy, hast, art, wilt, you, your, have, are, is,
  …eth) mehr in Weichen-Argumenten.
- `{{…}}`-Markup ausgewogen lassen; `&#10;`-Zeilenumbrüche stehen im `value` als echte
  Zeilenumbrüche — so belassen.
- Kein „du/dich/dir/dein…" direkt nach einem `=ifplayerplural:…=`-Token (= Doppelung).
- Keine Ihr/Euch/Euer/Sie-Höflichkeitsform.
- Doppelpunkt `:` und `=` innerhalb von Argumenten sind verboten (Trennzeichen!).
