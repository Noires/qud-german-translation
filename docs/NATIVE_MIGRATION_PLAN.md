# Native Migration Plan — official replacer/post-processor pipeline

> **Status: EXECUTED (2026-07-17).** Phase 2 complete — the DLL stack (`COQDE.dll`,
> `Bootstrap.cs`, `Patterns.json`, `Terms.json`, `build/COQDE/`) is deleted; only
> `GenderLexicon.tsv` + `Verbs.json` remain as shared data for the native token layer.
> This document is kept for the locked decisions and testing strategy.

Goal: replace the external Harmony runtime (`COQDE.dll` + `Patterns.json` regex) with the
game's **official** localization pipeline — `[LanguageProvider("de")]` + `[VariableReplacer]`
+ `[VariablePostProcessor]` — mirroring the Freehold-authored Turkish reference
(`docs/archive/caves-of-qud-turkish-main`, author: "Freehold Games and Community Contributors").

That reference proves the official way is sufficient: it covers a *harder* language than German
(full case system, vowel harmony, verb conjugation) **with zero Harmony, zero external DLL,
only `.cs` the game compiles.**

## Why migrate

| | Current (COQDE.dll) | Native (target) |
|---|---|---|
| Mechanism | external Harmony DLL + regex on finished strings | game-compiled replacers/post-processors in the token pipeline |
| Route coverage | only the ~7 patched methods (the "62-hooks" ceiling) | all text through the engine, automatically |
| Case handling | guessed after assembly | encoded in the template we author (`:dativ`) |
| Stability | Harmony vs. internal methods → breaks on updates | official API, update-safe |
| Build | dotnet + Managed refs + reflection loader | none — just `.cs` |

Reframe: we already run `[HasVariableReplacer(Lang="de")]` (article replacers). This is an
**extension of what works + retirement of the DLL**, not a rewrite from zero.

## Target architecture (all under the game-compiled Code folder)

- `Translator.de.cs` — `[LanguageProvider("de")] class TranslatorGerman : TranslatorBase`.
  Engine core: culture (de-DE), capitalization, gender resolution, article/adjective tables,
  helpers. Port from `GermanGrammar.cs` + `Gender.cs`.
- `VariableReplacers.de.cs` (extend existing) — case + name replacers:
  - `nom` / `akk` / `dat` / `gen` (e.g. `=object.the.name:dat=` → "dem …/der …/den …"),
    with type-overloads `(VariableContext, GameObject)` / `(…, string)`.
  - verb conjugation replacer (`=subject.konj:verb=`) — port `Verbs.json` + `ConjugateEnglish`.
  - pronouns/possessives (or defer to `Genders.de.xml`, which already localizes them).
  - reflexive via `Context.Invocation.Subject == Object` → "sich"/"euch".
- `PostProcessors.de.cs` — chained `|` transforms: adjective declension, case fixups, capitalize
  (built-in). Use `Context.SetState/GetState` for cross-token sentence state.
- `*.de.xml` + `HistorySpice.jsonc` — existing translations, **progressively enriched** with
  grammar tokens where declension matters.

## German-specific design notes

- **Gender source** is German's extra need (Turkish has none): keep `Gender.cs` heuristic +
  `GenderLexicon.tsv` for grammatical gender of common nouns.
- **Case** is encoded by the translator in the template (`:dat` after "mit/von/zu", `:gen`, etc.).
  This is the crux the DLL couldn't solve — now solved because *we* author the template.
- **Adjective declension** (strong/weak/mixed × case × gender) — port from `GermanGrammar.cs`;
  determiner type comes from which replacer/param produced the article.
- **Color markup**: preserve `{{...}}` while inflecting — mirror Turkish `Handle*Color` helpers.
- **Reflexive**: German is simple — 3rd person → "sich", player (Ihr) → "euch".

## Phases

**Phase 0 — Spike (GATE).** Add `[LanguageProvider("de")]` skeleton + one `:dat` case replacer;
compile in-game (`testreplacers`/`testlangreplacers` wishes), prove the pipeline and inspect the
real `VariableContext` surface (gender access, player, capitalize, state). Confirm whether the
lang-experimental branch already ships a `de` provider we must coexist with. Decides everything.

**Phase 1 — Grammar engine port.** `Translator.de.cs` + core replacers (nom/akk/dat/gen article
+ name, verb conjugation, reflexive). Validate with the in-game replacer test wishes.

