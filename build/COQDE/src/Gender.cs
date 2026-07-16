using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;

namespace COQDE
{
    // German grammatical gender + article resolution.
    //
    // This is the SINGLE canonical home of the gender heuristic, the curated override
    // table, and the der/die/das + ein/eine article tables. Both the runtime message
    // post-processor (this DLL) and the token VariableReplacers use this logic; see
    // docs/RUNTIME_POSTPROCESSOR_PLAN.md §5b.
    public enum Gender { Masc, Fem, Neut, Plural }

    public enum GCase { Nom, Acc, Dat, Gen }

    public static class GermanGender
    {
        // Curated gender overrides for common game nouns (head-noun form, lowercase, both
        // umlaut and folded spellings). Grows over time; this is the one place to add a noun.
        public static readonly Dictionary<string, Gender> Overrides = new Dictionary<string, Gender>
        {
            // creatures / bodies
            {"bär", Gender.Masc}, {"baer", Gender.Masc}, {"spinne", Gender.Fem}, {"käfer", Gender.Masc}, {"kaefer", Gender.Masc},
            {"amöbe", Gender.Fem}, {"amoebe", Gender.Fem}, {"schwein", Gender.Neut}, {"hund", Gender.Masc}, {"katze", Gender.Fem},
            {"schlange", Gender.Fem}, {"ratte", Gender.Fem}, {"fledermaus", Gender.Fem}, {"vogel", Gender.Masc}, {"fisch", Gender.Masc},
            {"leiche", Gender.Fem}, {"kadaver", Gender.Masc}, {"pilz", Gender.Masc}, {"pflanze", Gender.Fem}, {"schnecke", Gender.Fem},
            {"affe", Gender.Masc}, {"pavian", Gender.Masc}, {"wurm", Gender.Masc}, {"biene", Gender.Fem}, {"skorpion", Gender.Masc},
            {"schnappkiefer", Gender.Masc}, {"kiefer", Gender.Masc}, {"ziege", Gender.Fem}, {"molch", Gender.Masc}, {"kröte", Gender.Fem},
            {"kroete", Gender.Fem}, {"echse", Gender.Fem}, {"quall", Gender.Fem}, {"qualle", Gender.Fem}, {"nachtschatten", Gender.Masc},
            {"brut", Gender.Fem}, {"made", Gender.Fem}, {"larve", Gender.Fem}, {"krebs", Gender.Masc}, {"ratz", Gender.Masc},
            // masculine weak nouns ending -e (exceptions to the "-e => feminine" heuristic)
            {"schütze", Gender.Masc}, {"schuetze", Gender.Masc}, {"riese", Gender.Masc}, {"bote", Gender.Masc},
            {"kunde", Gender.Masc}, {"junge", Gender.Masc}, {"hase", Gender.Masc}, {"rabe", Gender.Masc},
            {"zeuge", Gender.Masc}, {"erbe", Gender.Masc}, {"insasse", Gender.Masc}, {"nachkomme", Gender.Masc},
            {"sklave", Gender.Masc}, {"jäger", Gender.Masc}, {"gefährte", Gender.Masc}, {"pilger", Gender.Masc},
            // more Qud creatures (neuter / irregular that the ending heuristic gets wrong)
            {"krokodil", Gender.Neut}, {"tausendfüßer", Gender.Masc}, {"tausendfuesser", Gender.Masc},
            {"reptil", Gender.Neut}, {"insekt", Gender.Neut}, {"gleiter", Gender.Masc}, {"raider", Gender.Masc},
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
            {"keule", Gender.Fem}, {"messer", Gender.Neut}, {"beil", Gender.Neut}, {"pfeil", Gender.Masc}, {"bogen", Gender.Masc},
        };

