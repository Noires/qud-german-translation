# Änderungsverlauf – Caves of Qud Deutsch (lang-experimental)

Deutsche Lokalisierung auf Basis der offiziellen Lokalisierungs-Unterstützung im
`lang-experimental`-Branch. Daten-Mod plus eine kompilierte Laufzeit-DLL (`COQDE.dll`)
für die im Code zusammengesetzten Meldungen (seit v0.8.0).

## v0.8.0 – Laufzeit-Nachbearbeitung der Meldungsprotokolle (COQDE.dll, Prototyp)

- **Neue Laufzeit-DLL `languages/lang-de/COQDE/COQDE.dll`** (Harmony-Patch), die die
  **im C#-Code zusammengebauten** Meldungsprotokoll-Zeilen übersetzt, die weder die
  Datenschicht (`*.de.xml`) noch die Token-Ersetzer (`VariableReplacers.de.cs`) erreichen.
  Beispiel: „The snapjaw dies." → „Der Schnappkiefer stirbt." Dies entspricht dem Ansatz
  des koreanischen Referenz-Mods (`COQKR.dll`). Siehe `docs/RUNTIME_POSTPROCESSOR_PLAN.md`.
- **Funktionsweise:** Harmony-Prefix auf `XRL.Messages.MessageQueue.AddPlayerMessage`
  schreibt die Meldung um, bevor sie erscheint. Die Übersetzung ist datengesteuert:
  - `Patterns.json` – geordnete Regex-Umschreibungen (erster Treffer gewinnt); im Ersatz
    verweist `{gruppe:form}` auf eine Fanggruppe, die zuerst über `Terms.json` übersetzt und
    dann durch den deutschen Grammatik-Operator geführt wird.
  - Formen: `nom`/`acc`/`dat`/`gen` (bestimmter/unbestimmter Artikel im jeweiligen Kasus,
    Definitheit wird aus dem englischen Artikel abgeleitet), `name` (bloßer Name, für
    Eigennamen), `v-<Infinitiv>` (deutsche Verbkonjugation, `Verbs.json`).
  - `Terms.json` – Wort-/Teilstring-Ersetzungen für Namen, die die Datenschicht verpasst.
- **Startprotokoll & Selbsttest:** die DLL schreibt beim Laden `[QudDE] COQDE runtime
  loaded (patterns=… verbs=… terms=…)` und führt Beispielzeilen durch den Prozessor
  (Ein-/Ausgabe im `Player.log`) – so ist die Korrektheit ohne Spielsitzung prüfbar.
- **Sprach-Schutz (fail-open):** die Umschreibung greift nur, wenn die aktive Sprache
  positiv als Deutsch erkannt wird; ist der Sprach-Accessor nicht auflösbar, wird übersetzt
  (Mod wird ohnehin gemeinsam mit der Sprache aktiviert – wie beim Referenz-Mod).
- **Startumfang:** 34 der häufigsten Kampf-/Status-Rahmen (Tod, Zerstörung, Treffer/Fehl-
  schlag, Schaden durch Effekt, Blutung, benommen, bewusstlos, Weg versperrt, blocken,
  nachladen …). Die englischen Rahmen sind an den echten Spielzeichenketten ausgerichtet
  (abgeglichen mit den `MessageLog`-Mustern des koreanischen Mods).
- **Todesbildschirm (`Popup`-Route neu):** zusätzlicher Harmony-Prefix auf `XRL.UI.Popup`
  übersetzt die im Code zusammengebauten Todesmeldungen (die weder Datenschicht noch der
  `MessageLog`-Hook erreichten), z. B. „You were bitten to death by a Snapjaw-Brut." →
  „Ihr wurdet von einer Snapjaw-Brut zu Tode gebissen." (Kasus/Genus des Getöteten, gebackene
  Partizipien je Todesart + generischer Rückfall; ein bereits deutscher Vorspann „Du bist
  gestorben." bleibt erhalten). Auf Nicht-`MessageLog`-Routen wird nur bei Mustertreffer
  ersetzt (kein Teilübersetzen beliebiger englischer UI-Texte).
- **`Terms.json` jetzt leer (mit Begründung):** die Demo-Namenseinträge wurden entfernt –
  im Spiel liefert die Datenschicht die Namen bereits deutsch, sodass Teilstring-Ersetzungen
  korrekte Namen **beschädigt** hätten (z. B. „Snapjaw-Brut" → „Schnappkiefer-Brut"). Terms
  sind reiner Fallback für echte Lücken; Einträge nur nach Nachweis über das Debug-Log.
