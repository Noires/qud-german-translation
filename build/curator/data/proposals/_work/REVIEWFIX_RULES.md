# Regeln: Markierte Fehlerstellen korrigieren

Eingabe `<batch>.input.json`: `{batch, units: [{uid, context, english, value, span, category, note}]}`.
Eine Prüferin hat in `value` eine Fehlerstelle markiert: `span` = `{start, end, text}`
(Zeichenpositionen im `value`), dazu Kategorie und Notiz. Ausgabe `<batch>.output.json`:
`{"items": [{"uid": ..., "new_value": "...", "note": "..."}]}` — ein Eintrag je Einheit;
lass `new_value` weg (oder gleich `value`), wenn du die Markierung für unbegründet hältst,
und begründe das in `note`.

## Was du tust
- Korrigiere **nur die markierte Stelle**. Höchstens 16 Zeichen links/rechts davon dürfen
  mitgeändert werden (z. B. Artikel oder Endung vor dem markierten Nomen) — sonst lehnt
  das Prüf-Gate ab.
- Halte dich an die Notiz der Prüferin; sie hat Vorrang vor deinem Geschmack.
- Ist keine Stelle markiert (`span` null), gilt der ganze Wert — trotzdem so wenig wie möglich ändern.
- Spieler-Anrede ist **du**. „Ihr Licht“/„Bei Ihrem Licht“ (die Göttin) bleibt groß.

## Harte Regeln
- `=…=`-Tokens bleiben byte-genau erhalten (keine neuen, keine entfernten), außer die Markierung
  liegt genau auf einem Token und die Notiz verlangt dessen Änderung.
- `{{…}}`-Farbcodes ausgewogen lassen, Zeilenumbrüche erhalten.
