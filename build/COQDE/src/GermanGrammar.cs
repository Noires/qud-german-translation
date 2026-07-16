using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace COQDE
{
    // Per-capture shape operators used inside Patterns.json replacements: {group:shape}.
    //
    // Article shapes carry CASE; definiteness is inferred from the English article that the
    // captured fragment carried, because Caves of Qud builds "the X" / "a X" in code
    // (GameObject.The / .A). This gives a reliable signal:
    //   * leading "the"  -> German definite article (der/die/das ...) in the requested case
    //   * leading "a/an" -> German indefinite article (ein/eine ...) in the requested case
    //   * no article     -> proper noun (Qud never prefixes "the" to proper names) or the
    //                       player pronoun -> emit bare, no article ("Warden Ualraig", "Ihr")
    //
    // Supported shapes:
    //   nom | acc | dat | gen         article (case) + name; alias subject=nom, object=acc
    //   name                          bare cleaned name, never an article
    //   v-<infinitive>                conjugate a German verb to agree with this subject
    //                                 (player pronoun -> 2nd person "Ihr"; else 3rd singular)
    public static class GermanGrammar
    {
        public enum Person { S3, P2, P3 } // 3rd sg, 2nd pl / "Ihr", 3rd pl

        public sealed class VerbForms
        {
            public string En;    // English base form the game's GetVerb receives (are/have/wade)
            public string Inf;   // German infinitive (sterben)
            public string S3;    // 3rd person singular (er/sie/es stirbt)
            public string P2;    // 2nd person plural / formal "Ihr" (ihr sterbt)
            public string P3;    // 3rd person plural (sie sterben)

            public string Form(Person p)
            {
                switch (p)
                {
                    case Person.P2: return P2 ?? Inf;
                    case Person.P3: return P3 ?? Inf;
                    default: return S3 ?? Inf;
                }
            }
        }

        private static readonly Dictionary<string, VerbForms> ByInf =
            new Dictionary<string, VerbForms>(System.StringComparer.OrdinalIgnoreCase);
        private static readonly Dictionary<string, VerbForms> ByEn =
            new Dictionary<string, VerbForms>(System.StringComparer.OrdinalIgnoreCase);

        public static void LoadVerbs(IEnumerable<VerbForms> verbs)
        {
            ByInf.Clear(); ByEn.Clear();
            if (verbs == null) return;
            foreach (var v in verbs)
            {
                if (v == null) continue;
                if (!string.IsNullOrEmpty(v.Inf)) ByInf[v.Inf] = v;
                if (!string.IsNullOrEmpty(v.En)) ByEn[v.En] = v;
            }
        }

        // For the GameObject.GetVerb postfix: map the verb the game passes to its German form for
        // the subject's person. The input is usually an English base form ("wade", "have"), but
        // some templates pass a German infinitive that the data layer already translated (e.g.
        // DefaultVerb "harvest" -> "ernten"), so we look up both the English key and the German
        // infinitive. Returns null if we have no mapping (caller keeps the game's output).
        public static string ConjugateEnglish(string verb, Person p)
        {
            if (string.IsNullOrEmpty(verb)) return null;
            string key = verb.Trim();
            if (ByEn.TryGetValue(key, out var v)) return v.Form(p);
            if (ByInf.TryGetValue(key, out var w)) return w.Form(p);
            return null;
        }

        private static readonly Regex LeadingArticle =
            new Regex(@"^(?<art>the|an|a)\b[ \t]*", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

        public static bool IsSupportedShape(string shape)
        {
            if (string.IsNullOrEmpty(shape)) return false;
            switch (shape)
            {
                case "nom": case "acc": case "dat": case "gen":
                case "subject": case "object": case "name":
                case "def": case "possgen": case "euer":
                case "possnom": case "possacc": case "possdat":
                case "strongnom": case "strongacc": case "strongdat":
                    return true;
            }
            return shape.StartsWith("v-", System.StringComparison.Ordinal) && shape.Length > 2;
        }

        public static string Apply(string fragment, string shape)
        {
            string clean = GermanGender.VisibleText(fragment ?? "");
            if (clean.Length == 0) return clean;

            bool player = IsPlayerPronoun(clean);

            if (shape.StartsWith("v-", System.StringComparison.Ordinal))
                return Conjugate(shape.Substring(2), player);

            // def/euer/possgen: forced determiner (possessive phrases carry no English article).
            if (shape == "def")
                return BuildPhrase(StripArticle(clean), GCase.Nom, DetKind.Def, null, true);
            if (shape == "euer")
                return BuildPhrase(StripArticle(clean), GCase.Nom, DetKind.Poss, "euer", true);
            if (shape == "possgen")
                return PossGen(StripArticle(clean));

            // Determiner-less shapes: inflect attributive adjectives with strong declension
            // (no article), e.g. a liquid name "brackig Schleim" -> "brackiger Schleim".
            if (shape == "strongnom" || shape == "strongacc" || shape == "strongdat")
            {
                GCase sc = shape == "strongacc" ? GCase.Acc : shape == "strongdat" ? GCase.Dat : GCase.Nom;
                return BuildPhrase(clean, sc, DetKind.None, null, false);
            }

            // Weapon/item possessive shapes: determiner comes from a leading English word
            // (your/its/his/her/their/a/the); case from the shape.
            if (shape == "possnom" || shape == "possacc" || shape == "possdat")
            {
                GCase pc = shape == "possacc" ? GCase.Acc : shape == "possdat" ? GCase.Dat : GCase.Nom;
                return PossItem(clean, pc);
            }

            GCase c = CaseOf(shape);

            // Player pronoun: Ihr (nom) / Euch (acc, dat, gen).
            if (player)
                return (c == GCase.Nom) ? "Ihr" : "Euch";

            var m = LeadingArticle.Match(clean);
            if (!m.Success)
                return clean; // no English article -> proper noun; emit bare

            bool definite = string.Equals(m.Groups["art"].Value, "the", System.StringComparison.OrdinalIgnoreCase);
            bool capitalize = char.IsUpper(clean[0]);
            string name = clean.Substring(m.Length).Trim();
            if (name.Length == 0) name = clean;
            return BuildPhrase(name, c, definite ? DetKind.Def : DetKind.Indef, null, capitalize);
        }

        private static string StripArticle(string clean)
        {
            var m = LeadingArticle.Match(clean);
            string name = m.Success ? clean.Substring(m.Length).Trim() : clean;
            return name.Length == 0 ? clean : name;
        }

        // Genitive owner ("des Schnappkiefers" / "der Ziege"), with masc/neut -s on the head noun.
        private static string PossGen(string name)
        {
            var words = name.Split(new[] { ' ' }, System.StringSplitOptions.RemoveEmptyEntries);
            if (words.Length == 0) return name;
            Gender g = GermanGender.Guess(words[words.Length - 1]);
            if (g == Gender.Masc || g == Gender.Neut)
            {
                string h = words[words.Length - 1];
                char last = h.Length > 0 ? char.ToLowerInvariant(h[h.Length - 1]) : ' ';
                if (last != 's' && last != 'ß' && last != 'x' && last != 'z') words[words.Length - 1] = h + "s";
            }
            return BuildPhraseWords(words, GCase.Gen, DetKind.Def, null, false);
        }

        // Item possessive: the leading determiner may be English (your/its/his/her/their/a/an/the)
        // OR an already-(partly)-translated German possessive (sein.../ihr.../eu(e)r.../mein.../
        // dein.../unser...) — the pronoun layer often converts "its"->"sein" etc. before we see
        // the line. Normalize either to a German possessive/article and inflect for case+gender.
        private static readonly System.Text.RegularExpressions.Regex PossDet =
            new System.Text.RegularExpressions.Regex(
                @"^(?<d>seiner|seines|seinem|seinen|seine|sein|ihrer|ihres|ihrem|ihren|ihre|ihr|eurem|euren|eurer|eures|eure|euer|meinem|meinen|meiner|meines|meine|mein|deinem|deinen|deiner|deines|deine|dein|unserem|unseren|unsere|unser|your|its|his|her|their|an|a|the)\b[ \t]*",
                System.Text.RegularExpressions.RegexOptions.IgnoreCase | System.Text.RegularExpressions.RegexOptions.CultureInvariant);

        private static string PossItem(string clean, GCase c)
        {
            var m = PossDet.Match(clean);
            DetKind kind = DetKind.None; string possStem = null; bool cap = false;
            if (m.Success)
            {
                string d = m.Groups["d"].Value.ToLowerInvariant();
                if (d == "the") kind = DetKind.Def;
                else if (d == "a" || d == "an") kind = DetKind.Indef;
                else
                {
                    kind = DetKind.Poss;
                    if (d == "your" || d.StartsWith("eu")) { possStem = "euer"; cap = true; } // formal politeness
                    else if (d == "its" || d == "his" || d.StartsWith("sein")) possStem = "sein";
                    else if (d == "her" || d == "their" || d.StartsWith("ihr")) possStem = "ihr";
                    else if (d.StartsWith("mein")) possStem = "mein";
                    else if (d.StartsWith("dein")) possStem = "dein";
                    else if (d.StartsWith("unser")) possStem = "unser";
                    else possStem = "sein";
                }
            }
            string name = m.Success ? clean.Substring(m.Length).Trim() : clean;
            if (name.Length == 0) name = clean;
            return BuildPhrase(name, c, kind, possStem, cap);
        }

        private enum DetKind { Def, Indef, Poss, None }
        private enum DeclType { Weak, Mixed, Strong }

        private static string BuildPhrase(string name, GCase c, DetKind kind, string possStem, bool capitalize)
        {
            var words = name.Split(new[] { ' ' }, System.StringSplitOptions.RemoveEmptyEntries);
            return words.Length == 0 ? name : BuildPhraseWords(words, c, kind, possStem, capitalize);
        }

        // words = [adjectives..., head]. Emits determiner + inflected adjectives + head.
        private static string BuildPhraseWords(string[] words, GCase c, DetKind kind, string possStem, bool capitalize)
        {
            string head = words[words.Length - 1];
            Gender g = GermanGender.Guess(head);

            string det; DeclType decl;
            switch (kind)
            {
                case DetKind.Def: det = GermanGender.Definite(g, c); decl = DeclType.Weak; break;
                case DetKind.Poss: det = PossWord(possStem, c, g); decl = DeclType.Mixed; break;
                case DetKind.Indef:
                    if (g == Gender.Plural) { det = null; decl = DeclType.Strong; } // no indefinite plural article
                    else { det = "ein" + EinEnding(c, g); decl = DeclType.Mixed; }
                    break;
                default: det = null; decl = DeclType.Strong; break;
            }

            var parts = new List<string>();
            if (det != null) parts.Add(capitalize ? Cap(det) : det);
            for (int i = 0; i < words.Length - 1; i++)
                parts.Add(AdjStem(words[i]) + AdjEnding(decl, c, g));
            parts.Add(head);
            if (det == null && capitalize && parts.Count > 0) parts[0] = Cap(parts[0]);
            return string.Join(" ", parts);
        }

        private static string Cap(string s) => string.IsNullOrEmpty(s) ? s : char.ToUpperInvariant(s[0]) + s.Substring(1);

        // ein-word (ein/kein/possessive) ending by case/gender.
        private static string EinEnding(GCase c, Gender g)
        {
            switch (c)
            {
                case GCase.Acc: return g == Gender.Masc ? "en" : g == Gender.Fem ? "e" : g == Gender.Plural ? "e" : "";
                case GCase.Dat: return g == Gender.Fem ? "er" : g == Gender.Plural ? "en" : "em";
                case GCase.Gen: return g == Gender.Fem || g == Gender.Plural ? "er" : "es";
                default: return g == Gender.Fem ? "e" : g == Gender.Plural ? "e" : ""; // Nom
            }
        }

        private static string PossWord(string stem, GCase c, Gender g)
        {
            string end = EinEnding(c, g);
            if (string.Equals(stem, "euer", System.StringComparison.OrdinalIgnoreCase))
                return end.Length == 0 ? "euer" : "eur" + end;
            return stem + end;
        }

        // Attributive adjective ending by declension type / case / gender.
        private static string AdjEnding(DeclType t, GCase c, Gender g)
        {
            if (t == DeclType.Weak)
            {
                if (c == GCase.Nom) return g == Gender.Plural ? "en" : "e";
                if (c == GCase.Acc) return (g == Gender.Masc || g == Gender.Plural) ? "en" : (g == Gender.Fem || g == Gender.Neut) ? "e" : "en";
                return "en"; // dat/gen
            }
            if (t == DeclType.Mixed)
            {
                if (c == GCase.Nom) return g == Gender.Masc ? "er" : g == Gender.Fem ? "e" : g == Gender.Neut ? "es" : "en";
                if (c == GCase.Acc) return g == Gender.Masc ? "en" : g == Gender.Fem ? "e" : g == Gender.Neut ? "es" : "en";
                return "en"; // dat/gen
            }
            // Strong (no determiner)
            switch (c)
            {
                case GCase.Nom: return g == Gender.Masc ? "er" : g == Gender.Fem ? "e" : g == Gender.Neut ? "es" : "e";
                case GCase.Acc: return g == Gender.Masc ? "en" : g == Gender.Fem ? "e" : g == Gender.Neut ? "es" : "e";
                case GCase.Dat: return g == Gender.Fem ? "er" : g == Gender.Plural ? "en" : "em";
                default: return g == Gender.Fem || g == Gender.Plural ? "er" : "en"; // Gen
            }
        }

        // Reduce a possibly-already-inflected adjective to its stem (verrostete->verrostet,
        // Klebriger->klebrig, eiserne->eisern, blutig->blutig).
        private static string AdjStem(string word)
        {
            string w = GermanGender.VisibleText(word).ToLowerInvariant();
            foreach (var suf in new[] { "em", "en", "er", "es", "e" })
                if (w.Length - suf.Length >= 3 && w.EndsWith(suf, System.StringComparison.Ordinal))
                    return w.Substring(0, w.Length - suf.Length);
            return w;
        }

        // Build the German laterality adjective(s) for a Laterality bit-flag code, inflected
        // (strong nominative, no article) to agree with the base noun's gender:
        //   masc -er, fem -e, neut -es, plural -e  (e.g. rechter Arm / rechte Hand / rechtes Bein).
        // Flag values mirror XRL.World.Capabilities.Laterality.
        public static string LateralityAdjectives(int code, Gender g)
        {
            string e = (g == Gender.Fem || g == Gender.Plural) ? "e" : (g == Gender.Neut ? "es" : "er");
            var parts = new List<string>();
            void Add(int flag, string stem) { if ((code & flag) != 0) parts.Add(stem + e); }
            Add(4, "ober");     // UPPER
            Add(8, "unter");    // LOWER
            Add(16, "vorder");  // FORE
            Add(32, "mittler"); // MID
            Add(64, "hinter");  // HIND
            Add(512, "inner");  // INNER
            Add(1024, "äußer"); // OUTER
            Add(128, "inner");  // INSIDE
            Add(256, "äußer");  // OUTSIDE
            Add(1, "link");     // LEFT   (closest to the noun)
            Add(2, "recht");    // RIGHT
            return string.Join(" ", parts);
        }

        private static GCase CaseOf(string shape)
        {
            switch (shape)
            {
                case "acc": case "object": return GCase.Acc;
                case "dat": return GCase.Dat;
                case "gen": return GCase.Gen;
                default: return GCase.Nom; // nom, subject, name
            }
        }

        private static bool IsPlayerPronoun(string clean)
        {
            return clean == "you" || clean == "You" || clean == "Ihr" || clean == "Euch"
                || clean.Equals("yourself", System.StringComparison.OrdinalIgnoreCase);
        }

        private static string Conjugate(string inf, bool player)
        {
            if (ByInf.TryGetValue(inf, out var v))
                return player ? (v.P2 ?? v.Inf) : (v.S3 ?? v.Inf);
            // Fallback (weak verb, no vowel change) so a missing entry is legible, not blank.
            string stem = inf.EndsWith("en") ? inf.Substring(0, inf.Length - 2)
                        : inf.EndsWith("n") ? inf.Substring(0, inf.Length - 1) : inf;
            return player ? stem + "t" : stem + "t";
        }
    }
}