- **Debug-Log:** liegt die Datei `COQDE.debug` neben der DLL, protokolliert die Laufzeit alle
  nicht getroffenen Meldungszeilen (`[QudDE] unmatched: [Route] …`) – so liefert echtes
  Spielen die nächste Musterliste.
- **Lückenanalyse dokumentiert:** `docs/KOREAN_PARITY_GAPS.md` listet alle Hooks/Routen des
  koreanischen Referenz-Mods, ihre Relevanz für Deutsch (Datenschicht deckt vieles ab) und die
  empfohlene Reihenfolge (nächste Kandidaten: `GameSummary`, `BodyPart`/Lateralität,
  `Possessive`).
- **Farb-Markup wird jetzt behandelt:** ganz in ein Qud-Farb-Tag gehüllte Zeilen
  (`{{g|The X is dazed.}}`) blockierten bisher die verankerten Muster (`^…$`). Sie werden nun
  ausgepackt, übersetzt und wieder eingepackt (`{{g|Der X ist benommen.}}`). Das war die
  häufigste Ursache dafür, dass gefärbte Kampf-/Statuszeilen englisch blieben.
- **Genus-Korrekturen:** schwache Maskulina auf -e (Schütze, Riese, Bote, Pilger …) und
  einige Kreaturen (Krokodil = neutral, Tausendfüßer = maskulin) in die Override-Tabelle
  aufgenommen (vorher riet die Endungsheuristik falsch, z. B. „die Schütze").
- **Weitere Muster:** „begins flying", „whizzes past …", „You discover …!",
  „You note the location of … in the … section of your journal." sowie eine Bereinigung für
  das halbdeutsche „X begins Blutung!" der Datenschicht.
- **Gemeinsames Genus-Lexikon (`COQDE/GenderLexicon.tsv`, 215 Einträge):** grammatisches
  Genus hat jetzt EINE Datenquelle, die sowohl der Token-Ersetzer (`VariableReplacers.de.cs`)
  als auch die DLL laden. Behebt falsche Artikel aus der Endungsheuristik – z. B. „einen
  Becken" → „ein Becken" (Becken = neutral). Die Inline-Tabelle + Heuristik bleiben als
  Rückfall, falls die Datei fehlt. Erweiterbar (Haiku-tauglich) an einer Stelle. (Offen bleibt
  der Kasus nach Präpositionen – siehe nächster Punkt.)
- **Kasus nach Dativ-Präpositionen korrigiert (DLL-Nachlauf):** ein präpositions-bewusster
  Durchlauf verbessert den Artikelkasus nach `aus/bei/mit/nach/seit/von/zu`:
  „mit den Dolch" → „mit dem Dolch", „mit sein Bronzedolch" → „mit seinem Bronzedolch",
  „von das Schwert" → „von dem Schwert". Es werden nur kollisionsfreie Umwandlungen angewandt;
  `-n`-Formen sind gegen korrekte Dativ-Plurale abgesichert (übersprungen, wenn das folgende
  Nomen auf `-n` endet), und Akkusativ-Präpositionen (`durch`, `für` …) bleiben unangetastet.
  Offen: Wechselpräpositionen (`in/an/auf` … – Dativ/Akkusativ mehrdeutig) und feminines
  `die`/`ihr` nach Dativ (formgleich).
- **Koch-Zutatenliste:** „a dram of X" → „ein Dram X" (fehlender `Strings.de.xml`-Eintrag
  `a dram of =item.liquid.name=` ergänzt); zusätzlich flektiert ein Laufzeit-Nachlauf das
  Flüssigkeits-Adjektiv („ein Dram brackig Schleim" → „ein Dram brackiger Schleim",
  „schleimig Salz" → „schleimiges Salz") über den neuen Operator `strongnom` (starke Deklination
  ohne Artikel).
- **Vollständige Datenschicht-Parität mit dem koreanischen Mod erreicht** (außer `Naming.xml`,
  das für Deutsch nicht nötig ist – lateinische Schrift). Zusätzlich abgeschlossen:
  - `Items.de.xml`: +120 fehlende Objekte (880 → 1000).
  - `Strings.Extend.de.xml` neu (Ort / Zuletzt gespeichert / Attributpunkte).
  - `HistorySpice.jsonc` neu: die prozedurale Chronik-/Legenden-Datenbank – 5187 Textbausteine
    übersetzt (3784 eindeutige, Haiku-Bulklauf). Struktur & Schlüssel-Konvention des koreanischen
    Mods gespiegelt (Array-Schlüssel mit „=" zum Ersetzen, `@`-Schlüssel wie dort weggelassen);
    alle Spieltokens (`=…=`, `=^:…!random=`, `{{Farbe|…}}`) erhalten, mit Token-Integritätsprüfung
    (bei Abweichung Rückfall auf Englisch). JSON validiert.
- **Objekt-Dateien großflächig übersetzt (+604 Objekte, Haiku-Bulklauf):** die vier größten
  Datenlücken gegenüber dem koreanischen Mod geschlossen —
  `HiddenObjects.de.xml` (9 → 308), `Foods.de.xml` (20 → 140), `Furniture.de.xml` (269 → 436),
  `PhysicalPhenomena.de.xml` (12 → 30). Übersetzt wurden nur `DisplayName` und Beschreibungen;
  Spieltokens (`=…=`, `{{Farbe|…}}`) blieben erhalten. **Nur angehängt** – alle bestehenden
  Einträge blieben unangetastet; jede Datei wurde nach dem Schreiben validiert (wohlgeformtes
  XML, `Name=`-Schlüssel unverändert, keine Duplikate). Damit liegt die Datenschicht bei ~99 %
  Deckung ggü. dem koreanischen Referenz-Mod (Vergleichsbericht in `docs/`).
- **Fehlerkorrekturen (aus Screenshots):**
  - **Stufenaufstieg zeigte Englisch** („2 hitpoints" …): ein früherer Edit hatte versehentlich
    die `ID` (den englischen Abgleichsschlüssel) mitüberschrieben, nicht nur den `Value` – dadurch
    fand das Spiel die Übersetzung nicht. IDs wiederhergestellt → „2 Trefferpunkte",
    „78 Skillpunkte", „1 Mutationspunkt".
  - **„[y]Z YesZ"-Knopf**: beschädigter Eintrag in `Strings.de.xml` (Streu-„Z" und „Yes" nie
    übersetzt) → korrigiert zu „[y] Ja".
- **Popups/Menüs breiter abgedeckt (Parität mit koreanischem Ansatz):** neuer `MenuOption`-Hook
  (`Popup.GetPopupOption`) übersetzt Auswahllisten; Farbnamen (schwarz/dunkelblau/…), Ja/Nein und
  Umbenennungs-Optionen als Begriffe/Muster; `Popup`-Muster für die codegebauten Dialoge
  (Genom-Erregung, „…Ränge…", Benennen/Umbenennen/Farbe-wählen).
- **Mutationsbeschreibungen (`Mutations.de.xml`, 6 KB → 49 KB):** alle 82
  Mutationsbeschreibungen und Stufentexte sind jetzt deutsch (bisher nur die Namen). Spieltokens
  (`=…=`, `<stat/>`, `<statline/>`, `{{Farbe|…}}`, `<p>/<br/>`) bleiben erhalten; formelles „Ihr".
- **Screenshot-Analyse umgesetzt (4 Phasen, siehe `docs/SCREENSHOT_FIXES_PLAN.md`):**
  - **Kampf-Meldungen:** neue Muster für Treffer ohne Ziel/Penetration, Kritische, „verfehlt
    Euch … [W vs. V]", „schlägt/trifft Euch", „pfählt sich an …", „Der Angriff zerbricht …".
    Alternativen im Regex (`you|Euch`, `with|mit`, `hits|trifft` …) fangen den uneinheitlichen
    Vorübersetzungs-Zustand ab. Neuer Operator `{…:possnom/possacc/possdat}` erkennt englische
    *und* deutsche Possessive (`your/its/sein/euer …`), beugt nach Kasus/Genus und flektiert
    Adjektive. → „Der Skorpiock trifft (x1) für 4 Schaden mit seinem Giftstachel. [8]".
  - **Adjektiv-Deklination:** vollständige Endungstabellen (stark/schwach/gemischt × Kasus ×
    Genus) mit Stamm-Rückführung, in alle Artikel-/Possessiv-Operatoren integriert →
    „blutigen Skorpiock", „eisernen Rebenklinge", „verrosteten Metallwand", „klebrigen Pseudopod".
  - **Kompositum-Genus:** unbekannte Nomen erben das Genus eines bekannten End-Nomens
    (`Metallwand`→`Wand`=feminin) → „von einer verrosteten Metallwand".
  - **Weitere Rahmen/Begriffe:** „You're lost/regain your bearings", „You are paralyzed",
    „…cures you of…", Umgebungs-Sprechzeilen („Der … schreit, …"); Datenschicht-Korrekturen
    in `Strings.de.xml` (Verirrt-Popup, Stufenaufstiegs-Gewinne: Treffer-/Skill-/Mutationspunkte)
    sowie Begriffe `legendary`→`legendär`, `workshop`→`Werkstatt`, `paralyzed`→`gelähmt`.
- **Feinschliff II (aus In-Game-Screenshots):**
  - „an … vorbei" mit mehreren Objekten: jetzt alle Artikel im Dativ, auch nach „und"
    („an einer Wasserwinde und einer Wasserwinde vorbei"). Ein Code-Durchlauf ersetzt die
    bisherigen Einzelmuster und deckt beliebig viele Objekte ab.
  - **Autoerkundungs-Meldungen an der Quelle korrigiert** (`Strings.de.xml`):
    - Richtung „zum Westen" → „im Westen" (`direction.description`-Vorlage, wirkt für alle
      Himmelsrichtungen).
    - „… und hörst auf Bewegen." → „… und hört auf, euch zu bewegen." Die Gerundien
      (`moving`/`exploring`/… ) sind jetzt zu-Infinitiv-Formen und die vier `spotmessage`/
      Interrupt-Vorlagen entsprechend umformuliert (falsches „hörst"/„du" behoben).
- **Feinschliff (aus In-Game-Screenshots):**
  - „an … vorbei" (vorbeigehen) nimmt jetzt den **Dativ**: „an eine Wasserwinde vorbei" →
    „an einer Wasserwinde vorbei", „an ein Schlammgras vorbei" → „an einem Schlammgras vorbei".
  - „X beginnt flying" → „X beginnt zu fliegen" (das Gerundium wird zu „zu <Infinitiv>";
    nötig, weil `GetVerb` „begins" schon vor dem Zusammenbau zu „beginnt" macht).
  - Deutsche Infinitive aus der Datenschicht (z. B. `harvest`→`ernten` über `#verb`) werden
    jetzt ebenfalls konjugiert: „Ihr ernten …" → „Ihr erntet …".
  - Genus ergänzt: `Gras`/`Schlammgras` = neutral, `(Reben)wafer`/`Winde` = feminin.
- **Drei weitere Routen-Hooks (Parität mit dem koreanischen Mod, #1–#3):**
  - **`GameSummary`** – Prefix auf `GameSummaryUI.Show` übersetzt Todesursache und Details des
    End-/Todesbildschirms (die Todesmuster greifen dort ebenfalls).
  - **`BodyPart`** – Postfix auf `GetCardinal/Ordinal Name/Description`: trennt das englische
    Lateralitäts-Adjektiv ab (`Laterality.StripLateralityAdjective` + Lateralitäts-Bits des
    Körperteils), übersetzt das Grundnomen (BodyPart-Begriffe) und hängt ein deutsches, nach
    Genus flektiertes Adjektiv wieder an: „rechte Hand", „vorderes linkes Bein".
  - **`Possessive`** – Postfix auf `GameObject.Poss`: „Your X" → „Euer/Eure X" (genusabhängig),
    „The X's Y" → „Der Y des X…" (Genitiv-Umstellung), „Name's Y" → „Names Y".
- **Verben an der Quelle konjugiert (Harmony-Postfix auf `GameObject.GetVerb`):** die
  Verb-Ersetzer des Spiels (`=…Does:wade=`, `=…verb:X=`, `=…is=`, `.Has`) laufen alle durch
  diese eine Methode, die mangels deutscher Konjugation bisher das englische Grundverb ausgab
  („Ihr wade", „Ihr Sehen", „Ihr have"). Der Postfix bildet das englische Grundverb auf die
  deutsche Konjugation für die Person des Subjekts ab (`Verbs.json`, Schlüssel `en`; 62 Verben,
  Rest fällt auf Englisch zurück – keine Regression). Damit werden „Ihr watet", „Ihr seht",
  „Ihr habt" usw. in **allen** Vorlagen auf einmal korrekt, ohne Einzelmuster. Person wird wie
  in `GetVerb` bestimmt (Spieler→„Ihr"/2. Pl.; Plural→3. Pl.; sonst 3. Sg.).
- **Ladepfad:** `COQDE/Bootstrap.cs` (vom Spiel kompiliert) lädt `COQDE.dll` per Reflection
  und ruft `COQDE.COQDEMod.Init()` auf – analog zum koreanischen `COQKRLoader`. Der
  DLL-Quellcode liegt unter `build/COQDE/` **außerhalb** des Mod-Ordners, da das Spiel jede
  `.cs` im Mod-Ordner kompilieren würde (sonst doppelte Typdefinitionen mit der DLL).
- **Konsolidierung/Doku (Plan §5b):** `VariableReplacers.de.cs` erhält einen Kopfkommentar,
  der die Aufteilung dokumentiert (Token-Strings hier / Code-Meldungen in der DLL); das
  Lade-Beacon ist entsprechend umbenannt. Die kanonische Genus-Logik liegt nun (auch) in
  `COQDE/src/Gender.cs`.
  - **Bewusst verschoben:** die laufzeitgeteilte Genus-Quelle per Reflection (Plan §5b.1) –
    sie würde den bereits funktionierenden Token-Pfad an die Ladereihenfolge der DLL koppeln
    und ist ohne Spielsitzung nicht verifizierbar. Die beiden Override-Tabellen sind vorerst
    parallel zu pflegen.
  - **Prototyp-Grenzen:** Farb-/Shader-Markup in Namen wird für die Genus-/Artikel-Erkennung
    entfernt (die Ausgabezeile ist reiner Text – Farbe geht in umgeschriebenen Zeilen
    verloren); Plural-Subjekte und Possessiv-Formen („your …", „X's …") sind noch grob.

### Vollständige Abdeckung der Datenschicht (Parität zum koreanischen Mod)

- **Datenschicht auf ~100 % der übersetzbaren Inhalte gebracht** (vorher ~87 %). Grundlage ist
  die spielseitige Manifestdatei `ExampleLanguage/*.example.xml`, in der jeder übersetzbare
  Wert mit `▶` markiert ist – der maßgebliche Abgleich für 100-%-Prüfung.
- **Prüfwerkzeug `build/tools/coverage_audit.py`:** vergleicht das `▶`-Manifest gegen die
  `*.de.xml` und meldet je Datei fehlende Einheiten nach Kategorie. Restposten sind
  nachweislich Zähl-Rauschen (verschachtelte `<p>`-Beschreibungen, deren deutscher Text
  vorhanden ist) bzw. inhaltsleere Token-/Leerzeichen-Strings.
- **~2300 fehlende Einheiten übersetzt und eingemischt** – attributgenaues In-Place-Merge, das
  **jeden bestehenden Wert unverändert lässt** (inhaltliche Vorher/Nachher-Prüfung: 0 geändert,
  keine `ID`/`Name`-Schlüssel angetastet). Betroffen u. a. `Creatures`, `Items`, `Furniture`,
  `Worlds`, `Mutations`, `HiddenObjects`, `Foods`, `Quests`, `Walls`, `PhysicalPhenomena`.
- **Neue Dateien:** `HistorySpice.jsonc` (5187 Lore-Fragmente, `=`-Ersatz-Schlüssel wie im
  koreanischen Mod), `Genders.de.xml`, `TutorialStaging.de.xml`, `Strings.Extend.de.xml`,
  `Templates.de.xml` (Einheit „Runde" für Cooldown/Duration). `Mutations.de.xml` von 6 KB auf
  49 KB (Mutationsbeschreibungen).
- **`Strings.de.xml`:** Stufenaufstiegs-Meldungen, Ja/Nein-Knopf, Autoerkunden/Richtungen sowie
  der Annalen-Eintrag und Werte-Tooltips ergänzt (Token wie `{{…}}`/`=…=` erhalten).

## v0.7.0 – Pronomen (er/sie/es) und Lücken zum koreanischen Referenz-Mod

- **`Genders.de.xml` neu:** die Personal-/Possessivpronomen und Anrede-Begriffe des
  Spiels (bisher englisch: he/she/it/they …) sind jetzt deutsch. Betroffen sind alle
  automatisch generierten Verweise auf Kreaturen über ihr Geschlecht:
  - männlich → er/ihn/sein/seins/sich (Mann, Junge, Freund, Sohn, Bruder, Vater)
  - weiblich → sie/sie/ihr/ihres/sich (Frau, Mädchen, Freundin, Tochter, Schwester, Mutter)
  - neutral → es/es/sein/seins/sich; Plural/Kollektiv → sie/… (Leute, Kinder …)
  - Sondergeschlechter (hindren, hartind) und Neopronomen (elverson: ey/em/eir) ergänzt.
  - Grenze: Objektiv = Akkusativ (ihn/sie/es); Dativ (ihm/ihr) unterscheidet das Token
    nicht – gleiche Einschränkung wie beim Artikel-Helfer.
- **`TutorialStaging.de.xml` neu:** Anzeigename des Tutorial-Käfers
  („Uhrwerk-Käfer und Paria seines Volkes").
- **Artikel-Helfer war wirkungslos – jetzt behoben** (`VariableReplacers.de.cs`,
  `Override = true`): Das Spiel registriert die Artikel-Token (`the`/`the.name`/`t`/`a`/
  `a.name`/`an`) bereits selbst; unsere gleichnamigen Ersetzer wurden daher beim Laden als
  „duplicate signature" **übersprungen** (im Player.log sichtbar) und hatten keinerlei
  Wirkung. Mit dem Attribut-Flag `Override = true` überschreiben sie nun die eingebauten
  Ersetzer korrekt (nur für Sprache `de`). Der koreanische Referenz-Mod umgeht die Kollision
  anders – er definiert eigene, neue Token (은/는, krsubject …) und macht die Nachbearbeitung
  komplexer Sätze über eine kompilierte DLL (`COQKR.dll`).
- **Artikel-Helfer verbessert** (`VariableReplacers.de.cs`): Eigennamen erhalten jetzt
  korrekt **keinen** Artikel („Wächter Ualraig greift an." statt „der Wächter Ualraig …")
  – über `HasProperName`. Pluralobjekte bekommen den Plural-Artikel „die" und keinen
  unbestimmten Artikel – über `IsPlural`. Beides ergänzt die Genus-Heuristik, die nur für
  Gattungsnamen zuständig ist; die Pronomen (er/sie/es) kommen weiterhin aus `Genders.de.xml`
  (biologisches Geschlecht), der Artikel aus dem grammatischen Genus des Nomens.
- **Abgleich mit dem koreanischen Referenz-Mod abgeschlossen.** Verbleibende
  bewusste Auslassungen: `Naming` (prozedurale Namenssilben – lateinische Schrift
  funktioniert für Deutsch unverändert), die koreanische `COQKR`-Laufzeit-DLL
  (durch unseren eigenen `VariableReplacers.de.cs` ersetzt) und `Strings.Extend`
  (dessen drei Einträge sind bei uns bereits in `Strings.de.xml` enthalten).
  Einzige noch offene Inhaltslücke: `HistorySpice` (prozedurale Chronik-/Legenden-
  Bausteine, ~1950 Zeilen) – noch nicht übersetzt.

## v0.6.0 – Deutscher Grammatik-Helfer (Prototyp)

Erster deutscher Grammatik-Helfer im Code (`languages/lang-de/CODE/VariableReplacers.de.cs`,
analog zum koreanischen Referenz-Mod). Er überschreibt die Artikel-Token des Spiels für die
Sprache `de`, sodass zur Laufzeit zusammengesetzte Objekt-Verweise einen **deutschen Artikel**
erhalten statt des englischen „the/a":

- `=the=`, `=the.name=`, `=t=` (z. B. `=subject.t=`, `=object.t=`) → `der/die/das/den`
- `=a=`, `=a.name=`, `=an=` → `ein/eine/einen`

Betroffen sind u. a. Kampfmeldungen, „Ansehen"-Texte, Aufheben-Meldungen und Dialogverweise
(„Der Riesenkäfer greift Euch an." statt „the Riesenkäfer …").

### Grenzen (Prototyp)

- **Genus** wird aus dem Kopf-Substantiv abgeleitet (Endungs-Heuristik + Ausnahmeliste
  häufiger Nomen). Deutsches Genus ist teils willkürlich – bei seltenen Nomen kann der
  Artikel falsch sein.
- **Kasus** ist nur als Subjekt (Nominativ) bzw. Objekt (Akkusativ) bekannt; Dativ/Genitiv
  nach Präpositionen liefert das Token nicht, daher dort ggf. falscher Artikel (aber immer
  noch deutscher statt englischer).
- **Adjektive** in zusammengesetzten Namen sind reiner Text (kein Token) und werden nicht
  gebeugt.

**Hinweis:** Dies ist ein Code-Mod-Bestandteil und wird vom Spiel beim Laden kompiliert
(Scripting muss aktiviert sein). Bei Kompilierfehlern wird der Helfer ignoriert.

## v0.5.0 – Kreaturen-Umgebungssprache

Erster Schritt bei den prozeduralen Inhalten: die kurzen „Stimme"-Zeilen von
Kreaturen wurden von Hand übersetzt und den Basis-Kreaturen als Tags hinzugefügt
(`SimpleConversation`, `PetResponse`) – 39 Einträge, 45 Tags auf 30 Objekten
(Creatures, HiddenObjects).

- Lautmalerische `=verb:x=`-Token wurden durch echte deutsche Verben ersetzt, die
  strukturellen Token (`=subject.T=`, `=object.t=`, `=player.…=`) und die
  `{{emote|…}}`-Markierungen bleiben erhalten. Beispiele:
  - `=subject.T= wogt.` (ein Seeigel wogt)
  - `=subject.T= starrt =object.t= ausdruckslos an.` (Haustier-Reaktion)
  - `{{emote|*sanftes Wiehern*}}` (Equiden im Leerlauf)
  - „Mond und Sonne. Weisheit und Wille.~Möge die Erde in dieser Jahreszeit für uns
    Ertrag bringen.~Friede, =player.formalAddressTerm=."

### Bewusst noch nicht übersetzt

Die rekombinationsanfälligen Felder (`HeroNameTitle*` für generierte Legenden-Namen,
`xtagTextFragments` für zusammengesetzte Beschreibungen) bleiben vorerst englisch.
Eine korrekte deutsche Ausgabe erfordert Beugung (Artikel/Adjektiv/Kasus), die das
Token-System zur Laufzeit nicht leistet – dafür wäre ein deutscher Grammatik-Helfer
(`VariableReplacers.de.cs`, analog zum koreanischen Referenz-Mod) nötig.

## v0.4.0 – Echte Umlaute

Die offizielle Lokalisierungs-API stellt Umlaute korrekt dar (getestet). Daher wurde
der gesamte Mod von der ASCII-Ersatzschreibung (ae/oe/ue/ss) auf **echte Umlaute
(ä ö ü ß)** umgestellt:

- Von Workflows übersetzte Inhalte (UI, Dialoge, 25 weitere Kategorien) wurden
  verlustfrei aus den ursprünglichen (umlauthaltigen) Übersetzungen neu erzeugt.
- Aus dem QudDE-Projekt übernommene, zuvor gefaltete Inhalte (Objekt-Namen und
  -Beschreibungen, Charaktererstellung, Mutationen) sowie ein Teil der UI wurden aus
  den englischen Vorlagen neu mit Umlauten übersetzt (Haiku, token-geprüft).

Ergebnis: der gesamte deutsche Text nutzt jetzt korrekte Orthographie
(z. B. „Bär", „Höhlenspinne", „Riesenkäfer", „Stärke"). Auch die anfangs
verbliebenen komplexen Platzhalter-Einträge (Grammatik- und Spice-Token) wurden
in kleineren Chargen token-genau neu übersetzt – **alle umgestellten Einträge
(3520/3520) sind übersetzt, 0 Reste in ASCII-Schreibung.**

## v0.3.0 – Restliche Inhalte

### Neu

25 weitere Kategorien übersetzt (jeweils aus den offiziellen `ExampleLanguage`-Vorlagen,
KI-gestützt via Haiku, Token- und Tag-geprüft: `=…=`, `{{…}}`, Inline-Tags wie
`<p>`, `<br/>`, `<stat/>` bleiben erhalten):

- **Fertigkeiten** (`Skills.de.xml`) – Namen, Beschreibungen und Kräfte
- **Aktivierte Fähigkeiten** (`ActivatedAbilities.de.xml`)
- **Bücher** (`Books.de.xml`) – Buchtexte/Seiten
- **Quests** (`Quests.de.xml`)
- **Optionen** (`Options.de.xml`), **Inventar-Aktionen** (`InventoryActions.de.xml`),
  **Statistiken** (`Statistics.de.xml`), **Handbuch** (`Manual.de.xml`)
- **Fraktionen** (`Factions.de.xml`, `ChiliadFactions.de.xml`), **Untertypen**
  (`Subtypes.de.xml`), **Relikte** (`Relics.de.xml`)
- **Flüssigkeiten** (`Liquids.de.xml`), **Effekt-Details** (`EffectsDetails.de.xml`),
  **versteckte Mutationen** (`HiddenMutations.de.xml`)
- **Gelände** (`WorldTerrain.de.xml`, `ZoneTerrain.de.xml`), **Welten/Biome**
  (`Worlds.de.xml`, `Biomes.de.xml`), **Einschiffungs-Module** (`EmbarkModules.de.xml`)
- sowie `Data`, `Mods`, `PronounSets`, `Widgets`, `SparkingBaetyls`

Alle **3.181 Textbausteine** dieser Kategorien wurden übersetzt (100 %) – inklusive
der komplexen Einträge mit verschachtelten Platzhaltern (`<switch>`/`<case>`,
mehrfache `<stat/>`, `=spice:…=`), die zum Schluss von Hand token-genau übertragen wurden.

### Nicht übersetzt (absichtlich)

- **Namen-Generierung** (`Naming`): besteht aus prozeduralen Namenssilben/-fragmenten;
  eine Übersetzung würde die Namensbildung beschädigen und wird daher ausgelassen.

## v0.2.0 – Vollständige Oberfläche und Dialoge

### Neu

- **Oberfläche (UI) nahezu vollständig:** `Strings.de.xml` von 1362 auf **5120 von 5189**
  Strings erweitert (≈ 99 %). Menüs, Optionen, Tooltips, Pop-ups, Ladebildschirm-,
  Tutorial- und Hinweistexte sind jetzt fast durchgängig auf Deutsch.
- **Dialoge vollständig:** `Strings.Conversations.de.xml` mit **4571 von 4571** Zeilen
  (100 %). NPC-Gespräche, Antwortoptionen und Erzähltext erscheinen auf Deutsch.
- **UI-Anhang:** `Strings.appendix.de.xml` **14 von 14** (100 %).

Die zusätzlichen Übersetzungen wurden aus den offiziellen Vorlagen
(`ExampleLanguage/*.example.xml`) erzeugt (KI-gestützt, Token-geprüft: `=…=`, `{{…}}`,
`{0}` bleiben erhalten). Rund 69 UI-Strings mit komplexen Platzhaltern bleiben vorerst
englisch.

## v0.1.0 – Erste Version

### Aktuell übersetzt

| Bereich | Datei | Umfang |
|---|---|---|
| Kreaturen (Namen + Beschreibungen) | `Creatures.de.xml` | 1096 Objekte |
| Gegenstände (Namen + Beschreibungen) | `Items.de.xml` | 880 Objekte |
| Möbel/Einrichtung | `Furniture.de.xml` | 276 Objekte |
| Wände/Gelände-Blöcke | `Walls.de.xml` | 172 Objekte |
| Mutationen (Namen + Kategorien) | `Mutations.de.xml` | 82 Mutationen, 5 Kategorien |
| Nahrung | `Foods.de.xml` | 20 Objekte |
| Physikalische Phänomene | `PhysicalPhenomena.de.xml` | 12 Objekte |
| Versteckte Objekte | `HiddenObjects.de.xml` | 8 Objekte |
| Genotypen (Rassen + Attribut-Beschreibungen) | `Genotypes.de.xml` | 2 Genotypen |
| Oberfläche / UI-Texte | `Strings.de.xml` | 1362 Strings |
| UI-Anhang | `Strings.appendix.de.xml` | 5 Strings |
| Dialoge (Konversationen) | `Strings.Conversations.de.xml` | 15 Strings |

Konkret bedeutet das: Menüs, Optionen, Ladebildschirm-Meldungen, Tutorial-Texte, viele
Pop-ups sowie die Namen und „Untersuchen"-Beschreibungen von Kreaturen, Gegenständen,
Möbeln, Wänden und die Charaktererstellung (Genotypen, Mutationsnamen) erscheinen bereits
auf Deutsch.

### In Arbeit (noch nicht enthalten)

- **Restliche UI-Texte:** von 5189 UI-Strings sind aktuell 1362 übersetzt; die übrigen
  ~3600 werden gerade übersetzt und folgen in v0.2.
- **Dialoge:** von ~4500 Konversationszeilen sind erst 15 übersetzt; die vollständige
  Dialogübersetzung ist in Arbeit und folgt in v0.2.
- Noch nicht portiert: Bücher, Quests, Fertigkeiten (Skills), Fraktionen, aktivierte
  Fähigkeiten, Relikte, Statistiken, Biome u. a.

### Bekannte Einschränkungen

- **Keine Umlaute:** Die übernommenen Übersetzungen verwenden ASCII-Schreibweise
  (ae/oe/ue/ss statt ä/ö/ü/ß). Grund ist die Herkunft aus dem älteren QudDE-Projekt.
  Die offizielle Lokalisierungs-API kann echte Umlaute vermutlich darstellen – eine
  spätere Umstellung auf ä/ö/ü ist geplant.
- **Maschinelle Übersetzung:** Nahezu alle Texte stammen aus einer KI-gestützten
  Übersetzung (gesichtet, aber fehleranfällig). Übersetzungsfehler, fehlende Stellen und
  gelegentlich unglückliche Formulierungen sind wahrscheinlich.
- **Prototyp:** Noch unvollständig; viele Bereiche bleiben vorerst englisch.

### Voraussetzungen

- Caves of Qud auf dem **`lang-experimental`**-Branch (Steam → Eigenschaften → Betas).
- Mod aktivieren (Scripting), dann unter „Languages" **Deutsch** wählen.

### Grundlage

Übersetzungsinhalte stammen aus dem [QudDE-Projekt](https://github.com/Noires/qud-german-localization-mod).
Format und Aufbau orientieren sich an den offiziellen Beispiel-Sprachdateien des Spiels
(`ExampleLanguage/*.example.xml`), am koreanischen Referenz-Mod sowie am
[Caves of Qud Japanese Mod](https://github.com/ToaruPen/coq-japanese_stable) von ToaruPen.
