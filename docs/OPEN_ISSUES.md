# Open Issues & Resources (native migration)

_Last updated: 2026-07-17. Branch: `native-migration`._

## Open issues

### 1. Body-part names in the anatomy/equipment paperdoll (UI)
- **Symptom:** body-part names show English on the equipment/anatomy screen.
- **What we know:** the paperdoll builds names via `BodyPart.GetCardinalName()` **in C#** — no
  `=part.name=` token, no provider hook (`TranslatorBase` has `GameObjectDisplayName` but nothing
  for BodyPart). The old DLL worked by Harmony-patching exactly `GetCardinalName()`.
- **Official reference confirms the wall:** the Turkish mod shelved its body-part replacer in a file
  named `UnusedDelegates.tr.cs`; their anatomy UI stays English.
- **What DOES work natively:** our `name`/`ordinalName` replacer override localizes body parts in
  **combat / ability / mutation text** (the token path). Only the paperdoll UI is out of reach.
- **Open decision:** (a) confirm empirically via a fresh string-miss log, (b) keep a minimal Harmony
  shim patching only `GetCardinalName()`, or (c) accept English there (100% DLL-free like Turkish).

### 2. Death screen ("You were killed by …")
- **Symptom:** death cause reported as English in a playtest.
- **What we know:** death reasons ARE data-layer localizable (Turkish does it). Our 5 entries are
  **byte-identical to Turkish's** (`DeathReason Killed By`, `Self Kill`, `SunderMind` ×2,
  `Core DeathReason Abandoned Hope`). The generic combat death maps to `DeathReason Killed By`.
- **Open question:** was the English death a *normal combat death* (should now be German after a fresh
  run), a *specific reason* we don't cover yet (thirst/fall/effect → add it), or an *old/cached death*?
- **Definitive test:** enable string-miss logging (already ON), die fresh, read `Player.log` — a miss
  line gives the exact `Context`/`ID` to fill; no miss = the cause is cached in C# (needs a shim).

### 3. Worlds.de.xml — 188 untranslated zones (separate, pre-existing)
- 188 of 469 `<zone>` entries still English, marked with a `▶` prefix (endgame Sheva/Ark zones).
- The `▶` prefix is what generates the `MODWARN XmlDataHelper` spam in the log.
- Cleanup/translation pass needed; unrelated to body parts/death.

## Status of what's DONE (native)
- Verbs (`=konjde:INF=`), cases (nom/akk/dat/gen), adjective declension, pronouns — native.
- Body parts in **text** — native (replacer override).
- 5 death reasons — native (match Turkish).
- 15 string-table misses from the last playtest — all covered (8 added, 7 dup entries removed).
- Smoke-compile passes; deployed to the mod folder and in sync.

## Resources on hand (in `docs/`)

### Game source (reference, gitignored under `docs/archive/`)
- `docs/archive/coqcode/` — the game's localization engine source:
  - `Translator.cs`, `Translator.Provider.cs`, `TranslatorBase.cs`, `TranslatorEnglish.cs`,
    `Grammar.cs` — the provider contract & English baseline (what we can override).
  - `Delegates/Delegates.*.cs` (~33 files) — every built-in `[VariableReplacer]`. Key ones:
    - `Delegates.BodyPart.cs` — proves `name` uses `Part.Name`; paperdoll bypasses tokens.
    - `Delegates.GameObject.cs` — object display-name replacers.
    - `Delegates.PostProcessors.cs` — chained `|postprocessor` delegates.
- `docs/archive/caves-of-qud-turkish-main/` — official 100% native reference mod:
  - `Data/Code/*.tr.cs` — their replacers/post-processors (incl. `UnusedDelegates.tr.cs`, the
    abandoned body-part attempt).
  - `Data/Strings.tr.xml`, `Strings.Conversations.tr.xml` — their data-layer strings incl.
    `… DeathReason` entries (our death IDs match these exactly).
  - `Data/Mutations.tr.xml` — `<switch Name="BodyPartName">` pattern example.

### Our planning docs
- `docs/NATIVE_MIGRATION_PLAN.md` — full plan, locked decisions, testing strategy.
- `docs/RUNTIME_POSTPROCESSOR_PLAN.md` — replacer/post-processor design notes.
- `docs/KOREAN_PARITY_GAPS.md` — parity diff vs the Korean mod.
- `docs/SCREENSHOT_FIXES_PLAN.md` + `docs/screenshots/` — in-game issue screenshots & fixes.

### Diagnostics
- `OptionDebugStringTableMisses` — already ON; logs `String table miss - Lang de - Context=… ID=…`
  to `Player.log` (`%AppData%/../LocalLow/Freehold Games/CavesOfQud/Player.log`). This is the
  ground-truth tool for both open issues above.
- `build/smoke/smoke.csproj` — mandatory pre-deploy compile gate for `CODE/*.cs`.
