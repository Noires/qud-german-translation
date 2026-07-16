# Plan: German Runtime Message Post-Processor (Korean-parity)

Status: **Phase 1 IMPLEMENTED (prototype), v0.8.0.** Skeleton, engine, seed patterns and
build are in place and verified offline; in-game verification pending.
Goal: translate the *code-built* combat/status message log (e.g. "The snapjaw dies.")
that the data layer and VariableReplacers cannot reach, using the same technique the
Korean reference mod uses.

## Implementation status (updated 2026-07-16)

DONE (Phase 1):
- `build/COQDE/` net48 project builds `COQDE.dll` against the game's own Managed assemblies
  (all `Private=false` — only the DLL is produced). Source split into game-decoupled `src/`
  (Gender, GermanGrammar, RouteTranslator — System + Newtonsoft only) and game-coupled
  `game/` (Init, Harmony discovery, MessageLog hook, language guard, self-test).
- `languages/lang-de/COQDE/`: `Bootstrap.cs` (game-compiled reflection loader), `COQDE.dll`,
  and seed `Patterns.json` (34 frames), `Verbs.json` (7), `Terms.json` (9).
- Hooks: Harmony **Prefix** on `XRL.Messages.MessageQueue.AddPlayerMessage` (route
  `MessageLog`) and on `XRL.UI.Popup.Show*` (route `Popup`), both rewriting string args. (COQKR
  uses Prefixes here too.) Term fallthrough is restricted to `MessageLog`; `Popup` gets
  anchored-pattern rewrites only, so it can't half-translate arbitrary UI text.
- Death-screen frames added (route `MessageLog`+`Popup`+`UIText`): "You were &lt;verb&gt; to death
  by X.", "You were killed by X.", "You bled to death[ because of …].", preserving the already-
  German "Du bist gestorben." prefix. This fixed the reported "You were bitten to death by a
  Snapjaw-Brut." → "Ihr wurdet von einer Snapjaw-Brut zu Tode gebissen."
- Full Korean-mod route/hook gap analysis: **docs/KOREAN_PARITY_GAPS.md** (next candidates:
  `GameSummary` for the death/end screen, `BodyPart` laterality, `Possessive`).
- `unmatched`-line debug logging (enable by placing an empty `COQDE.debug` next to the DLL).
- Shape operators implemented: `nom/acc/dat/gen` (+ aliases `subject`/`object`), `name`,
  `v-<infinitive>`. Definiteness is inferred from the captured English article ("the" vs
  "a"); absence of an English article ⇒ proper noun ⇒ no article (matches Qud conventions).
- **Offline verification harness** (net48 console over `src/` + NuGet Newtonsoft): 14/14
  assertions pass, incl. the headline "The snapjaw dies." → "Der Schnappkiefer stirbt.",
  gender/case, article casing, optional `(xN)` groups, proper nouns, player pronoun,
  unmatched-line term fallthrough.

DEFERRED / KNOWN GAPS:
- **In-game verification** (Player.log beacon + self-test lines) — not yet run this session.
- **§5b.1 shared gender via reflection** — deferred: would couple the working token-replacer
  to the DLL's load order and cannot be verified without the game. Canonical logic now also
  lives in `COQDE/src/Gender.cs`; the two override tables are maintained in parallel for now.
- **Color/shader markup** in captured names is stripped for gender detection, so rewritten
  lines lose color (the COQKR `NormalizedText` slice-back that preserves markup was not
  ported yet). Plural subjects and possessive fragments ("your …", "X's …") are still rough.
- **§5b.3** — the token-path beacon (`GermanReplacerBootstrap`) was **kept** (relabelled),
  not removed: during the prototype two clearly-labelled load lines are more debuggable than
  one. Revisit once the runtime is game-verified.

---

## 1. Problem statement

Our mod currently localizes via two mechanisms, both of which are **blind to a large
class of gameplay messages**:

| Layer | Handles | Blind to |
|---|---|---|
| Data (`*.de.xml`) | Object names, descriptions, UI strings, dialogue, menus | Sentences assembled in C# code |
| `VariableReplacers.de.cs` | `=object.the.name=`-style **token** strings | Messages that never use those tokens |

**Evidence that combat log is code-built (gathered 2026-07-16):**
- `GameObject.The` / `.the` / `.A` / `.a` exist as C# properties (`get_The`, …) that build
  the article in code — they do **not** route through the `the`/`the.name` VariableReplacer.
- The generic death message ("X dies.") appears in **no** `ExampleLanguage/*.example.xml`
  template — searched all files. It is emitted straight to the message log from code.
- Observed in-game: "The snapjaw dies." — English article **and** English verb **and**
  English name (base "Snapjaw" was left untranslated). None of it is data-localizable.
- The Korean mod solves exactly this with a **compiled Harmony runtime** (`COQKR.dll`) that
  rewrites the assembled message line; its `Patterns.json` entries are `"routes":["MessageLog"]`
  regex rewrites, plus a `Terms.json` display-name dictionary.

