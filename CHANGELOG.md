# Änderungsverlauf – Caves of Qud Deutsch (lang-experimental)

Deutsche Lokalisierung auf Basis der offiziellen Lokalisierungs-Unterstützung im
`lang-experimental`-Branch. Reines Daten-Mod (keine Harmony-Patches, keine DLL).

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
