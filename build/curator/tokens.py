"""Token-Registry: welche =token=-Namen sind gültig?

Drei Quellen (hybrid):
  1. geparst aus [VariableReplacer(new string[]{...})] in VariableReplacers.de.cs
  2. abgeleitet aus dem englischen Korpus (Manifest-IDs + vorhandene IDs) —
     was das Spiel selbst emittiert, ist per Definition gültig
  3. statisch data/base_tokens.json (pronouns.*, Zahl-Tokens, Wildcards)

Token-Grammatik fürs Matching: =TEIL[:param][#param]= ; TEIL kann mit einem
Ziel beginnen (subject./object./beliebige Laufzeit-Variable), deshalb gilt ein
Token als bekannt, wenn der volle Name ODER der Name ohne erstes Segment
registriert ist. Großschreibung des ersten Buchstabens ist Kapitalisierungs-
Konvention und wird normalisiert.
"""
import json
import os
import re

from . import config

TOKEN_RE = re.compile(r"=([^=\s][^=]*?)=")
CS_REPLACER_RE = re.compile(
    r"\[VariableReplacer\((?:new\s+string\[\]\s*\{(?P<names>[^}]*)\})?", re.S)
_STR_RE = re.compile(r'"([^"]*)"')

# Deutsche Grammatik-Tokens für die Palette (Name, Tooltip)
PALETTE = [
    ("=object.dativ=", "bestimmter Artikel + Name im Dativ (mit/von/zu/aus/bei)"),
    ("=object.akkusativ=", "bestimmter Artikel + Name im Akkusativ (Richtung)"),
    ("=object.nominativ=", "bestimmter Artikel + Name im Nominativ"),
    ("=object.genitiv=", "bestimmter Artikel + Name im Genitiv"),
    ("=object.a.dativ=", "unbestimmter Artikel + Name im Dativ"),
    ("=subject.konjde:INFINITIV=", "deutsches Verb konjugieren (sieht/seht/sehen)"),
    ("=subject.its:akk:f=", "Possessiv-Determinativ, Kasus+Genus annotiert"),
    ("=subject.its.item:dat#weapon=", "Possessiv + Item (Genus vom Item)"),
    ("=subject.its.part:dat#part=", "Possessiv + Körperteil"),
    ("=subject.the.name's=", "vorangestellter Genitiv (des Krokodils …)"),
    ("=subject.Does:VERB=", "Name + konjugiertes Laufzeit-Verb"),
    ("=pronouns.subjective=", "Subjektpronomen der Figur"),
]


def _parse_cs_names(cs_path):
    names = set()
    try:
        with open(cs_path, encoding="utf-8") as f:
            src = f.read()
    except OSError:
        return names
    for m in CS_REPLACER_RE.finditer(src):
        block = m.group("names")
        if not block:
            continue
        for s in _STR_RE.finditer(block):
            names.add(s.group(1))
    return names


def _norm(name):
    return name[:1].lower() + name[1:] if name else name


def token_base(content):
    """Innenleben eines Tokens -> (voller Basisname, Name ohne 1. Segment).
    Parameter (:…), Item-Anker (#…) und Pipes (|…) werden abgeschnitten."""
    base = re.split(r"[:#|]", content, 1)[0].strip()
    parts = base.split(".")
    rest = ".".join(parts[1:]) if len(parts) > 1 else None
    return base, rest


class Registry:
    def __init__(self, lang_dir=None, cs_path=None, game_dir=None):
        self.cs_path = cs_path or config.CODE_CS
        self.exact = set()      # normalisierte Basisnamen
        self.prefixes = []      # Wildcard-Präfixe ("pronouns.", "spice:")
        self._load_static()
        self.cs_names = _parse_cs_names(self.cs_path)
        self.exact.update(_norm(n) for n in self.cs_names)

    def _load_static(self):
        p = os.path.join(config.DATA_DIR, "base_tokens.json")
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except OSError:
            data = {"exact": [], "prefixes": []}
        self.exact.update(_norm(n) for n in data.get("exact", []))
        self.prefixes = list(data.get("prefixes", []))

    def add_corpus(self, english_texts):
        """Alle Tokens aus englischen Vorlagen als gültig registrieren."""
        for text in english_texts:
            if not text or "=" not in text:
                continue
            for m in TOKEN_RE.finditer(text):
                base, rest = token_base(m.group(1))
                if base:
                    self.exact.add(_norm(base))
                if rest:
                    self.exact.add(_norm(rest))

    def known(self, content):
        """Ist der Token-Inhalt (ohne =) bekannt?"""
        base, rest = token_base(content)
        if not base:
            return False
        full = _norm(content.strip())
        # Wildcard-Präfixe gegen den VOLLEN Inhalt (inkl. ':'), z. B. "commandKey:"
        for p in self.prefixes:
            if full.startswith(p) or (rest and _norm(rest).startswith(p)):
                return True
        for cand in filter(None, (base, rest)):
            if _norm(cand) in self.exact:
                return True
        return False

    def palette(self):
        return [{"t": t, "tip": tip} for t, tip in PALETTE]
