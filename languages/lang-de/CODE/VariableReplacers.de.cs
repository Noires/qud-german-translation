using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;
using XRL;
using XRL.Language;
using XRL.World;
using XRL.World.Text;
using XRL.World.Text.Attributes;
using XRL.World.Text.Delegates;

namespace LanguagesOfQudGerman
{
    // Diagnostic: prints a line to Player.log at mod init so we can confirm the German
    // grammar code actually compiled and loaded (successful VariableReplacer registration
    // is otherwise silent). Look for "[QudDE]" in Player.log. This beacon covers the
    // TOKEN-string path (this file); the runtime message post-processor logs its own
    // "[QudDE] COQDE runtime loaded ..." beacon (see languages/lang-de/COQDE/).
    [HasModSensitiveStaticCache]
    public static class GermanReplacerBootstrap
    {
        [ModSensitiveCacheInit]
        public static void Init()
        {
            UnityEngine.Debug.Log("[QudDE] VariableReplacers (token strings) loaded (Lang=de, Override=true).");
            VariableReplacers.LoadLexicon();
        }
    }

    // German grammar replacer (prototype).
    //
    // SCOPE / SPLIT (see docs/RUNTIME_POSTPROCESSOR_PLAN.md §5b): German runtime grammar is
    // handled in two places that do NOT overlap — do not delete one thinking the other covers
    // it:
    //   * THIS file (game-compiled) rewrites the ~300 TOKEN strings ("=object.the.name=",
    //     "=the=", "=a.name=" …) via Override=true. Only token-based strings reach it.
    //   * COQDE.dll (languages/lang-de/COQDE/) rewrites the code-built MESSAGE LOG lines
    //     ("The snapjaw dies." …) that never use those tokens and so never reach this file.
    //
    // Gender note: grammatical gender now has ONE shared data source — the lexicon
    // languages/lang-de/COQDE/GenderLexicon.tsv, loaded by BOTH this token replacer
    // (LoadLexicon below) and the COQDE DLL. The inline Overrides table + ending-heuristic
    // remain as the fallback baseline if the file is missing. (The conjugation/logic is still
    // duplicated because this is a separate, reflection-loaded assembly from the game-compiled
    // CODE/; sharing the *logic* at runtime would couple this proven token path to the DLL's
    // load order. Keep the two override tables in sync when adding nouns. (Reflection-based
    // single-source consolidation is a tracked follow-up.)
    //
    // Overrides the definite/indefinite article tokens so that runtime-composed object
    // references ("the giant beetle", "a leather boot", "=subject.t=", "=object.t=") render
    // with a German article (der/die/das/ein/eine/einen) instead of the English fallback.
    //
    // KNOWN LIMITATIONS (see CHANGELOG):
    //   * Gender is inferred from the head noun (ending heuristics + a curated override table);
    //     German gender is partly arbitrary, so some articles will be wrong for uncommon nouns.
    //   * Case is only known as Subject (nominative) vs Object (accusative) via TargetType.
    //     Dative/genitive after prepositions is not conveyed by the token, so those come out
    //     nominative/accusative (e.g. "mit der ..." may render "mit die ...") - still more German
    //     than the English "the".
    //   * Adjectives inside assembled names/descriptions are plain text (not tokenized) and
    //     therefore cannot be inflected here.
    [HasVariableReplacer(Lang = "de")]
    public static class VariableReplacers
    {
        private enum Gender { Masc, Fem, Neut, Plural }
        private enum Case { Nom, Acc }

