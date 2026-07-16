using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using Newtonsoft.Json.Linq;

namespace COQDE
{
    // Route-scoped translation engine. Mirrors the proven COQKR pipeline:
    //   1. try the ordered regex patterns for this route; first match wins.
    //      In the replacement, {group:shape} substitutes a captured group after
    //      term-translating it and running the German shape operator (GermanGrammar).
    //   2. no pattern matched -> apply route terms, then common ("*") terms.
    //
    // Data files (Patterns.json, Terms.json, Verbs.json) live next to COQDE.dll.
    public static class RouteTranslator
    {
        public static Action<string, string> Log = delegate { };

        // When true, message lines that matched no pattern are logged (phase "unmatched")
        // so real gameplay reveals the exact frames still to translate.
        public static bool Debug;

        // Whole-string term fallthrough (partial translation of unmatched lines) runs only on
        // these routes. Other routes (Popup, UIText) get pattern rewrites ONLY, so hooking
        // them cannot half-translate arbitrary English UI text.
        private static readonly HashSet<string> FallthroughRoutes =
            new HashSet<string>(StringComparer.Ordinal) { "MessageLog", "BodyPart", "MenuOption" };

        private static readonly TimeSpan PatternTimeout = TimeSpan.FromMilliseconds(100.0);

        private sealed class Entry
        {
            public string Key;
            public string Value;
            public Regex WordRegex;
            public Entry(string key, string value, bool word)
            {
                Key = key; Value = value;
                WordRegex = word ? new Regex(@"(?<![A-Za-z])" + Regex.Escape(key) + @"(?![A-Za-z])", RegexOptions.CultureInvariant) : null;
            }
        }

        private sealed class PatternEntry
        {
            public string Id;
            public Regex Regex;
            public string Replacement;
            public HashSet<string> GroupNames;
            public PatternEntry(string id, Regex regex, string replacement)
            {
                Id = id; Regex = regex; Replacement = replacement;
                GroupNames = new HashSet<string>(regex.GetGroupNames(), StringComparer.Ordinal);
            }
        }

        private sealed class TranslationData
        {
            public readonly Dictionary<string, List<Entry>> RouteTerms = new Dictionary<string, List<Entry>>(StringComparer.Ordinal);
            public readonly List<Entry> CommonTerms = new List<Entry>();
            public readonly Dictionary<string, List<PatternEntry>> Patterns = new Dictionary<string, List<PatternEntry>>(StringComparer.Ordinal);
        }

        private static TranslationData data;
        private static readonly Regex TokenRegex =
            new Regex(@"\{(?<name>[A-Za-z_][A-Za-z0-9_]*|\d+)(?::(?<shape>[A-Za-z0-9_-]+))?\}", RegexOptions.CultureInvariant);

        public static int PatternCount { get; private set; }
        public static int TermCount { get; private set; }
        public static int VerbCount { get; private set; }

        public static void Load(string dataDir)
        {
            var d = new TranslationData();
            LoadTerms(d, Path.Combine(dataDir, "Terms.json"));
            LoadPatterns(d, Path.Combine(dataDir, "Patterns.json"));
            LoadVerbs(Path.Combine(dataDir, "Verbs.json"));
            foreach (var list in d.RouteTerms.Values)
                list.Sort((a, b) => b.Key.Length.CompareTo(a.Key.Length));
            d.CommonTerms.Sort((a, b) => b.Key.Length.CompareTo(a.Key.Length));
            data = d;
        }

        public static string Translate(string route, string source)
        {
            string text = source ?? string.Empty;
            if (text.Length == 0) return text;
            var d = data;
            if (d == null) return text;

            // If the WHOLE line is wrapped in a single Qud color tag ({{color|...}}), our
            // anchored ^...$ patterns can't match. Unwrap, translate the inner text, re-wrap.
            // (Handles the common case: fully-colored status/combat lines like
            // "{{g|The X is dazed.}}". Per-token markup inside a line is handled by the
            // shape operators, which strip markup for gender detection.)
            if (TryUnwrapOuterTag(text, out string color, out string body))
                return "{{" + color + "|" + Translate(route, body) + "}}";

            string result = null;
            if (d.Patterns.TryGetValue(route, out var patterns))
            {
                foreach (var p in patterns)
                {
                    Match m;
                    try { m = p.Regex.Match(text); }
                    catch (RegexMatchTimeoutException) { Log("pattern-timeout", p.Id); continue; }
                    if (m.Success) { result = ApplyReplacement(d, route, p, m); break; }
                }
            }
            if (result == null)
            {
                if (Debug) Log("unmatched", "[" + route + "] " + text);
                if (FallthroughRoutes.Contains(route))
                    result = ApplyEntries(d.CommonTerms, ApplyTerms(d.RouteTerms, route, text));
                else
                    result = text;
            }
            return WalkPastDativeFix(CasePrepFix(result));
        }

