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
using Newtonsoft.Json.Linq;

namespace LanguagesOfQudGerman
{
    // Diagnostic: prints a line to Player.log at mod init so we can confirm the German
    // grammar code actually compiled and loaded (successful VariableReplacer registration
    // is otherwise silent). Look for "[QudDE]" in Player.log.
    [HasModSensitiveStaticCache]
    public static class GermanReplacerBootstrap
    {
        [ModSensitiveCacheInit]
        public static void Init()
        {
            UnityEngine.Debug.Log("[QudDE] VariableReplacers (token strings) loaded (Lang=de, Override=true).");
            VariableReplacers.LoadLexicon();
            VariableReplacers.LoadVerbs();
            VariableReplacers.SelfTestCases();
            VariableReplacers.SelfTestPipeline();
            TranslatorDeutsch.SelfTest();
        }
    }

    // German grammar replacer.
    //
    // SCOPE: this file (game-compiled) rewrites the ~300 TOKEN strings ("=object.the.name=",
    // "=the=", "=a.name=" …) via Override=true. Only token-based strings reach it. Code-built
    // MESSAGE LOG lines ("The snapjaw dies." …) never use tokens and are NOT translated here —
    // the retired COQDE.dll used to rewrite those at runtime (removed 2026-07-17, recoverable
    // from git history; see docs/OPEN_ISSUES.md — waiting on official localization support).
    //
    // Gender note: grammatical gender has ONE shared data source — the lexicon
    // languages/lang-de/COQDE/GenderLexicon.tsv, loaded by LoadLexicon below. The inline
    // Overrides table + ending-heuristic remain as the fallback baseline if the file is
    // missing.
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
        private enum Case { Nom, Acc, Dat, Gen }

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
        // override table above. File entries win over the inline defaults; on any error we keep
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
            // Kompositum: Genus vom Grundwort erben (langschwert -> schwert, werkbank -> bank).
            // Längster bekannter Suffix gewinnt; VOR der Endungs-Heuristik, weil Grundwörter
            // wie "raum" sonst von Pseudo-Endungen (-um -> Neut) gekapert würden.
            // Falsche Erbschaften (z. B. gewand ≠ wand) per exaktem Lexikon-Eintrag abfangen.
            int bestLen = 0; Gender bestGender = Gender.Masc;
            foreach (var kv in Overrides)
            {
                string k = kv.Key;
                if (k.Length >= 3 && k.Length < h.Length && k.Length > bestLen
                    && h.EndsWith(k, StringComparison.Ordinal))
                { bestLen = k.Length; bestGender = kv.Value; }
            }
            if (bestLen > 0) return bestGender;
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
                case Gender.Masc: return c == Case.Gen ? "des" : c == Case.Dat ? "dem" : c == Case.Acc ? "den" : "der";
                case Gender.Fem: return (c == Case.Dat || c == Case.Gen) ? "der" : "die";
                case Gender.Neut: return c == Case.Gen ? "des" : c == Case.Dat ? "dem" : "das";
                default: return c == Case.Dat ? "den" : c == Case.Gen ? "der" : "die"; // plural
            }
        }

        private static string Indefinite(Gender g, Case c)
        {
            switch (g)
            {
                case Gender.Masc: return c == Case.Dat ? "einem" : c == Case.Gen ? "eines" : c == Case.Acc ? "einen" : "ein";
                case Gender.Fem: return (c == Case.Dat || c == Case.Gen) ? "einer" : "eine";
                case Gender.Neut: return c == Case.Dat ? "einem" : c == Case.Gen ? "eines" : "ein";
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

        // Parameter-aware variant for the case replacers: honors the same display params the
        // game's own name replacers accept (single, long, withTitles, asIfKnown), so templates
        // can write e.g. "=object.dativ:single=" without losing the parameter semantics.
        private static string GermanName(GameObject obj, VariableContext ctx)
        {
            if (ctx == null || ctx.Parameters == null || ctx.Parameters.Count == 0)
                return GermanName(obj);
            bool wantLong = ctx.HasParameter("long");
            bool withTitles = ctx.HasParameter("withTitles");
            return obj.GetDisplayName(
                Short: !wantLong,
                BaseOnly: !wantLong && !withTitles,
                Single: ctx.HasParameter("single"),
                WithoutTitles: !withTitles,
                AsIfKnown: ctx.HasParameter("asIfKnown"));
        }

        // Genitive phrase of an object ("des Schnappkiefers", "der eisernen Kiste").
        private static string GenitivePhrase(GameObject obj)
        {
            string n = GermanName(obj);
            if (IsProper(obj)) return GenitiveNoun(n, Gender.Masc);
            return BuildDefinitePhrase(n, Case.Gen, IsPlural(obj), false);
        }

        // itsPossessor / itsSubjectPossessor: append the holder's genitive
        // ("aus der Wasserhaut des Schnappkiefers"). Player holders get no suffix -
        // second-person context already implies ownership.
        private static string WithPossessor(string phrase, VariableContext ctx, GameObject obj)
        {
            if (ctx != null && (ctx.HasParameter("itsPossessor") || ctx.HasParameter("itsSubjectPossessor")))
            {
                GameObject holder = obj?.Holder;
                if (holder != null && holder.IsCreature && !holder.IsPlayer())
                    return phrase + " " + GenitivePhrase(holder);
            }
            return phrase;
        }

        // Definite article for an object, respecting plural ("die") over the noun heuristic.
        private static string DefiniteFor(GameObject obj, Case c)
        {
            if (IsPlural(obj)) return c == Case.Dat ? "den" : c == Case.Gen ? "der" : "die";
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

        // ---- native-migration Phase 1a: full case system (definite article + name) ----
        // The case is supplied by the translator in the German template:
        //   "=object.nominativ=", "=object.akkusativ=",
        //   "=object.dativ="  (e.g. "mit =object.dativ="),
        //   "=object.genitiv=" (e.g. "der Zorn =object.genitiv=").
        // Player (second person): nom "Ihr", akk/dat "Euch", gen "Euer".
        // Reflexive: an object in object/dative position that refers back to the sentence
        // subject renders as "sich" (or "euch" for the player).

        private static string PlayerPronoun(Case c)
        {
            switch (c)
            {
                case Case.Acc:
                case Case.Dat: return "euch";
                case Case.Gen: return "euer";
                default: return "Ihr"; // nominative
            }
        }

        // Object in object/dative position that refers back to the sentence subject.
        private static bool IsReflexive(VariableContext ctx, GameObject obj)
        {
            return obj != null && ctx.Invocation != null
                && ReferenceEquals(ctx.Invocation.Subject, obj)
                && ctx.Type == TargetType.Object;
        }

        // Genitive head-noun for masc/neut: append -s (or -es after s/ß/x/z). Fem/plural unchanged.
        private static string GenitiveNoun(string name, Gender g)
        {
            if (g == Gender.Fem || g == Gender.Plural || string.IsNullOrEmpty(name)) return name;
            char last = char.ToLowerInvariant(name[name.Length - 1]);
            if (last == 's' || last == 'ß' || last == 'x' || last == 'z') return name + "es";
            return name + "s";
        }

        // ---- Phase 1b: attributive adjective declension (ported from COQDE GermanGrammar) ----
        private enum DeclType { Weak, Mixed, Strong }

        private static string AdjEnding(DeclType t, Case c, Gender g)
        {
            if (t == DeclType.Weak)
            {
                if (c == Case.Nom) return g == Gender.Plural ? "en" : "e";
                if (c == Case.Acc) return (g == Gender.Masc || g == Gender.Plural) ? "en" : "e";
                return "en"; // dat/gen
            }
            if (t == DeclType.Mixed)
            {
                if (c == Case.Nom) return g == Gender.Masc ? "er" : g == Gender.Fem ? "e" : g == Gender.Neut ? "es" : "en";
                if (c == Case.Acc) return g == Gender.Masc ? "en" : g == Gender.Fem ? "e" : g == Gender.Neut ? "es" : "en";
                return "en"; // dat/gen
            }
            switch (c) // Strong (no determiner)
            {
                case Case.Nom: return g == Gender.Masc ? "er" : g == Gender.Fem ? "e" : g == Gender.Neut ? "es" : "e";
                case Case.Acc: return g == Gender.Masc ? "en" : g == Gender.Fem ? "e" : g == Gender.Neut ? "es" : "e";
                case Case.Dat: return g == Gender.Fem ? "er" : g == Gender.Plural ? "en" : "em";
                default: return (g == Gender.Fem || g == Gender.Plural) ? "er" : "en"; // Gen
            }
        }

        // Reduce a possibly-already-inflected adjective to its stem (eiserne->eisern, großer->groß).
        private static string AdjStem(string word)
        {
            string w = word.ToLowerInvariant();
            foreach (var suf in new[] { "em", "en", "er", "es", "e" })
                if (w.Length - suf.Length >= 3 && w.EndsWith(suf, StringComparison.Ordinal))
                    return w.Substring(0, w.Length - suf.Length);
            return w;
        }

        // Definite noun phrase: determiner + weak-declined adjectives + head (genitive-suffixed).
        // For a single-word name this reduces to "article + name" (identical to Phase 1a).
        private static string BuildDefinitePhrase(string name, Case c, bool plural, bool capitalize)
        {
            string[] words = name.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            if (words.Length == 0) return name;
            string head = words[words.Length - 1];
            Gender g = plural ? Gender.Plural : GuessGender(head);
            var parts = new List<string> { Cap(Definite(g, c), capitalize) };
            for (int i = 0; i < words.Length - 1; i++)
                parts.Add(AdjStem(words[i]) + AdjEnding(DeclType.Weak, c, g));
            parts.Add(c == Case.Gen ? GenitiveNoun(head, g) : head);
            return string.Join(" ", parts);
        }

        // Shared core for all four case replacers.
        private static string CaseName(VariableContext Context, GameObject Object, Case c)
        {
            if (Object.IsPlayer() && Grammar.AllowSecondPerson)
                return Cap(PlayerPronoun(c), Context.Capitalize);
            if ((c == Case.Acc || c == Case.Dat) && IsReflexive(Context, Object))
                return Cap("sich", Context.Capitalize);
            string name = GermanName(Object, Context);
            // asPossessed: Besitzer-Artikel statt bestimmtem Artikel. Spieler-Besitz ->
            // dekliniertes "Euer" ("aus Eurem Wischmopp"); Kreaturen-Besitz -> Genitiv-Anhang.
            if (Context.HasParameter("asPossessed"))
            {
                GameObject holder = Object.Holder;
                if (holder != null && holder.IsPlayer() && Grammar.AllowSecondPerson)
                    return BuildPossessivePhrase(name, c, IsPlural(Object), Context.Capitalize);
                if (holder != null && holder.IsCreature)
                    return BuildDefinitePhrase(name, c, IsPlural(Object), Context.Capitalize)
                        + " " + GenitivePhrase(holder);
            }
            if (IsProper(Object))
                return WithPossessor(c == Case.Gen ? GenitiveNoun(name, Gender.Masc) : name, Context, Object);
            return WithPossessor(BuildDefinitePhrase(name, c, IsPlural(Object), Context.Capitalize), Context, Object);
        }

        [VariableReplacer(new string[] { "nominativ" }, Capitalization = true)]
        [VariableExample("das Krokodil:Das Krokodil", "Croc")]
        [VariableExample("der Leuchtfisch:Der Leuchtfisch", "Glowfish")]
        public static string Nominativ(VariableContext Context, GameObject Object)
        { return CaseName(Context, Object, Case.Nom); }

        [VariableReplacer(new string[] { "akkusativ" }, Capitalization = true)]
        [VariableExample("das Krokodil:Das Krokodil", "Croc")]
        [VariableExample("den Leuchtfisch:Den Leuchtfisch", "Glowfish")]
        public static string Akkusativ(VariableContext Context, GameObject Object)
        { return CaseName(Context, Object, Case.Acc); }

        [VariableReplacer(new string[] { "dativ" }, Capitalization = true)]
        [VariableExample("dem Krokodil:Dem Krokodil", "Croc")]
        [VariableExample("dem Leuchtfisch:Dem Leuchtfisch", "Glowfish")]
        public static string Dativ(VariableContext Context, GameObject Object)
        { return CaseName(Context, Object, Case.Dat); }

        [VariableReplacer(new string[] { "genitiv" }, Capitalization = true)]
        [VariableExample("des Krokodils:Des Krokodils", "Croc")]
        [VariableExample("des Leuchtfischs:Des Leuchtfischs", "Glowfish")]
        public static string Genitiv(VariableContext Context, GameObject Object)
        { return CaseName(Context, Object, Case.Gen); }

        // ---- indefinite case forms: "=object.a.dativ=" -> "einem Käfer / einer Wand" ----
        // ein-word determiner (einem/einer/eines), mixed adjective declension (strong for
        // plural, which has no indefinite article). Fixes "von einen X" -> "von einem X".
        private static string BuildIndefinitePhrase(string name, Case c, bool plural, bool capitalize)
        {
            string[] words = name.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            if (words.Length == 0) return name;
            string head = words[words.Length - 1];
            Gender g = plural ? Gender.Plural : GuessGender(head);
            string art = Indefinite(g, c); // "" for plural (no indefinite plural article)
            DeclType decl = art.Length == 0 ? DeclType.Strong : DeclType.Mixed;
            var parts = new List<string>();
            if (art.Length != 0) parts.Add(Cap(art, capitalize));
            for (int i = 0; i < words.Length - 1; i++)
                parts.Add(AdjStem(words[i]) + AdjEnding(decl, c, g));
            parts.Add(c == Case.Gen ? GenitiveNoun(head, g) : head);
            if (art.Length == 0 && capitalize && parts.Count > 0) parts[0] = Cap(parts[0], true);
            return string.Join(" ", parts);
        }

        private static string IndefCaseName(VariableContext Context, GameObject Object, Case c)
        {
            if (Object.IsPlayer() && Grammar.AllowSecondPerson)
                return Cap(PlayerPronoun(c), Context.Capitalize);
            if (IsProper(Object))
            {
                string pn = GermanName(Object, Context);
                return WithPossessor(c == Case.Gen ? GenitiveNoun(pn, Gender.Masc) : pn, Context, Object);
            }
            return WithPossessor(
                BuildIndefinitePhrase(GermanName(Object, Context), c, IsPlural(Object), Context.Capitalize),
                Context, Object);
        }

        [VariableReplacer(new string[] { "a.nominativ" }, Capitalization = true)]
        public static string IndefNominativ(VariableContext Context, GameObject Object)
        { return IndefCaseName(Context, Object, Case.Nom); }

        [VariableReplacer(new string[] { "a.akkusativ" }, Capitalization = true)]
        public static string IndefAkkusativ(VariableContext Context, GameObject Object)
        { return IndefCaseName(Context, Object, Case.Acc); }

        [VariableReplacer(new string[] { "a.dativ" }, Capitalization = true)]
        [VariableExample("einem Krokodil:Einem Krokodil", "Croc")]
        [VariableExample("einem Leuchtfisch:Einem Leuchtfisch", "Glowfish")]
        public static string IndefDativ(VariableContext Context, GameObject Object)
        { return IndefCaseName(Context, Object, Case.Dat); }

        [VariableReplacer(new string[] { "a.genitiv" }, Capitalization = true)]
        public static string IndefGenitiv(VariableContext Context, GameObject Object)
        { return IndefCaseName(Context, Object, Case.Gen); }

        // ---- Phase 2 (Turkish-way): German conjugation replacer, keyed on the GERMAN infinitive.
        // The translator authors German verbs in data-layer templates:
        //   "=subject.konjde:sehen=" -> sieht / seht / sehen  (by the subject's person).
        // Strong (irregular) verbs come from Verbs.json by 'inf'; regular (weak) verbs are
        // conjugated algorithmically. We deliberately do NOT override the game's English "verb"
        // replacer (neither does the Turkish reference) — any remaining legacy =verb:X= tokens
        // simply render their English conjugation until the template is converted to =konjde:=.
        private static readonly Dictionary<string, string[]> VerbsByInf = new Dictionary<string, string[]>(StringComparer.OrdinalIgnoreCase);

        internal static void LoadVerbs()
        {
            try
            {
                foreach (var mod in ModManager.Mods)
                {
                    string p = Path.Combine(mod.Path, "languages", "lang-de", "COQDE", "Verbs.json");
                    if (!File.Exists(p)) continue;
                    var arr = (JArray)JObject.Parse(File.ReadAllText(p))["verbs"];
                    int n = 0;
                    foreach (var v in arr)
                    {
                        string inf = (string)v["inf"];
                        string s3 = (string)v["s3"];
                        if (string.IsNullOrEmpty(inf)) continue;
                        // Only STRONG verbs (explicit s3) go in the table; WEAK verbs (inf only)
                        // fall through to WeakConjugate's algorithmic present tense.
                        if (string.IsNullOrEmpty(s3)) continue;
                        VerbsByInf[inf] = new[] { s3, (string)v["p2"] ?? inf, (string)v["p3"] ?? inf };
                        n++;
                    }
                    UnityEngine.Debug.Log("[QudDE] verb table (by infinitive): " + n + " strong verbs");
                    return;
                }
            }
            catch (Exception ex) { UnityEngine.Debug.LogWarning("[QudDE] verb table load failed: " + ex.Message); }
        }

        // 0 = 3rd sg (er/sie/es), 1 = 2nd pl / "Ihr" (player), 2 = 3rd pl.
        private static int VerbPerson(GameObject o)
        {
            if (o == null) return 0;
            if (o.IsPlayer() && Grammar.AllowSecondPerson) return 1;
            if (o.IsPlural) return 2;
            return 0;
        }

        // Regular (weak) German present tense from an infinitive: s3/p2 = stem+t (+e- after t/d),
        // p3 = infinitive. Strong verbs are handled by the Verbs.json table, not here.
        private static string WeakConjugate(string inf, int person)
        {
            if (string.IsNullOrEmpty(inf)) return inf;
            if (person == 2) return inf; // 3rd plural = infinitive
            string stem = inf.EndsWith("en") ? inf.Substring(0, inf.Length - 2)
                        : inf.EndsWith("n") ? inf.Substring(0, inf.Length - 1) : inf;
            char last = stem.Length > 0 ? stem[stem.Length - 1] : ' ';
            return stem + ((last == 't' || last == 'd') ? "et" : "t");
        }

        [VariableReplacer(new string[] { "konjde" }, Capitalization = true)]
        [VariableParametrizedExample("sehen", "sieht:Sieht", "Croc")]
        [VariableParametrizedExample("machen", "macht:Macht", "Croc")]
        public static string KonjDe(VariableContext Context, GameObject Object)
        {
            string inf = (Context.Parameters != null && Context.Parameters.Count > 0) ? Context.Parameters[0] : "";
            int p = VerbPerson(Object);
            string de = (VerbsByInf.TryGetValue(inf, out var f) && !string.IsNullOrEmpty(f[p])) ? f[p] : WeakConjugate(inf, p);
            return Cap(de, Context.Capitalize);
        }

        // ---- Phase 2: native body-part replacer (German laterality inflection) ----
        // Overrides the BodyPart "name"/"ordinalName" replacers: strip English laterality,
        // translate the base part name, re-add German laterality inflected by the part's gender
        // ("right hand" -> "rechte Hand", "left leg" -> "linkes Bein"). Replaces the DLL BodyPartPatch.
        private static readonly Dictionary<string, string> BodyPartTerms = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            { "head", "Kopf" }, { "face", "Gesicht" }, { "eye", "Auge" }, { "eyes", "Augen" },
            { "hand", "Hand" }, { "hands", "Hände" }, { "arm", "Arm" }, { "arms", "Arme" },
            { "foot", "Fuß" }, { "feet", "Füße" }, { "leg", "Bein" }, { "legs", "Beine" },
            { "tail", "Schwanz" }, { "claw", "Klaue" }, { "tongue", "Zunge" }, { "wing", "Flügel" },
            { "body", "Körper" }, { "head slot", "Kopf" },
        };

        private static string LateralityAdjectives(int code, Gender g)
        {
            string e = (g == Gender.Fem || g == Gender.Plural) ? "e" : (g == Gender.Neut ? "es" : "er");
            var parts = new List<string>();
            void Add(int flag, string stem) { if ((code & flag) != 0) parts.Add(stem + e); }
            Add(4, "ober"); Add(8, "unter"); Add(16, "vorder"); Add(32, "mittler"); Add(64, "hinter");
            Add(512, "inner"); Add(1024, "äußer"); Add(128, "inner"); Add(256, "äußer");
            Add(1, "link"); Add(2, "recht");
            return string.Join(" ", parts);
        }

        private static string TranslateBodyPartName(string eng)
        {
            if (string.IsNullOrEmpty(eng)) return eng;
            if (BodyPartTerms.TryGetValue(eng.Trim(), out var de)) return de;
            var words = eng.Split(' ');
            for (int i = 0; i < words.Length; i++)
                if (BodyPartTerms.TryGetValue(words[i], out var w)) words[i] = w;
            return string.Join(" ", words);
        }

        private static readonly Regex BpPosSuffix = new Regex(@"\s*\((\d+)\)\s*$", RegexOptions.CultureInvariant);

        private static string TransformBodyPart(string eng, int lat, bool capitalize)
        {
            if (string.IsNullOrEmpty(eng)) return eng;
            if (eng.IndexOf("{{", StringComparison.Ordinal) >= 0 || eng.IndexOf('[') >= 0 || eng.IndexOf('<') >= 0)
                return TranslateBodyPartName(eng);
            string suffix = "", core = eng;
            var mm = BpPosSuffix.Match(eng);
            if (mm.Success) { suffix = " (" + mm.Groups[1].Value + ")"; core = eng.Substring(0, mm.Index); }
            bool upper = core.Length > 0 && char.IsUpper(core[0]);
            string baseEng = lat != 0 ? XRL.World.Capabilities.Laterality.StripLateralityAdjective(core, lat, false) : core;
            string baseDe = TranslateBodyPartName(baseEng.Trim());
            Gender g = GuessGender(baseDe);
            string adj = lat != 0 ? LateralityAdjectives(lat, g) : "";
            string composed = (adj.Length > 0 ? adj + " " : "") + baseDe + suffix;
            if (upper && composed.Length > 0) composed = char.ToUpperInvariant(composed[0]) + composed.Substring(1);
            return composed;
        }

        // Overrides the game's BodyPart "name"/"ordinalName" replacers (Delegates.BodyPart.cs).
        // The engine dispatches on (replacer-name + parameter type), NOT return type, so a
        // string-returning override cleanly replaces the game's void Name for the TOKEN path
        // (combat / ability / mutation text). NOTE: this does NOT reach the equipment/anatomy
        // paperdoll, which calls BodyPart.GetCardinalName() directly in C# (no token, no provider
        // hook, no string-table lookup) -- the official Turkish mod hit the same wall and shelved
        // its body-part replacer (see docs/archive/.../UnusedDelegates.tr.cs). That surface needs
        // a Harmony patch on GetCardinalName (the retired DLL's approach) or stays English.
        [VariableReplacer(new string[] { "name" }, Override = true, Capitalization = true)]
        public static string BodyPartName(VariableContext Context, XRL.World.Anatomy.BodyPart Part)
        { return TransformBodyPart(Part.GetCardinalName(), Part.Laterality, Context.Capitalize); }

        [VariableReplacer(new string[] { "ordinalName" }, Override = true, Capitalization = true)]
        public static string BodyPartOrdinalName(VariableContext Context, XRL.World.Anatomy.BodyPart Part)
        { return TransformBodyPart(Part.GetOrdinalName(), Part.Laterality, Context.Capitalize); }

        // ---- Possessiv: vorangestellter Genitiv & Euer-Deklination ----
        // Englische 's-Konstruktionen werden als vorangestellter deutscher Genitiv gerendert:
        // "Barathrum's leg" -> "Barathrums Bein", "the croc's leg" -> "des Krokodils Bein"
        // (gehoben/archaisch, passt zum Qud-Ton). Spieler-Besitz -> "Euer" (Grundform, da das
        // Genus des FOLGENDEN Substantivs hier nicht bekannt ist).

        // Deutsche 's-Regel für nackte Namen: +s, nach s/ß/x/z nur Apostroph (Marx').
        internal static string GermanPossessiveSuffix(string s)
        {
            if (string.IsNullOrEmpty(s)) return s;
            int wrap = 0;
            while (s.EndsWith("}}", StringComparison.Ordinal)) { wrap++; s = s.Substring(0, s.Length - 2); }
            char last = s.Length > 0 ? char.ToLowerInvariant(s[s.Length - 1]) : ' ';
            s += ("sßxz".IndexOf(last) >= 0) ? "'" : "s";
            for (int i = 0; i < wrap; i++) s += "}}";
            return s;
        }

        // Overrides des "possessive"/"'s"-Postprocessors (Grammar.MakePossessive ist englisch).
        // Wirkt auf alle "|'s"-Templates, v. a. die HistorySpice-Sätze
        // ("=spice.entity:name|'s= Wagen" -> "Reshephs Wagen").
        // String-Return statt Value-Mutation: die Delegate-Registrierung akzeptiert beide
        // Formen (typeof(void)/typeof(string)-Check im Engine-Code), und TextBuilder-Schreib-
        // Overloads (Append/Insert) sind im net48-Smoke-Build nicht auflösbar (CS0518/Span).
        [VariablePostProcessor("possessive", "makePossessive", "'s", Override = true)]
        public static string PossessivePost(VariableContext Context)
        {
            return GermanPossessiveSuffix(Context.Value.ToString());
        }

        [VariableReplacer(new string[] { "the.name's", "t's" }, Override = true, Capitalization = true)]
        public static string PossessiveDefinite(VariableContext Context, GameObject Object)
        {
            if (Object.IsPlayer() && Grammar.AllowSecondPerson) return Cap("Euer", Context.Capitalize);
            string n = GermanName(Object, Context);
            if (IsProper(Object)) return Cap(GenitiveNoun(n, Gender.Masc), Context.Capitalize);
            return BuildDefinitePhrase(n, Case.Gen, IsPlural(Object), Context.Capitalize);
        }

        [VariableReplacer(new string[] { "name's", "basename's", "refname's" }, Override = true, Capitalization = true)]
        public static string PossessiveBare(VariableContext Context, GameObject Object)
        {
            if (Object.IsPlayer() && Grammar.AllowSecondPerson) return Cap("Euer", Context.Capitalize);
            string n = GermanName(Object, Context);
            return Cap(GenitiveNoun(n, IsPlural(Object) ? Gender.Plural : GuessGender(n)), Context.Capitalize);
        }

        [VariableReplacer(new string[] { "a.name's", "an's" }, Override = true, Capitalization = true)]
        public static string PossessiveIndefinite(VariableContext Context, GameObject Object)
        {
            if (Object.IsPlayer() && Grammar.AllowSecondPerson) return Cap("Euer", Context.Capitalize);
            return IndefCaseName(Context, Object, Case.Gen);
        }

        // Possessivartikel "euer" dekliniert nach Kasus + Genus des Besitztums.
        private static string Euer(Gender g, Case c)
        {
            switch (c)
            {
                case Case.Nom: return (g == Gender.Fem || g == Gender.Plural) ? "eure" : "euer";
                case Case.Acc: return g == Gender.Masc ? "euren" : (g == Gender.Neut ? "euer" : "eure");
                case Case.Dat: return g == Gender.Fem ? "eurer" : g == Gender.Plural ? "euren" : "eurem";
                default: return (g == Gender.Fem || g == Gender.Plural) ? "eurer" : "eures";
            }
        }

        // "Eurem rostigen Wischmopp" - Possessivartikel + Mixed-Deklination (wie ein-Wörter).
        private static string BuildPossessivePhrase(string name, Case c, bool plural, bool capitalize)
        {
            string[] words = name.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            if (words.Length == 0) return name;
            string head = words[words.Length - 1];
            Gender g = plural ? Gender.Plural : GuessGender(head);
            var parts = new List<string> { Cap(Euer(g, c), capitalize) };
            for (int i = 0; i < words.Length - 1; i++)
                parts.Add(AdjStem(words[i]) + AdjEnding(DeclType.Mixed, c, g));
            parts.Add(c == Case.Gen ? GenitiveNoun(head, g) : head);
            return string.Join(" ", parts);
        }

        // Pipeline self-test: runs a real template ("=object.dativ=") through the game's
        // replacer engine on a sample object, proving the FULL chain (token -> replacer ->
        // German) at load, without needing the in-game testreplacers wish. Self-diagnosing:
        // a resolved output ("dem Krokodil") = success; a literal "=object.dativ=" = the role
        // didn't bind. Guarded so it can never harm load.
        public static void SelfTestPipeline()
        {
            // {blueprint, template, expected}. Runs each through the real replacer engine on a
            // freshly-created object and logs PASS/FAIL — the Turkish [VariableExample] idea,
            // self-run at load so it needs no testreplacers wish / active game.
            string[][] tests = {
                new[] { "Croc",      "=object.nominativ=", "das Krokodil" },
                new[] { "Croc",      "=object.akkusativ=", "das Krokodil" },
                new[] { "Croc",      "=object.dativ=",     "dem Krokodil" },
                new[] { "Croc",      "=object.genitiv=",   "des Krokodils" },
                new[] { "Glowfish",  "=object.nominativ=", "der Leuchtfisch" },
                new[] { "Glowfish",  "=object.akkusativ=", "den Leuchtfisch" },
                new[] { "Glowfish",  "=object.dativ=",     "dem Leuchtfisch" },
                new[] { "Glowfish",  "=object.genitiv=",   "des Leuchtfischs" },
                new[] { "Goat",      "=object.dativ=",     "der Ziege" },
                new[] { "Snapjaw",   "=object.akkusativ=", "den Schnappkiefer" },
                new[] { "Croc",      "=object.a.dativ=",   "einem Krokodil" },
                new[] { "Glowfish",  "=object.a.dativ=",   "einem Leuchtfisch" },
                new[] { "Goat",      "=object.a.dativ=",   "einer Ziege" },
            };
            // Distinct dummy for the unused role: avoids the game's "null subject" error and,
            // being a different instance, keeps subject != object so reflexive doesn't fire.
            GameObject other = null;
            try { other = GameObjectFactory.Factory.CreateObject("Snapjaw"); } catch { }
            int pass = 0, fail = 0;
            foreach (var t in tests)
            {
                try
                {
                    GameObject o = GameObjectFactory.Factory.CreateObject(t[0]);
                    string got = GameText.VariableReplace(t[1], other, o);
                    bool ok = string.Equals(got, t[2], StringComparison.Ordinal);
                    if (ok) pass++; else fail++;
                    UnityEngine.Debug.Log("[QudDE] pipeline-test " + (ok ? "PASS" : "FAIL") + ": "
                        + t[0] + " " + t[1] + " -> \"" + got + "\""
                        + (ok ? "" : " (expected \"" + t[2] + "\")"));
                }
                catch (Exception e)
                {
                    fail++;
                    UnityEngine.Debug.Log("[QudDE] pipeline-test ERROR: " + t[0] + " " + t[1] + " : " + e.Message);
                }
            }
            // German conjugation replacer (subject-based): GameText.VariableReplace(text, subject, object)
            string[][] vtests = {
                new[] { "Croc", "=subject.konjde:sehen=",    "sieht" },   // strong (from Verbs.json)
                new[] { "Croc", "=subject.konjde:machen=",   "macht" },   // weak (algorithmic)
                new[] { "Croc", "=subject.konjde:waten=",    "watet" },   // weak, -et after t
                new[] { "Croc", "=subject.konjde:schlagen=", "schlägt" }, // agent strong: a->ä
                new[] { "Croc", "=subject.konjde:graben=",   "gräbt" },   // agent strong: a->ä
                new[] { "Croc", "=subject.konjde:tragen=",   "trägt" },   // agent strong: a->ä
                new[] { "Croc", "=subject.konjde:heilen=",   "heilt" },   // agent weak
                new[] { "Croc", "=subject.konjde:fangen=",   "fängt" },   // separable base (abfangen)
                new[] { "Croc", "=subject.konjde:lassen=",   "lässt" },   // separable base (fallen lassen)
            };
            foreach (var t in vtests)
            {
                try
                {
                    GameObject o = GameObjectFactory.Factory.CreateObject(t[0]);
                    string got = GameText.VariableReplace(t[1], o, other);
                    bool ok = string.Equals(got, t[2], StringComparison.Ordinal);
                    if (ok) pass++; else fail++;
                    UnityEngine.Debug.Log("[QudDE] verb-test " + (ok ? "PASS" : "FAIL") + ": "
                        + t[0] + " " + t[1] + " -> \"" + got + "\"" + (ok ? "" : " (expected \"" + t[2] + "\")"));
                }
                catch (Exception e) { UnityEngine.Debug.Log("[QudDE] verb-test ERROR: " + t[1] + " : " + e.Message); }
            }
            // body-part transform (logic-level: strip English laterality -> German inflected)
            object[][] bp = {
                new object[] { "right hand", 2, "rechte Hand" },
                new object[] { "left leg",   1, "linkes Bein" },
                new object[] { "hand",       0, "Hand" },
            };
            foreach (var t in bp)
            {
                try
                {
                    string got = TransformBodyPart((string)t[0], (int)t[1], false);
                    bool ok = string.Equals(got, (string)t[2], StringComparison.Ordinal);
                    if (ok) pass++; else fail++;
                    UnityEngine.Debug.Log("[QudDE] bodypart-test " + (ok ? "PASS" : "FAIL") + ": \""
                        + t[0] + "\" (lat " + t[1] + ") -> \"" + got + "\"" + (ok ? "" : " (expected \"" + t[2] + "\")"));
                }
                catch (Exception e) { UnityEngine.Debug.Log("[QudDE] bodypart-test ERROR: " + t[0] + " : " + e.Message); }
            }
            // Possessiv-Logik (pure Funktionen, ohne Engine)
            string[][] poss = {
                new[] { GermanPossessiveSuffix("Krokodil"), "Krokodils" },
                new[] { GermanPossessiveSuffix("Marx"), "Marx'" },
                new[] { GermanPossessiveSuffix("{{M|Resheph}}"), "{{M|Reshephs}}" },
                new[] { BuildPossessivePhrase("rostiger Wischmopp", Case.Dat, false, false), "eurem rostigen Wischmopp" },
                new[] { BuildPossessivePhrase("Flammenpistole", Case.Dat, false, false), "eurer Flammenpistole" },
                new[] { Euer(Gender.Neut, Case.Acc), "euer" },
            };
            foreach (var t in poss)
            {
                bool ok = string.Equals(t[0], t[1], StringComparison.Ordinal);
                if (ok) pass++; else fail++;
                if (!ok) UnityEngine.Debug.Log("[QudDE] possessiv-test FAIL: \"" + t[0] + "\" (erwartet \"" + t[1] + "\")");
            }
            UnityEngine.Debug.Log("[QudDE] pipeline-test summary: " + pass + " passed, " + fail + " failed");
        }

        // Load-time self-test: logs every case for representative nouns to Player.log
        // ("[QudDE] case-selftest:"), so grammar is verifiable offline without testreplacers.
        public static void SelfTestCases()
        {
            string[] nouns = { "Wand", "Käfer", "Schwert", "Krokodil", "Leuchtfisch" };
            string[] labels = { "nom", "akk", "dat", "gen" };
            Case[] cs = { Case.Nom, Case.Acc, Case.Dat, Case.Gen };
            foreach (var noun in nouns)
            {
                Gender g = GuessGender(noun);
                var sb = new System.Text.StringBuilder();
                for (int i = 0; i < cs.Length; i++)
                {
                    string art = Definite(g, cs[i]);
                    string head = cs[i] == Case.Gen ? GenitiveNoun(noun, g) : noun;
                    sb.Append(labels[i]).Append('=').Append(art).Append(' ').Append(head);
                    if (i < cs.Length - 1) sb.Append(" | ");
                }
                UnityEngine.Debug.Log("[QudDE] case-selftest: " + noun + " (" + g + "): " + sb);
            }
            // Phase 1b: adjective declension on multi-word literal names (no GameObject needed).
            string[] phrases = { "eiserne Rebenklinge", "rostige alte Kette", "großer Käfer" };
            foreach (var p in phrases)
                UnityEngine.Debug.Log("[QudDE] phrase-selftest: \"" + p + "\" -> nom=\""
                    + BuildDefinitePhrase(p, Case.Nom, false, false) + "\" | akk=\""
                    + BuildDefinitePhrase(p, Case.Acc, false, false) + "\" | dat=\""
                    + BuildDefinitePhrase(p, Case.Dat, false, false) + "\"");
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
