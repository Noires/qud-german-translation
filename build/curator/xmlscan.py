"""Span-Scanner für die *.de.xml-Dateien.

Liefert Übersetzungseinheiten MIT exakten Zeichen-Spans in den Original-Text,
damit writer.py chirurgisch splicen kann. ElementTree scheidet fürs Schreiben
aus (BOM/CRLF/Quote-Stil variieren pro Datei); dieser Scanner fasst den Text
nie an, er misst nur.

Einheiten-Arten (kind):
  string       Value-Attribut eines einzeiligen <string ... />
  string-text  Textform <string ID="...">text</string>
  attr         Attribut in Blueprint-Dateien (<part DisplayName=.../>)
  text         reiner Text-Inhalt eines Leaf-Elements (<p>, <page>, ...)

Mixed content (Kinder + Text, z. B. <p>... <stat/> ...</p>) wird bewusst NICHT
als Einheit indiziert (im MVP nicht editierbar) — Parität dazu prüft
tests/test_xmlscan.py gegen ElementTree mit derselben Regel.

`value` in Unit ist immer der ROHE Span-Inhalt (XML-escaped); `display_value()`
liefert die entschärfte Form für die UI.
"""
import bisect
import hashlib
import re

# Ein Master-Regex läuft sequenziell über den Text; Kommentare/PI/CDATA werden
# als eigene Alternativen konsumiert und übersprungen, damit Tags darin nicht
# fälschlich matchen (Naming.de.xml hat einen großen Kommentar-Header).
TAG_RE = re.compile(
    r"<!--.*?-->"
    r"|<!\[CDATA\[.*?\]\]>"
    r"|<\?.*?\?>"
    r"|<!(?:[^<>\"']|\"[^\"]*\"|'[^']*')*>"  # DOCTYPE u. ä.
    r"|<(?P<close>/?)(?P<name>[\w.:-]+)"
    r"(?P<attrs>(?:\s+[\w.:-]+\s*=\s*(?:\"[^\"]*\"|'[^']*'))*)"
    r"\s*(?P<selfclose>/?)>",
    re.DOTALL,
)
ATTR_RE = re.compile(r"(?P<key>[\w.:-]+)\s*=\s*(?P<q>[\"'])(?P<val>.*?)(?P=q)", re.DOTALL)

_ENT = {"lt": "<", "gt": ">", "amp": "&", "quot": '"', "apos": "'"}
_ENT_RE = re.compile(r"&(?:(?P<name>lt|gt|amp|quot|apos)|#(?P<dec>[0-9]+)|#x(?P<hex>[0-9a-fA-F]+));")


def xml_unescape(s):
    def sub(m):
        if m.group("name"):
            return _ENT[m.group("name")]
        if m.group("dec"):
            return chr(int(m.group("dec")))
        return chr(int(m.group("hex"), 16))
    return _ENT_RE.sub(sub, s)


def xml_escape_attr(s, quote='"'):
    s = s.replace("&", "&amp;").replace("<", "&lt;")
    if quote == '"':
        s = s.replace('"', "&quot;")
    else:
        s = s.replace("'", "&apos;")
    return s.replace("\n", "&#10;").replace("\t", "&#9;")


