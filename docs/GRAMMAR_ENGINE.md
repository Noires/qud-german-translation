# Die deutsche Grammatik-Engine — Referenz

_Zuletzt verifiziert: 2026-07-17 gegen Commit `e4a0568`. Re-Verifikation: Smoke bauen
(`dotnet build build/smoke/smoke.csproj -c Release`), Spiel starten, `[QudDE]`-Selbsttestzeilen
in `Player.log` prüfen (alle PASS = die Beispiele in diesem Dokument gelten noch)._

> **Docs = Fakten, Skill = Verfahren.** Dieses Dokument erklärt, WIE die Engine funktioniert
> und WO ihre Grenzen liegen. Das Arbeitsverfahren (Finding-Diagnose, Checklisten) steht im
> Projekt-Skill `.claude/skills/qud-de-grammatik/SKILL.md`. Harte Kontrakte werden hier
> begründet und in `docs/OPEN_ISSUES.md` als Status geführt.
>
> **Drift-Regel:** Keine Zeilennummern oder Zählwerte in diesem Dokument. Token- und
> Funktionsnamen stehen exakt wie im Code (grep-bar, z. B. `rg '"konjde"' languages/lang-de/CODE/`).
> Verbindliche Beispiele mit Erwartungswerten leben NICHT hier, sondern in den
> `[VariableExample]`-Attributen und den Selbsttest-Tabellen (`SelfTestPipeline`,
> `SelfTestCases` in `VariableReplacers.de.cs`; `SelfTest` in `Translator.de.cs`) — sie werden
> bei jedem Spielstart ausgeführt.

## 1. Architektur auf einer Seite

Drei Pfade erzeugen deutschen Text; ein Finding gehört immer zu genau einem davon:

```
┌─ DATEN-SCHICHT ────────────────────────────────────────────────────────────┐
│ languages/lang-de/*.de.xml, HistorySpice.jsonc, Naming.de.xml,             │
│ LibraryCorpus.de.json. String-Tabelle: Lookup per (Context, ID) — die ID   │
│ ist das BYTE-EXAKTE englische Template. Value = deutsches Template mit     │
│ Tokens. Blueprint-Attribute (z. B. PrepMessageOther) per Load="Merge".     │
└──────────────┬─────────────────────────────────────────────────────────────┘
               │ Tokens (=subject.dativ=, =konjde:sehen=, …)
┌──────────────▼─────────────────────────────────────────────────────────────┐
│ TOKEN-ENGINE  languages/lang-de/CODE/VariableReplacers.de.cs               │
│ [HasVariableReplacer(Lang="de")] — Replacer & Postprocessor. Dispatch auf  │
│ Name + Parametertyp (NICHT Return-Typ); Override=true ersetzt das          │
│ englische Original. Lädt GenderLexicon.tsv + Verbs.json aus               │
│ languages/lang-de/COQDE/.                                                  │
└──────────────┬─────────────────────────────────────────────────────────────┘
               │ C#-Pfad (GameObject.The/.its_, XDidY, Zahlen-Tokens)
┌──────────────▼─────────────────────────────────────────────────────────────┐
│ TRANSLATOR-PROVIDER  languages/lang-de/CODE/Translator.de.cs               │
│ [LanguageProvider("de")] TranslatorDeutsch : TranslatorBase.               │
│ Erreicht C#-komponierte Zeilen, die NIE durch Tokens laufen: Artikel       │
│ (DefiniteArticle/IndefiniteArticle-Fallback), Possessivphrasen             │
│ (GameObjectDisplayName-Hook), Zahlwörter (Cardinal/Ordinal/…), de-DE.      │
└────────────────────────────────────────────────────────────────────────────┘
```