        // Merge the shared gender lexicon (GenderLexicon.tsv) into the override table so the
        // token replacer and this DLL agree on gender from one data source. File entries win.
        public static int LoadLexicon(string path)
        {
            if (!File.Exists(path)) return 0;
            int n = 0;
            foreach (var raw in File.ReadAllLines(path))
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
            _suffixes = null; // rebuild compound-suffix list to include lexicon nouns
            return n;
        }

        private static readonly Regex ShaderTag = new Regex(@"\{\{[^{}|]+\|([^{}]*)\}\}", RegexOptions.CultureInvariant);
        private static readonly Regex WordRegex = new Regex(@"[A-Za-zÄÖÜäöüß-]+", RegexOptions.CultureInvariant);

        // Strip Qud color/shader markup so we operate on the visible German text.
        //   {{y|text}} -> text ;  &Y and ^r foreground/background codes -> removed
        public static string VisibleText(string value)
        {
            if (string.IsNullOrEmpty(value)) return value;
            string result = value;
            while (true)
            {
                string next = ShaderTag.Replace(result, "$1");
                if (next == result) break;
                result = next;
            }
            result = Regex.Replace(result, @"&.", "");
            result = Regex.Replace(result, @"\^.", "");
            return result.Trim();
        }

        // Last alphabetic word is the head noun; compounds inherit the head's gender.
        public static string HeadNoun(string name)
        {
            var words = WordRegex.Matches(VisibleText(name));
            if (words.Count == 0) return "";
            string last = words[words.Count - 1].Value;
            int dash = last.LastIndexOf('-');
            if (dash >= 0 && dash < last.Length - 1) last = last.Substring(dash + 1);
            return last;
        }

        // Lexicon nouns usable as compound tails, longest first (built lazily). A closed compound
        // like "Metallwand" inherits the gender of its last element ("Wand" = fem).
        private static List<KeyValuePair<string, Gender>> _suffixes;
        private static List<KeyValuePair<string, Gender>> Suffixes()
        {
            if (_suffixes != null) return _suffixes;
            var list = new List<KeyValuePair<string, Gender>>();
            foreach (var kv in Overrides)
                if (kv.Key.Length >= 4) list.Add(kv);
            list.Sort((a, b) => b.Key.Length.CompareTo(a.Key.Length));
            _suffixes = list;
            return list;
        }

        public static Gender Guess(string name)
        {
            string head = HeadNoun(name);
            if (head.Length == 0) return Gender.Neut;
            string h = head.ToLowerInvariant();
            if (Overrides.TryGetValue(h, out var g)) return g;
            // compound: inherit the gender of a known trailing noun (Metallwand -> Wand = fem)
            foreach (var s in Suffixes())
                if (h.Length > s.Key.Length && h.EndsWith(s.Key, System.StringComparison.Ordinal))
                    return s.Value;
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

        public static string Definite(Gender g, GCase c)
        {
            switch (g)
            {
                case Gender.Masc:
                    return c == GCase.Acc ? "den" : c == GCase.Dat ? "dem" : c == GCase.Gen ? "des" : "der";
                case Gender.Fem:
                    return c == GCase.Dat ? "der" : c == GCase.Gen ? "der" : "die";
                case Gender.Neut:
                    return c == GCase.Acc ? "das" : c == GCase.Dat ? "dem" : c == GCase.Gen ? "des" : "das";
                default: // plural
                    return c == GCase.Dat ? "den" : c == GCase.Gen ? "der" : "die";
            }
        }

        public static string Indefinite(Gender g, GCase c)
        {
            switch (g)
            {
                case Gender.Masc:
                    return c == GCase.Acc ? "einen" : c == GCase.Dat ? "einem" : c == GCase.Gen ? "eines" : "ein";
                case Gender.Fem:
                    return c == GCase.Dat ? "einer" : c == GCase.Gen ? "einer" : "eine";
                case Gender.Neut:
                    return c == GCase.Dat ? "einem" : c == GCase.Gen ? "eines" : "ein";
                default:
                    return ""; // no indefinite plural article
            }
        }
    }
}
