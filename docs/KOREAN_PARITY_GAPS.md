# Korean mod (COQKR) → German (COQDE) parity gaps

What runtime hooks/routes the Korean reference mod uses, and which are relevant for German.
Compiled 2026-07-16 from the decompiled `COQKR.dll` + its `Patterns.json`/`Terms.json`.

## Key difference from Korean

Korean needs a runtime hook on **almost all** text because Korean postpositions (josa 은/는/이/가…)
depend on the *preceding* word and cannot be baked into static XML. German does **not** have that
problem: our data layer (`*.de.xml`) already localizes static names, descriptions, dialogue and
UI. So for German the runtime DLL is only needed where text is **assembled in C# code** (frames,
articles, case, verb agreement, possessives, laterality) — a much smaller surface than Korean's.

Legend — German relevance:
- **HIGH** = code-built text the data layer cannot reach; visible often.
- **MED**  = mostly covered by `*.de.xml`; runtime only for code-composed leftovers.
- **LOW**  = niche/cosmetic, or very large for little gain.

## What COQDE has today  (status as of 2026-07-16, after in-game testing)

| Route | Hook (Harmony) | Status |
|---|---|---|
| `MessageLog` | Prefix `XRL.Messages.MessageQueue.AddPlayerMessage` | ✅ ~50 pattern entries (combat/status/death/misc) |
| `Popup` | Prefix `XRL.UI.Popup.Show*` (first 4 string args) | ✅ death frames + discover/note-location; death LINE verified in-game |

