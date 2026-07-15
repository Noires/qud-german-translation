using System.Collections.Generic;
using System.Text.RegularExpressions;
using XRL.Language;
using XRL.World;
using XRL.World.Text;
using XRL.World.Text.Attributes;
using XRL.World.Text.Delegates;

namespace LanguagesOfQudGerman
{
    // German grammar replacer (prototype).
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

        // ---- definite article, no name ("=the=") ----
        [VariableReplacer(new string[] { "the" }, Default = "der ", Capitalization = true)]
        public static string DefiniteArticle(VariableContext Context, GameObject Object)
        {
            if (Object.IsPlayer() && Grammar.AllowSecondPerson) return "";
            var art = Definite(GuessGender(GermanName(Object)), CaseOf(Context));
            return Cap(art, Context.Capitalize) + " ";
        }

        // ---- definite article + name ("=the.name=", "=t=", "=subject.t=", "=object.t=") ----
        [VariableReplacer(new string[] { "the.name", "t", "formattedName" }, Capitalization = true)]
        public static string DefiniteName(VariableContext Context, GameObject Object)
        {
            string name = GermanName(Object);
            if (Object.IsPlayer() && Grammar.AllowSecondPerson)
                return Context.Capitalize ? "Ihr" : "Ihr";
            var art = Definite(GuessGender(name), CaseOf(Context));
            return Cap(art, Context.Capitalize) + " " + name;
        }

        // ---- indefinite article, no name ("=a=") ----
        [VariableReplacer(new string[] { "a" }, Default = "ein ", Capitalization = true)]
        public static string IndefiniteArticle(VariableContext Context, GameObject Object)
        {
            var art = Indefinite(GuessGender(GermanName(Object)), CaseOf(Context));
            if (art.Length == 0) return "";
            return Cap(art, Context.Capitalize) + " ";
        }

        // ---- indefinite article + name ("=a.name=", "=an=") ----
        [VariableReplacer(new string[] { "a.name", "an" }, Default = "ein Ding", Capitalization = true)]
        public static string IndefiniteName(VariableContext Context, GameObject Object)
        {
            string name = GermanName(Object);
            if (Object.IsPlayer() && Grammar.AllowSecondPerson)
                return "Ihr";
            var art = Indefinite(GuessGender(name), CaseOf(Context));
            if (art.Length == 0) return name;
            return Cap(art, Context.Capitalize) + " " + name;
        }
    }
}
