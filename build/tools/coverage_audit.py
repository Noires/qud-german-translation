#!/usr/bin/env python3
"""
Translation coverage auditor for the German mod.

The game ships ExampleLanguage/*.example.xml where EVERY translatable value is
prefixed with the marker '▶'. That is the authoritative manifest of translatable
strings. This script compares it against languages/lang-de/*.de.xml and reports,
per file, how many translatable units have a German translation.

Usage:
    py build/tools/coverage_audit.py [GAME_EXAMPLE_DIR]

GAME_EXAMPLE_DIR defaults to the Steam install path below; override if yours differs.

Reliability notes:
  * Attribute-based translatables (DisplayName, Short, Value on distinct elements,
    and <string ID=...>) are matched EXACTLY by key -> these counts are trustworthy.
  * Element text inside repeated children (e.g. mutation <description><p>..</p></p>)
    shares one key per parent, so 'description-text' counts are approximate. Treat
    them as a hint, not gospel (mutation descriptions are already translated).
  * Naming.xml is skipped by default (procedural Latin syllables; not needed for German).
"""
import os, sys, glob
from collections import Counter
import xml.etree.ElementTree as ET

MARK = "▶"  # the game's translatable marker

DEFAULT_GAME = r"C:/Program Files (x86)/Steam/steamapps/common/Caves of Qud/CoQ_Data/StreamingAssets/Base/ExampleLanguage"
DE = os.path.join(os.path.dirname(__file__), "..", "..", "languages", "lang-de")

def parse(p):
    try: return ET.parse(p).getroot()
    except Exception: return None

def category(attr, elem, elemname):
    if attr == "#text": return "description-text"
    if attr == "DisplayName": return "DisplayName"          # player-visible name
    if attr in ("Short", "Long"): return "Description"      # player-visible description
    if elem == "tag" and elemname in ("PetResponse", "SimpleConversation"): return "ambient"
    if elem.startswith("xtag"): return "xtag-flavor"
    return "other-attr"

def units_example(root, is_strings):
    U = set()
    if is_strings:
        for s in root.iter("string"):
            if (s.text and MARK in s.text) or any(v and v.startswith(MARK) for v in s.attrib.values()):
                U.add(("S", s.get("ID")))
        return U
    def walk(el, on):
        if el.tag in ("object", "mutation"): on = el.get("Name") or on
        for a, v in el.attrib.items():
            if a != "Name" and isinstance(v, str) and v.startswith(MARK):
                U.add((on, el.tag, el.get("Name") or "", a))
        if el.text and MARK in el.text:
            U.add((on, el.tag, el.get("Name") or "", "#text"))
        for ch in el: walk(ch, on)
    walk(root, None); return U

def covered_de(root, is_strings):
    if root is None: return set()
    C = set()
    if is_strings:
        return {("S", s.get("ID")) for s in root.iter("string") if s.get("ID")}
    def walk(el, on):
        if el.tag in ("object", "mutation"): on = el.get("Name") or on
        for a, v in el.attrib.items():
            if a != "Name" and isinstance(v, str) and v.strip():
                C.add((on, el.tag, el.get("Name") or "", a))
        if el.text and el.text.strip():
            C.add((on, el.tag, el.get("Name") or "", "#text"))
        for ch in el: walk(ch, on)
    walk(root, None); return C

def main():
    game = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_GAME
    total_u = total_c = 0
    gcat = Counter()
    print(f"{'file':24}{'units':>7}{'cov':>7}{'miss':>7}{'cov%':>6}  missing-by-category")
    for ex in sorted(glob.glob(os.path.join(game, "*.example.xml"))):
        name = os.path.basename(ex).replace(".example.xml", "")
        if name == "Naming": continue
        exroot = parse(ex)
        if exroot is None: continue
        is_strings = exroot.tag == "strings"
        deroot = parse(os.path.join(DE, f"{name}.de.xml"))
        exu = units_example(exroot, is_strings)
        if not exu: continue
        deu = covered_de(deroot, is_strings)
        miss = exu - deu
        total_u += len(exu); total_c += len(exu) - len(miss)
        c = Counter()
        for u in miss:
            c["strings-ID" if is_strings else category(u[-1], u[1], u[2])] += 1
            gcat[("strings-ID" if is_strings else category(u[-1], u[1], u[2]))] += 1
        cov = 100 * (len(exu) - len(miss)) // len(exu)
        cats = ", ".join(f"{k}:{v}" for k, v in c.most_common()) if miss else "-- complete --"
        print(f"{name:24}{len(exu):7}{len(exu)-len(miss):7}{len(miss):7}{cov:6}  {cats}")
    print(f"\n{'TOTAL':24}{total_u:7}{total_c:7}{total_u-total_c:7}{100*total_c//total_u:6}")
    print("\nmissing by category (player-visible first):")
    for k in ("strings-ID", "DisplayName", "Description", "description-text", "other-attr", "ambient", "xtag-flavor"):
        if gcat.get(k): print(f"  {k:18}{gcat[k]}")

if __name__ == "__main__":
    main()
