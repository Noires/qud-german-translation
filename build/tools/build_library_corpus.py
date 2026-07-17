# -*- coding: utf-8 -*-
"""Erzeugt languages/lang-de/LibraryCorpus.de.json für die prozeduralen Markov-Bücher.

Repliziert exakt XRL.MarkovChain.AppendCorpus (order=2): Chain[key "w1 w2"] -> Liste der
Folgewörter (Duplikate = Gewichtung), OpeningWords = Bigramme nach einem Satzende.
Serialisierung wie MarkovChainData.OnBeforeSerialize: values -gejoint;
geladen wird die Datei über DataManager.FilePathFromBasePreferModFile, das bei aktiver
Sprache zuerst "librarycorpus.de.json" in Mods sucht.

Quellen (Beschluss 2026-07-17): Books.de.xml + Beschreibungstexte + Konversationen.

Aufruf:  python build/tools/build_library_corpus.py
"""
import io
import json
import os
import re
import xml.etree.ElementTree as ET

BASE = os.path.join(os.path.dirname(__file__), "..", "..", "languages", "lang-de")
OUT = os.path.join(BASE, "LibraryCorpus.de.json")
ORDER = 2

TOKEN = re.compile(r"=[^=\s][^=]*=")          # =subject.the.name= u. ä.
COLOR = re.compile(r"\{\{[^{}|]*\|([^{}]*)\}\}")
CTRL = re.compile(r"[&^].")
TAGLIKE = re.compile(r"[<>\[\]]")
WS = re.compile(r"\s+")

# Sultans-Platzhalter: PostprocessLoadedCorpus ersetzt "*sultan*" beim Laden durch echte
# Sultansnamen der aktuellen Historie - ohne diese Sätze fehlt dem deutschen Korpus die
# Namens-Einwebung, die das englische Original über sein Trainingsmaterial bekommt.
SULTAN_SEED = [
    "Gepriesen sei *sultan*, in Chrom gewandet und in Salz geboren.",
    "Und *sultan* sprach zu den Wassergeborenen: Lebt und trinkt.",
    "In jenem Jahr erhob sich *sultan* und die Erde bebte.",
    "Die Chroniken berichten, dass *sultan* sechs Nächte lang wachte.",
    "Wer kennt nicht die Taten, die *sultan* im Dschungel vollbrachte?",
    "Selig sind jene, die dem Pfad folgen, den *sultan* wies.",
    "Von *sultan* stammt das Wort: Das Salz erinnert sich.",
    "Da zog *sultan* gen Norden, und die Türme neigten sich.",
    "Man sagt, *sultan* habe mit den Baetylen selbst gesprochen.",
    "Im Namen von *sultan* wurden die Tore des Tempels versiegelt.",
    "Und so endete das Zeitalter, das *sultan* begonnen hatte.",
    "Die Priester schrieben jede Silbe nieder, die *sultan* sprach.",
    "Kein Kodex bindet *sultan*, denn die Geschichte selbst gehorcht.",
    "Am Grab von *sultan* wächst seither der Sternenlotus.",
    "Es war *sultan*, der die Wasser teilte und die Dünen zählte.",
]


def visible(s):
    while True:
        t = COLOR.sub(r"\1", s)
        if t == s:
            break
        s = t
    return CTRL.sub("", s).replace("▶", "")


def harvest_sentences(text):
    """Bereinigt einen Textblock und liefert brauchbare Sätze (ohne Token-Reste)."""
    text = visible(text)
    text = WS.sub(" ", text).strip()
    if not text:
        return
    # grob in Sätze teilen, tokenhaltige/degenerierte verwerfen
    for sent in re.split(r"(?<=[.!?])\s+", text):
        sent = sent.strip()
        if len(sent) < 16 or len(sent) > 400:
            continue
        if TOKEN.search(sent) or TAGLIKE.search(sent) or "=" in sent:
            continue
        if not re.search(r"[A-Za-zÄÖÜäöüß]{3}", sent):
            continue
        if not sent.endswith((".", "!", "?")):
            sent += "."
        yield sent


def collect():
    sentences = []

    # 1. Buchtexte: kompletter Textinhalt aller Elemente in Books.de.xml
    root = ET.parse(os.path.join(BASE, "Books.de.xml")).getroot()
    for el in root.iter():
        for chunk in (el.text, el.tail):
            if chunk and chunk.strip():
                sentences.extend(harvest_sentences(chunk))

    # 2. Beschreibungstexte (part Description Short="...")
    for f in ["Items.de.xml", "Creatures.de.xml", "Furniture.de.xml", "Foods.de.xml",
              "Walls.de.xml", "HiddenObjects.de.xml", "PhysicalPhenomena.de.xml",
              "Liquids.de.xml"]:
        t = io.open(os.path.join(BASE, f), encoding="utf-8-sig").read()
        for m in re.finditer(r'<part Name="Description" Short="([^"]+)"', t):
            raw = (m.group(1).replace("&quot;", '"').replace("&#10;", "\n")
                   .replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
            sentences.extend(harvest_sentences(raw))

    # 3. Konversationen (deutsche Values/Textknoten)
    root = ET.parse(os.path.join(BASE, "Strings.Conversations.de.xml")).getroot()
    for el in root.iter("string"):
        val = el.get("Value") if el.get("Value") is not None else (el.text or "")
        sentences.extend(harvest_sentences(val))

    sentences.extend(SULTAN_SEED)
    return sentences


def build_chain(sentences):
    corpus = " ".join(sentences)
    words = corpus.split(" ")
    chain = {}
    opening = []
    flag = False
    for i in range(len(words) - ORDER):
        prev = words[i - 1] if i != 0 else " "
        if prev == "":
            prev = " "
        if prev[-1] == ".":
            flag = True
        key = words[i]
        for j in range(1, ORDER):
            key = key + " " + words[i + j]
        if flag:
            opening.append(key)
            flag = False
        chain.setdefault(key, []).append(words[i + ORDER])
    return chain, opening


def main():
    sentences = collect()
    print(f"Sätze: {len(sentences)}")
    chain, opening = build_chain(sentences)
    print(f"Chain-Keys: {len(chain)}  OpeningWords: {len(opening)}")
    data = {
        "order": ORDER,
        "OpeningWords": opening,
        "keys": list(chain.keys()),
        "values": ["".join(v) for v in chain.values()],
    }
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"geschrieben: {OUT} ({os.path.getsize(OUT)} Bytes)")

    # Qualitäts-Smoke: ein paar Sätze wie GenerateSentence ziehen
    import random
    rng = random.Random(42)
    for _ in range(4):
        key = rng.choice(opening)
        out = key.split(" ")
        for _ in range(60):
            nxt = chain.get(" ".join(out[-ORDER:]))
            if not nxt:
                break
            w = rng.choice(nxt)
            out.append(w)
            if "." in w:
                break
        print("BEISPIEL:", " ".join(out))


if __name__ == "__main__":
    main()