        // ---- preposition-aware case correction (Fix B2) ----
        // The article tokens only know Subject->Nom / Object->Acc, so after a dative-governing
        // preposition a masculine/neuter article comes out accusative ("mit den Dolch" instead
        // of "mit dem Dolch"). Here we correct the article's case from the preceding preposition.
        // Only conversions that cannot corrupt already-correct text are applied; the -n forms
        // (den, seinen, ...) are guarded because a dative PLURAL is also "…n" — we skip when the
        // following noun ends in -n (dative plurals almost always do, singulars usually don't).
        private static readonly Regex CasePrepRegex = new Regex(
            @"(?i)\b(?<prep>aus|bei|mit|nach|seit|von|zu)(?<s1>[ \t]+)(?<art>den|das|einen|ein|keinen|kein|seinen|sein|meinen|mein|deinen|dein|euren|euer|unseren|unser)(?<s2>[ \t]+)(?<next>\S+)",
            RegexOptions.CultureInvariant);

        private static readonly Dictionary<string, string> AccToDat = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            {"den","dem"}, {"das","dem"}, {"einen","einem"}, {"ein","einem"}, {"keinen","keinem"}, {"kein","keinem"},
            {"seinen","seinem"}, {"sein","seinem"}, {"meinen","meinem"}, {"mein","meinem"},
            {"deinen","deinem"}, {"dein","deinem"}, {"euren","eurem"}, {"euer","eurem"}, {"unseren","unserem"}, {"unser","unserem"},
        };
        // Forms whose -n could instead be a correct dative-plural marker: skip if next noun ends -n.
        private static readonly HashSet<string> PluralGuarded = new HashSet<string>(StringComparer.Ordinal)
        { "den", "keinen", "seinen", "meinen", "deinen", "euren", "unseren" };

        // "an <span> vorbei" (vorbeigehen an) is reliably dative for every object in the span,
        // including coordinated ones ("an X und Y vorbei"). Convert all indefinite articles in
        // the span to dative (eine->einer, ein/einen->einem), plus the safe definite das->dem.
        private static readonly Regex WalkPastRegex = new Regex(@"\ban (?<span>.+?) vorbei\b", RegexOptions.CultureInvariant);
        private static readonly Regex SpanArticleRegex = new Regex(@"\b(einen|eine|ein|das)\b", RegexOptions.CultureInvariant);

        private static string WalkPastDativeFix(string text)
        {
            if (text.IndexOf("vorbei", StringComparison.Ordinal) < 0) return text;
            return WalkPastRegex.Replace(text, m =>
            {
                string span = SpanArticleRegex.Replace(m.Groups["span"].Value, am =>
                {
                    switch (am.Value)
                    {
                        case "eine": return "einer";
                        case "einen": return "einem";
                        case "ein": return "einem";
                        case "das": return "dem";
                        default: return am.Value;
                    }
                });
                return "an " + span + " vorbei";
            });
        }

        private static string CasePrepFix(string text)
        {
            if (string.IsNullOrEmpty(text) || text.IndexOf(' ') < 0) return text;
            return CasePrepRegex.Replace(text, m =>
            {
                string artLower = m.Groups["art"].Value.ToLowerInvariant();
                if (!AccToDat.TryGetValue(artLower, out string dat)) return m.Value;
                if (PluralGuarded.Contains(artLower) && VisibleEndsWithN(m.Groups["next"].Value))
                    return m.Value; // looks like a correct dative plural -> leave it
                string art = m.Groups["art"].Value;
                if (art.Length > 0 && char.IsUpper(art[0])) dat = char.ToUpperInvariant(dat[0]) + dat.Substring(1);
                return m.Groups["prep"].Value + m.Groups["s1"].Value + dat + m.Groups["s2"].Value + m.Groups["next"].Value;
            });
        }

