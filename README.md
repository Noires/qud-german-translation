# Caves of Qud – Deutsch (lang-experimental)

Deutsche Lokalisierung für Caves of Qud auf Basis der **offiziellen Lokalisierungs-Unterstützung** im `lang-experimental`-Branch. Im Gegensatz zum älteren [QudDE](https://github.com/Noires/qud-german-localization-mod)-Mod (Harmony-Patches für die 1.0.4-Release-Version) ist dies ein reines **Daten-Mod** ohne Laufzeit-Patches: Es liefert Übersetzungstabellen im offiziellen Format unter `languages/lang-de/`.

## Status

Prototyp. Die Übersetzungen wurden aus dem QudDE-Projekt übernommen (KI-gestützt, gesichtet). Fehler, fehlende Stellen und unglückliche Formulierungen sind wahrscheinlich.

## Aufbau

- `manifest.json` – Mod-Metadaten (offizielles Format).
- `languages/languages.xml` – deklariert die Sprache `de` / „Deutsch“.
- `languages/lang-de/*.de.xml` – Übersetzungstabellen pro Kategorie (Strings, Creatures, Items, Walls, Furniture, Genotypes, Mutations, …), analog zu den Vorlagen unter
  `CoQ_Data/StreamingAssets/Base/ExampleLanguage/*.example.xml`.

## Voraussetzungen

- Caves of Qud auf dem **`lang-experimental`**-Branch (in Steam unter Eigenschaften → Betas auswählen).
- Scripting/Mods im Spiel aktivieren, dann unter „Languages" **Deutsch** wählen.

## Grundlage

Basiert auf dem Format der offiziellen Beispiel-Sprachdateien sowie auf dem koreanischen Referenz-Mod und dem [Caves of Qud Japanese Mod](https://github.com/ToaruPen/coq-japanese_stable) von ToaruPen. Übersetzungsinhalte stammen aus dem QudDE-Projekt.

Caves of Qud ist ein Werk von Freehold Games. Dies ist ein inoffizielles Community-Mod.
