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
            VariableReplacers.LoadPlurals();
            VariableReplacers.SelfTestCases();
            VariableReplacers.SelfTestPipeline();
            VariableReplacers.CuratorTests();
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
            // neuter endings ("-ma" ist KEINE Regel: der Puma, die Firma, das Thema -
            // die griechischen Neutra stehen stattdessen im Lexikon)
            if (h.EndsWith("chen") || h.EndsWith("lein") || h.EndsWith("ment") || h.EndsWith("tum")
                || h.EndsWith("um"))
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

        // Deutsche Artikel für den C#-Pfad (GameObject.The/A -> Translator.DefiniteArticle):
        // von TranslatorDeutsch aufgerufen, wenn die Basis auf ihr englisches "the "/"a "
        // zurückfällt. Kasus ist dort unbekannt -> Nominativ (Subjektposition dominiert).
        internal static string CSharpDefiniteArticle(GameObject obj, bool capital)
        {
            if (obj == null) return capital ? "Der " : "der ";
            string art = DefiniteFor(obj, Case.Nom);
            return Cap(art, capital) + " ";
        }

        internal static string CSharpIndefiniteArticle(GameObject obj, bool capital)
        {
            if (obj == null) return capital ? "Ein " : "ein ";
            string art = Indefinite(IsPlural(obj) ? Gender.Plural : GuessGender(GermanName(obj)), Case.Nom);
            if (art.Length == 0) return "";
            return Cap(art, capital) + " ";
        }

        // C#-Pfad "with its X" (GameObject.its_ -> GetDisplayName mit Possessiv als
        // DefaultDefiniteArticle): komplette deutsche Possessivphrase inkl. Adjektiv-
        // deklination ("seiner gepanzerten Klaue"). Bei Markup im Namen (Farbtags) wird
        // nur der Artikel dekliniert, der Name bleibt unangetastet.
        internal static string CSharpPossessivePhrase(string bareName, GameObject obj, string stem, bool dative, bool capitalize)
        {
            if (string.IsNullOrEmpty(bareName)) return bareName;
            Case c = dative ? Case.Dat : Case.Nom;
            bool plural = obj != null && IsPlural(obj);
            if (bareName.IndexOf("{{", StringComparison.Ordinal) >= 0 || bareName.IndexOf('[') >= 0)
            {
                Gender g = plural ? Gender.Plural : GuessGender(VisibleText(bareName));
                return Cap(DeclinePoss(stem, g, c), capitalize) + " " + bareName;
            }
            return BuildPossessivePhrase(bareName, c, plural, capitalize, stem);
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
                return Cap(PlayerPronoun(CaseOf(Context)), Context.Capitalize);
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
        // Player (second person, informelles du — Anrede-Richtlinie 2026-10-22):
        // nom "du", akk "dich", dat "dir", gen "deiner".
        // Reflexive: an object in object/dative position that refers back to the sentence
        // subject renders as "sich" (for the player: "dich"/"dir").

        private static string PlayerPronoun(Case c)
        {
            switch (c)
            {
                case Case.Acc: return "dich";
                case Case.Dat: return "dir";
                case Case.Gen: return "deiner";
                default: return "du"; // nominative
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

        // Wörter, nach denen ein Name KEINE "Adjektive + Kopf"-Phrase mehr ist
        // ("Phiole mit Wasser", "Zahnrad aus der Großen Maschine").
        private static readonly HashSet<string> FunctionWords = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "aus", "mit", "von", "der", "die", "das", "dem", "den", "des", "ein", "eine",
            "einem", "einen", "einer", "eines", "und", "im", "in", "an", "auf", "für", "fuer",
            "zu", "zur", "zum", "voller", "ohne", "über", "ueber", "unter",
        };

        // Farb-Verpackung eines Wortes abspalten: "{{r|blutig}}" und "&rblutig" tragen den
        // deklinierbaren Kern innen; ohne das griffe das Sicherheits-Muster nie bei den
        // eingefärbten Zustands-Adjektiven der Flüssigkeits-Daten.
        private static readonly Regex ColorWrap = new Regex(@"^(\{\{[^|{}]+\|)(.+?)(\}\})$", RegexOptions.CultureInvariant);
        private static readonly Regex ColorPrefix = new Regex(@"^((?:[&^].)+)(.+)$", RegexOptions.CultureInvariant);

        private static void SplitColor(string w, out string pre, out string core, out string post)
        {
            pre = ""; post = ""; core = w;
            var m = ColorWrap.Match(core);
            if (m.Success) { pre = m.Groups[1].Value; core = m.Groups[2].Value; post = m.Groups[3].Value; }
            var p = ColorPrefix.Match(core);
            if (p.Success) { pre += p.Groups[1].Value; core = p.Groups[2].Value; }
        }

        private static string DeclineAdj(string word, DeclType t, Case c, Gender g)
        {
            SplitColor(word, out string pre, out string core, out string post);
            return pre + AdjStem(core) + AdjEnding(t, c, g) + post;
        }

        // "kleingeschriebene Adjektive + großgeschriebener Kopf"? Nur dann dürfen führende
        // Wörter dekliniert werden - alles andere bekommt den Artikel unverändert vorangestellt.
        private static bool IsAdjNounPattern(string[] words)
        {
            if (words.Length == 0) return false;
            SplitColor(words[words.Length - 1], out _, out string head, out _);
            if (head.Length == 0 || !char.IsUpper(head[0])) return words.Length == 1;
            for (int i = 0; i < words.Length - 1; i++)
            {
                SplitColor(words[i], out _, out string w, out _);
                if (w.Length == 0 || FunctionWords.Contains(w)) return false;
                foreach (char ch in w)
                    if (!char.IsLetter(ch) || char.IsUpper(ch)) return false;
            }
            return true;
        }

        // Genus-Kopf einer Phrase: bei "Phiole mit Wasser" zählt das Wort VOR dem ersten
        // Funktionswort (Phiole, nicht Wasser); sonst wie gehabt das letzte Wort.
        private static string PhraseGenderHead(string[] words)
        {
            for (int i = 1; i < words.Length; i++)
                if (FunctionWords.Contains(words[i]))
                    return words[i - 1];
            return words[words.Length - 1];
        }

        // Definite noun phrase: determiner + weak-declined adjectives + head (genitive-suffixed).
        // For a single-word name this reduces to "article + name" (identical to Phase 1a).
        private static string BuildDefinitePhrase(string name, Case c, bool plural, bool capitalize)
        {
            string[] words = name.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            if (words.Length == 0) return name;
            Gender g = plural ? Gender.Plural : GuessGender(PhraseGenderHead(words));
            if (!IsAdjNounPattern(words))
                return Cap(Definite(g, c), capitalize) + " " + name;
            string head = words[words.Length - 1];
            var parts = new List<string> { Cap(Definite(g, c), capitalize) };
            for (int i = 0; i < words.Length - 1; i++)
                parts.Add(DeclineAdj(words[i], DeclType.Weak, c, g));
            parts.Add(c == Case.Gen ? GenitiveNoun(head, g) : head);
            return string.Join(" ", parts);
        }

        // Nachdeklination für den C#-Pfad: "Der nass Leuchtfisch" -> "Der nasse Leuchtfisch".
        // Der Artikel wurde bereits (von uns oder Daten-Overrides) vorangestellt; hier werden
        // nur die Adjektive dazwischen dekliniert - ausschließlich beim sicheren Muster.
        internal static string DeclineAfterArticle(string s, GameObject obj)
        {
            if (string.IsNullOrEmpty(s)) return s;
            string[] all = s.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            if (all.Length < 3) return s;   // Artikel + Adjektiv + Kopf ist das Minimum
            string art = all[0];
            string artLower = art.ToLowerInvariant();
            Gender g;
            DeclType decl;
            var rest = new string[all.Length - 1];
            Array.Copy(all, 1, rest, 0, rest.Length);
            if (!IsAdjNounPattern(rest)) return s;
            switch (artLower)
            {
                case "der": g = Gender.Masc; decl = DeclType.Weak; break;
                case "das": g = Gender.Neut; decl = DeclType.Weak; break;
                case "die":
                    g = (obj != null && IsPlural(obj)) ? Gender.Plural : Gender.Fem;
                    decl = DeclType.Weak; break;
                case "eine": g = Gender.Fem; decl = DeclType.Mixed; break;
                case "ein":
                    g = GuessGender(PhraseGenderHead(rest));
                    if (g == Gender.Fem) g = Gender.Masc;   // "ein" schließt Fem aus
                    decl = DeclType.Mixed; break;
                default: return s;
            }
            var parts = new List<string> { art };
            for (int i = 0; i < rest.Length - 1; i++)
                parts.Add(DeclineAdj(rest[i], decl, Case.Nom, g));
            parts.Add(rest[rest.Length - 1]);
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
            // dekliniertes "dein" ("aus deinem Wischmopp"); Kreaturen-Besitz -> Genitiv-Anhang.
            if (Context.HasParameter("asPossessed"))
            {
                GameObject holder = Object.Holder;
                if (holder != null && holder.IsPlayer() && Grammar.AllowSecondPerson)
                    return BuildPossessivePhrase(name, c, IsPlural(Object), Context.Capitalize, "dein");
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
            Gender g = plural ? Gender.Plural : GuessGender(PhraseGenderHead(words));
            string art = Indefinite(g, c); // "" for plural (no indefinite plural article)
            if (!IsAdjNounPattern(words))
                return art.Length == 0 ? Cap(name, capitalize) : Cap(art, capitalize) + " " + name;
            string head = words[words.Length - 1];
            DeclType decl = art.Length == 0 ? DeclType.Strong : DeclType.Mixed;
            var parts = new List<string>();
            if (art.Length != 0) parts.Add(Cap(art, capitalize));
            for (int i = 0; i < words.Length - 1; i++)
                parts.Add(DeclineAdj(words[i], decl, c, g));
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
        // Englisches Basisverb -> deutsche Formen {s3,p2,p3,s2}: erlaubt dem Does-Override,
        // LAUFZEIT-Verben ("see", "hear" aus #verb-Argumenten) deutsch zu konjugieren.
        private static readonly Dictionary<string, string[]> VerbsByEn = new Dictionary<string, string[]>(StringComparer.OrdinalIgnoreCase);

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
                        var forms = new[] { s3, (string)v["p2"] ?? inf, (string)v["p3"] ?? inf,
                                            (string)v["s2"] ?? DeriveS2(s3, inf) };
                        VerbsByInf[inf] = forms;
                        string en = (string)v["en"];
                        if (!string.IsNullOrEmpty(en))
                            foreach (string e in en.Split('/'))
                                if (e.Trim().Length > 0) VerbsByEn[e.Trim()] = forms;
                        n++;
                    }
                    UnityEngine.Debug.Log("[QudDE] verb table (by infinitive): " + n + " strong verbs, "
                        + VerbsByEn.Count + " english keys");
                    return;
                }
            }
            catch (Exception ex) { UnityEngine.Debug.LogWarning("[QudDE] verb table load failed: " + ex.Message); }
        }

        // Deutsche Verbform für ein Laufzeit-Verb, das deutsch (Infinitiv, ggf. aus einem
        // übersetzten Datenfeld wie "Sehen") ODER englisch ("see") ankommen kann.
        // Nur echte Tabellentreffer gelten als gefunden - naive Weak-Konjugation englischer
        // Wörter ("open" -> "opent") wäre schlimmer als der englische Fallback.
        private static bool TryGermanVerb(string verb, int person, out string form)
        {
            form = null;
            if (string.IsNullOrEmpty(verb)) return false;
            string v = verb.Trim();
            if (VerbsByInf.TryGetValue(v, out var f) || VerbsByEn.TryGetValue(v, out f))
            {
                form = f[person];
                return !string.IsNullOrEmpty(form);
            }
            // deutsch aussehende Infinitive (Umlaut oder -en + kein englischer Tabellen-Key)
            string lower = v.ToLowerInvariant();
            if (lower.IndexOfAny(new[] { 'ä', 'ö', 'ü', 'ß' }) >= 0 && lower.EndsWith("en"))
            {
                form = WeakConjugate(lower, person);
                return true;
            }
            return false;
        }

        // 0 = 3rd sg (er/sie/es), 1 = 2nd pl (ihr), 2 = 3rd pl, 3 = 2nd sg "du" (player).
        private static int VerbPerson(GameObject o)
        {
            if (o == null) return 0;
            if (o.IsPlayer() && Grammar.AllowSecondPerson) return 3;
            if (o.IsPlural) return 2;
            return 0;
        }

        // Regular (weak) German present tense from an infinitive: s3/p2 = stem+t (+e- after t/d),
        // s2 = stem+st (+e- after t/d, only -t after s/ß/x/z: "du reist"),
        // p3 = infinitive. Strong verbs are handled by the Verbs.json table, not here.
        private static string WeakConjugate(string inf, int person)
        {
            if (string.IsNullOrEmpty(inf)) return inf;
            if (person == 2) return inf; // 3rd plural = infinitive
            string stem = inf.EndsWith("en") ? inf.Substring(0, inf.Length - 2)
                        : inf.EndsWith("n") ? inf.Substring(0, inf.Length - 1) : inf;
            char last = stem.Length > 0 ? stem[stem.Length - 1] : ' ';
            if (person == 3)
                return stem + ((last == 't' || last == 'd') ? "est" : ("sßxz".IndexOf(last) >= 0 ? "t" : "st"));
            return stem + ((last == 't' || last == 'd') ? "et" : "t");
        }

        // s2 ("du"-Form) eines STARKEN Verbs aus seiner s3-Form, falls Verbs.json kein s2 hat:
        // sieht->siehst, trägt->trägst, lässt->lässt, hält->hältst (t-Stamm), lädt->lädst
        // (d-Stamm). Echte Unregelmäßige (bist, hast, wirst, kannst …) stehen explizit in der Datei.
        internal static string DeriveS2(string s3, string inf)
        {
            if (string.IsNullOrEmpty(s3)) return WeakConjugate(inf, 3);
            string stem = inf != null && inf.EndsWith("en") ? inf.Substring(0, inf.Length - 2) : (inf ?? "");
            char sl = stem.Length > 0 ? stem[stem.Length - 1] : ' ';
            // löst, lässt, zerbirst, heißt: s3 trägt das -st/-t schon in sich
            if (s3.EndsWith("st") || s3.EndsWith("ßt") || s3.EndsWith("zt") || s3.EndsWith("xt")) return s3;
            if (!s3.EndsWith("t")) return s3;
            if (sl == 't') return s3.EndsWith("et") ? s3.Substring(0, s3.Length - 1) + "st" : s3 + "st";
            if (sl == 'd') return s3.EndsWith("et") ? s3.Substring(0, s3.Length - 1) + "st"
                                                    : s3.Substring(0, s3.Length - 1) + "st";
            return s3.Substring(0, s3.Length - 1) + "st";
        }

        // Kleines Adverb-Lexikon für die "adverb:verb"-Form von Does ("already:have").
        private static readonly Dictionary<string, string> Adverbs = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            { "already", "bereits" }, { "just", "gerade" }, { "merely", "lediglich" },
            { "still", "noch" }, { "now", "jetzt" }, { "then", "dann" }, { "also", "auch" },
            { "no longer", "nicht mehr" }, { "suddenly", "plötzlich" },
        };

        // ---- Does-Override: "Name + konjugiertes Verb" auch für LAUFZEIT-Verben ----
        // "=subject.Does#verb=" bekommt sein Verb erst zur Laufzeit (Autoact: "Sehen"/"see").
        // Der englische Does kann weder deutsche Infinitive noch englische Verben deutsch
        // konjugieren ("Ihr Sehen ein Krokodil"). Bei Tabellentreffer bauen wir deutsch
        // ("Ihr seht", "der Schnappkiefer sieht"); sonst greift unverändert das Original.
        private static string DoesDe(VariableContext Context, GameObject Object, string verb, string adverb, Func<string> original)
        {
            int person = VerbPerson(Object);
            if (!TryGermanVerb(verb, person, out string form))
                return original();
            string name = DefiniteName(Context, Object);
            string adv = null;
            if (!string.IsNullOrEmpty(adverb))
                adv = Adverbs.TryGetValue(adverb.Trim(), out var a) ? a : adverb;
            return name + " " + form + (adv == null ? "" : " " + adv);
        }

        [VariableReplacer(new string[] { "does", "did" }, Default = "do", Override = true, Capitalization = true)]
        public static string DoesDeParam(VariableContext Context, GameObject Object)
        {
            int paramCnt = Context.Parameters.Count;
            bool hasEarlyEmpty = paramCnt >= 2 && string.IsNullOrEmpty(Context.Parameters[1]);
            int verbidx = (paramCnt >= 2 && !hasEarlyEmpty) ? 1 : 0;
            string verb = paramCnt >= 1 ? Context.Parameters[verbidx] : Context.Default;
            string adverb = (paramCnt >= 2 && !hasEarlyEmpty) ? Context.Parameters[0] : null;
            return DoesDe(Context, Object, verb, adverb, () => Context.Capitalize
                ? Object.Does(verb, Adverb: adverb,
                    Single: Context.HasParameter("single"),
                    Short: !Context.HasParameter("long"),
                    WithoutTitles: !Context.HasParameter("withTitles"))
                : Object.does(verb, Adverb: adverb,
                    Single: Context.HasParameter("single"),
                    Short: !Context.HasParameter("long"),
                    WithoutTitles: !Context.HasParameter("withTitles")));
        }

        [VariableReplacer(new string[] { "does", "did" }, Override = true, Capitalization = true)]
        public static string DoesDeArg(VariableContext Context, GameObject Object, string Verb)
        {
            return DoesDe(Context, Object, Verb, null, () => Context.Capitalize
                ? Object.Does(Verb,
                    Single: Context.HasParameter("single"),
                    Short: !Context.HasParameter("long"),
                    WithoutTitles: !Context.HasParameter("withTitles"))
                : Object.does(Verb,
                    Single: Context.HasParameter("single"),
                    Short: !Context.HasParameter("long"),
                    WithoutTitles: !Context.HasParameter("withTitles")));
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
        // (gehoben/archaisch, passt zum Qud-Ton). Spieler-Besitz -> "dein" (Grundform, da das
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
            if (Object.IsPlayer() && Grammar.AllowSecondPerson) return Cap("dein", Context.Capitalize);
            string n = GermanName(Object, Context);
            if (IsProper(Object)) return Cap(GenitiveNoun(n, Gender.Masc), Context.Capitalize);
            return BuildDefinitePhrase(n, Case.Gen, IsPlural(Object), Context.Capitalize);
        }

        [VariableReplacer(new string[] { "name's", "basename's", "refname's" }, Override = true, Capitalization = true)]
        public static string PossessiveBare(VariableContext Context, GameObject Object)
        {
            if (Object.IsPlayer() && Grammar.AllowSecondPerson) return Cap("dein", Context.Capitalize);
            string n = GermanName(Object, Context);
            return Cap(GenitiveNoun(n, IsPlural(Object) ? Gender.Plural : GuessGender(n)), Context.Capitalize);
        }

        [VariableReplacer(new string[] { "a.name's", "an's" }, Override = true, Capitalization = true)]
        public static string PossessiveIndefinite(VariableContext Context, GameObject Object)
        {
            if (Object.IsPlayer() && Grammar.AllowSecondPerson) return Cap("dein", Context.Capitalize);
            return IndefCaseName(Context, Object, Case.Gen);
        }

        // Possessiv-STAMM eines Besitzers. Benannte Figuren behalten ihre Pronomen-Daten
        // (respektiert they/them-Sets aus PronounSets.de.xml); generische Kreaturen richten
        // sich nach dem grammatischen Genus ihres deutschen Nomens: das Krokodil -> "sein",
        // die Schlange -> "ihr" (deutsche Kongruenzregel, nicht das Spiel-Gender).
        internal static string PossStemFor(GameObject owner) { return PossStem(owner); }

        private static string PossStem(GameObject owner)
        {
            if (owner.IsPlayer() && Grammar.AllowSecondPerson) return "dein";
            // Sinn-Kongruenz vor Nomen-Genus: echte männliche/weibliche Figuren behalten ihr
            // Geschlecht ("die Karawanenwache (m) ... mit seiner Axt"). Erst ungegenderte
            // Kreaturen (nonspecific/neuter) fallen auf das grammatische Genus des deutschen
            // Nomens zurück (das Krokodil -> sein, die Schlange -> ihr).
            string gname = owner.GetGender()?.Name;
            if (gname == "male" || gname == "hindren male") return "sein";
            if (gname == "female" || gname == "hindren female") return "ihr";
            if (gname == "males" || gname == "females" || gname == "plural" || gname == "collective") return "ihr";
            if (IsProper(owner))
            {
                string adj = owner.GetPronounProvider().PossessiveAdjective;
                return string.IsNullOrEmpty(adj) ? "sein" : adj.ToLowerInvariant();
            }
            Gender g = IsPlural(owner) ? Gender.Plural : GuessGender(GermanName(owner));
            return (g == Gender.Fem || g == Gender.Plural) ? "ihr" : "sein";
        }

        // Dekliniert sein/ihr/euer/mein/dein/unser nach Genus des Besitztums + Kasus
        // (ein-Wort-Deklination; euer -> eure/eurem). Unbekannte Stämme aus Pronomen-Sets
        // (hir, xyr, eir ...) bleiben unverändert - besser undekliniert als verstümmelt.
        private static string DeclinePoss(string stem, Gender g, Case c)
        {
            bool known = stem == "sein" || stem == "ihr" || stem == "euer"
                      || stem == "mein" || stem == "dein" || stem == "unser";
            if (!known) return stem;
            string end;
            switch (c)
            {
                case Case.Nom: end = (g == Gender.Fem || g == Gender.Plural) ? "e" : ""; break;
                case Case.Acc: end = g == Gender.Masc ? "en" : (g == Gender.Neut ? "" : "e"); break;
                case Case.Dat: end = g == Gender.Fem ? "er" : (g == Gender.Plural ? "en" : "em"); break;
                default: end = (g == Gender.Fem || g == Gender.Plural) ? "er" : "es"; break;
            }
            if (end.Length == 0) return stem;
            return (stem == "euer" ? "eur" : stem) + end;
        }

        // Kasus aus Token-Parametern (":dativ"/":dat" ...); ohne Parameter Nominativ.
        private static Case CaseParam(VariableContext ctx)
        {
            if (ctx.HasParameter("dativ") || ctx.HasParameter("dat")) return Case.Dat;
            if (ctx.HasParameter("akkusativ") || ctx.HasParameter("akk")) return Case.Acc;
            if (ctx.HasParameter("genitiv") || ctx.HasParameter("gen")) return Case.Gen;
            return Case.Nom;
        }

        // "deinem rostigen Wischmopp" / "seinem gefrorenen Biss" - Possessivartikel mit
        // beliebigem Stamm + Mixed-Adjektivdeklination (wie nach ein-Wörtern).
        private static string BuildPossessivePhrase(string name, Case c, bool plural, bool capitalize, string stem = "dein")
        {
            string[] words = name.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            if (words.Length == 0) return name;
            // Genus über den Phrasen-Kopf (GuessGender strippt Farbcodes/Markup selbst).
            Gender g = plural ? Gender.Plural : GuessGender(PhraseGenderHead(words));
            string det = DeclinePoss(stem, g, c);
            if (!IsAdjNounPattern(words))
                return Cap(det, capitalize) + " " + name;
            string head = words[words.Length - 1];
            var parts = new List<string> { Cap(det, capitalize) };
            for (int i = 0; i < words.Length - 1; i++)
                parts.Add(DeclineAdj(words[i], DeclType.Mixed, c, g));
            parts.Add(c == Case.Gen ? GenitiveNoun(head, g) : head);
            return string.Join(" ", parts);
        }

        // ---- Possessivpronomen-Replacer (Finding: "mit ihr Biss" -> "mit seinem Biss") ----

        // Alleinstehendes "=X.its=" vor festem deutschen Substantiv: Kasus + Genus des
        // Folgeworts als Parameter annotieren, z. B. "=subject.its:akk:f= Energiezelle"
        // -> "seine/ihre/Eure Energiezelle". Ohne Parameter: unflektierter Stamm.
        [VariableReplacer(new string[] { "possessive", "their", "its", "possessiveAdjective" }, Override = true, Capitalization = true)]
        public static string PossessiveAdjDe(VariableContext Context, GameObject Object)
        {
            string stem = PossStem(Object);
            Gender? g = null;
            if (Context.HasParameter("m")) g = Gender.Masc;
            else if (Context.HasParameter("f")) g = Gender.Fem;
            else if (Context.HasParameter("n")) g = Gender.Neut;
            else if (Context.HasParameter("pl")) g = Gender.Plural;
            string de = g.HasValue ? DeclinePoss(stem, g.Value, CaseParam(Context)) : stem;
            return Cap(de, Context.Capitalize);
        }

        // "=subject.its.item:dativ#weapon=" -> "mit seinem Biss" / "mit Eurer Klinge".
        // Genus kommt vom Item selbst; Eigennamen-Items lassen das Possessiv weg (wie das
        // englische Original: "his Stopsvalinn" -> "Stopsvalinn").
        [VariableReplacer(new string[] { "its.item", "its_" }, Override = true, Capitalization = true)]
        public static string ItsItemDe(VariableContext Context, GameObject Object, GameObject Item)
        {
            string n = GermanName(Item);
            if (IsProper(Item)) return Cap(n, Context.Capitalize);
            return BuildPossessivePhrase(n, CaseParam(Context), IsPlural(Item), Context.Capitalize, PossStem(Object));
        }

        // Kombiniert Possessiv + Körperteil in EINEM Token, damit das Genus des Teils die
        // Endung bestimmen kann: "von =subject.its.part:dat#part=!" -> "von seiner rechten
        // Hand!" (ersetzt Muster "=subject.its= =part.ordinalName=").
        [VariableReplacer(new string[] { "its.part" }, Capitalization = true)]
        public static string ItsPartDe(VariableContext Context, GameObject Object, XRL.World.Anatomy.BodyPart Part)
        {
            string de = TransformBodyPart(Part.GetOrdinalName(), Part.Laterality, false);
            return BuildPossessivePhrase(de, CaseParam(Context), false, Context.Capitalize, PossStem(Object));
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
                new[] { BuildPossessivePhrase("rostiger Wischmopp", Case.Dat, false, false), "deinem rostigen Wischmopp" },
                new[] { BuildPossessivePhrase("Flammenpistole", Case.Dat, false, false), "deiner Flammenpistole" },
                new[] { BuildPossessivePhrase("Biss", Case.Dat, false, false, "sein"), "seinem Biss" },
                new[] { BuildPossessivePhrase("rechte Hand", Case.Dat, false, false, "ihr"), "ihrer rechten Hand" },
                new[] { DeclinePoss("euer", Gender.Neut, Case.Acc), "euer" },
                new[] { DeclinePoss("sein", Gender.Fem, Case.Acc), "seine" },
                new[] { DeclinePoss("ihr", Gender.Plural, Case.Dat), "ihren" },
                new[] { DeclinePoss("hir", Gender.Masc, Case.Dat), "hir" },
                new[] { CSharpPossessivePhrase("gepanzerte Klaue", null, "sein", true, false), "seiner gepanzerten Klaue" },
                new[] { CSharpPossessivePhrase("Anzeige", null, "sein", false, true), "Seine Anzeige" },
                new[] { CSharpPossessivePhrase("Kampfaxt", null, "ihr", true, false), "ihrer Kampfaxt" },
                new[] { TryGermanVerb("see", 1, out var vSee) ? vSee : "?", "seht" },
                new[] { TryGermanVerb("see", 3, out var vDu) ? vDu : "?", "siehst" },
                new[] { DeriveS2("hält", "halten"), "hältst" },
                new[] { DeriveS2("lädt", "laden"), "lädst" },
                new[] { DeriveS2("lässt", "lassen"), "lässt" },
                new[] { WeakConjugate("machen", 3), "machst" },
                new[] { WeakConjugate("waten", 3), "watest" },
                new[] { WeakConjugate("reisen", 3), "reist" },
                new[] { Demonstrative(Gender.Masc, Case.Dat), "diesem" },
                new[] { Demonstrative(Gender.Fem, Case.Nom), "diese" },
                new[] { DativeFromAccusative("ihn", false), "ihm" },
                new[] { DativeFromAccusative("sie", false), "ihr" },
                new[] { DativeFromAccusative("sie", true), "ihnen" },
                new[] { DativeFromAccusative("es", false), "ihm" },
                new[] { DativeFromAccusative("dich", false), "dir" },
                new[] { PluralWord("Klinge"), "Klingen" },
                new[] { PluralWord("Rüstung"), "Rüstungen" },
                new[] { PluralWord("Käfer"), "Käfer" },
                new[] { PluralWord("Museum"), "Museen" },
                new[] { GermanPlural("rostiger Wischmopp"), "rostige Wischmoppe" },
                new[] { TryGermanVerb("Sehen", 0, out var vSehen) ? vSehen : "?", "sieht" },
                new[] { TryGermanVerb("open", 0, out _) ? "TREFFER" : "fallback", "fallback" },
                new[] { DeclineAfterArticle("Der nass Leuchtfisch", null), "Der nasse Leuchtfisch" },
                new[] { DeclineAfterArticle("ein nass Leuchtfisch", null), "ein nasser Leuchtfisch" },
                new[] { DeclineAfterArticle("das Zahnrad aus der Großen Maschine", null), "das Zahnrad aus der Großen Maschine" },
                new[] { BuildDefinitePhrase("Phiole mit Wasser", Case.Nom, false, false), "die Phiole mit Wasser" },
                new[] { BuildDefinitePhrase("Phiole mit Wasser", Case.Dat, false, false), "der Phiole mit Wasser" },
                new[] { BuildDefinitePhrase("nass Leuchtfisch", Case.Nom, false, false), "der nasse Leuchtfisch" },
                new[] { DeclineAfterArticle("Der {{r|blutig}} Issachari-Raider", null), "Der {{r|blutige}} Issachari-Raider" },
                new[] { DeclineAfterArticle("Der &rblutig Leuchtfisch", null), "Der &rblutige Leuchtfisch" },
            };
            foreach (var t in poss)
            {
                bool ok = string.Equals(t[0], t[1], StringComparison.Ordinal);
                if (ok) pass++; else fail++;
                if (!ok) UnityEngine.Debug.Log("[QudDE] possessiv-test FAIL: \"" + t[0] + "\" (erwartet \"" + t[1] + "\")");
            }
            UnityEngine.Debug.Log("[QudDE] pipeline-test summary: " + pass + " passed, " + fail + " failed");
        }

        // Kurator-Tests: datengetriebene Grammatik-Tests aus COQDE/CuratorTests.json,
        // gepflegt über die Kurator-UI (build/curator/, py build/curator/server.py).
        // Fehlende/leere Datei => stiller Skip. Die UI liest die Ergebniszeilen aus
        // Player.log; der geloggte file-mtime ist ihr Staleness-Anker (Log-Ergebnis
        // vs. aktuell deployte Testdatei).
        public static void CuratorTests()
        {
            try
            {
                string p = null;
                foreach (var mod in ModManager.Mods)
                {
                    string cand = Path.Combine(mod.Path, "languages", "lang-de", "COQDE", "CuratorTests.json");
                    if (File.Exists(cand)) { p = cand; break; }
                }
                if (p == null) return;
                var arr = (JArray)JObject.Parse(File.ReadAllText(p))["tests"];
                if (arr == null || arr.Count == 0) return;
                UnityEngine.Debug.Log("[QudDE] curator-tests file-mtime=" + File.GetLastWriteTimeUtc(p).Ticks
                    + " count=" + arr.Count);
                int pass = 0, fail = 0;
                foreach (var t in arr)
                {
                    if (t["enabled"] != null && !(bool)t["enabled"]) continue;
                    string id = (string)t["id"] ?? "?";
                    string template = (string)t["template"] ?? "";
                    string want = (string)t["expected"] ?? "";
                    try
                    {
                        GameObject subj = GameObjectFactory.Factory.CreateObject((string)t["subject"] ?? "Snapjaw");
                        GameObject obj = GameObjectFactory.Factory.CreateObject((string)t["object"] ?? "Snapjaw");
                        string got = GameText.VariableReplace(template, subj, obj);
                        bool ok = string.Equals(got, want, StringComparison.Ordinal);
                        if (ok) pass++; else fail++;
                        UnityEngine.Debug.Log("[QudDE] curator-test " + id + " " + (ok ? "PASS" : "FAIL")
                            + (ok ? "" : " got=\"" + got + "\" want=\"" + want + "\""));
                    }
                    catch (Exception e)
                    {
                        fail++;
                        UnityEngine.Debug.Log("[QudDE] curator-test " + id + " ERROR " + e.Message);
                    }
                }
                UnityEngine.Debug.Log("[QudDE] curator-tests summary: " + pass + " passed, " + fail + " failed");
            }
            catch (Exception ex)
            {
                UnityEngine.Debug.LogWarning("[QudDE] curator-tests load failed: " + ex.Message);
            }
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

        // ---- Demonstrativ: "=subject.this=" -> dieser/diese/dieses (statt englisch this/these) ----
        // Das Original (IndicativeProximal) liest das Pronomen-Set; Deutsch braucht Genus des
        // NOMENS + Kasus (:akk/:dat/:gen wie bei its). Spieler (du) -> Personalpronomen.
        private static string Demonstrative(Gender g, Case c)
        {
            switch (g)
            {
                case Gender.Masc: return c == Case.Acc ? "diesen" : c == Case.Dat ? "diesem" : c == Case.Gen ? "dieses" : "dieser";
                case Gender.Fem: return (c == Case.Dat || c == Case.Gen) ? "dieser" : "diese";
                case Gender.Neut: return c == Case.Dat ? "diesem" : "dieses";
                default: return c == Case.Dat ? "diesen" : c == Case.Gen ? "dieser" : "diese";
            }
        }

        [VariableReplacer(new string[] { "this", "indicativeProximal" }, Override = true, Capitalization = true)]
        [VariableExample("dieses:Dieses", "Croc")]
        [VariableExample("diese:Diese", "Goat")]
        [VariableExample("dieser:Dieser", "Glowfish")]
        public static string DemonstrativeDe(VariableContext Context, GameObject Object)
        {
            if (Object.IsPlayer() && Grammar.AllowSecondPerson)
                return Cap(PlayerPronoun(CaseParam(Context)), Context.Capitalize);
            Gender g = IsPlural(Object) ? Gender.Plural : GuessGender(GermanName(Object));
            return Cap(Demonstrative(g, CaseParam(Context)), Context.Capitalize);
        }

        // "=object.that=" / indicativeDistal: das Original liefert englisch "that/those" aus dem
        // Pronomen-Set. Deutsch unterscheidet nah/fern im Alltag nicht ("jener" klingt gestelzt)
        // -> dieselbe Form wie this: dieser/diese/dieses, Kasus per :akk/:dat/:gen.
        [VariableReplacer(new string[] { "that", "indicativeDistal" }, Override = true, Capitalization = true)]
        [VariableExample("dieses:Dieses", "Croc")]
        public static string DistalDemonstrativeDe(VariableContext Context, GameObject Object)
        {
            return DemonstrativeDe(Context, Object);
        }

        // ---- Objektpronomen mit Kasus: "von =subject.them:dat=" -> "von ihm" ----
        // Ohne Parameter bleibt es beim Akkusativ aus dem Pronomen-Set (Genders.de.xml /
        // PronounSets.de.xml: ihn/sie/es/dich). :dat bildet den Dativ aus dieser Akkusativform
        // (ihn/es -> ihm, sie -> ihr bzw. Plural ihnen, dich -> dir); unbekannte Formen
        // (Neopronomen em/hir/xem/zir) bleiben unverändert.
        internal static string DativeFromAccusative(string acc, bool plural)
        {
            switch ((acc ?? "").ToLowerInvariant())
            {
                case "ihn": case "es": return "ihm";
                case "sie": return plural ? "ihnen" : "ihr";
                case "dich": return "dir";
                case "mich": return "mir";
                default: return acc; // euch/uns gleichlautend, Neopronomen unverändert
            }
        }

        [VariableReplacer(new string[] { "objective", "them" }, Override = true, Capitalization = true)]
        public static string ObjectiveDe(VariableContext Context, GameObject Object)
        {
            Case c = CaseParam(Context);
            if (Object.IsPlayer() && Grammar.AllowSecondPerson && c != Case.Nom)
                return Cap(PlayerPronoun(c), Context.Capitalize);
            string acc = Object.GetPronounProvider().Objective;
            string s = c == Case.Dat ? DativeFromAccusative(acc, IsPlural(Object)) : acc;
            return Cap(s, Context.Capitalize);
        }

        // ---- Deutscher Plural (pluralize/plural): ersetzt Grammar.Pluralize (englische Regeln) ----
        // Quelle 1: COQDE/PluralLexicon.tsv (Singular<TAB>Plural; Komposita erben vom längsten
        // bekannten Grundwort wie beim Genus). Quelle 2: konservative Endungsregeln. Nur das
        // Kopfwort wird gebeugt; führende Adjektive bekommen die starke Plural-Endung -e, wenn
        // das sichere Adjektiv+Kopf-Muster vorliegt. Farbcodes bleiben (SplitColor).
        private static readonly Dictionary<string, string> Plurals = new Dictionary<string, string>(StringComparer.Ordinal);

        internal static void LoadPlurals()
        {
            try
            {
                foreach (var mod in ModManager.Mods)
                {
                    string p = Path.Combine(mod.Path, "languages", "lang-de", "COQDE", "PluralLexicon.tsv");
                    if (!File.Exists(p)) continue;
                    int n = 0;
                    foreach (var raw in File.ReadAllLines(p))
                    {
                        string line = raw.Trim();
                        if (line.Length == 0 || line[0] == '#') continue;
                        var parts = raw.Split('\t');
                        if (parts.Length < 2) continue;
                        string sg = parts[0].Trim().ToLowerInvariant(), pl = parts[1].Trim().ToLowerInvariant();
                        if (sg.Length == 0 || pl.Length == 0) continue;
                        Plurals[sg] = pl;
                        n++;
                    }
                    UnityEngine.Debug.Log("[QudDE] plural lexicon: " + n + " entries");
                    return;
                }
            }
            catch (Exception ex) { UnityEngine.Debug.LogWarning("[QudDE] plural lexicon load failed: " + ex.Message); }
        }

        // Plural EINES Wortes (Kopfnomen), Groß-/Kleinschreibung des Originals bleibt.
        internal static string PluralWord(string word)
        {
            if (string.IsNullOrEmpty(word)) return word;
            string w = word.ToLowerInvariant();
            if (Plurals.TryGetValue(w, out var exact)) return KeepCase(word, exact);
            // Kompositum: längstes bekanntes Grundwort (>= 3 Zeichen) am Wortende
            string bestKey = null;
            foreach (var k in Plurals.Keys)
                if (k.Length >= 3 && k.Length < w.Length && w.EndsWith(k, StringComparison.Ordinal)
                    && (bestKey == null || k.Length > bestKey.Length))
                    bestKey = k;
            if (bestKey != null)
                return word.Substring(0, word.Length - bestKey.Length) + Plurals[bestKey];
            if (w.EndsWith("chen") || w.EndsWith("lein") || w.EndsWith("er") || w.EndsWith("el") || w.EndsWith("en"))
                return word;
            if (w.EndsWith("ung") || w.EndsWith("heit") || w.EndsWith("keit") || w.EndsWith("schaft")
                || w.EndsWith("ion") || w.EndsWith("tät") || w.EndsWith("ik")) return word + "en";
            if (w.EndsWith("in")) return word + "nen";
            if (w.EndsWith("um")) return word.Substring(0, word.Length - 2) + "en";
            if (w.EndsWith("e")) return word + "n";
            char last = w[w.Length - 1];
            if ("aiouy".IndexOf(last) >= 0) return word + "s";
            Gender g = GuessGender(word);
            return word + (g == Gender.Fem ? "en" : "e");
        }

        private static string KeepCase(string original, string lower)
        {
            if (original.Length > 0 && char.IsUpper(original[0]) && lower.Length > 0)
                return char.ToUpperInvariant(lower[0]) + lower.Substring(1);
            return lower;
        }

        // Plural eines Namens/einer Phrase ("rostiger Wischmopp" -> "rostige Wischmoppe").
        internal static string GermanPlural(string name)
        {
            if (string.IsNullOrEmpty(name)) return name;
            string[] words = name.Split(new[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            if (words.Length == 0) return name;
            int head = words.Length - 1;
            for (int i = 1; i < words.Length; i++)
                if (FunctionWords.Contains(words[i])) { head = i - 1; break; }  // "Phiole mit Wasser"
            SplitColor(words[head], out string pre, out string core, out string post);
            words[head] = pre + PluralWord(core) + post;
            if (head == words.Length - 1 && IsAdjNounPattern(words))
                for (int i = 0; i < head; i++)
                    words[i] = DeclineAdj(words[i], DeclType.Strong, Case.Nom, Gender.Plural);
            return string.Join(" ", words);
        }

        [VariableReplacer(new string[] { "pluralize", "plural" }, Override = true, Capitalization = true)]
        [VariableExample("Krokodile:Krokodile", "Croc")]
        [VariableExample("Ziegen:Ziegen", "Goat")]
        public static string PluralizeDe(VariableContext Context, GameObject Object)
        {
            string n = GermanName(Object, Context);
            return Cap(IsPlural(Object) ? n : GermanPlural(n), Context.Capitalize);
        }

        // "=subject.pluralize:Wort=" / "=subject.pluralize.word:Wort=": das ANGEGEBENE Wort nach
        // der Pluralität des Objekts (deutsches Wort im Template).
        [VariableReplacer(new string[] { "pluralize.word" }, Override = true, Capitalization = true)]
        public static string PluralizeWordDe(VariableContext Context, GameObject Object)
        {
            string what = Context.Parameters != null && Context.Parameters.Count > 0 ? Context.Parameters[0] : "";
            return Cap(IsPlural(Object) ? GermanPlural(what) : what, Context.Capitalize);
        }

        [VariableReplacer(new string[] { "pluralize", "plural", "pluralize.word" }, Override = true, Capitalization = true)]
        public static string PluralizeArgDe(VariableContext Context, GameObject Object, string What)
        {
            return Cap(IsPlural(Object) ? GermanPlural(What) : What, Context.Capitalize);
        }

        // Zahl + Wort: "=amount.pluralize:Dram=" / "=amount.pluralize:Punkt:Punkte=".
        [VariableReplacer(new string[] { "pluralize" }, Override = true)]
        public static string PluralizeNumberDe(VariableContext Context, int Number)
        {
            if (Context.Parameters == null || Context.Parameters.Count == 0) return "";
            if (Number == 1) return Context.Parameters[0];
            return Context.Parameters.Count > 1 ? Context.Parameters[1] : GermanPlural(Context.Parameters[0]);
        }

        [VariableReplacer(new string[] { "pluralize" }, Override = true)]
        public static string PluralizeLongDe(VariableContext Context, long Number)
        {
            if (Context.Parameters == null || Context.Parameters.Count == 0) return "";
            if (Number == 1) return Context.Parameters[0];
            return Context.Parameters.Count > 1 ? Context.Parameters[1] : GermanPlural(Context.Parameters[0]);
        }

        [VariablePostProcessor("pluralize", "plural", Override = true)]
        public static string PluralizePost(VariableContext Context)
        {
            return GermanPlural(Context.Value.ToString());
        }

        [VariablePostProcessor("pluralize", "plural", Override = true)]
        public static string PluralizePostNumber(VariableContext Context, int Number)
        {
            string v = Context.Value.ToString();
            return Number == 1 ? v : GermanPlural(v);
        }

        [VariablePostProcessor("pluralize", "plural", Override = true)]
        public static string PluralizePostObject(VariableContext Context, GameObject Object)
        {
            string v = Context.Value.ToString();
            return Object.GetPlurality(Context.HasParameter("asIfKnown")) ? GermanPlural(v) : v;
        }

        // ---- Körperteile mit Kasus/Possessiv: "=part.dativ=" -> "der rechten Hand",
        // "=part.poss:dat=" -> "deiner rechten Hand" (Besitzer = Träger des Körpers). Ersetzt
        // Muster wie "an Eurem =part.ordinalName=", deren Endung das Genus nicht kennt.
        private static string PartName(XRL.World.Anatomy.BodyPart Part)
        {
            return TransformBodyPart(Part.GetOrdinalName(), Part.Laterality, false);
        }

        private static string PartCase(VariableContext Context, XRL.World.Anatomy.BodyPart Part, Case c)
        {
            return BuildDefinitePhrase(PartName(Part), c, Part.Plural, Context.Capitalize);
        }

        [VariableReplacer(new string[] { "nominativ" }, Capitalization = true)]
        public static string PartNominativ(VariableContext Context, XRL.World.Anatomy.BodyPart Part)
        { return PartCase(Context, Part, Case.Nom); }

        [VariableReplacer(new string[] { "akkusativ" }, Capitalization = true)]
        public static string PartAkkusativ(VariableContext Context, XRL.World.Anatomy.BodyPart Part)
        { return PartCase(Context, Part, Case.Acc); }

        [VariableReplacer(new string[] { "dativ" }, Capitalization = true)]
        public static string PartDativ(VariableContext Context, XRL.World.Anatomy.BodyPart Part)
        { return PartCase(Context, Part, Case.Dat); }

        [VariableReplacer(new string[] { "genitiv" }, Capitalization = true)]
        public static string PartGenitiv(VariableContext Context, XRL.World.Anatomy.BodyPart Part)
        { return PartCase(Context, Part, Case.Gen); }

        [VariableReplacer(new string[] { "poss" }, Capitalization = true)]
        public static string PartPossessive(VariableContext Context, XRL.World.Anatomy.BodyPart Part)
        {
            GameObject owner = Part.ParentBody?.ParentObject;
            string stem = owner != null ? PossStem(owner) : "sein";
            return BuildPossessivePhrase(PartName(Part), CaseParam(Context), Part.Plural, Context.Capitalize, stem);
        }

        [VariableReplacer(new string[] { "pluralize", "plural" }, Override = true, Capitalization = true)]
        public static string PartPluralizeDe(VariableContext Context, XRL.World.Anatomy.BodyPart Part)
        {
            string n = PartName(Part);
            return Cap(Part.Plural ? n : GermanPlural(n), Context.Capitalize);
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
                return Cap(PlayerPronoun(CaseOf(Context)), Context.Capitalize);
            // Plurals and proper names get the bare name (no indefinite article).
            if (IsPlural(Object) || IsProper(Object)) return name;
            var art = Indefinite(GuessGender(name), CaseOf(Context));
            if (art.Length == 0) return name;
            return Cap(art, Context.Capitalize) + " " + name;
        }
    }
}
