# Screenshot-driven fixes — analysis & plan (2026-07-16)

Captured from 9 in-game screenshots + the `COQDE.debug` unmatched-line log. Screenshots
archived under `docs/screenshots/2026-07-16/`. This plan builds on the architecture in
`docs/RUNTIME_POSTPROCESSOR_PLAN.md` and `docs/KOREAN_PARITY_GAPS.md`.

## Evidence (current → desired)

| # | Current (in-game) | Desired |
|---|---|---|
| E1 | `The Skorpiock trifft (x1) for 4 damage with sein Giftstachel. [8]` | `Der Skorpiock trifft (x1) für 4 Schaden mit seinem Giftstachel. [8]` |
| E2 | `The Riesige Amöbe verfehlt Euch mit sein Klebriger Pseudopod! [5 vs. 8]` | `Die Riesige Amöbe verfehlt Euch mit ihrem klebrigen Pseudopod! [5 vs. 8]` |
| E3 | `The Skorpiock impales sich on Euer Stacheln and nimmt 1 damage!` | `Der Skorpiock pfählt sich an Euren Stacheln und erleidet 1 Schaden!` |
| E4 | `The Skorpiock strikes Ihr mit sein Giftstachel!` | `Der Skorpiock trifft Euch mit seinem Giftstachel!` |
| E5 | `Ihr trefft (x1) mit Eurem eiserne Rebenklinge für 3 Schaden! [14]` | `Ihr trefft (x1) mit Eurer eisernen Rebenklinge für 3 Schaden! [14]` |
| E6 | `The attack breaks two Stacheln!` | `Der Angriff zerbricht zwei Stacheln!` |
| E7 | `The Wasserrebenbauern-Konvertit schreit, '…'` | `Der Wasserrebenbauern-Konvertit schreit: '…'` |
| E8 | `Der Weg wird von einem verrostete Metallwand versperrt.` | `Der Weg wird von einer verrosteten Metallwand versperrt.` |
| E9 | `Ihr entdeckt das workshop von Mamuuq, legendary Edelsteinschleifer!` | `Ihr entdeckt die Werkstatt von Mamuuq, dem legendären Edelsteinschleifer!` |
| E10 | `Ihr gewinnt 1 hitpoint` / `78 Skill Points` / `1 Mutation Point` | `1 Trefferpunkt` / `78 Fertigkeitspunkte` / `1 Mutationspunkt` |
| E11 | `You're lost! Regain your bearings by exploring your surroundings.` | `Ihr habt euch verirrt! Erkundet eure Umgebung, um euch neu zu orientieren.` |
| E12 | `You regain your bearings.` | `Ihr orientiert euch wieder.` |
| E13 | `You are paralyzed!` | `Ihr seid gelähmt!` |
| E14 | `Your regenerative metabolism cures you of paralyzed.` | `Euer regenerativer Stoffwechsel heilt euch von Lähmung.` |
| E15 | `Ihr wurdet von einem blutig Skorpiock zu Tode gebissen.` | `Ihr wurdet von einem blutigen Skorpiock zu Tode gebissen.` |

Not errors (already correct German, listed to avoid re-touching): zone-name lines like
`Salzwüste, Oberfläche, Die Untiefen`; `Ihr nehmt einen Schluck Süßwasser aus dem
Wasserschlauch.` (B2 fixes the article post-log).

## Root-cause categories

### C1 — Combat frames half-translated (GetVerb vs MessageLog collision) — HIGH
`E1, E2, E3, E4, E5, E6`. The `GameObject.GetVerb` postfix translates combat verbs
(`hit`→`trifft`, `miss`→`verfehlt`, `strike`, `impale`) **before** the message is assembled, so
our English `MessageLog` combat patterns (which match `hits`/`misses`) no longer match — the line
ends up with a German verb but an English frame (`for N damage with`, English `The`, English
`with`). We also simply lack patterns for the **no-target / penetration-count** hit form and the
`misses … [R vs. D]`, `strikes`, `impales itself on …` forms.

