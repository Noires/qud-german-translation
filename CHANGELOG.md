# Änderungsverlauf – Caves of Qud Deutsch (lang-experimental)

Deutsche Lokalisierung auf Basis der offiziellen Lokalisierungs-Unterstützung im
`lang-experimental`-Branch. Reines Daten-Mod (keine Harmony-Patches, keine DLL).

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