        // Curated gender overrides for common game nouns (head-noun form, lowercase, folded/umlaut).
        private static readonly Dictionary<string, Gender> Overrides = new Dictionary<string, Gender>
        {
            // creatures / bodies
            {"bär", Gender.Masc}, {"baer", Gender.Masc}, {"spinne", Gender.Fem}, {"käfer", Gender.Masc}, {"kaefer", Gender.Masc},
            {"amöbe", Gender.Fem}, {"amoebe", Gender.Fem}, {"schwein", Gender.Neut}, {"hund", Gender.Masc}, {"katze", Gender.Fem},
            {"schlange", Gender.Fem}, {"ratte", Gender.Fem}, {"fledermaus", Gender.Fem}, {"vogel", Gender.Masc}, {"fisch", Gender.Masc},
            {"leiche", Gender.Fem}, {"kadaver", Gender.Masc}, {"pilz", Gender.Masc}, {"pflanze", Gender.Fem}, {"schnecke", Gender.Fem},
            {"affe", Gender.Masc}, {"pavian", Gender.Masc}, {"wurm", Gender.Masc}, {"biene", Gender.Fem}, {"skorpion", Gender.Masc},
            // materials / walls / terrain
            {"stein", Gender.Masc}, {"wand", Gender.Fem}, {"mauer", Gender.Fem}, {"boden", Gender.Masc}, {"fels", Gender.Masc},
            {"schiefer", Gender.Masc}, {"sandstein", Gender.Masc}, {"kalkstein", Gender.Masc}, {"marmor", Gender.Masc}, {"glas", Gender.Neut},
            {"tür", Gender.Fem}, {"tuer", Gender.Fem}, {"zaun", Gender.Masc}, {"säule", Gender.Fem}, {"saeule", Gender.Fem},
            // items / body parts
            {"klinge", Gender.Fem}, {"axt", Gender.Fem}, {"dolch", Gender.Masc}, {"schwert", Gender.Neut}, {"speer", Gender.Masc},
            {"stiefel", Gender.Masc}, {"handschuh", Gender.Masc}, {"helm", Gender.Masc}, {"rüstung", Gender.Fem}, {"ruestung", Gender.Fem},
            {"haut", Gender.Fem}, {"fell", Gender.Neut}, {"panzer", Gender.Masc}, {"schnabel", Gender.Masc}, {"horn", Gender.Neut},
            {"auge", Gender.Neut}, {"arm", Gender.Masc}, {"bein", Gender.Neut}, {"kopf", Gender.Masc}, {"hand", Gender.Fem},
            {"flügel", Gender.Masc}, {"fluegel", Gender.Masc}, {"schwanz", Gender.Masc}, {"zunge", Gender.Fem}, {"zahn", Gender.Masc},
        };

        // Merge the shared gender lexicon (languages/lang-de/COQDE/GenderLexicon.tsv) into the
        // override table above. Same file the COQDE DLL loads, so both layers agree on gender
        // from one data source. File entries win over the inline defaults; on any error we keep
        // the inline table (no regression).
        internal static void LoadLexicon()
        {
            try
            {
                foreach (var mod in ModManager.Mods)
                {
                    string p = Path.Combine(mod.Path, "languages", "lang-de", "COQDE", "GenderLexicon.tsv");
                    if (!File.Exists(p)) continue;
                    int n = 0;
                    foreach (var raw in File.ReadAllLines(p))
                    {
                        string line = raw.Trim();
                        if (line.Length == 0 || line[0] == '#') continue;
                        var parts = raw.Split('\t');
                        if (parts.Length < 2) continue;
                        string noun = parts[0].Trim().ToLowerInvariant();
                        if (noun.Length == 0) continue;
                        switch (parts[1].Trim().ToLowerInvariant())
                        {
                            case "m": Overrides[noun] = Gender.Masc; n++; break;
                            case "f": Overrides[noun] = Gender.Fem; n++; break;
                            case "n": Overrides[noun] = Gender.Neut; n++; break;
                            case "p": Overrides[noun] = Gender.Plural; n++; break;
                        }
                    }
                    UnityEngine.Debug.Log("[QudDE] gender lexicon (token layer): " + n + " entries");
                    return;
                }
            }
            catch (Exception ex)
            {
                UnityEngine.Debug.LogWarning("[QudDE] gender lexicon load failed: " + ex.Message);
            }
        }

        private static string VisibleText(string value)
        {
            if (string.IsNullOrEmpty(value)) return value;
            string result = value;
            while (true)
            {
                string next = Regex.Replace(result, @"\{\{[^{}|]+\|([^{}]*)\}\}", "$1");
                if (next == result) break;
                result = next;
            }
            result = Regex.Replace(result, @"&.", "");
            result = Regex.Replace(result, @"\^.", "");
            return result.Trim();
        }

        // Take the last alphabetic word as the head noun (compounds inherit the head's gender).
        private static string HeadNoun(string name)
        {
            var words = Regex.Matches(VisibleText(name), @"[A-Za-zÄÖÜäöüß-]+");
            if (words.Count == 0) return "";
            string last = words[words.Count - 1].Value;
            int dash = last.LastIndexOf('-');
            if (dash >= 0 && dash < last.Length - 1) last = last.Substring(dash + 1);
            return last;
        }

        private static Gender GuessGender(string name)
        {
            string head = HeadNoun(name);
            if (head.Length == 0) return Gender.Neut;
            string h = head.ToLowerInvariant();
            if (Overrides.TryGetValue(h, out var g)) return g;
            // crude plural: German plurals often end -en/-er/-e after a stem; skip (too unreliable) -> singular.
            // feminine endings
            if (h.EndsWith("ung") || h.EndsWith("heit") || h.EndsWith("keit") || h.EndsWith("schaft")
                || h.EndsWith("ion") || h.EndsWith("tät") || h.EndsWith("taet") || h.EndsWith("ik")
                || h.EndsWith("enz") || h.EndsWith("anz") || h.EndsWith("ur") || h.EndsWith("ie"))
                return Gender.Fem;
            // neuter endings
            if (h.EndsWith("chen") || h.EndsWith("lein") || h.EndsWith("ment") || h.EndsWith("tum")
                || h.EndsWith("um") || h.EndsWith("ma"))
                return Gender.Neut;
            // masculine endings
            if (h.EndsWith("er") || h.EndsWith("ling") || h.EndsWith("ismus") || h.EndsWith("ich")
                || h.EndsWith("ig") || h.EndsWith("ant") || h.EndsWith("or") || h.EndsWith("ast"))
                return Gender.Masc;
            if (h.EndsWith("e")) return Gender.Fem;   // many -e nouns are feminine
            return Gender.Masc;                        // default
        }