        private static bool VisibleEndsWithN(string word)
        {
            string v = GermanGender.VisibleText(word).TrimEnd('.', ',', '!', '?', ';', ':', ')', ']', '"');
            return v.Length > 0 && (v[v.Length - 1] == 'n' || v[v.Length - 1] == 'N');
        }

        // True iff `text` is exactly one balanced {{color|...}} tag spanning the whole string.
        // Returns the color name and the inner body. Rejects "{{a|x}} y {{b|z}}" (not a single
        // wrapper) by requiring the opening tag's depth to return to zero only at the end.
        private static bool TryUnwrapOuterTag(string text, out string color, out string body)
        {
            color = null; body = null;
            if (text.Length < 5 || text[0] != '{' || text[1] != '{') return false;
            int bar = -1;
            for (int i = 2; i < text.Length; i++)
            {
                char c = text[i];
                if (c == '|') { bar = i; break; }
                if (c == '{' || c == '}') return false; // no '|' before a brace -> not an open tag
            }
            if (bar < 0) return false;
            if (!(text[text.Length - 2] == '}' && text[text.Length - 1] == '}')) return false;
            string inner = text.Substring(bar + 1, text.Length - 2 - (bar + 1));
            // inner (between '|' and the closing '}}') must be brace-balanced and never dip
            // below zero — otherwise the closing '}}' we found is not this tag's own close.
            int depth = 0;
            for (int i = 0; i + 1 < inner.Length; i++)
            {
                if (inner[i] == '{' && inner[i + 1] == '{') { depth++; i++; }
                else if (inner[i] == '}' && inner[i + 1] == '}') { depth--; i++; if (depth < 0) return false; }
            }
            if (depth != 0) return false;
            color = text.Substring(2, bar - 2);
            body = inner;
            return true;
        }

        private static string ApplyReplacement(TranslationData d, string route, PatternEntry pattern, Match match)
        {
            return TokenRegex.Replace(pattern.Replacement, token =>
            {
                string name = token.Groups["name"].Value;
                string captured = CaptureValue(pattern, match, name);
                if (captured == null) return token.Value;   // undefined group name -> keep literal (typo guard)
                if (captured.Length == 0) return string.Empty; // defined but unmatched optional -> vanish
                string translated = TranslateFragment(d, route, captured);
                var shape = token.Groups["shape"];
                return shape.Success ? GermanGrammar.Apply(translated, shape.Value) : translated;
            });
        }

        private static string CaptureValue(PatternEntry pattern, Match match, string name)
        {
            if (int.TryParse(name, out var idx))
            {
                int n = idx + 1;
                if (n >= match.Groups.Count) return null;
                return match.Groups[n].Value; // "" if the numbered group did not participate
            }
            if (!pattern.GroupNames.Contains(name)) return null; // name not in this regex
            return match.Groups[name].Value; // "" if the named group did not participate
        }

        private static string TranslateFragment(TranslationData d, string route, string fragment)
        {
            string s = ApplyTerms(d.RouteTerms, route, fragment);
            return ApplyEntries(d.CommonTerms, s);
        }

        private static string ApplyTerms(Dictionary<string, List<Entry>> byRoute, string route, string source)
        {
            return byRoute.TryGetValue(route, out var list) ? ApplyEntries(list, source) : source;
        }

        private static string ApplyEntries(List<Entry> entries, string source)
        {
            string text = source;
            foreach (var e in entries)
                text = e.WordRegex == null ? text.Replace(e.Key, e.Value) : e.WordRegex.Replace(text, _ => e.Value);
            return text;
        }

        // ---- loaders ----

        private static List<JObject> ReadArray(string path, string arrayKey)
        {
            JObject root;
            try { root = JObject.Parse(File.ReadAllText(path, new UTF8Encoding(false))); }
            catch (Exception ex) { Log("data-skip", path + ": parse " + ex.GetType().Name); return null; }
            var list = new List<JObject>();
            if (root[arrayKey] is JArray arr)
                foreach (var t in arr)
                    if (t is JObject o) list.Add(o);
            return list;
        }

