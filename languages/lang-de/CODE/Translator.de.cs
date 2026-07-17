using System.Globalization;
using XRL.Language;

namespace LanguagesOfQudGerman
{
    // German TranslatorBase provider. Registered exactly like the official Turkish reference
    // ([LanguageProvider("tr")] in Translator.tr.cs). Every number token in the game
    // (=cardinal=, =cardinal.no=, =ordinal=, =ordinal.digits=, =multiplicative=,
    // =cardinal.things=, =a.or.cardinal.names=, ...) routes through Translator.Cardinal /
    // Ordinal / OrdinalWithDigits / Multiplicative (see Delegates.Numbers.cs), so this single
    // provider makes all of them German - no replacer overrides needed.
    //
    // Deliberately NOT overridden: ExtractArticle/AddArticle (English-name parsing),
    // MakeAndList/MakeCommaList/MutateZoneName (already localized via their _S/_T string-table
    // entries in Strings.de.xml), GameObjectDisplayName (base behavior + data suffices).
    //
    // Definite/IndefiniteArticle ARE overridden: the TOKEN path goes through our
    // VariableReplacers, but C#-composed message-log lines call GameObject.The/A ->
    // Translator.DefiniteArticle directly ("The Chitinpanzer-Puma hits ..."); we replace only
    // the base implementation's English fallback so property/xtag article overrides keep
    // working (Worlds.de.xml IndefiniteArticle="die" etc.).
    [LanguageProvider("de")]
    public class TranslatorDeutsch : TranslatorBase
    {
        private static CultureInfo _de;
        public override CultureInfo GetCultureInfo() => _de ??= new CultureInfo("de-DE");

        // C#-Pfad-Artikel: nur den englischen Fallback der Basis ersetzen - Property-/xtag-
        // Overrides (DefiniteArticle/IndefiniteArticle-Attribute aus den Daten), Eigennamen-
        // Unterdrückung und Examiner-Rekursion der Basis bleiben unangetastet.
        public override string DefiniteArticle(DefiniteArticleParams Params)
        {
            string a = base.DefiniteArticle(Params);
            if (a == "the " || a == "The ")
                return VariableReplacers.CSharpDefiniteArticle(Params.Object, a[0] == 'T');
            return a;
        }

        public override string IndefiniteArticle(IndefiniteArticleParams Params)
        {
            string a = base.IndefiniteArticle(Params);
            if (a == "a " || a == "an " || a == "A " || a == "An ")
                return VariableReplacers.CSharpIndefiniteArticle(Params.Object, char.IsUpper(a[0]));
            if (a == "some ") return "etwas ";
            if (a == "Some ") return "Etwas ";
            return a;
        }

        private static readonly string[] Einer =
        {
            "null", "eins", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun",
            "zehn", "elf", "zwölf", "dreizehn", "vierzehn", "fünfzehn", "sechzehn", "siebzehn",
            "achtzehn", "neunzehn",
        };

        private static readonly string[] Zehner =
        {
            "", "", "zwanzig", "dreißig", "vierzig", "fünfzig", "sechzig", "siebzig", "achtzig", "neunzig",
        };

        // {Skalenwert, Singular, Plural} - große Skalen sind eigenständige Wörter mit Leerzeichen.
        private static readonly (long Value, string Singular, string Plural)[] Skalen =
        {
            (1_000_000_000_000_000_000L, "Trillion", "Trillionen"),
            (1_000_000_000_000_000L, "Billiarde", "Billiarden"),
            (1_000_000_000_000L, "Billion", "Billionen"),
            (1_000_000_000L, "Milliarde", "Milliarden"),
            (1_000_000L, "Million", "Millionen"),
        };

        // 0-999 als ein zusammengeschriebenes Wort. "eins" wird in Verbindungen zu "ein"
        // (einhundert, einundzwanzig, eintausend); nur als letztes Wort bleibt es "eins".
        private static string Unter1000(long n, bool einAlsPrefix)
        {
            string s = "";
            if (n >= 100)
            {
                long h = n / 100;
                s += (h == 1 ? "ein" : Einer[h]) + "hundert";
                n %= 100;
            }
            if (n == 0) return s;
            if (n == 1) return s + (einAlsPrefix ? "ein" : "eins");
            if (n < 20) return s + Einer[n];
            long e = n % 10;
            if (e == 0) return s + Zehner[n / 10];
            return s + (e == 1 ? "ein" : Einer[e]) + "und" + Zehner[n / 10];
        }

