# COQDE — German runtime message post-processor

Pre-built Harmony DLL that translates the *code-built* message-log lines the data layer
(`*.de.xml`) and `VariableReplacers.de.cs` cannot reach (e.g. "The snapjaw dies." →
"Der Schnappkiefer stirbt."). Design: `docs/RUNTIME_POSTPROCESSOR_PLAN.md`.

## Layout

```
build/COQDE/                 (SOURCE — never copied into the game Mods folder)
  COQDE.csproj               net48, references the game's own Managed assemblies
  src/                       pure logic, no game deps (System + Newtonsoft only)
    Gender.cs                canonical gender heuristic + override table + article tables
    GermanGrammar.cs         {group:shape} operators (nom/acc/dat/gen, name, v-<inf>) + verbs
    RouteTranslator.cs       pattern/term engine (mirrors the COQKR pipeline)
  game/
    COQDEMod.cs              Init, Harmony patch discovery, MessageLog hook, language guard, self-test

languages/lang-de/COQDE/     (SHIPPED with the mod)
  Bootstrap.cs               game-compiled loader -> reflection-loads COQDE.dll, calls Init()
  COQDE.dll                  built output (commit this)
  Patterns.json Terms.json Verbs.json   translation data (hand/Haiku-authored)
```

## Build

```sh
dotnet build build/COQDE/COQDE.csproj -c Release
cp build/COQDE/bin/Release/COQDE.dll languages/lang-de/COQDE/COQDE.dll
```

The `.csproj` references the game assemblies from
`C:\Program Files (x86)\Steam\steamapps\common\Caves of Qud\CoQ_Data\Managed` (adjust
`<GameManaged>` if your install differs). All references are `Private=false`, so only
`COQDE.dll` is produced — no game assemblies are copied into the mod.

## IMPORTANT: do not ship the source

The game compiles **every `.cs` under a loaded mod folder** (recursively). If `build/`
were copied into the Mods folder, the game would compile `src/`+`game/` *and* load the
DLL, producing duplicate `COQDE.*` types. Deploy only `languages/`, `manifest.json`,
`workshop.json`, `preview.png`, `README.md`, `CHANGELOG.md` — never `build/`.

## Offline verification

The `src/` logic has no game dependency, so it is unit-tested without launching the game:
build a net48 console that includes `src/*.cs` + a NuGet `Newtonsoft.Json`, point it at
`languages/lang-de/COQDE/`, and assert `RouteTranslator.Translate("MessageLog", input)`.
(The game's repacked `Newtonsoft.Json.dll` fails strong-name verification outside the game,
so use the NuGet package in the harness.)
