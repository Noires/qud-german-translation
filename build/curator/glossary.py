"""Glossar + Anrede-Richtlinie für die Terminologie-Konsistenz.

build/curator/data/glossary.json — committbar, wird NICHT deployt:
  policy: {player_address: "Ihr", choice_address: "Ihr"}
  terms:  [{en, de, gender (m/f/n/p), plural, variants_forbidden[], note}]

Die Prüfregeln G1/G2 (context_lint.py) und die Term-Markierung der
Szenen-Vorschau lesen diese Datei. Vorschläge kommen aus den {{X|…}}-
eingefärbten Begriffen der englischen IDs, ausgerichtet an den eingefärbten
Spannen des deutschen Werts (gleiche Reihenfolge).
"""
import json
import os
import re
import threading
from collections import Counter

from . import config

PATH = os.path.join(config.DATA_DIR, "glossary.json")
ADDRESS_FORMS = ("Ihr", "Sie", "du")
GENDERS = ("m", "f", "n", "p")
DEFAULT = {"policy": {"player_address": "Ihr", "choice_address": "Ihr"}, "terms": []}

_lock = threading.Lock()
_COLORED = re.compile(r"\{\{[^|{}]+\|([^{}]+)\}\}")


class Glossary:
    def __init__(self, path=None):
        self.path = path or PATH
        self._cache = None  # (sig, data)

    def sig(self):
        try:
            st = os.stat(self.path)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None

    def load(self):
        sig = self.sig()
        if self._cache and self._cache[0] == sig:
            return self._cache[1]
        data = json.loads(json.dumps(DEFAULT))
        if sig:
            try:
                with open(self.path, encoding="utf-8") as f:
                    raw = json.load(f)
                data["policy"].update(raw.get("policy") or {})
                data["terms"] = raw.get("terms") or []
            except (OSError, ValueError):
                pass
        self._cache = (sig, data)
        return data

    def _write(self, data):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        out = {"note": "Glossar + Anrede-Richtlinie der Kurator-UI (build/curator/). "
                       "Prüfregeln K2/G1/G2. Committbar, wird NICHT deployt.",
               "policy": data["policy"],
               "terms": sorted(data["terms"], key=lambda t: t["en"].lower())}
        tmp = self.path + ".curator-tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, self.path)
        self._cache = None

    def policy(self):
        return self.load()["policy"]

    def terms(self):
        return self.load()["terms"]

    def set_policy(self, policy):
        for k in ("player_address", "choice_address"):
            if k in policy and policy[k] not in ADDRESS_FORMS:
                raise ValueError("%s muss eine von %s sein." % (k, ", ".join(ADDRESS_FORMS)))
        with _lock:
            data = self.load()
            data = {"policy": {**data["policy"], **{k: v for k, v in policy.items()
                                                     if k in ("player_address", "choice_address")}},
                    "terms": list(data["terms"])}
            self._write(data)

    def set_term(self, term):
        en = (term.get("en") or "").strip()
        de = (term.get("de") or "").strip()
        if not en or not de:
            raise ValueError("en und de sind erforderlich.")
        g = (term.get("gender") or "").strip().lower()
        if g and g not in GENDERS:
            raise ValueError("gender muss m, f, n oder p sein.")
        clean = {"en": en, "de": de, "gender": g, "plural": (term.get("plural") or "").strip(),
                 "variants_forbidden": [v.strip() for v in term.get("variants_forbidden") or []
                                        if v.strip()],
                 "note": (term.get("note") or "").strip()}
        with _lock:
            data = self.load()
            terms = [t for t in data["terms"] if t["en"].lower() != en.lower()]
            terms.append(clean)
            self._write({"policy": data["policy"], "terms": terms})
        return clean

    def delete_term(self, en):
        with _lock:
            data = self.load()
            terms = [t for t in data["terms"] if t["en"].lower() != (en or "").lower()]
            if len(terms) == len(data["terms"]):
                raise KeyError("Begriff „%s“ nicht im Glossar." % en)
            self._write({"policy": data["policy"], "terms": terms})

    def suggest(self, store, limit=80):
        """Eingefärbte Begriffe (EN) mit ihren häufigsten deutschen Spannen."""
        known = {t["en"].lower() for t in self.terms()}
        pairs = Counter()
        en_count = Counter()
        for u in store.all_units():
            if u.kind not in ("string", "string-text") or not u.english:
                continue
            en_spans = [s.strip() for s in _COLORED.findall(u.english)]
            if not en_spans:
                continue
            de_spans = [s.strip() for s in _COLORED.findall(u.display_value())]
            for i, en in enumerate(en_spans):
                # Emotes (*…*), UI-Klammern ([…]) und Sätze sind keine Begriffe
                if "=" in en or len(en) < 3 or len(en) > 40 or en.lower() in known                         or en[0] in "*[(" or len(en.split()) > 4:
                    continue
                en_count[en.lower()] += 1
                if len(de_spans) == len(en_spans):
                    pairs[(en.lower(), de_spans[i])] += 1
        out = []
        for en, n in en_count.most_common():
            if n < 2:
                break
            cands = sorted(((de, c) for (e, de), c in pairs.items() if e == en),
                           key=lambda x: -x[1])
            out.append({"en": en, "count": n,
                        "de": [{"de": de, "count": c} for de, c in cands[:4]]})
            if len(out) >= limit:
                break
        return out


    def suggest_names(self, store, english_fn, min_uses=3, limit=150):
        """Kanonische Begriffe aus Blueprint-Namen: englischer DisplayName (Manifest)
        -> deutscher DisplayName, wenn der englische Name im Korpus mindestens
        min_uses-mal vorkommt. Genus vorbefüllt aus Lexikon/Heuristik."""
        from . import german, grammar_emu
        known = {t["en"].lower() for t in self.terms()}
        # (englisch klein, deutsch klein) aller String-Einheiten, sichtbarer Text
        pairs = [(german.visible_text(u.english or "").lower(),
                  german.visible_text(u.display_value()).lower())
                 for u in store.all_units() if u.kind in ("string", "string-text") and u.english]
        cands = {}
        for u in store.all_units():
            if u.attr != "DisplayName" or u.elem != "part":
                continue
            en = english_fn(u)
            de = german.visible_text(u.display_value()).strip()
            if not en or not de or "=" in en or "=" in de:
                continue
            en = german.visible_text(en).strip().lower()
            # interne Blueprint-Namen ("BasePaxKlanq") und unübersetzte Namen raus
            if len(en) < 4 or len(en.split()) > 3 or en in known or en == de.lower() \
                    or (" " not in de and re.search(r"[a-z][A-Z]", de)):
                continue
            cands.setdefault(en, set()).add((de, u.objname))
        out = []
        for en, des in cands.items():
            rx = re.compile(r"\b%s\b" % re.escape(en))
            occ = [d for e, d in pairs if en in e and rx.search(e)]
            if len(occ) < min_uses:
                continue
            variants = []
            for de, bp in sorted(des):
                head = german.head_noun(de).lower()
                stem = head[:max(4, len(head) - 2)]
                hits = sum(1 for d in occ if stem and stem in d)
                variants.append((hits, de, bp))
            variants.sort(reverse=True)
            hits, de, bp = variants[0]
            g, src = german.guess_gender(de, grammar_emu.lexicon())
            out.append({"en": en, "de": de, "count": len(occ), "attested": round(hits / len(occ), 2),
                        "gender": g, "gender_source": src, "blueprint": bp,
                        "alternatives": [v[1] for v in variants[1:4]], "source": "DisplayName"})
        out.sort(key=lambda x: (x["attested"] < 0.5, -x["count"]))
        return out[:limit]


GLOSSARY = Glossary()