Fix:
1. **Remove combat verbs** (`hit`, `miss`, and any combat-only ones) from `Verbs.json` so they
   stay English until a `MessageLog` pattern owns the whole frame. (They are overwhelmingly
   combat; verify no important non-combat use via the debug log first.)
2. **Add the missing combat patterns** (model on COQKR's set), each translating: attacker
   `The X`→`{x:nom}`, weapon possessive→dative (see C7), `for N damage`→`für N Schaden`, roll
   `[R]` / `[R vs. D]`. Needed variants: incoming hit no-target (`X hits (xN) for N damage with
   W. [R]`), incoming hit you, `X misses you with W! [R vs. D]`, `X strikes you with W!`,
   `X impales itself on Y and takes N damage!`, player no-target hit, critical variants, and
   `The attack breaks X!`.

### C2 — Attributive adjective declension in names — HIGH, HARD
`E2 (klebrigen), E5 (eisernen), E8 (verrosteten), E15 (blutigen)`. Adjectives inside captured
names are emitted in a default/base form and not inflected for case+gender+article
(`blutig Skorpiock` → `blutigen`, `eiserne Rebenklinge` (dat) → `eisernen`). These come from the
data layer / procedural prefixes (`bloody`, `rusted`, `sticky`, `iron`).

Fix (in the shape operators): when an operator prepends an article to a captured fragment, also
inflect the **non-head words** (adjectives = every word before the head noun) to the correct
declension for the chosen case/gender/definiteness (strong vs weak/mixed endings). Requires:
- reducing an already-inflected adjective to a stem (`verrostete`→`verrostet`, `blutig`→`blutig`,
  `eiserne`→`eisern`), then re-applying the right ending;
- a declension table (der-/ein-/no-article × case × gender). This is the single most complex
  piece; scope it as its own phase and start with the operator-controlled cases (`nom/acc/dat`,
  possessives). Adjectives inside plain data names not routed through an operator remain a known
  limitation.

### C3 — Compound-noun gender — MED, easy
`E8 Metallwand` guessed masculine → should be feminine (die Wand). `HeadNoun` only splits on
spaces/hyphens, so a closed compound (`Metallwand`) is looked up whole and misses the lexicon.

Fix: in `GermanGender.Guess`, if the head noun isn't found, test whether it **ends with** a known
lexicon noun (`…wand`→`wand`=f, `…stein`→m, `…tür`→f, `…schwert`→n …) and use that gender. Keep
a minimum length to avoid false hits. Also add explicit entries as needed.

### C4 — Leading `The ` in unpatterned frames — MED
`E6, E7` (and any `The X <verb> …` with no pattern). `The` is code-built (`GameObject.The`) and
English; it only becomes German when a pattern captures the subject as `{x:nom}`.

Fix: add patterns for the remaining subject-first frames (`X says/shouts, "…"` → `X sagt/ruft:
"…"`, `The attack breaks …`, etc.). A blanket "translate any leading `The `" cleanup is risky
(can't find the noun-phrase boundary reliably) — prefer per-frame patterns driven by the log.

### C5 — Data-layer term / name gaps — MED
`E9 (workshop, legendary), E10 (hitpoint, Skill Points, Mutation Point), E13/E14 (paralyzed)`.
Untranslated English words the data layer emits.

Fix: translate at the source where possible:
- `workshop`→`Werkstatt`, `legendary`→`legendär` — procedural lair/merchant naming; find in
  `Strings.de.xml` / naming data (or `HistoricStringExpander`) and translate.
- `hitpoint`/`Skill Points`/`Mutation Point` — level-up reward lines; likely `Strings.de.xml`
  entries to translate (`Trefferpunkt`, `Fertigkeitspunkte`, `Mutationspunkt`).
- `paralyzed`→`gelähmt`/`Lähmung` — status-effect name; `EffectsDetails.de.xml` / effect term.
- Last-resort: `Terms.json` entries (guard against corrupting correct names).

### C6 — Fully-English frames missing translation — MED
`E11, E12, E13, E14`, plus `You are paralyzed!`. Code/data English lines with no pattern.

Fix: add `MessageLog`/`Popup` patterns (or `Strings.de.xml` entries if token-based). Note the
"lost/bearings" and "cures you of <status>" frames; `cures you of paralyzed` needs the status
term from C5.

### C7 — Possessive pronoun case + gender — HIGH (enables C1)
`E1/E2/E4 (its W → sein/ihr), E5 (your W → Euer/Eure)`. Weapon possessives arrive as
`its/your <adj> <noun>` and must become a **dative** possessive agreeing with the noun's gender
(`its stinger`→`seinem … Stachel` or `ihrem …` when the noun is feminine) and, for `its`, ideally
the *attacker's* grammatical gender.

Fix: a `{w:possdat}` operator (and `possacc`) that handles a leading `your`/`its`/`his`/`her`/
`a` + adjective(s) + noun → German possessive/indefinite in the requested case, with C2 adjective
inflection. `its` gender: default to the noun's grammatical gender (cannot see the owner in the
operator); acceptable approximation. `your`→`Eurem/Eurer`.

## Phased plan (priority order) — ALL IMPLEMENTED 2026-07-16 (offline-verified, in-game pending)

- ☑ **Phase 1 — Combat frames (C1 + C7).** Kept combat verbs in `GetVerb` and instead wrote
  combat patterns with **alternations** (`(?:you|Euch)`, `(?:with|mit)`, `(?:hits|trifft)`, …)
  that absorb the inconsistent pre-translation; added `{group:possnom/possacc/possdat}` operators
  that accept English *or* German possessives (`your/its/sein/euer …`), inflect for case+gender,
  and (Phase 3) decline adjectives. New frames: no-target/penetration hit, crit no-target,
  `misses you … [R vs D]`, `strikes`, `impales itself on …`, `attack breaks`, player no-target,
  and a German-cleanup for the data-layer player hit. Fixes E1–E6.
- ☑ **Phase 2 — Compound-noun gender (C3).** `GermanGender.Guess` now falls back to matching the
  head against lexicon nouns as a **compound suffix** (`Metallwand`→`Wand`=fem). Fixes E8 gender.
- ☑ **Phase 3 — Adjective declension (C2).** Full strong/weak/mixed × case × gender ending
  tables + adjective-stem reduction, integrated into every article/possessive operator. Fixes
  E2/E5/E8/E15 (`blutigen`, `eisernen`, `verrosteten`, `klebrigen`).
- ☑ **Phase 4 — Frames & terms (C4/C5/C6).** `Strings.de.xml` source fixes (lost popup, level-up
  hitpoint/SP/MP gains); DLL patterns (lost/regain bearings, you-are-paralyzed, cures-you-of,
  ambient `The X schreit …`); terms (`legendary`→`legendär`, `workshop`→`Werkstatt`,
  `paralyzed`→`gelähmt`).

### Known remaining approximations (documented, acceptable)
- Possessive `its` for a **feminine** creature defaults to `sein…` (owner gender not visible in
  the operator) — ending is still correct (`seinem klebrigen …`); ideal would be `ihrem`.
- Plural body-part objects (`Euren Stacheln`) may render as singular-masc when the noun isn't
  recognized as plural.
- `das Werkstatt`/`legendär …` articles/apposition endings not fully inflected (term-level fix).
- Adjectives inside plain data names not routed through an operator remain uninflected.

Each phase: implement in `build/COQDE/`, add assertions to the offline harness, rebuild + deploy
DLL/data, verify in-game, then update `KOREAN_PARITY_GAPS.md` / this file.

## Cross-cutting note (important)
Phase 1 exposes a general rule discovered here: **a verb must be handled by exactly one layer.**
Combat verbs belong to the `MessageLog` pattern layer (full-frame restructuring); only verbs that
appear in otherwise-untranslated token sentences (wade/see/have/harvest…) belong in the `GetVerb`
lexicon. When adding a verb to `Verbs.json`, check it doesn't also appear in a `MessageLog`
pattern frame.
