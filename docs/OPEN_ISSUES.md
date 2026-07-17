# Open Issues & Resources (native migration)

_Last updated: 2026-07-17 (session 2). Branch: `native-migration`._

## Open issues

### 1. Body-part names in the anatomy/equipment paperdoll (UI) — decision deferred
- **Symptom:** body-part names show English on the equipment/anatomy screen.
- **What we know:** the paperdoll builds names via `BodyPart.GetCardinalName()` **in C#** — no
  `=part.name=` token, no provider hook. The old DLL worked by Harmony-patching exactly
  `GetCardinalName()`. The Turkish mod shelved its attempt (`UnusedDelegates.tr.cs`).
- **DONE (committed):** native `name`/`ordinalName` replacer override with German laterality
  inflection (`TransformBodyPart`: "right hand" → "rechte Hand") covers the **token path**
  (combat / ability / mutation text). Load-time self-test included.
- **Decision (2026-07-17): deferred by user.** Options remain: (b) minimal Harmony shim patching
  only `GetCardinalName()` (can reuse `TransformBodyPart`), or (c) accept English there
  (100% DLL-free like Turkish).

### 2. Death screen ("You were killed by …") — likely fixed, needs one in-game death to confirm
- Both `DeathReason` entries exist (IDs byte-identical to Turkish's) and the German word order was
  improved ("Ihr wurdet [versehentlich ]von =object.a.dativ= getötet.").
- Log evidence: the 2026-07-17 00:44 run reached `XRLCore.BuildScore` (death screen) with **no**
  `DeathReason` string-table miss logged → the lookup hit. Any English seen earlier was likely
  a pre-fix or cached death.
- **To close:** die once in a fresh run; if the death line is English, check `Player.log` for a
  new miss line and add that exact `Context`/`ID`.

## Resolved 2026-07-17 (session 2)

### ID-attribute corruption (major regression, found while auditing) — FIXED
- The `=verb:X=` → `=konjde:INF=` conversion (commits a28f0c0, 1e4e0cb) rewrote verb tokens in
  **ID attributes as well as Values**. The game resolves entries via
  `ContextStrings(Context).TryGetValue(ID)` (`XRL.Language.Strings.TryGetString`) with the exact
  **English** template as key → 505 entries in `Strings.de.xml` + 1 in
  `Strings.Conversations.de.xml` silently fell back to English.
- Restored original English IDs from pre-conversion commit 0520a1b (matched by Context +
  token-stripped skeleton); German Values kept; 8 stale duplicates deleted. Commit ce1c901.
- **Rule going forward: never edit `ID="…"` — it is the lookup key, byte-exact English.**

### 3. Worlds.de.xml — FIXED (was "188 untranslated zones")
- The 188 `▶` entries were **orphaned generator stubs** directly under `<worlds>` (outside any
  `<world>`/`<cell>`), duplicating zones already translated in the structured section. Verified
  against the game's `Base/Worlds.xml`: 281/284 zone keys covered, the 3 absent are
  `Name="None"` engine sentinels (Turkish omits them too), 0 stale keys. Stubs deleted.
- Also fixed translated booleans: `ProperName="wahr"`(27)/`"Falsch"`(4) → `"true"`/`"false"`;
  per-zone ProperName now matches English exactly. Commit a295c8a.

### Mutations.de.xml MODWARN spam — FIXED
- The `MODWARN XmlDataHelper` spam was **not** (only) Worlds: 59 warnings came from
  `<statline Name=… DisplayName=…/>` elements misplaced as direct children of `<mutation>`.
  Merged each DisplayName onto the matching `<statline>` inside `<leveltext>` (Turkish-mod
  placement), orphans removed. Commit f31edd3. Together with the Worlds stub removal, all 247
  of our MODWARN lines should be gone — verify in the next run's `Player.log`.

## Status of what's DONE (native)
- Verbs (`=konjde:INF=`), cases (nom/akk/dat/gen), adjective declension, pronouns — native.
- Body parts in **text** — native (replacer override incl. laterality inflection).
- 5 death reasons — native (match Turkish); word order improved.
- All 15 string-table misses from the last playtest — covered.
- 506 corrupted lookup IDs restored; Worlds/Mutations schema warnings eliminated.
- Smoke-compile passes; deployed mod copy verified hash-identical for all changed files.

## Resources on hand (in `docs/`)

### Game source (reference, gitignored under `docs/archive/`)
- `docs/archive/coqcode/` — the game's localization engine source:
  - `Translator.cs`, `Translator.Provider.cs`, `TranslatorBase.cs`, `TranslatorEnglish.cs`,
    `Grammar.cs` — the provider contract & English baseline (what we can override).
  - `Delegates/Delegates.*.cs` (~33 files) — every built-in `[VariableReplacer]`. Key ones:
    - `Delegates.BodyPart.cs` — proves `name` uses `Part.Name`; paperdoll bypasses tokens.
    - `Delegates.GameObject.cs` — object display-name replacers.
    - `Delegates.PostProcessors.cs` — chained `|postprocessor` delegates.
  - NOTE: the string-table lookup itself is NOT in the archive; decompile
    `XRL.Language.Strings` from Assembly-CSharp with `ilspycmd` when needed.
- `docs/archive/caves-of-qud-turkish-main/` — official 100% native reference mod:
  - `Data/Code/*.tr.cs` — their replacers/post-processors (incl. `UnusedDelegates.tr.cs`, the
    abandoned body-part attempt).
  - `Data/Strings.tr.xml`, `Strings.Conversations.tr.xml` — their data-layer strings incl.
    `… DeathReason` entries (our death IDs match these exactly).
  - `Data/Mutations.tr.xml` — `<switch Name="BodyPartName">` pattern + correct statline placement.
  - `Data/Worlds.tr.xml` — correct zone localization structure (`ProperName="true"`, no stubs).

### Our planning docs
- `docs/NATIVE_MIGRATION_PLAN.md` — full plan, locked decisions, testing strategy.
- `docs/RUNTIME_POSTPROCESSOR_PLAN.md` — replacer/post-processor design notes.
- `docs/KOREAN_PARITY_GAPS.md` — parity diff vs the Korean mod.
- `docs/SCREENSHOT_FIXES_PLAN.md` + `docs/screenshots/` — in-game issue screenshots & fixes.

### Diagnostics
- `OptionDebugStringTableMisses` — already ON; logs `String table miss - Lang de - Context=… ID=…`
  to `Player.log` (`%AppData%/../LocalLow/Freehold Games/CavesOfQud/Player.log`). This is the
  ground-truth tool for the open issues above.
- `MODWARN [Caves of Qud German Translation]` lines in `Player.log` — schema errors in our
  `*.de.xml`; should now be zero.
- `build/smoke/smoke.csproj` — mandatory pre-deploy compile gate for `CODE/*.cs`.
