"""Fehlende Nicht-String-Einträge (EffectsDetails-Templates, Blueprint-Attribute,
Optionen) aus einem Agenten-Ergebnis byte-erhaltend in die .de.xml-Dateien einfügen.

  py build/curator/tools/insert_blueprint.py NAME            # Trockenlauf (nur Bericht)
  py build/curator/tools/insert_blueprint.py NAME --write    # schreiben

Eingabe data/proposals/_work/<NAME>.output.json:
  {"templates": [{"id", "german_xml"}], "attrs": [{"file", "key":[scope, elem, anker, attr], "german"}]}

Garantien je Datei: Einfügen nur (kein bestehendes Byte geändert außer dem
Einfügepunkt), Kandidat ist wohlgeformt, jede bestehende Einheit (xmlscan) behält
uid UND Wert, Name/ID-Attribute werden nur für NEUE Elemente gesetzt.
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from curator import config, proposals, xmlscan  # noqa: E402

WORK = os.path.join(proposals.DIR, "_work")


def _read(fn):
    text, bom, _ = xmlscan.read_file(os.path.join(config.LANG_DE, fn))
    return text, bom


def _eol(text):
    return "\r\n" if "\r\n" in text else "\n"


def _attr(v):
    return xmlscan.xml_escape_attr(v, '"')


def insert_templates(text, templates):
    eol = _eol(text)
    close = text.rfind("</templates>")
    assert close > 0, "</templates> fehlt"
    line_start = text.rfind("\n", 0, close) + 1
    block = "".join("  " + t["german_xml"].strip().replace("\r\n", "\n").replace("\n", eol) + eol
                    for t in templates)
    return text[:line_start] + block + text[line_start:]


def _object_span(text, scope):
    m = re.search(r'<object Name="%s"[^>]*>' % re.escape(_attr(scope)), text)
    if not m:
        return None
    end = text.find("</object>", m.end())
    return m.start(), m.end(), end


def insert_attr(text, fn, key, german):
    """key = [scope, elem, anker, attr]. Fügt Attribut an bestehendes Element an
    oder legt das Element (bzw. Objekt) neu an."""
    scope, elem, anchor, attr = key
    eol = _eol(text)
    if fn == "Options.de.xml" and elem == "option":
        m = re.search(r'<option ID="%s"[^>]*?(/?)>' % re.escape(_attr(anchor)), text)
        if m:  # Attribut an bestehende Option
            pos = m.end() - (2 if m.group(1) else 1)
            while text[pos - 1] == " ":
                pos -= 1
            return text[:pos] + ' %s="%s"' % (attr, _attr(german)) + text[pos:]
        close = text.rfind("</options>")
        line_start = text.rfind("\n", 0, close) + 1
        new = '  <option ID="%s" %s="%s" />%s' % (_attr(anchor), attr, _attr(german), eol)
        return text[:line_start] + new + text[line_start:]
    span = _object_span(text, scope)
    if span is None:  # Objekt fehlt ganz -> neu vor </objects>
        close = text.rfind("</objects>")
        line_start = text.rfind("\n", 0, close) + 1
        new = ('  <object Name="%s" Load="Merge">%s    <%s Name="%s" %s="%s" />%s  </object>%s'
               % (_attr(scope), eol, elem, _attr(anchor), attr, _attr(german), eol, eol))
        return text[:line_start] + new + text[line_start:]
    o_start, o_open_end, o_end = span
    body = text[o_open_end:o_end]
    m = re.search(r'<%s Name="%s"[^>]*?(/?)>' % (re.escape(elem), re.escape(_attr(anchor))), body)
    if m:
        pos = o_open_end + m.end() - (2 if m.group(1) else 1)
        while text[pos - 1] == " ":
            pos -= 1
        return text[:pos] + ' %s="%s"' % (attr, _attr(german)) + text[pos:]
    line_start = text.rfind("\n", 0, o_end) + 1
    new = '    <%s Name="%s" %s="%s" />%s' % (elem, _attr(anchor), attr, _attr(german), eol)
    return text[:line_start] + new + text[line_start:]


def verify(fn, old_text, new_text):
    ET.fromstring(new_text)
    old = {u.uid: u.display_value() for u in xmlscan.scan_text(old_text, fn).units}
    new = {u.uid: u.display_value() for u in xmlscan.scan_text(new_text, fn).units}
    changed = [k for k, v in old.items() if new.get(k) != v]
    assert not changed, "%s: %d bestehende Einheiten verändert" % (fn, len(changed))
    return len(new) - len(old)


def main(name, write):
    with open(os.path.join(WORK, name + ".output.json"), encoding="utf-8") as f:
        data = json.load(f)
    edits = {}
    if data.get("templates"):
        edits.setdefault("EffectsDetails.de.xml", []).append(("templates", data["templates"]))
    for a in data.get("attrs", []):
        edits.setdefault(a["file"], []).append(("attr", a))
    for fn, ops in edits.items():
        old, bom = _read(fn)
        text = old
        for kind, payload in ops:
            if kind == "templates":
                text = insert_templates(text, payload)
            else:
                text = insert_attr(text, fn, payload["key"], payload["german"])
        added = verify(fn, old, text)
        print("%-24s +%d Einheiten%s" % (fn, added, "" if write else "  (Trockenlauf)"))
        if write:
            p = os.path.join(config.LANG_DE, fn)
            tmp = p + ".curator-tmp"
            with open(tmp, "wb") as f:
                f.write(bom + text.encode("utf-8"))
            os.replace(tmp, p)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
    else:
        main(sys.argv[1], "--write" in sys.argv)
