"""Verlauf je Eintrag („warum steht das so da?") und Konkordanz (Begriff → alle Fassungen).

Verlauf = Git-Commits, die die Zeile des Eintrags geändert haben (git log -L, folgt
Zeilenverschiebungen), plus Vorschlags-Batches aus data/proposals/, die die Einheit
betrafen (mit Regel, Status, alt → neu).
"""
import glob
import json
import os
import re
import subprocess

from . import config, proposals

MAX_COMMITS = 15


def git_history(store, u):
    if not u.line or u.kind == "json":
        return []
    path = os.path.relpath(store.path(u.file), config.REPO_ROOT).replace("\\", "/")
    try:
        out = subprocess.run(
            ["git", "log", "-n", str(MAX_COMMITS), "--date=short",
             "--format=@@C %h|%ad|%s", "-L%d,%d:%s" % (u.line, u.line, path)],
            cwd=config.REPO_ROOT, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return []
    commits, cur = [], None
    for line in out.stdout.splitlines():
        if line.startswith("@@C "):
            h, d, s = (line[4:].split("|", 2) + ["", ""])[:3]
            cur = {"commit": h, "date": d, "subject": s, "old": None, "new": None}
            commits.append(cur)
        elif cur is not None and line[:1] in ("+", "-") and not line.startswith(("+++", "---")):
            m = re.search(r'Value="([^"]*)"', line) or re.search(r">([^<]+)<", line)
            val = m.group(1) if m else line[1:].strip()
            cur["new" if line[0] == "+" else "old"] = val[:400]
    return commits


def proposal_history(uid):
    out = []
    for p in sorted(glob.glob(os.path.join(proposals.DIR, "*.json"))):
        try:
            with open(p, encoding="utf-8") as f:
                b = json.load(f)
        except (OSError, ValueError):
            continue
        for it in b.get("items", []):
            if it.get("uid") == uid or it.get("created_uid") == uid:
                out.append({"batch": b.get("batch"), "rule": b.get("rule"), "created": b.get("created"),
                            "status": it.get("status"), "old": it.get("old_value"),
                            "new": it.get("new_value"), "note": it.get("note", "")})
    return out


def history(store, uid):
    u = store.get(uid)
    if u is None:
        return None
    return {"uid": uid, "git": git_history(store, u), "proposals": proposal_history(uid)}


def concordance(store, term, limit=300):
    """Alle Einheiten, deren englische Vorlage den Begriff (als Wort) enthält."""
    term = (term or "").strip()
    if len(term) < 2:
        return {"term": term, "total": 0, "items": []}
    rx = re.compile(r"(?<![A-Za-z])%s(?![a-z])" % re.escape(term), re.I)
    hits = [u for u in store.all_units() if u.english and u.display_value() and rx.search(u.english)]
    return {"term": term, "total": len(hits), "items": [
        {"uid": u.uid, "file": u.file, "context": u.context or u.key, "english": u.english,
         "value": u.display_value()} for u in hits[:limit]]}