**Phase 2 — Retire external build.** Once native covers the combat/death/popup cases, remove
`COQDEMod.cs` (Harmony), `Bootstrap.cs` (reflection loader), the `.csproj`/dotnet build, and
`Patterns.json`. Keep running the DLL in parallel until then (no regression window).

**Phase 3 — Template enrichment.** Add case/grammar tokens to existing German templates where
declension matters, prioritized by visibility. Large but incremental; base translations already
exist.

**Phase 4 — Residual.** Truly-literal strings not in the manifest (e.g. some code-built popups)
are unreachable by any replacer → data-layer / report to devs, not our code.

## Keep / port / drop

- **Keep & port:** `GermanGrammar.cs`, `Gender.cs`, `GenderLexicon.tsv`, `Verbs.json` (logic),
  `Terms.json`; all `*.de.xml` + `HistorySpice.jsonc`.
- **Drop (Phase 2):** `COQDEMod.cs`, `Bootstrap.cs`, `build/COQDE/*.csproj` + dotnet build,
  `Patterns.json`, the compiled `COQDE.dll`.

## Decisions (locked 2026-07-16)

1. **Mod layout**: **STAY** on `languages/lang-de/CODE/` (already game-compiled). No move to `Data/`.
2. **Branch/build target**: **STAY** on our current build (`lang-experimental`). Phase 0 must
   confirm `TranslatorBase`/`LanguageProvider` are available here.
3. **Pronoun/possessive**: **MOVE to `GetPronounProvider()` replacers** (reads the same data as
   `Genders.de.xml`, but lets us control emission — reflexive, case, capitalization).

## Testing strategy (our "test way")

Mirrors the Freehold/Turkish model (examples-as-tests, verified in-game), plus an offline
layer they don't have. Three tiers, cheapest first:

1. **Smoke-compile (offline, every change, mandatory gate).** `build/smoke/smoke.csproj`
   compiles the game-compiled `.cs` (`languages/lang-de/CODE/*.cs`) against the game's Managed
   DLLs via `dotnet build`. A syntax/API error here would otherwise silently disable **all**
   replacers in-game. **Never deploy a `.cs` that hasn't smoke-compiled to 0 errors.**

2. **`[VariableExample]` attributes on every replacer/post-processor (the canonical grammar
   test).** Exactly the Turkish convention: `[VariableExample("dem Krokodil:Dem Krokodil", "Croc")]`
   = for input `Croc`, expect `dem Krokodil` (or capitalized). The built-in `GameTextTests`
   harness runs them via the base-game wishes **`testreplacers` / `testlangreplacers`** (these are
   base-game `WishCommand`s, not mod-provided; they require an **active game session**, not the
   main menu). For state-dependent grammar, adopt Turkish's custom
   `VariableInvocationExampleAttribute` (pre-sets `Context.Invocation` state before the example
   runs; syntax `"var"` / `"!var"` / `"var::value"`, joined by `;;`).

3. **Load-time self-test log (offline, no active game needed).** A `SelfTest*()` method called
   from the mod-init prints input→output to `Player.log` as `[QudDE] …-selftest:` lines (same
   idea as the existing `[QudDE] self-test:` beacons). This is our advantage over the Turkish
   mod, which can only validate in-game: we can confirm grammar output by **restarting to the
   main menu and reading the log** — no wish, no character. Use it for the tricky paths
   (gender→article, declension) during development; keep `[VariableExample]` as the durable suite.

**Coverage** (separate concern, unchanged): `build/tools/coverage_audit.py` diffs the `▶`
manifest vs our `*.de.xml` — our equivalent of the Turkish `Scripts/*.js` completeness tools.

Rule of thumb: **smoke-compile before every deploy; add a `[VariableExample]` for every new
grammatical case; use the log self-test to debug, `testreplacers` for the full in-game suite.**

## Risks

- **Compile fragility**: the game compiles `Code/*.cs`; any error disables the whole class set →
  set up a local smoke-compile against the Managed DLLs before every deploy.
- **Content scale**: enriching thousands of templates with case tokens is the big cost — but
  incremental, and only where grammar is visibly wrong today.
- **Coexistence with a built-in `de` provider** (if one exists on lang-experimental) — Phase 0
  must clarify whether we subclass, override, or replace it.