def xml_escape_text(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


class Unit:
    __slots__ = ("uid", "file", "kind", "key", "covkey", "context", "english",
                 "value", "span", "quote", "line", "objname", "elem", "elemname",
                 "attr", "eol")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def display_value(self):
        if self.kind == "json":  # JSON-Zeichenkette (jsonscan.py)
            import json
            return json.loads('"' + self.value + '"')
        if self.kind in ("text", "string-text"):
            # XML-EOL-Normalisierung wie ElementTree: \r\n -> \n (VOR dem
            # Unescape, damit ein &#13;-Charref als echtes \r erhalten bleibt).
            return xml_unescape(self.value.replace("\r\n", "\n"))
        return xml_unescape(self.value)

    def escape_back(self, new_display_value):
        """Escaped einen UI-Wert zurück in die Slot-Syntax dieser Unit."""
        if self.kind == "json":
            import json
            return json.dumps(new_display_value, ensure_ascii=False)[1:-1]
        if self.kind in ("text", "string-text"):
            s = xml_escape_text(new_display_value)
            if (self.eol or "\n") == "\r\n":
                s = s.replace("\r\n", "\n").replace("\n", "\r\n")
            return s
        return xml_escape_attr(new_display_value, self.quote or '"')

    def to_json(self):
        return {
            "uid": self.uid, "file": self.file, "kind": self.kind,
            "context": self.context, "english": self.english,
            "value": self.display_value(),
            "line": self.line, "objname": self.objname, "elem": self.elem,
            "elemname": self.elemname, "attr": self.attr, "key": self.key,
        }


def read_file(path):
    """-> (text ohne BOM, bom_bytes, sha256 des Roh-Inhalts)"""
    with open(path, "rb") as f:
        raw = f.read()
    digest = hashlib.sha256(raw).hexdigest()
    bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
    text = raw[len(bom):].decode("utf-8")
    return text, bom, digest


# Elemente, deren Name im ▶-Manifest übersetzbar markiert ist (deutscher Name ≠
# englischer): für den Abdeckungs-Schlüssel (covkey) über die Position unter dem
# Elternelement identifiziert statt über den Namen. Gemeinsam mit coverage.py.
POSITIONAL_TAGS = frozenset({"zone", "step", "quest", "location", "pregen", "relictypemapping"})
# Elemente, die den Abdeckungs-Bereich (covkey[0]) setzen. Unit.objname bleibt
# bewusst beim Blueprint-/Mutations-Namen (OBJ_TAGS); <cell> zählt nur für covkey,
# damit positionale <zone>-Schlüssel verschiedener Zellen nicht kollidieren.
OBJ_TAGS = ("object", "mutation")
SCOPE_TAGS = OBJ_TAGS + ("cell",)


def cov_anchor(tag, name_or_id, sibling_index):
    return "#%d" % sibling_index if tag in POSITIONAL_TAGS else name_or_id


def _mkuid(filename, kind, keystr):
    return hashlib.sha1(("%s|%s|%s" % (filename, kind, keystr)).encode("utf-8")).hexdigest()[:16]


class _Lines:
    def __init__(self, text):
        self.nl = [i for i, ch in enumerate(text) if ch == "\n"]

    def line(self, pos):
        return bisect.bisect_right(self.nl, pos - 1) + 1


def scan(path, filename):
    """Scannt eine .de.xml-Datei -> ScanResult(units, text, bom, digest, root_tag)."""
    text, bom, digest = read_file(path)
    return scan_text(text, filename, bom, digest)


def scan_text(text, filename, bom=b"", digest=None):
    """Scannt XML-Text (ohne BOM) -> ScanResult."""
    lines = _Lines(text)
    eol = "\r\n" if "\r\n" in text else "\n"
    units = []
    seen_keys = {}

    def emit(kind, keystr, **kw):
        # Duplikate Keys (z. B. doppelte <object Name=...>-Blöcke in Data.de.xml)
        # deterministisch disambiguieren, damit uids eindeutig bleiben.
        n = seen_keys.get((kind, keystr), 0) + 1
        seen_keys[(kind, keystr)] = n
        if n > 1:
            keystr = "%s~%d" % (keystr, n)
        units.append(Unit(uid=_mkuid(filename, kind, keystr), file=filename,
                          kind=kind, key=keystr, eol=eol, **kw))
    root_tag = None
    # Stack-Eintrag: [tag, restore_scope, path, child_counter, {tag: anzahl}, restore_cscope]
    stack = []
    scope = None    # Unit.objname (Blueprint/Mutation)
    cscope = None   # covkey-Bereich (zusätzlich <cell>)
    # (tag, open_end, key_base, cov_scope, elemname, kind, cov_anchor, objname) für Text-Units
    pending = None

    for m in TAG_RE.finditer(text):
        if m.group("name") is None:
            pending = None  # Kommentar/CDATA im Inhalt => nicht als reiner Text editieren
            continue
        tag = m.group("name")

        if m.group("close"):
            if pending is not None and pending[0] == tag:
                ptag, open_end, keybase, cov_scope, pname, pkind, panchor, pobj = pending
                inner = text[open_end:m.start()]
                if inner.strip():
                    emit(pkind, keybase + "@#text",
                         covkey=("S", pname) if pkind == "string-text"
                                else (cov_scope, ptag, panchor if ptag != "string" else "", "#text"),
                         context=None, english=pname if pkind == "string-text" else None,
                         value=inner, span=(open_end, m.start()), quote=None,
                         line=lines.line(open_end),
                         objname=pobj, elem=ptag,
                         elemname=pname, attr="#text")
            pending = None
            if stack and stack[-1][0] == tag:
                popped = stack.pop()
                scope = popped[1]
                cscope = popped[5]
            continue

        # öffnendes oder self-closing Tag
        pending = None  # Kind-Element => Elterninhalt ist mixed
        if root_tag is None:
            root_tag = tag
        is_root = not stack

        attrs = []
        base = m.start("attrs")
        for am in ATTR_RE.finditer(m.group("attrs")):
            attrs.append((am.group("key"), am.group("val"),
                          base + am.start("val"), base + am.end("val"), am.group("q")))
        # Schlüssel/Metadaten immer entschärft (ET-/coverage-kompatibel);
        # nur der editierbare Roh-Wert (Unit.value) bleibt escaped.
        adict = {k: xml_unescape(v) for k, v, _s, _e, _q in attrs}
        # Pfad-Anker: Name/ID/Command identifizieren Container (ability nutzt
        # Command) — macht Pfade positionsunabhängig und Manifest-Matching exakt.
        name_or_id = adict.get("Name") or adict.get("ID") or adict.get("Command") or ""

        if stack:
            stack[-1][3] += 1
            idx = stack[-1][3]
            tagcount = stack[-1][4]
            sib = tagcount.get(tag, 0)
            tagcount[tag] = sib + 1
        else:
            idx = 0
            sib = 0
        anchor = cov_anchor(tag, name_or_id, sib)
        seg = tag + ("[" + name_or_id + "]" if name_or_id else "#%d" % idx)
        path = (stack[-1][2] if stack else "") + "/" + seg

        restore_scope = scope
        restore_cscope = cscope
        if tag == "string":
            ctx = adict.get("Context", "")
            sid = adict.get("ID", "")
            keybase = "%s|%s" % (ctx, sid)
            for k, v, s, e, q in attrs:
                if k == "Value":
                    emit("string", keybase, covkey=("S", sid),
                         context=ctx, english=sid, value=v, span=(s, e), quote=q,
                         line=lines.line(s),
                         objname=None, elem="string", elemname=sid, attr="Value")
            if not m.group("selfclose"):
                stack.append([tag, restore_scope, path, 0, {}, restore_cscope])
                if "Value" not in adict:
                    pending = ("string", m.end(), keybase, "S", sid, "string-text", "", None)
            continue

        if tag in OBJ_TAGS:
            scope = name_or_id or scope
        if tag in SCOPE_TAGS:
            cscope = name_or_id or cscope

        if root_tag != "strings" and not is_root:
            for k, v, s, e, q in attrs:
                # Name/ID/Command sind Schlüssel-Attribute (Spiel-Lookup bzw.
                # Pfad-Anker), Load ist Merge-Steuerung — nie editierbar.
                # Kein einziges ID-Attribut ist im ▶-Manifest übersetzbar markiert.
                if k in ("Name", "ID", "Load", "Command"):
                    continue
                emit("attr", path + "@" + k,
                     covkey=(cscope, tag, anchor, k),
                     context=None, english=None, value=v, span=(s, e), quote=q,
                     line=lines.line(s),
                     objname=scope, elem=tag, elemname=adict.get("Name") or "", attr=k)

        if m.group("selfclose"):
            continue
        stack.append([tag, restore_scope, path, 0, {}, restore_cscope])
        if not is_root:
            pending = (tag, m.end(), path, cscope, adict.get("Name") or "", "text", anchor, scope)

    return ScanResult(units, text, bom, digest, root_tag)


class ScanResult:
    __slots__ = ("units", "text", "bom", "digest", "root_tag")

    def __init__(self, units, text, bom, digest, root_tag):
        self.units = units
        self.text = text
        self.bom = bom
        self.digest = digest
        self.root_tag = root_tag

    def by_uid(self):
        return {u.uid: u for u in self.units}
