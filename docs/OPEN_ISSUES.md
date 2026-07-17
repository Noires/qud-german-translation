# Open Issues & Resources (native migration)

_Last updated: 2026-07-17 (session 3). Branch: `native-migration`._

## Waiting on official localization support (decision 2026-07-17: no shims, wait for the dev team)

### 1. Body-part names in the anatomy/equipment paperdoll (UI)
- The paperdoll builds names via `BodyPart.GetCardinalName()` **in C#** — no `=part.name=` token,
  no provider hook, no string-table lookup. Only a Harmony patch could reach it (the retired
  DLL's approach); the official Turkish mod shelved its attempt (`UnusedDelegates.tr.cs`).
- **Covered natively (committed):** the token path (combat / ability / mutation text) via our
  `name`/`ordinalName` replacer override with German laterality inflection
  ("right hand" → "rechte Hand"). Load-time self-test passes in every run.
- **Status: WAIT** for the dev team to expose a body-part hook/token for the paperdoll.

### 2. Death screen ("You were killed by …")
- **Generic combat deaths** go through the string table: `"DeathReason Killed By"` exists exactly
  once in Assembly-CSharp (2.0.212.29), our entry is present with a byte-correct English ID, and
  no `DeathReason` miss appears in any post-fix log — that path should render German.
- **Specific causes are C# literals with no data hook:** confirmed by binary scan —
  `"bled to death"` (1 hit), `"died of thirst"` (2 hits), `"You died"` (5 hits) are embedded
  strings, not templates; no `Context="DeathReason …"` exists for them. The Turkish mod only
  covers the same 5 entries we ship. The old DLL translated these at display time.
- **Status: WAIT** for the dev team to route death causes through the string table.
  (In current disable-DLL mode these show English by design.)

## Known-benign (do not chase)

### 7 string-table misses at every startup (DifficultyEvaluation ×6, Message Log Title)
- Logged at app startup **before** `RefreshModDirectory` runs — the base game queries them during
  boot, before mod string tables exist. Both `StringsLoader` and the consumer cache
  (`DifficultyEvaluation._DifficultyTranslations`) are `[ModSensitiveStaticCache]`: they are
  cleared when mods load and rebuilt on next access, so **in-game text is German**. The miss
  lines are once-per-session log noise and cannot be fixed from mod data.

## Resolved 2026-07-17

### ID-attribute corruption (major regression) — FIXED (ce1c901)
- The `=verb:X=` → `=konjde:INF=` conversion (a28f0c0, 1e4e0cb) rewrote verb tokens in
  **ID attributes as well as Values**. The game resolves entries via
  `ContextStrings(Context).TryGetValue(ID)` with the exact **English** template as key →
  505 entries in `Strings.de.xml` + 1 in `Strings.Conversations.de.xml` silently fell back to
  English. Restored from pre-conversion commit 0520a1b; 8 stale duplicates deleted.
- **Rule: never edit `ID="…"` — it is the lookup key, byte-exact English.**

### 3. Worlds.de.xml — FIXED (a295c8a)
- The "188 untranslated zones" were orphaned generator stubs outside any `<world>`; the
  structured section already covers 281/284 zone keys (3 absent are `Name="None"` sentinels,
  Turkish omits them too). Stubs deleted; `ProperName="wahr"/"Falsch"` booleans → `"true"/"false"`.

### Mutations.de.xml MODWARN spam — FIXED (f31edd3 + session 3)
- 59 `<statline DisplayName=…>` elements were misplaced as direct children of `<mutation>`:
  54 merged into `<leveltext>`, 5 redundant ones removed; the last 5 stragglers (Slime Glands,
  Kindle — mutations whose statlines live inside `<description>` in the English source) moved
  to match English placement. Expected MODWARN count for our mod next run: **0**.

## Current mode
- **100% native — DLL retired 2026-07-17**: `COQDE.dll`, `Bootstrap.cs`, `Patterns.json` and
  `Terms.json` removed from repo and deploy (recoverable from git history, last present at
  commit e19d38d). `languages/lang-de/COQDE/` now holds only the shared data files
  `GenderLexicon.tsv` + `Verbs.json`, loaded by `CODE/VariableReplacers.de.cs`. Code-built
  message-log lines are untranslated pending official support (same as Turkish).
- Native layer self-tests: 25/25 PASS every run (cases, phrases, verbs, body parts).

## Status of what's DONE (native)
- Verbs (`=konjde:INF=`), cases (nom/akk/dat/gen), adjective declension, pronouns — native.
- Body parts in **text** — native (replacer override incl. laterality inflection).
- 5 death reasons — native (match Turkish); word order improved.
- 506 corrupted lookup IDs restored; Worlds/Mutations schema warnings eliminated.
- **`TranslatorDeutsch` provider** (`CODE/Translator.de.cs`, `[LanguageProvider("de")]`):
  de-DE culture + German number words. Covers ALL number tokens (=cardinal=, =ordinal=,
  =multiplicative=, cardinal.things, …) since they route through Translator.* (verified in
  Delegates.Numbers.cs). Self-test `[QudDE] zahl-test` runs at load.
- **`TextConstants.de.xml`**: weirdSets without ä/Ä/ö/Ö/ü/Ü/ß; German article word-list so
  `MutateZoneName` injects biome adjectives AFTER the article.
- **`Naming.de.xml`**: partial file (Turkish pattern) — site-name templates, hero titles/
  epithets, village roles, Gyre wights. Syllable pools inherit from Base. SUBSTRING CONTRACT:
  hero builders check `text.Contains(_S("<X> Naming.xml Context", …))` — Naming values must
  contain the matching Strings.de.xml value as substring (10 legacy values fixed for this).
- **`Untranslated.de.xml`**: bookkeeping for intentionally-identical templates (never loaded,
  `Lang="de-unuebersetzt"`).
- `Genders.de.xml` confirmed loaded (generic `GetXMLFilesWithRoot("genders")` path).
- Smoke-compile passes; deployed mod copy synced.

## Follow-ups (deliberately NOT done yet)
- **Possessive `'s` tokens** (49 Values, fast alles HistorySpice): `Grammar.MakePossessive`
  ist hartes Englisch-C#; sauberste Lösung ist Umformulierung auf `=genitiv=` je Stelle.
- **2 asPossessed-Kasus-Fälle** (Rest von ursprünglich ~15, erledigt 2026-07-17): die
  Kasus-Replacer unterstützen jetzt `single/long/withTitles/asIfKnown` + `itsPossessor`
  (Besitzer-Genitiv-Anhang). Offen nur noch `:asPossessed:secondPerson` (2 Values,
  „Eurer X"-Possessivpronomen-Logik) — Suchmuster `asPossessed:secondPerson` in Strings.de.xml.
- **`LibraryCorpus.de.json`** (prozedurale Markov-Bücher, Base 2.4 MB): Generator-Skript über
  die schon übersetzte `Books.de.xml` wäre der Weg; großer Sichtungsaufwand.
- **LICENSE-Datei**: Nutzerentscheidung (QudDE-kompatibel vs. MIT).

## Resources on hand (in `docs/`)

### Game source (reference, gitignored under `docs/archive/`)
- `docs/archive/coqcode/` — the game's localization engine source:
  - `Translator.cs`, `Translator.Provider.cs`, `TranslatorBase.cs`, `TranslatorEnglish.cs`,
    `Grammar.cs` — the provider contract & English baseline (what we can override).
  - `Delegates/Delegates.*.cs` (~33 files) — every built-in `[VariableReplacer]`.
  - NOTE: the string-table code (`XRL.Language.Strings`, `StringsLoader`) is NOT in the archive;
    decompile from Assembly-CSharp with `ilspycmd -t <type>` when needed.
- `docs/archive/caves-of-qud-turkish-main/` — official 100% native reference mod
  (Strings/Worlds/Mutations structure, DeathReason entries, shelved body-part attempt).

### Our planning docs
- `docs/NATIVE_MIGRATION_PLAN.md` — the migration plan (executed; kept for the locked decisions).
- DLL-era docs (`RUNTIME_POSTPROCESSOR_PLAN`, `KOREAN_PARITY_GAPS`, `SCREENSHOT_FIXES_PLAN`)
  were removed with the DLL on 2026-07-17 — recover from git history if ever needed.

### Diagnostics
- `OptionDebugStringTableMisses` — ON; logs `String table miss - Lang de - Context=… ID=…` to
  `Player.log`. Expected baseline: exactly the 7 benign startup misses listed above.
- `MODWARN [Caves of Qud German Translation]` in `Player.log` — schema errors; expected: 0.
- `build/smoke/smoke.csproj` — mandatory pre-deploy compile gate for `CODE/*.cs`.