Nicht erreichbar (wartet auf offizielle Unterstützung, siehe OPEN_ISSUES „Waiting on
official localization support"): Paperdoll-Körperteilnamen, C#-Literal-Todesursachen,
Satzgerüste C#-komponierter Kampfzeilen („hits for 5 damage with").

## 2. Kasus-System (Token-Pfad)

**Definite Kasus-Tokens:** `nominativ`, `akkusativ`, `dativ`, `genitiv` —
`=object.dativ=` → „dem Krokodil". **Indefinite Varianten:** `a.nominativ`, `a.akkusativ`,
`a.dativ`, `a.genitiv` — `=object.a.dativ=` → „einem Krokodil". Gemeinsamer Kern:
`CaseName`/`IndefCaseName` → `BuildDefinitePhrase`/`BuildIndefinitePhrase`.

**Verhalten:**
- Spieler + Zweitperson → Pronomen statt Phrase: Nom „Ihr", Akk/Dat „Euch", Gen „Euer"
  (`PlayerPronoun`).
- Reflexiv (Objekt == Satzsubjekt, Akk/Dat) → „sich" (`IsReflexive`).
- Eigennamen (`HasProperName`) → nackter Name; Genitiv per `GenitiveNoun` („Barathrums").
- Plural (Engine-Flag `IsPlural`) → die/den/der-Pluralformen, keine indefiniten Artikel.

**Display-Parameter** (werden an `GetDisplayName` durchgereicht, `GermanName(obj, ctx)`):
`:single`, `:long`, `:withTitles`, `:asIfKnown`. **Besitz-Parameter:** `:itsPossessor` /
`:itsSubjectPossessor` hängt den Halter im Genitiv an („aus der Wasserhaut des
Schnappkiefers", `WithPossessor`); `:asPossessed` rendert Spieler-Besitz als dekliniertes
„Euer" und Kreaturen-Besitz mit Genitiv-Anhang.

**Konvention — der Übersetzer wählt den Kasus im Value:**

| Kontext im deutschen Value | Token |
|---|---|
| `mit / von / zu / aus / bei / seit / gegenüber` + Objekt | `=X.dativ=` / `=X.a.dativ=` |
| Wechselpräposition, Lage (in/an/auf/vor … „wo?") | `=X.dativ=` |
| Wechselpräposition, Richtung („wohin?") | `=X.akkusativ=` |
| direktes Objekt ohne Präposition | `=X.the.name=` reicht — Objektrolle rendert bereits Akkusativ (`CaseOf`) |
| „X des Y" | `=Y.genitiv=` |

**Upside:** explizit, lesbar, beim Übersetzen selbstdokumentierend. **Downside:** jede
Stelle muss manuell annotiert werden; vergessene Annotation fällt auf Nominativ zurück
(sichtbar als „mit die/der-falsch").

## 3. Genus-Auflösung

Eine Quelle für beide Pfade: `GuessGender` in `VariableReplacers.de.cs`.

**Reihenfolge:**
1. **Exakter Lexikon-Treffer** — `languages/lang-de/COQDE/GenderLexicon.tsv`
   (`wort<TAB>m|f|n|p`, `#`-Kommentare; Umlaut- UND Folded-Schreibweise pflegen) plus
   Inline-`Overrides`-Tabelle als Fallback, falls die Datei fehlt. Datei gewinnt.
2. **Längster Lexikon-Suffix-Match** — Komposita erben vom Grundwort: langschwert→schwert n,
   werkbank→bank f, chitinpanzer-puma→puma m. Läuft VOR der Endungsheuristik, damit
   Grundwörter wie „raum" nicht von Pseudo-Endungen gekapert werden.
3. **Endungsheuristik** — Fem: -ung/-heit/-keit/-schaft/-ion/-tät/-ik/-enz/-anz/-ur/-ie;
   Neut: -chen/-lein/-ment/-tum/-um; Masc: -er/-ling/-ismus/-ich/-ig/-ant/-or/-ast;
   dann -e→Fem; Default Masc. **„-ma" ist bewusst KEINE Regel** (der Puma, die Firma,
   das Thema — die griechischen Neutra stehen im Lexikon).
4. **Phrasen-Kopf:** bei Namen mit Funktionswörtern zählt das Wort VOR dem ersten
   Funktionswort (`PhraseGenderHead`): „Phiole mit Wasser" → Phiole → f.

**Bekannte Fallen:** falsche Suffix-Erbschaften brauchen einen exakten Eintrag
(gewand n ≠ wand f). **Fix-Weg für falsche Artikel ist IMMER eine TSV-Zeile, nie Code.**

## 4. Adjektivdeklination & Markup-Sicherheit

**Deklinationstabellen** (`AdjEnding`): Weak (nach der/die/das), Mixed (nach ein-Wörtern
und Possessiven), Strong (ohne Determinierer). `AdjStem` reduziert bereits flektierte
Adjektive auf den Stamm (eiserne→eisern).

**Sicherheitsmuster `IsAdjNounPattern`:** Führende Wörter werden NUR dekliniert, wenn der
Name dem Muster „kleingeschriebene Adjektive + großgeschriebener Kopf" entspricht und kein
Funktionswort (`FunctionWords`: aus/mit/von/der/…) enthält. Alles andere („Zahnrad aus der
Großen Maschine", „Phiole mit Wasser") bekommt nur den korrekten Artikel, der Name bleibt
unangetastet. **Trade-off: konservativ = verstümmelt nie, dekliniert manchmal zu wenig.**

**Farbcodes:** `SplitColor` zerlegt `{{r|blutig}}`- und `&rblutig`-Verpackungen,
`DeclineAdj` dekliniert den Kern und setzt die Verpackung wieder zusammen — in allen vier
Deklinationspfaden (definit, indefinit, possessiv, Nachdeklination).

**Nachdeklination im C#-Pfad:** `DeclineAfterArticle` repariert vom Spiel vorangeklebte
Zustands-Adjektive nach bereits gesetztem Artikel („Der nass Leuchtfisch" → „Der nasse
Leuchtfisch"), Genus aus dem Artikel (der/das) bzw. Objekt-Plural (die), nur beim sicheren
Muster. Eingehängt im `GameObjectDisplayName`-Override.

## 5. Possessive

**Vorangestellter Genitiv** für englische `'s`-Konstruktionen (archaisch-poetisch, passt
zum Qud-Ton): Replacer-Overrides `the.name's`/`t's`, `name's`/`basename's`/`refname's`,
`a.name's`/`an's` → „des Krokodils Bein", „Barathrums", „eines Krokodils"; Spieler → „Euer".
Der Postprocessor-Override `possessive`/`makePossessive`/`'s` deckt alle `|'s`-Templates ab
(HistorySpice: „Reshephs Wagen"); deutsche Regel in `GermanPossessiveSuffix` (+s, nach
s/ß/x/z Apostroph, farbtag-sicher).

**Possessivpronomen** (`DeclinePoss` dekliniert sein/ihr/euer/mein/dein/unser; exotische
Stämme aus Pronomen-Sets wie hir/xyr bleiben bewusst undekliniert):
- `possessive`/`their`/`its`/`possessiveAdjective` (1 Objekt): vor FESTEM Substantiv per
  Annotation `=subject.its:akk:f= Energiezelle` (Kasus `:nom/:akk/:dat/:gen` bzw.
  Langformen, Genus `:m/:f/:n/:pl`); ohne Annotation nur der Stamm.
- `its.item`/`its_` (Besitzer + Item): Genus kommt vom Item selbst, Kasus als Parameter —
  `mit =subject.its.item:dat#weapon=` → „mit seinem Biss". Eigennamen-Items lassen das
  Possessiv weg (wie das englische Original).
- `its.part` (Besitzer + BodyPart): kombiniert Possessiv + Körperteil in einem Token —
  `aus =subject.its.part:dat#part=` → „aus seiner rechten Hand".

**Stamm-Regel** (`PossStem`) — Sinn-Kongruenz vor Nomen-Genus:
1. Spieler → „euer" (Ausgabe immer großgeschrieben, Qud-Anrede).
2. Spiel-Gender male/female (+hindren-Varianten) → sein/ihr — „die Karawanenwache (m) …
   mit seiner Axt" (Konstruktion ad sensum).
3. Plural-Gender → „ihr".
4. Benannte Figuren → Pronomen-Daten (respektiert they/them-Sets).
5. Generische ungegenderte Kreaturen → grammatisches Genus des deutschen Nomens
   (das Krokodil → sein, die Schlange → ihr).

**C#-Pfad-Hook** (`GameObjectDisplayName`-Override + `CSharpPossessivePhrase`): fängt
`GameObject.its_(Weapon)`-Konstruktionen ab (Pronomen kommt als `DefaultDefiniteArticle`
durch), Stamm via `Item.Holder`→`PossStem`, volle Phrase inkl. Adjektivdeklination.
**Dokumentierte HEURISTIK mit bekannten Fehlermodi:** kleingeschriebenes Pronomen =
satzintern nach Präposition → Dativ; großes „Its" (Satzanfang) → Nominativ; „Euer" (in den
Daten immer groß) → Dativ-Wette. Satzinitiale „Euer X"-Zeilen und Nicht-Präpositions-
Kleinschreibfälle bekommen den falschen Kasus — Ein-Zeilen-Justierung, wenn ein
Gegenbeispiel auftaucht. Bei Markup im Namen wird nur der Artikel dekliniert.

## 6. Verben

**`konjde` (Token):** `=subject.konjde:INFINITIV=` — der Übersetzer schreibt den deutschen
Infinitiv ins Template. Starke/unregelmäßige Verben kommen aus
`languages/lang-de/COQDE/Verbs.json` (`{inf, s3, p2, p3, en}`; s3=3. Sg, p2=„Ihr"-Form,
p3=3. Pl); alles andere konjugiert `WeakConjugate` algorithmisch (Stamm+t, -et nach t/d).
Person über `VerbPerson`: Spieler→p2, Plural→p3, sonst s3. **Nur Präsens.**

**Verbs.json-Regeln:** nur nicht-trennbare starke Verben eintragen (trennbare wie „greift
an" brechen die Wortstellung in Ein-Token-Ersetzungen); `en`-Feld dokumentiert die
englischen Basisverben (Slash-Aliase: `"en": "disappear/vanish"`) und speist `VerbsByEn`.

**`does`/`did`-Override:** für LAUFZEIT-Verben (`=subject.Does#verb=` — das Verb kommt
erst zur Laufzeit, deutsch „Sehen" oder englisch „see"). `TryGermanVerb` akzeptiert NUR
echte Tabellentreffer (VerbsByInf oder VerbsByEn) plus umlauthaltige -en-Infinitive —
naive Konjugation englischer Wörter („open"→„opent") wäre schlimmer als der englische
Fallback, der bei Nichttreffen unverändert greift. Adverb-Minilexikon (`Adverbs`:
already→bereits …) für die `adverb:verb`-Form.

## 7. Körperteile

Overrides `name`/`ordinalName` mit BodyPart-Parametertyp: `TransformBodyPart` strippt die
englische Lateralität (`Laterality.StripLateralityAdjective`), übersetzt den Grundnamen
(`BodyPartTerms`-Wörterbuch), und fügt deutsche Lateralitäts-Adjektive genuskorrekt wieder
an („right hand" → „rechte Hand"; Flag-Mapping in `LateralityAdjectives` gegen die
dekompilieren `Laterality`-Konstanten verifiziert). **Nur Token-Pfad** — der
Ausrüstungs-/Anatomie-Paperdoll ruft `GetCardinalName()` direkt in C# (OPEN_ISSUES,
„Waiting on official localization support").

## 8. Zahlen & Kultur (Translator-Provider)

Alle Zahlen-Tokens des Spiels (`=cardinal=`, `=cardinal.no=`, `=ordinal=`,
`=ordinal.digits=`, `=multiplicative=`, `cardinal.things`, `a.or.cardinal.names`, …)
routen durch `Translator.*` — ein Provider deckt alles ab, keine Replacer-Overrides nötig:
- `Cardinal`: deutsche Zahlwörter inkl. Komposita („einundzwanzig",
  „eintausenddreihundertsiebenunddreißig") und großen Skalen mit korrektem Genus/Numerus
  („eine Million" / „zwei Millionen", Milliarde statt „billion").
- `Ordinal`: Grundform auf -e (erste/dritte/siebte/achte-Sonderfälle auch als letzte
  Kompositum-Komponente); -te bis 19, sonst -ste. Kasus ist am Token nicht bekannt —
  die schwache -e-Form ist die verträglichste Wahl.
- `OrdinalWithDigits`: „3." statt „3rd". `Multiplicative`: einmal/zweimal/dreimal/n-mal.
  `CardinalNo`: „keine". `GetCultureInfo`: de-DE (Umlaut-Groß/Kleinschreibung).
- `DefiniteArticle`/`IndefiniteArticle`: ersetzen NUR den englischen Basis-Fallback
  („the/The", „a/an", „some"→„etwas") durch deutsche Nominativ-Artikel — Daten-Overrides
  (`IndefiniteArticle="die"`-Attribute), Eigennamen-Unterdrückung und Examiner-Rekursion
  der Basis bleiben unangetastet.

## 9. Kontrakte & Trade-offs

| Kontrakt | Begründung |
|---|---|
| **`ID="…"` nie editieren** — byte-exaktes englisches Template | Lookup ist `ContextStrings(Context)[ID]`; eine 505-Einträge-Regression entstand durch Token-Konvertierung in IDs (still: Fallback auf Englisch, kein Fehler) |
| **Naming ⊇ Strings (Substring-Kontrakt)** | Hero-ObjectBuilder prüfen `text.Contains(_S("<X> Naming.xml Context", …))` — verletzt = Helden verlieren still ihre Boni. Beide Dateien im selben Commit pflegen |
| **String-Return statt TextBuilder-Mutation** in Replacern/Postprocessors | TextBuilder-Schreib-Overloads (Append/Insert) sind im net48-Smoke-Build nicht auflösbar (CS0518/ReadOnlySpan); die Engine-Registrierung akzeptiert `void` UND `string` gleichwertig |
| **Savegame-Persistenz** | FriendOrFoe-Reasons und Hero-Titel werden bei der Generierung gespeichert — Textänderungen wirken nur auf NEUE Kreaturen/Spielstände |
| **LibraryCorpus regenerieren** nach Buch-/Beschreibungs-Änderungen | `build/tools/build_library_corpus.py` trainiert auf den übersetzten Texten; die JSON ist ein Build-Artefakt |
| **Blueprint-Meldungen** per `Load="Merge"`-Part-Attribut übersetzen | Meldungs-Templates stecken teils in `ObjectBlueprints/*.xml`-Attributen (PrepMessageOther etc.) — Daten, kein Code |
| **Genus-Fixes ins Lexikon, nie in Code** | Eine TSV-Zeile, beide Pfade profitieren, kein Smoke nötig |

## 10. Nicht behandelte deutsche Grammatik

Checkbox-Liste — beim Schließen einer Lücke im selben Commit abhaken (Skill-Regel).
Stand: 2026-07-17, gegen den Code verifiziert.

- [ ] **N-Deklination schwacher Maskulina** — `GenitiveNoun` macht +s/+es; korrekt wäre
  „des Drachen/Bären", Akkusativ „den Bären" statt „den Bär". Bräuchte eine
  Schwach-Nomen-Liste im Lexikon + Kasusformen.
- [ ] **Dativ-Plural-n** — „den Hunden": der Phrasen-Kopf bleibt in allen Buildern
  unverändert; nur der Artikel dekliniert.
- [ ] **Fugenlaute in Komposita** — Titel-Muster kleben mit Bindestrich
  („Krabbe-Patriarch" statt „Krabben-Patriarch"); bräuchte Fugen-Lexikon.
- [ ] **Relativpronomen-Genus** — feste „das"-Relativsätze in Templates
  („von X, das mit Y kollidiert"); Genus des Bezugsworts wird nicht durchgereicht.
- [ ] **Automatische Wechselpräpositions-Erkennung** — Lage vs. Richtung wählt der
  Übersetzer manuell per `:dativ`/`:akkusativ`; im C#-Pfad nur die Heuristik aus
  Abschnitt „Possessive".
- [ ] **Genitiv-Präpositionen** (wegen/trotz/während) — Templates wurden auf
  Dativ/weil-Konstruktionen umformuliert statt Genitiv-Rektion zu modellieren.
- [ ] **Tempora jenseits Präsens** — `konjde`/`does` liefern nur Präsens (3. Sg,
  „Ihr"-Form, 3. Pl). Präteritum/Perfekt in Templates sind handformuliert
  (z. B. die „weil Ihr … habt"-Reason-Klauseln).
- [ ] **Trennbare Verben generell** — nur lexikalisierte nicht-trennbare Basen in
  Verbs.json; „X greift Y an"-Wortstellung ist mit Ein-Token-Ersetzung nicht baubar.
- [ ] **Steigerung** (Komparativ/Superlativ) — keine Unterstützung; kommt in Templates
  bisher nur als festes Wortmaterial vor.
- [ ] **Imperative** — nicht modelliert (Qud-Dialoge nutzen „Ihr"-Aussagesätze).
- [ ] **V2-/Verbend-Wortstellung in C#-Zeilen** — upstream-blockiert: das Satzgerüst
  („hits … for … damage with") ist ein C#-Literal (OPEN_ISSUES).
- [ ] **Register** — durchgängig archaisches „Ihr/Euch/Euer"; kein du/Sie-Wechsel je
  Sprecher.
- [ ] **Ordinal-Deklination** — `Ordinal` liefert die -e-Grundform; „zum dritten Mal"
  bräuchte Kasus am Token.

## 11. Selbsttests als Ground Truth

Beim Mod-Init (`GermanReplacerBootstrap.Init`) laufen und loggen nach `Player.log`:

| Log-Präfix | Quelle | Prüft |
|---|---|---|
| `[QudDE] case-selftest` / `phrase-selftest` | `SelfTestCases` | Artikel-/Phrasen-Deklination offline (ohne Engine) |
| `[QudDE] pipeline-test` | `SelfTestPipeline` | ECHTE Token→Replacer-Kette auf frisch erzeugten Objekten (Kasus, Verben, Körperteile) |
| `[QudDE] verb-test` / `bodypart-test` / `possessiv-test` | dito | Untergruppen inkl. reiner Logik-Funktionen |
| `[QudDE] zahl-test` | `TranslatorDeutsch.SelfTest` | Zahlwort-Engine |
| `[QudDE] pipeline-test summary: N passed, 0 failed` | — | Baseline; jedes FAIL nennt den Erwartungswert |

**Regel: Neues Verhalten ⇒ neue Selbsttest-Zeile im selben Commit.** Die Selbsttests sind
die verbindlichen Beispiele dieses Dokuments — wenn sie PASS melden, stimmen die hier
beschriebenen Verhalten noch.

## Verwandte Dokumente

- `docs/TURKISH_REFERENCE.md` — wie der offizielle türkische Mod dieselben Probleme löst
  (PUA-Marker, Vokalharmonie, Konventionen).
- `docs/OPEN_ISSUES.md` — Status, Wait-Liste, bekannte-benigne Log-Einträge, Diagnostik.
- `.claude/skills/qud-de-grammatik/SKILL.md` — das Arbeitsverfahren (Finding-Diagnose,
  Checklisten, Erweiterungs-Prozedur).