**Conclusion:** the only way to translate these lines is to post-process the assembled
string at the message boundary — the Korean approach.

---

## 2. Architecture (mirror Korean `COQKR`)

```
languages/lang-de/
  CODE/
    Bootstrap.cs          # game-compiled tiny loader: [ModSensitiveCacheInit] -> load DLL, call Init()
    VariableReplacers.de.cs  # (existing) article/pronoun token replacers — keep
  COQDE/
    COQDE.dll             # PRE-BUILT runtime (Harmony patches + processor). Built with dotnet.
    Patterns.json         # route-scoped regex rewrites (English frame -> German)
    Terms.json            # term dictionary (names/phrases the data layer misses)
    Verbs.json            # English verb -> German conjugations (see §5)
```

**Why a pre-built DLL (not game-compiled CODE/):** Korean ships a binary, proving the
pattern works and sidestepping any uncertainty about whether language-mod `CODE/`
compilation applies Harmony patches. `dotnet` SDK 10.0.204 is available locally to build it.
Bootstrap.cs (game-compiled) loads the DLL by reflection at mod-init, exactly like
Korean's `COQKRLoader`.

**Build target (match COQKR.dll):**
- `.NET Framework 4.8` (`net48`).
- References (from `CoQ_Data/Managed/`): `Assembly-CSharp.dll`, `0Harmony.dll`,
  `UnityEngine.CoreModule.dll`, `mscorlib`, `System.Core`, `Newtonsoft.Json.dll`.
- Output copied to `languages/lang-de/COQDE/COQDE.dll`.

---

## 3. Runtime hooks

Primary hook (output-only, safe — does NOT patch low-level getters used by UI/sorting):
- **Harmony Postfix on `XRL.Messages.MessageQueue.AddPlayerMessage(string Message, …)`**
  (both `string`/`char` color overloads). Rewrites `Message` before it is shown.

Secondary (only if names still leak English in messages):
- **Postfix on the display-name event** (Korean hooks `DisplayNameEvent`). Likely unnecessary
  for us because our data layer already localizes names — *once we translate the remaining
  base names* (see §6, Phase 0).

Guard: all patches no-op unless the active language is `de` (check the game's current
language once at Init / per call).

---

## 4. Processing pipeline (per message string)

1. **Terms pass** — literal substring replacements from `Terms.json` (names/phrases the data
   layer misses; applied first so later regex sees German nouns).
2. **Patterns pass** — ordered regex list from `Patterns.json`. Each entry:
   ```json
   { "id": "...", "pattern": "^(?<subj>.+?) dies\\.$", "replacement": "{subj:nom} stirbt.",
     "note": "..." }
   ```
   Named groups feed sub-processors referenced in `{group:op}`:
   - `{x:nom}` / `{x:acc}` — prepend German article der/die/das / den, gender-guessed
     (reuse `GuessGender` logic from VariableReplacers, shared into the DLL).
   - `{x:verb=<inf>}` — conjugate a German verb for the subject (see §5).
3. **First match wins per line** (ordered, like Korean). Log unmatched lines (opt-in debug)
   to build the pattern set iteratively.

Patterns/Terms are **data**, hot-reloadable in principle, and Haiku-translatable in bulk.

---

## 5. German-specific hard parts (the real work)

1. **Article gender** — der/die/das needs the noun's grammatical gender. Reuse the
   ending-heuristic + override table already in `VariableReplacers.de.cs` (factor into a
   shared `Gender.cs`). Same known limitation: wrong for rare nouns.
2. **Case** — the message frame implies case (subject=nominative, object=accusative, after
   prepositions=dative/genitive). Encode case in the pattern's `{group:op}` since the frame
   is known at authoring time (this is *better* than the replacer, which only had
   Subject/Object).