Cross-cutting, done:
- ✅ **Whole-line color markup** (`{{color|…}}`) is unwrapped → translated → re-wrapped, so
  colored status/combat lines match the anchored patterns (was the #1 reason colored lines stayed English).
- ✅ **Gender table** expanded (-e masculine weak nouns; Krokodil=neuter, etc.).
- ✅ **`unmatched` debug log** (`COQDE.debug` flag) to drive further pattern work.

Term fallthrough (partial translation of unmatched lines) runs on `MessageLog` only; other
routes get anchored-pattern rewrites only, so hooking them cannot half-translate stray English.

**Not a Korean-route gap, but the largest remaining quality issue** (discovered in testing):
many message templates are **pre-translated to broken German by the data layer** (`Strings.de.xml`
+ token/verb replacers) *before* COQDE sees them — untranslated verbs (`wade`, `see`→`Sehen`,
`have`), wrong articles (`einen Becken`). COQDE's English-frame patterns can't match German text;
these need either data-layer fixes or German→German cleanup patterns (one added: `begins Blutung`).
Tracked separately from the route list below.

## Missing routes, ranked by German relevance

### HIGH — code-built, frequently visible

| Route | Korean hooks | Carries | Why it matters for German |
|---|---|---|---|
| `GameSummary` | `XRL.UI.GameSummaryUI.Show` (Cause + details[]) | End-of-game / death summary screen: cause of death, run details | The death/obituary **screen** likely renders here (separate from the Popup line). If the reported death text still shows English after the Popup fix, this is the hook to add next. 84 Korean patterns. |
| `BodyPart` / `BodyPartBase` | Postfix `BodyPart.GetCardinal/OrdinalName/Description` | Body-part names + **laterality** ("right/left/front/upper" arm/leg/hand) | Laterality is built in code, not in the anatomy data. Body parts appear constantly (equipment, "X's right arm", severed limbs, targeting). German needs inflected adjectives ("rechter Arm", "linkes Bein"). 164+27 Korean entries — their single biggest term set. |
| `Possessive` | Postfix `GameObject.Poss` (display name) | "your X", "the snapjaw's tail" | Possessives are code-built and currently leak English ("your …", "X's …") in our combat lines. German: "Euer …", genitive "…s". Fixes the roughness already noted in the plan. |

### MED — data layer covers most; runtime for code-composed leftovers

| Route | Korean hooks | Carries | Note for German |
|---|---|---|---|
| `FloatingText` | `CombatJuice.floatingText`, `GameObject.ParticleText` | Floating combat text over creatures (miss/blocked/crit, damage) | Short code-built combat words; nice-to-have polish. |
| `DisplayNameEvent` | Postfix `GetDisplayNameEvent.GetFor/ProcessFor` | The display-name pipeline output | For names the data layer misses and **composed** names (severed limbs "X's right arm"). Pairs with `BodyPart`/`Possessive`. |
| `JournalAPI` | `IBaseJournalEntry` display text, `JournalAPI` | Journal/chronicle entries ("On the Nth of X, you were killed by Y") | Code-assembled sentences with articles/ordinals; our death-verb work applies here too. 34 entries. |
| `ActivatedAbility` | `ActivatedAbilities.AddAbility`, `GameObject.SetActivatedAbilityDisplayName`, class display | Ability names/descriptions added in code | `ActivatedAbilities.de.xml` covers most; hook only for code-composed ability text. 90 entries. |
| `MutationText` | `BaseMutation` desc/text | Mutation descriptions incl. per-level composed text | `Mutations.de.xml`/`HiddenMutations.de.xml` cover static; runtime for composed level text. |
| `Effect` / `EffectDescriptionReturn` | `Effect.GetDescription/GetStateDescription/GetDetails` | Status-effect names/details | `EffectsDetails.de.xml` covers most; runtime for composed effect strings. |
| `Category` | `Physics+Categories.GetDisplayName` (+ FilterBar/TradeLine relocalization) | Item categories in inventory/trade ("Melee Weapons", "Armor") | Inventory/trade UI; check if `Data.de.xml` already localizes these. 40 entries. |
| `MenuOption` | `Popup.GetPopupOption` (`QudMenuItem`), cybernetics choices | Popup menu item labels | Some menu text is code-built. 30 entries. |
| `SkillsPowers` | `SPNode.ModernUIText`, SkillsAndPowers screens | Skills & powers screen text | `Skills.de.xml` covers descriptions; runtime for composed lines. 29 entries. |
| `ConversationChoiceTag` / `ConversationTextAppend` | conversation choice tags / appended element text | Dynamic conversation bits ("[begin water ritual; N dram of X]", appended reputation lines) | Static dialogue is in `Strings.Conversations.de.xml`; only the code-appended/tagged bits leak. |
| `UIText` | Prefix `XRL.UI.UITextSkin.SetText` (backstop) | Catch-all for UI text not caught by a specific route | Broad backstop — powerful but risky (can touch any UI string). Korean guards it with token-protection. Consider only after the specific routes, and pattern-only (no term fallthrough). |

### LOW — niche / cosmetic / very large

| Route | Carries | Note |
|---|---|---|
| `LoadingStatus` | Loading-screen status text | Cosmetic. |
| `PickDirection` | Direction-picker labels | Tiny. |
| `Cybernetics` | Cybernetics screen body-part names | Covered indirectly once `BodyPart` exists. |
| `HistoricStringExpander` | `HistoryKit.HistoricStringExpander.ExpandString` — procedural history/legends | This is the `HistorySpice` corpus (~1950 lines, already noted untranslated). Large effort, niche lore. |

## Not translation (skip)

Korean ships many `[ProbeOnly]` diagnostic patches (`GameObjectGetVerbProbe`,
`SkillsPowersLineContractProbe`, `DisplayNameAssignmentProbe`, `MessageFrameProbe`,
conversation/popup probes, …) used only to discover routes with logging on. They are not needed
for shipping translation and are the reason COQKR carries a `RouteMode`/`FilterMode` logging
system. Our `COQDE.debug` flag + `unmatched` logging is the lightweight equivalent.

## Master checklist

Check each item off (`☐` → `☑`) as it is implemented AND verified. Details for each route are
in the tables above.

### Done (shipped this milestone)
- ☑ `MessageLog` route (Prefix on `MessageQueue.AddPlayerMessage`, ~50 patterns)
- ☑ `Popup` route (Prefix on `Popup.Show*`; death frames, discover/note-location)
- ☑ Whole-line color-markup unwrap/translate/re-wrap
- ☑ Verb conjugation at the source chokepoint (Harmony postfix on `GameObject.GetVerb`; `Verbs.json` keyed by `en`)
- ☑ Article GENDER via shared `GenderLexicon.tsv` (loaded by token layer + DLL)
- ☑ Article CASE after dative prepositions (B2 correction pass)
- ☑ `unmatched` debug log (`COQDE.debug` flag)

### HIGH — code-built, frequently visible
1. ☑ **`GameSummary`** — Prefix on `GameSummaryUI.Show` translates Cause + Details (route `GameSummary`, death frames apply). *In-game verify pending.*
2. ☑ **`BodyPart`** — Postfix on `GetCardinal/Ordinal Name/Description`: strips English laterality via `Laterality.StripLateralityAdjective` + the part's `Laterality` flags, translates the base noun (BodyPart terms), re-attaches a gender-inflected German adjective (`rechte Hand`, `vorderes linkes Bein`). *In-game verify pending.* (`BodyPartBase` route + full body-part noun coverage can grow via terms.)
3. ☑ **`Possessive`** — Postfix on `GameObject.Poss`: `Your X`→`Euer/Eure X` (gender-aware), `The X's Y`→`Der Y des X…` (genitive reorder), `Name's Y`→`Names Y`. *In-game verify pending.*

### MED — data layer covers most; runtime for code-composed leftovers
4. ☐ **`FloatingText`** — combat-juice text over creatures (miss/blocked/crit).
5. ☐ **`DisplayNameEvent`** — composed names / severed limbs (pairs with 2 & 3).
6. ☐ **`JournalAPI`** — chronicle entries ("On the Nth of X, you were killed by Y").
7. ☐ **`ActivatedAbility`** — code-composed ability names/descriptions.
8. ☐ **`MutationText`** — composed mutation/level text.
9. ☐ **`Effect` / `EffectDescriptionReturn`** — composed status-effect strings.
10. ☐ **`Category`** — item categories in inventory/trade.
11. ☐ **`MenuOption`** — code-built popup menu labels.
12. ☐ **`SkillsPowers`** — composed skills/powers screen lines.
13. ☐ **`ConversationChoiceTag` / `ConversationTextAppend`** — dynamic conversation bits.

### LOW — niche / cosmetic / large
14. ☐ **`UIText`** — broad `UITextSkin.SetText` backstop (do after specific routes).
15. ☐ **`LoadingStatus`** — loading-screen text (cosmetic).
16. ☐ **`PickDirection`** — direction-picker labels (tiny).
17. ☐ **`Cybernetics`** — mostly covered once `BodyPart` exists.
18. ☐ **`HistoricStringExpander`** — ~1950-line HistorySpice lore corpus (large, niche).

### Separate track — data-layer partial translations (not a route)
19. ☐ **Grow `Verbs.json`** from 62 → full ~164-verb corpus (mechanism ☑ done).
20. ☐ **Grow `GenderLexicon.tsv`** for the long tail of nouns (mechanism ☑ done).
21. ☐ **Remaining article-case gaps** (B2 follow-ups): two-way prepositions (`in/an/auf/…`),
    genitive prepositions (noun `-s`), feminine `die`/`ihr` after datives — or do **B1**
    (case-tagged tokens) for full correctness.

### Explicitly skip
- Korean's `[ProbeOnly]` diagnostic patches — our `COQDE.debug` unmatched-log is the equivalent.

---

Each new route is: add a `[HarmonyPatch]` class in `build/COQDE/game/COQDEMod.cs` calling
`RouteTranslator.Translate("<Route>", …)`, then author patterns/terms for it. The engine,
JSON contract, and `{group:shape}` operators already support any route name.
