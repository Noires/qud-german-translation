using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text.RegularExpressions;
using System.Threading;
using HarmonyLib;

namespace COQDE
{
    // Runtime entry point of the German message post-processor. Bootstrap.cs (game-compiled)
    // loads this assembly by reflection and calls Init(). Init loads the JSON data next to the
    // DLL, applies the Harmony patches, logs a beacon, and runs a self-test — all visible in
    // Player.log under "[QudDE]". See docs/RUNTIME_POSTPROCESSOR_PLAN.md.
    public static class COQDEMod
    {
        private static int initialized;

        public static void Init()
        {
            if (Interlocked.CompareExchange(ref initialized, 1, 0) == 1) return;
            try
            {
                RouteTranslator.Log = (phase, detail) => UnityEngine.Debug.Log("[QudDE] " + phase + ": " + detail);

                string dir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
                RouteTranslator.Debug = File.Exists(Path.Combine(dir, "COQDE.debug"));
                int lex = GermanGender.LoadLexicon(Path.Combine(dir, "GenderLexicon.tsv"));
                UnityEngine.Debug.Log("[QudDE] gender lexicon: " + lex + " entries");
                RouteTranslator.Load(dir);

                ApplyPatches(new Harmony("coqde.runtime"));

                UnityEngine.Debug.Log(string.Format(
                    "[QudDE] COQDE runtime loaded (patterns={0}, verbs={1}, terms={2}).",
                    RouteTranslator.PatternCount, RouteTranslator.VerbCount, RouteTranslator.TermCount));

                SelfTest();
            }
            catch (Exception ex)
            {
                Interlocked.Exchange(ref initialized, 0);
                UnityEngine.Debug.LogError("[QudDE] COQDE init failed: " + ex);
                throw;
            }
        }

        private static void ApplyPatches(Harmony harmony)
        {
            int applied = 0, failed = 0;
            foreach (Type type in AccessTools.GetTypesFromAssembly(Assembly.GetExecutingAssembly()))
            {
                if (type.GetCustomAttributes(typeof(HarmonyPatch), false).Length == 0) continue;
                try { harmony.CreateClassProcessor(type).Patch(); applied++; }
                catch (Exception ex)
                {
                    failed++;
                    UnityEngine.Debug.LogError("[QudDE] patch-fail " + type.FullName + ": " + ex.Message);
                }
            }
            UnityEngine.Debug.Log("[QudDE] Harmony patching: applied=" + applied + " failed=" + failed);
        }

        private static void SelfTest()
        {
            string[] samples =
            {
                "The snapjaw dies.",
                "You hit the goat with a dagger for 5 damage!",
                "The goat is destroyed!",
            };
            foreach (var s in samples)
                UnityEngine.Debug.Log("[QudDE] self-test: \"" + s + "\" -> \"" + RouteTranslator.Translate("MessageLog", s) + "\"");
        }
    }

    // Fail-open language guard: translation is skipped only when the game can be positively
    // determined to be running a non-German language. If the current-language accessor cannot
    // be resolved (API drift), we translate — the mod ships German data and is enabled together
    // with the German language, matching the reference mod's always-on behaviour.
    internal static class LanguageGuard
    {
        private static bool resolved;
        private static Func<string> getLanguage;

        internal static bool Active()
        {
            var read = Resolve();
            if (read == null) return true; // cannot determine -> fail open
            string code;
            try { code = read(); } catch { return true; }
            if (string.IsNullOrEmpty(code)) return true;
            return code.StartsWith("de", StringComparison.OrdinalIgnoreCase);
        }

        private static Func<string> Resolve()
        {
            if (resolved) return getLanguage;
            resolved = true;
            // Look for a static string accessor named ActiveLanguage or Language on the
            // known language types.
            string[] typeNames = { "XRL.Language.Translator", "XRL.Language.Strings", "XRL.Language.LanguageManager" };
            string[] memberNames = { "ActiveLanguage", "Language", "CurrentLanguage" };
            foreach (var tn in typeNames)
            {
                var t = AccessTools.TypeByName(tn);
                if (t == null) continue;
                foreach (var mn in memberNames)
                {
                    var p = t.GetProperty(mn, BindingFlags.Public | BindingFlags.Static);
                    if (p != null && p.PropertyType == typeof(string))
                    {
                        getLanguage = () => (string)p.GetValue(null, null);
                        return getLanguage;
                    }
                    var f = t.GetField(mn, BindingFlags.Public | BindingFlags.Static);
                    if (f != null && f.FieldType == typeof(string))
                    {
                        getLanguage = () => (string)f.GetValue(null);
                        return getLanguage;
                    }
                }
            }
            return null;
        }
    }