        public override string Cardinal(long num)
        {
            if (num == 0) return "null";
            string s = "";
            if (num < 0) { s = "minus "; num = -num; }
            foreach (var (value, singular, plural) in Skalen)
            {
                if (num < value) continue;
                long c = num / value;
                num %= value;
                s += (c == 1 ? "eine " + singular : Cardinal(c) + " " + plural);
                if (num > 0) s += " ";
            }
            long t = num / 1000;
            long rest = num % 1000;
            if (t > 0) s += Unter1000(t, einAlsPrefix: true) + "tausend";
            if (rest > 0) s += Unter1000(rest, einAlsPrefix: false);
            return s.TrimEnd();
        }

        // 0 Gegenstände -> "keine Gegenstände" (Plural-Kontext ist der Regelfall der Nutzung).
        public override string CardinalNo(long num)
        {
            return num == 0 ? "keine" : Cardinal(num);
        }

        // Grundform ohne Kasus-Endung ("die dritte ..."); der Kasus ist am Token nicht bekannt,
        // die feminine/schwache Grundform auf -e ist die verträglichste Wahl.
        public override string Ordinal(long num)
        {
            if (num == 0) return "nullte";
            string prefix = "";
            if (num < 0) { prefix = "minus "; num = -num; }
            switch (num)
            {
                case 1: return prefix + "erste";
                case 3: return prefix + "dritte";
                case 7: return prefix + "siebte";
                case 8: return prefix + "achte";
            }
            string cardinal = Cardinal(num);
            // Unregelmäßige letzte Komponente: einhunderteins -> einhunderterste usw.
            if (cardinal.EndsWith("eins")) return prefix + cardinal.Substring(0, cardinal.Length - 4) + "erste";
            if (cardinal.EndsWith("drei")) return prefix + cardinal.Substring(0, cardinal.Length - 4) + "dritte";
            if (cardinal.EndsWith("sieben") && !cardinal.EndsWith("siebzehn"))
                return prefix + cardinal.Substring(0, cardinal.Length - 6) + "siebte";
            if (cardinal.EndsWith("acht")) return prefix + cardinal + "e";
            // -te für 2..19 als letzte Komponente, sonst -ste (zwanzigste, hundertste, tausendste).
            long last = num % 100;
            return prefix + cardinal + (last >= 1 && last <= 19 ? "te" : "ste");
        }

        // Deutsche Ordnungszahl in Ziffern: "3." statt "3rd".
        public override string OrdinalWithDigits(long num)
        {
            return num + ".";
        }

        public override string Multiplicative(long num)
        {
            switch (num)
            {
                case 0: return "niemals";
                case 1: return "einmal";
                case 2: return "zweimal";
                case 3: return "dreimal";
                default: return Cardinal(num) + "mal";
            }
        }

        // Load-time self-test, called from GermanReplacerBootstrap. Logs PASS/FAIL to Player.log.
        internal static void SelfTest()
        {
            var t = new TranslatorDeutsch();
            (string got, string want)[] tests =
            {
                (t.Cardinal(0), "null"),
                (t.Cardinal(1), "eins"),
                (t.Cardinal(17), "siebzehn"),
                (t.Cardinal(21), "einundzwanzig"),
                (t.Cardinal(30), "dreißig"),
                (t.Cardinal(101), "einhunderteins"),
                (t.Cardinal(1337), "eintausenddreihundertsiebenunddreißig"),
                (t.Cardinal(2000000), "zwei Millionen"),
                (t.Cardinal(-21), "minus einundzwanzig"),
                (t.CardinalNo(0), "keine"),
                (t.Ordinal(1), "erste"),
                (t.Ordinal(3), "dritte"),
                (t.Ordinal(8), "achte"),
                (t.Ordinal(17), "siebzehnte"),
                (t.Ordinal(21), "einundzwanzigste"),
                (t.Ordinal(103), "einhundertdritte"),
                (t.OrdinalWithDigits(3), "3."),
                (t.Multiplicative(2), "zweimal"),
                (t.Multiplicative(21), "einundzwanzigmal"),
            };
            int pass = 0, fail = 0;
            foreach (var (got, want) in tests)
            {
                bool ok = got == want;
                if (ok) pass++; else fail++;
                if (!ok) UnityEngine.Debug.Log($"[QudDE] zahl-test FAIL: \"{got}\" (erwartet \"{want}\")");
            }
            UnityEngine.Debug.Log($"[QudDE] zahl-test: {pass} passed, {fail} failed");
        }
    }
}