        private static Case CaseOf(VariableContext ctx)
        {
            return ctx.Type == TargetType.Object ? Case.Acc : Case.Nom;
        }

        // Proper names ("Warden Ualraig", "Oboroqoru") take NO article in German.
        private static bool IsProper(GameObject obj)
        {
            return obj != null && obj.HasProperName;
        }

        // Engine knows singular/plural reliably; grammatical plural article is always "die".
        private static bool IsPlural(GameObject obj)
        {
            return obj != null && obj.IsPlural;
        }

        private static string Definite(Gender g, Case c)
        {
            switch (g)
            {
                case Gender.Masc: return c == Case.Acc ? "den" : "der";
                case Gender.Fem: return "die";
                case Gender.Neut: return "das";
                default: return "die"; // plural
            }
        }

        private static string Indefinite(Gender g, Case c)
        {
            switch (g)
            {
                case Gender.Masc: return c == Case.Acc ? "einen" : "ein";
                case Gender.Fem: return "eine";
                case Gender.Neut: return "ein";
                default: return ""; // no indefinite plural article
            }
        }

        private static string Cap(string s, bool capitalize)
        {
            if (!capitalize || string.IsNullOrEmpty(s)) return s;
            return char.ToUpperInvariant(s[0]) + s.Substring(1);
        }

        private static string GermanName(GameObject obj)
        {
            return obj.GetDisplayName(Short: true, BaseOnly: true);
        }

        // Definite article for an object, respecting plural ("die") over the noun heuristic.
        private static string DefiniteFor(GameObject obj, Case c)
        {
            if (IsPlural(obj)) return "die";
            return Definite(GuessGender(GermanName(obj)), c);
        }

        // ---- definite article, no name ("=the=") ----
        [VariableReplacer(new string[] { "the" }, Default = "der ", Capitalization = true, Override = true)]
        public static string DefiniteArticle(VariableContext Context, GameObject Object)
        {
            if (Object.IsPlayer() && Grammar.AllowSecondPerson) return "";
            // A proper name takes no article; the token stands alone, so emit nothing.
            if (IsProper(Object)) return "";
            var art = DefiniteFor(Object, CaseOf(Context));
            return Cap(art, Context.Capitalize) + " ";
        }

        // ---- definite article + name ("=the.name=", "=t=", "=subject.t=", "=object.t=") ----
        [VariableReplacer(new string[] { "the.name", "t", "formattedName" }, Capitalization = true, Override = true)]
        public static string DefiniteName(VariableContext Context, GameObject Object)
        {
            string name = GermanName(Object);
            if (Object.IsPlayer() && Grammar.AllowSecondPerson)
                return "Ihr";
            // Proper names ("Warden Ualraig") take no article in German.
            if (IsProper(Object)) return name;
            var art = DefiniteFor(Object, CaseOf(Context));
            return Cap(art, Context.Capitalize) + " " + name;
        }

        // ---- indefinite article, no name ("=a=") ----
        [VariableReplacer(new string[] { "a" }, Default = "ein ", Capitalization = true, Override = true)]
        public static string IndefiniteArticle(VariableContext Context, GameObject Object)
        {
            // No indefinite article before plurals or proper names.
            if (IsPlural(Object) || IsProper(Object)) return "";
            var art = Indefinite(GuessGender(GermanName(Object)), CaseOf(Context));
            if (art.Length == 0) return "";
            return Cap(art, Context.Capitalize) + " ";
        }

        // ---- indefinite article + name ("=a.name=", "=an=") ----
        [VariableReplacer(new string[] { "a.name", "an" }, Default = "ein Ding", Capitalization = true, Override = true)]
        public static string IndefiniteName(VariableContext Context, GameObject Object)
        {
            string name = GermanName(Object);
            if (Object.IsPlayer() && Grammar.AllowSecondPerson)
                return "Ihr";
            // Plurals and proper names get the bare name (no indefinite article).
            if (IsPlural(Object) || IsProper(Object)) return name;
            var art = Indefinite(GuessGender(name), CaseOf(Context));
            if (art.Length == 0) return name;
            return Cap(art, Context.Capitalize) + " " + name;
        }
    }
}