    // Hook: rewrite the message string as it enters the player message log. This is the
    // output boundary the data layer and VariableReplacers cannot reach (code-built lines).
    [HarmonyPatch]
    public static class MessageLogPatch
    {
        public static IEnumerable<MethodBase> TargetMethods()
        {
            Type type = AccessTools.TypeByName("XRL.Messages.MessageQueue");
            if (type == null) yield break;
            foreach (var m in type.GetMethods(BindingFlags.Public | BindingFlags.Static | BindingFlags.Instance | BindingFlags.DeclaredOnly))
                if (m.Name == "AddPlayerMessage")
                {
                    var ps = m.GetParameters();
                    if (ps.Length >= 1 && ps[0].ParameterType == typeof(string))
                        yield return m;
                }
        }

        public static void Prefix(object[] __args)
        {
            if (!LanguageGuard.Active()) return;
            if (__args != null && __args.Length > 0 && __args[0] is string source)
                __args[0] = RouteTranslator.Translate("MessageLog", source);
        }
    }

    // Hook: verb conjugation. GameObject.GetVerb is the single chokepoint every verb replacer
    // routes through (=subject.Does:wade=, =subject.verb:X=, =subject.is=, .Has, ...). The game
    // has no German conjugator, so it emits the English base verb ("wade", "have", "are"). We map
    // the English base verb to its German conjugation for the subject's person. Unmapped verbs
    // are left as the game produced them (English) — no regression. See docs/RUNTIME_POSTPROCESSOR_PLAN.md.
    [HarmonyPatch]
    public static class GetVerbPatch
    {
        public static IEnumerable<MethodBase> TargetMethods()
        {
            Type t = AccessTools.TypeByName("XRL.World.GameObject");
            if (t == null) yield break;
            var m = AccessTools.Method(t, "GetVerb");
            if (m != null) yield return m;
        }

        public static void Postfix(ref string __result, XRL.World.GameObject __instance, string Verb,
            bool PrependSpace, bool PronounAntecedent, bool AdjunctAntecedent, bool SecondPerson, bool AsIfKnown)
        {
            if (!LanguageGuard.Active()) return;
            if (string.IsNullOrEmpty(Verb) || __instance == null) return;
            var person = PersonFor(__instance, PronounAntecedent, AdjunctAntecedent, SecondPerson, AsIfKnown);
            string de = GermanGrammar.ConjugateEnglish(Verb, person);
            if (de == null) return; // no German mapping -> keep the game's English output
            __result = PrependSpace ? " " + de : de;
        }

        // Mirrors GetVerb's own base-vs-third-person selection so our person matches the game's.
        private static GermanGrammar.Person PersonFor(XRL.World.GameObject inst,
            bool pronounAntecedent, bool adjunctAntecedent, bool secondPerson, bool asIfKnown)
        {
            if (adjunctAntecedent) return GermanGrammar.Person.S3;
            if (secondPerson && inst.IsPlayer() && XRL.Language.Grammar.AllowSecondPerson)
                return GermanGrammar.Person.P2;
            if (inst.GetPlurality(asIfKnown)) return GermanGrammar.Person.P3;
            if (pronounAntecedent && inst.GetPseudoPlurality(asIfKnown)) return GermanGrammar.Person.P3;
            return GermanGrammar.Person.S3;
        }
    }

    // Hook: popup dialogs (death screen, prompts). Route "Popup" gets pattern rewrites only
    // (no term fallthrough — see RouteTranslator.FallthroughRoutes), so this cannot
    // half-translate arbitrary English popup text; only explicit anchored patterns fire.
    [HarmonyPatch]
    public static class PopupPatch
    {
        private static readonly HashSet<string> TargetNames = new HashSet<string>(StringComparer.Ordinal)
        {
            "Show", "ShowBlock", "ShowBlockPrompt", "ShowBlockSpace", "ShowBlockWithCopy", "ShowSpace",
            "ShowOptionList", "ShowOptionListAsync", "ShowYesNo", "ShowYesNoAsync", "ShowYesNoCancel", "ShowYesNoCancelAsync"
        };

        public static IEnumerable<MethodBase> TargetMethods()
        {
            Type type = AccessTools.TypeByName("XRL.UI.Popup");
            if (type == null) yield break;
            foreach (var m in type.GetMethods(BindingFlags.Public | BindingFlags.Static | BindingFlags.Instance | BindingFlags.DeclaredOnly))
                if (TargetNames.Contains(m.Name))
                    yield return m;
        }

        public static void Prefix(object[] __args)
        {
            if (!LanguageGuard.Active()) return;
            if (__args == null) return;
            for (int i = 0; i < __args.Length && i < 4; i++)
                if (__args[i] is string s)
                    __args[i] = RouteTranslator.Translate("Popup", s);
        }
    }

    // Hook: popup menu-option labels (Yes/No, color names, rename choices …). Popup.GetPopupOption
    // returns a Qud.UI.QudMenuItem whose `text` field we translate (route MenuOption, pattern +
    // term only). Defensive: if the method isn't present, TargetMethods yields nothing (no-op).
    [HarmonyPatch]
    public static class MenuOptionPatch
    {
        private static System.Reflection.FieldInfo textField;

