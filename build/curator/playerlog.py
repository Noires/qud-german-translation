"""Player.log-Parser: String-Misses, MODWARN, [QudDE]-Selbsttests, Kurator-Tests.

Formate (verifiziert am echten Log, 2026-07-18):
  ERROR  - System.Exception: String table miss - Lang de - Context="…" ID="…"
  MODWARN [Mod Name] - <text>
  [QudDE] pipeline-test PASS: Croc =object.nominativ= -> "das Krokodil"
  [QudDE] <name>-test summary: X passed, Y failed   (u. ä.)
  [QudDE] curator-tests file-mtime=<ticks> count=<n>     (Phase 6)
  [QudDE] curator-test <id> PASS|FAIL got="…" want="…"|ERROR <msg>
"""
import json
import os
import re

from . import config

MISS_RE = re.compile(r'String table miss - Lang de - Context="(?P<ctx>[^"]*)" ID="(?P<id>[^"]*)"')
MODWARN_RE = re.compile(r"^MODWARN \[(?P<mod>[^\]]+)\] - (?P<text>.*)$")
QUDDE_RE = re.compile(r"^\[QudDE\] (?P<text>.*)$")
CURATOR_HDR_RE = re.compile(r"^curator-tests file-mtime=(?P<mtime>\d+) count=(?P<count>\d+)")
CURATOR_TEST_RE = re.compile(
    r"^curator-test (?P<id>\S+) (?P<status>PASS|FAIL|ERROR)(?: (?P<detail>.*))?$")
SUMMARY_RE = re.compile(r"^(?P<name>[\w-]+) summary: (?P<passed>\d+) passed, (?P<failed>\d+) failed")
CS_WARN_RE = re.compile(r"warning CS\d+")

GERMAN_MOD = "Caves of Qud German Translation"


def load_benign():
    p = os.path.join(config.DATA_DIR, "benign_misses.json")
    try:
        with open(p, encoding="utf-8") as f:
            return {(m["context"], m["id"]) for m in json.load(f)["misses"]}
    except Exception:
        return set()


def parse_log(path):
    """-> dict mit misses/modwarns/qudde/curator_tests/summaries."""
    out = {
        "path": path, "exists": os.path.exists(path),
        "mtime": None, "misses": [], "modwarns": [],
        "selftests": {"pass": 0, "fail": 0, "fail_lines": [], "summaries": []},
        "curator": {"header": None, "results": []},
    }
    if not out["exists"]:
        return out
    out["mtime"] = os.stat(path).st_mtime
    seen_miss = set()
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.rstrip("\n")
                mm = MISS_RE.search(line)
                if mm:
                    key = (mm.group("ctx"), mm.group("id"))
                    if key not in seen_miss:
                        seen_miss.add(key)
                        out["misses"].append({"context": key[0], "id": key[1]})
                    continue
                mw = MODWARN_RE.match(line)
                if mw:
                    out["modwarns"].append({
                        "mod": mw.group("mod"), "text": mw.group("text"),
                        "compiler_warning": bool(CS_WARN_RE.search(mw.group("text"))),
                    })
                    continue
                qd = QUDDE_RE.match(line)
                if not qd:
                    continue
                text = qd.group("text")
                hdr = CURATOR_HDR_RE.match(text)
                if hdr:
                    out["curator"]["header"] = {
                        "file_mtime_ticks": int(hdr.group("mtime")),
                        "count": int(hdr.group("count"))}
                    continue
                ct = CURATOR_TEST_RE.match(text)
                if ct:
                    out["curator"]["results"].append({
                        "id": ct.group("id"), "status": ct.group("status"),
                        "detail": ct.group("detail") or ""})
                    continue
                sm = SUMMARY_RE.match(text)
                if sm:
                    out["selftests"]["summaries"].append({
                        "name": sm.group("name"),
                        "passed": int(sm.group("passed")),
                        "failed": int(sm.group("failed"))})
                    continue
                if " PASS" in text:
                    out["selftests"]["pass"] += 1
                elif " FAIL" in text:
                    out["selftests"]["fail"] += 1
                    out["selftests"]["fail_lines"].append(text[:300])
    except OSError as ex:
        out["error"] = str(ex)
    return out


def dashboard(store_obj):
    """Aufbereitete Sicht für die UI: aktueller + vorheriger Lauf, Misses
    klassifiziert (benigne / Eintrag vorhanden / fehlt), MODWARNs gruppiert."""
    cur = parse_log(config.CFG["player_log"])
    prev_path = config.CFG["player_log"].replace("Player.log", "Player-prev.log")
    benign = load_benign()

    # Miss -> existiert der Eintrag im Index?
    store_obj.refresh()
    by_key = {}
    for u in store_obj.all_units():
        if u.kind in ("string", "string-text"):
            by_key[(u.context or "", u.english or "")] = u.uid
    for m in cur["misses"]:
        key = (m["context"], m["id"])
        m["benign"] = key in benign
        m["uid"] = by_key.get(key)

    german_warns = [w for w in cur["modwarns"] if w["mod"] == GERMAN_MOD]
    other_warns = [w for w in cur["modwarns"] if w["mod"] != GERMAN_MOD]

    last_sync = None
    p = os.path.join(config.DATA_DIR, "last_sync.json")
    try:
        with open(p, encoding="utf-8") as f:
            last_sync = json.load(f)
    except Exception:
        pass

    return {
        "log": {"path": cur["path"], "exists": cur["exists"], "mtime": cur["mtime"]},
        "prev_exists": os.path.exists(prev_path),
        "misses": cur["misses"],
        "benign_count": sum(1 for m in cur["misses"] if m["benign"]),
        "new_misses": [m for m in cur["misses"] if not m["benign"]],
        "modwarns_german": german_warns,
        "modwarns_other_count": len(other_warns),
        "selftests": cur["selftests"],
        "curator": cur["curator"],
        "last_sync": last_sync,
    }