        private static List<string> StringArray(JToken token)
        {
            var list = new List<string>();
            if (token is JArray arr)
                foreach (var t in arr)
                    if ((string)t != null) list.Add((string)t);
            return list;
        }

        private static void LoadTerms(TranslationData d, string path)
        {
            if (!File.Exists(path)) { Log("data-missing", path); return; }
            var items = ReadArray(path, "terms");
            if (items == null) return;
            int n = 0, skip = 0;
            foreach (var o in items)
            {
                string id = (string)o["id"];
                var routes = StringArray(o["routes"]);
                string key = (string)o["key"];
                string repl = (string)o["replacement"];
                bool word = (bool?)o["word"] == true;
                if (string.IsNullOrEmpty(id) || routes.Count == 0 || string.IsNullOrEmpty(key) || repl == null)
                { skip++; Log("data-skip", path + ": " + (id ?? "(no-id)")); continue; }
                foreach (var r in routes)
                {
                    if (string.IsNullOrEmpty(r)) continue;
                    if (r == "*") { d.CommonTerms.Add(new Entry(key, repl, word)); n++; continue; }
                    if (!d.RouteTerms.TryGetValue(r, out var list)) { list = new List<Entry>(); d.RouteTerms[r] = list; }
                    list.Add(new Entry(key, repl, word)); n++;
                }
            }
            TermCount = n;
            Log("data-load", "Terms.json entries=" + n + " skipped=" + skip);
        }

        private static void LoadPatterns(TranslationData d, string path)
        {
            if (!File.Exists(path)) { Log("data-missing", path); return; }
            var items = ReadArray(path, "patterns");
            if (items == null) return;
            int n = 0, skip = 0;
            foreach (var o in items)
            {
                string id = (string)o["id"];
                var routes = StringArray(o["routes"]);
                string pat = (string)o["pattern"];
                string repl = (string)o["replacement"];
                if (string.IsNullOrEmpty(id) || !id.StartsWith("route-", StringComparison.Ordinal)
                    || routes.Count == 0 || string.IsNullOrEmpty(pat) || string.IsNullOrEmpty(repl))
                { skip++; Log("data-skip", path + ": " + (id ?? "(no-id)")); continue; }
                if (UsesUnsupportedShape(repl)) { skip++; Log("data-skip", path + ": " + id + " unsupported-shape"); continue; }
                Regex rx;
                try { rx = new Regex(pat, RegexOptions.CultureInvariant, PatternTimeout); }
                catch (Exception ex) { skip++; Log("data-skip", path + ": " + id + " " + ex.GetType().Name); continue; }
                var entry = new PatternEntry(id, rx, repl);
                foreach (var r in routes)
                {
                    if (string.IsNullOrEmpty(r)) continue;
                    if (!d.Patterns.TryGetValue(r, out var list)) { list = new List<PatternEntry>(); d.Patterns[r] = list; }
                    list.Add(entry); n++;
                }
            }
            PatternCount = n;
            Log("data-load", "Patterns.json entries=" + n + " skipped=" + skip);
        }

        private static bool UsesUnsupportedShape(string replacement)
        {
            foreach (Match m in Regex.Matches(replacement, @"\{(?:[A-Za-z_][A-Za-z0-9_]*|\d+):(?<shape>[A-Za-z0-9_-]+)\}"))
                if (!GermanGrammar.IsSupportedShape(m.Groups["shape"].Value)) return true;
            return false;
        }

        private static void LoadVerbs(string path)
        {
            if (!File.Exists(path)) { Log("data-missing", path); return; }
            var items = ReadArray(path, "verbs");
            if (items == null) return;
            var list = new List<GermanGrammar.VerbForms>();
            foreach (var o in items)
            {
                string inf = (string)o["inf"];
                if (string.IsNullOrEmpty(inf)) continue;
                list.Add(new GermanGrammar.VerbForms
                {
                    En = (string)o["en"],
                    Inf = inf,
                    S3 = (string)o["s3"],
                    P2 = (string)o["p2"],
                    P3 = (string)o["p3"],
                });
            }
            GermanGrammar.LoadVerbs(list);
            VerbCount = list.Count;
            Log("data-load", "Verbs.json entries=" + list.Count);
        }
    }
}