        public static IEnumerable<MethodBase> TargetMethods()
        {
            Type t = AccessTools.TypeByName("XRL.UI.Popup");
            if (t == null) yield break;
            var m = AccessTools.Method(t, "GetPopupOption");
            if (m != null) yield return m;
        }

        public static void Postfix(object __result)
        {
            if (!LanguageGuard.Active() || __result == null) return;
            var f = textField ?? (textField = __result.GetType().GetField("text"));
            if (f == null) return;
            if (f.GetValue(__result) is string s && s.Length > 0)
                f.SetValue(__result, RouteTranslator.Translate("MenuOption", s));
        }
    }

    // Hook (checklist #1): end-of-game / death summary screen. Show(int Score, string Details,
    // string Cause, string Name, string Leaderboard, bool bReal) — translate Details + Cause.
    [HarmonyPatch]
    public static class GameSummaryPatch
    {
        public static IEnumerable<MethodBase> TargetMethods()
        {
            Type t = AccessTools.TypeByName("XRL.UI.GameSummaryUI");
            if (t == null) yield break;
            var m = AccessTools.Method(t, "Show");
            if (m != null) yield return m;
        }

        public static void Prefix(object[] __args)
        {
            if (!LanguageGuard.Active() || __args == null) return;
            if (__args.Length > 1 && __args[1] is string details) __args[1] = RouteTranslator.Translate("GameSummary", details);
            if (__args.Length > 2 && __args[2] is string cause) __args[2] = RouteTranslator.Translate("GameSummary", cause);
        }
    }

    // Hook (checklist #2): body-part names with laterality. The four BodyPart name/description
    // getters return e.g. "right hand", "front left leg", "hand (2)". We split off the English
    // laterality adjective (via Laterality.StripLateralityAdjective + the part's Laterality
    // bit-flags), translate the base noun (BodyPart route terms), then re-attach a German
    // laterality adjective inflected for the noun's gender ("rechte Hand", "vorderes linkes Bein").
    [HarmonyPatch]
    public static class BodyPartPatch
    {
        private static readonly Regex PosSuffix = new Regex(@"\s*\((\d+)\)\s*$", RegexOptions.CultureInvariant);

        public static IEnumerable<MethodBase> TargetMethods()
        {
            Type t = AccessTools.TypeByName("XRL.World.Anatomy.BodyPart");
            if (t == null) yield break;
            foreach (var name in new[] { "GetCardinalName", "GetOrdinalName", "GetCardinalDescription", "GetOrdinalDescription" })
            {
                var m = AccessTools.Method(t, name);
                if (m != null && m.ReturnType == typeof(string)) yield return m;
            }
        }

        public static void Postfix(XRL.World.Anatomy.BodyPart __instance, ref string __result)
        {
            if (!LanguageGuard.Active() || string.IsNullOrEmpty(__result) || __instance == null) return;
            string res = __result;
            // Markup present: don't attempt the laterality recompose; just term-translate in place.
            if (res.IndexOf("{{", StringComparison.Ordinal) >= 0 || res.IndexOf('[') >= 0 || res.IndexOf('<') >= 0)
            {
                __result = RouteTranslator.Translate("BodyPart", res);
                return;
            }

            string suffix = "";
            string core = res;
            var mm = PosSuffix.Match(res);
            if (mm.Success) { suffix = " (" + mm.Groups[1].Value + ")"; core = res.Substring(0, mm.Index); }

            bool upper = core.Length > 0 && char.IsUpper(core[0]);
            int lat = __instance.Laterality;
            string baseEng = (lat != 0)
                ? XRL.World.Capabilities.Laterality.StripLateralityAdjective(core, lat, false)
                : core;
            string baseDe = RouteTranslator.Translate("BodyPart", baseEng.Trim());
            Gender g = GermanGender.Guess(baseDe);
            string adj = (lat != 0) ? GermanGrammar.LateralityAdjectives(lat, g) : "";
            string composed = (adj.Length > 0 ? adj + " " : "") + baseDe + suffix;
            if (upper && composed.Length > 0) composed = char.ToUpperInvariant(composed[0]) + composed.Substring(1);
            __result = composed;
        }
    }

    // Hook (checklist #3): possessive display names. GameObject.Poss(...) returns "Your X" /
    // "the snapjaw's tail". Route "Possessive" (pattern-only, no term fallthrough).
    [HarmonyPatch]
    public static class PossessivePatch
    {
        public static IEnumerable<MethodBase> TargetMethods()
        {
            Type t = AccessTools.TypeByName("XRL.World.GameObject");
            if (t == null) yield break;
            foreach (var m in t.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly))
                if (m.Name == "Poss" && m.ReturnType == typeof(string))
                    yield return m;
        }

        public static void Postfix(ref string __result)
        {
            if (!LanguageGuard.Active() || string.IsNullOrEmpty(__result)) return;
            __result = RouteTranslator.Translate("Possessive", __result);
        }
    }
}
