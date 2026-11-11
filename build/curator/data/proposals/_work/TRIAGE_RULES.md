# Regeln: LLM-Triage (MQM-Stil) — nur Sortierhilfe

Eingabe `<batch>.input.json`: `{batch, units: [{uid, context, english, value}]}` —
`english` ist die Spiel-Vorlage, `value` die deutsche Übersetzung (Caves of Qud, Deutsch,
Spieler wird **geduzt**). Ausgabe `<batch>.output.json`:
`{"items": [{"uid": ..., "errors": [{"text": "<genaue Stelle im value>", "category": ..., "severity": ..., "note": "..."}]}]}`
— **für jede Einheit genau ein Eintrag**; `errors: []`, wenn nichts falsch ist.

## Was du tust
Du bist Lektor:in. Melde nur **echte Fehler**, die ein deutscher Spieler bemerken würde.
Fast alle Texte sind bereits ordentlich — „keine Fehler“ ist die häufigste richtige Antwort.
Stilistische Vorlieben, alternative Formulierungen und „ginge auch anders“ sind KEINE Fehler.

## Kategorien (category)
- `bedeutung` — Inhalt falsch/fehlend/hinzugefügt gegenüber dem Englischen
- `kasus-genus` — falscher Fall, falsches Genus, Artikel passt nicht
- `verb` — falsche Verbform/Konjugation/Wortstellung
- `anrede` — Spieler nicht mit du angesprochen (Ihr/Sie/Euch); Ausnahme: „Ihr Licht" = Göttin
- `begriff` — Fachbegriff uneinheitlich oder falsch
- `unuebersetzt` — englischer Rest
- `tippfehler` — Rechtschreibung/Zeichensetzung
- `stil` — nur bei klar holprigem/ungrammatisch wirkendem Deutsch

## Schwere (severity)
- `critical` — Sinn verdreht, unverständlich, oder Spieler wird falsch geleitet
- `major` — deutlich falsch (Grammatikfehler, englischer Rest, falsche Anrede)
- `minor` — kleiner Fehler (Tippfehler, leicht holprig)

## Tokens nicht bewerten
`=…=`-Tokens werden zur Laufzeit ersetzt (Namen, Pronomen, Verbformen wie
`=subject.konjde:sehen=` → „siehst“/„sieht“). Bewerte den Satz so, als stünden dort passende
Wörter; melde Token nur, wenn sie offensichtlich am falschen Platz stehen.
`{{X|…}}` sind Farbcodes — ignorieren. Die Stelle (`text`) muss wörtlich im `value` vorkommen.