3. **Verb conjugation** — the biggest content task. Combat verbs ("dies/hits/bites/claws/
   slashes/…") are English and conjugated by `GetVerb`. Build `Verbs.json`:
   `{ "die": {"inf":"sterben","er":"stirbt","sie_pl":"sterben","du":"stirbst"} , … }`.
   Conjugate by subject person/number (player = 2nd person "Ihr"/"Euch"; else 3rd).
4. **Word order** — German main clauses are largely SVO like English for these short
   messages, so most patterns are near 1:1 (much simpler than Korean SOV). Subordinate
   clauses (verb-final) need care but are rarer in the log.

---

## 5b. Cleanup & consolidation (within the new mod)

Introducing `COQDE.dll` creates overlap with the existing `CODE/VariableReplacers.de.cs`.
Handle as part of this work (not a separate project):

1. **Shared gender/article helper.** `GuessGender`, the `Overrides` table, `HeadNoun`,
   `VisibleText`, and the der/die/das + ein/eine tables currently live in
   `VariableReplacers.de.cs`. The DLL needs the same logic. Extract into ONE source of truth:
   - Put the canonical implementation in the DLL (`COQDE/Gender.cs`, namespace shared).
   - Have `VariableReplacers.de.cs` call into the DLL's helper (Bootstrap already loads it), so
     the ending-heuristic + override table exist in exactly one place. No copy-paste drift.
   - The override table (currently ~50 nouns) becomes shared data used by both the token
     replacers and the message post-processor.
2. **Keep `VariableReplacers.de.cs` — but document why.** It is NOT redundant with the DLL:
   it handles the ~312 **token** strings (`=object.the.name=` …) via `Override=true`, a
   surface the message post-processor never sees. Add a header comment stating the split
   (replacer = token strings; DLL = code-built message log) so a future reader doesn't delete
   one thinking the other covers it.
3. **Drop the temporary diagnostics.** The `[QudDE] German VariableReplacers loaded` beacon
   (`GermanReplacerBootstrap`) was added only to prove the code path loads. Once the DLL's own
   beacon + self-test are in place, remove `GermanReplacerBootstrap` (or fold it into the DLL's
   single startup log) so there is one clear load line, not two.
4. **Single namespace.** `VariableReplacers.de.cs` uses `LanguagesOfQudGerman`; the DLL should
   share it (`LanguagesOfQudGerman` / `LanguagesOfQudGerman.Runtime`) so the replacer can
   reference the DLL's `Gender` helper without an assembly-name mismatch.

Out of scope for this cleanup (per decision): the separate 1.0.4 QudDE Harmony mod, and a
broad dead-data sweep. (Already-fixed stray data — the leaked `Key` node and 7 nonexistent
furniture blueprints — stay fixed; no further data sweep now.)

## 6. Phasing

- **Phase 0 — data cleanup (cheap, do first):** translate the remaining untranslated base
  creature/object names (Snapjaw, etc.) so names in messages are German. Data layer only.
- **Phase 1 — runtime skeleton + proof (includes §5b consolidation):** build `COQDE.dll` +
  `Bootstrap.cs`, Harmony postfix on `AddPlayerMessage`, JSON loader, and the **shared**
  `Gender.cs` helper (§5b.1) that both the DLL and `VariableReplacers.de.cs` use. Rewire the
  replacer to call the shared helper, add the header comment (§5b.2), and remove the temporary
  `GermanReplacerBootstrap` beacon (§5b.3) in favour of the DLL's single startup log. Seed a
  set (~30–50 highest-frequency frames: dies, is destroyed, hits/misses, attacks, takes N
  damage, bleeds, is frozen/on fire, falls unconscious). Verify "The snapjaw dies." -> "Der
  Schnappkiefer stirbt." via Player.log beacon + in-game.
- **Phase 2 — inventory:** extract the full code-built message corpus (string literals with
  frame words from `Assembly-CSharp.dll` + an in-game "unmatched line" debug log). Produce a
  work-list.
- **Phase 3 — bulk translate:** Haiku workflow over the inventory -> `Patterns.json` +
  `Verbs.json` + `Terms.json`, each verified (regex compiles, group names balanced, tokens
  preserved).
- **Phase 4 — iterate to parity:** replay unmatched-line logs, fill gaps, refine gender
  overrides and verb table until the log is substantially German.

---

## 7. Verification

- **Beacon:** DLL `Init()` logs `[QudDE] COQDE runtime vX loaded (patterns=N, verbs=M)` to
  `Player.log`. Harmony patch logs `[QudDE] AddPlayerMessage patched`.
- **Self-test:** at Init, run the processor over a fixed list of sample English lines and log
  input->output pairs, so correctness is checkable from the log without playing.
- **Debug unmatched:** optional flag logs message lines that no pattern matched -> feeds §Phase 2/4.
- **Regression:** patterns file validated at build (each regex compiles; every `{group}` in a
  replacement exists as a named group in its pattern).

---

## 8. Risks / open questions

- **DLL load in headless/other machines:** Bootstrap resolves the DLL path from the mod
  folder (like Korean's `ResolvePackagePath`). Fine for local + workshop installs.
- **Scripting consent:** mod must have code-execution enabled (already is — VariableReplacers
  compiled). A pre-built DLL is loaded by reflection from Bootstrap; confirm this is permitted
  under the same consent (Korean does it, so yes).
- **Framework mismatch:** must target net48 to match the game's Mono runtime; verify the built
  DLL loads (no `TypeLoadException` in Player.log).
- **Harmony version:** compile against the game's bundled `0Harmony.dll` (do not ship our own).
- **Over-matching:** greedy patterns could corrupt lines; keep anchored (`^…$`), ordered,
  first-match-wins, and log before/after in debug.
- **Maintenance:** game updates may add/alter messages; the pattern set needs occasional
  replay-and-fill. Acceptable, same as Korean.

---

## 9. Not in scope (still handled elsewhere)

- Object names/descriptions, UI, dialogue, menus — data layer (`*.de.xml`).
- Token strings (`=object.the.name=` …) — `VariableReplacers.de.cs` (with `Override=true`).
- The post-processor only touches assembled message-log lines the above two miss.
