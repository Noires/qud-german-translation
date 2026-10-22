"""Repo ↔ deployte Mod-Kopie: Hash-Abgleich + Sync.

Manifest = git-getrackte Dateien aus: CHANGELOG.md LICENSE README.md
manifest.json preview.png workshop.json languages/** (identisch zur
kuratierten Kopie unter AppData\\LocalLow). NIE kopiert: .git, build/, docs/,
.claude/, ungetrackte Dateien. Gelöscht wird Überzähliges nur unter languages/.
"""
import hashlib
import json
import os
import shutil
import subprocess
import time

from . import config

MANIFEST_PATHS = ["CHANGELOG.md", "LICENSE", "README.md", "manifest.json",
                  "preview.png", "workshop.json", "languages/"]


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def tracked_files():
    """Manifest-Dateien, repo-relativ mit '/': git-getrackt PLUS untracked-
    aber-nicht-ignoriert (z. B. frisch angelegte CuratorTests.json vor dem
    Commit). .gitignore-Ausschlüsse gelten weiterhin."""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--"]
        + MANIFEST_PATHS,
        cwd=config.REPO_ROOT, capture_output=True, text=True, check=True)
    return sorted({l for l in out.stdout.splitlines() if l.strip()})


def status():
    deploy = config.CFG["deploy_dir"]
    result = {"deploy_dir": deploy, "exists": os.path.isdir(deploy),
              "identical": [], "changed": [], "missing": [], "surplus": []}
    if not result["exists"]:
        return result
    tracked = tracked_files()
    tracked_set = set(tracked)
    for rel in tracked:
        src = os.path.join(config.REPO_ROOT, rel)
        dst = os.path.join(deploy, rel.replace("/", os.sep))
        if not os.path.exists(dst):
            result["missing"].append(rel)
        elif _sha(src) != _sha(dst):
            result["changed"].append(rel)
        else:
            result["identical"].append(rel)
    # Überzähliges nur unter languages/ betrachten
    lang_root = os.path.join(deploy, "languages")
    for root, _dirs, files in os.walk(lang_root):
        for fn in files:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, deploy).replace(os.sep, "/")
            if rel not in tracked_set:
                result["surplus"].append(rel)
    result["in_sync"] = not (result["changed"] or result["missing"] or result["surplus"])
    return result


def plan():
    st = status()
    return {"copy": sorted(st["changed"] + st["missing"]),
            "delete": sorted(st["surplus"]),
            "deploy_dir": st["deploy_dir"], "exists": st["exists"]}


def sync():
    """Repo -> Deploy kopieren, Überzähliges unter languages/ löschen."""
    st = status()
    if not st["exists"]:
        raise RuntimeError("Deploy-Ordner existiert nicht: %s" % st["deploy_dir"])
    copied, deleted = [], []
    for rel in st["changed"] + st["missing"]:
        src = os.path.join(config.REPO_ROOT, rel)
        dst = os.path.join(st["deploy_dir"], rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)
    for rel in st["surplus"]:
        if not rel.startswith("languages/"):
            continue  # Sicherheitsnetz: nur unter languages/ löschen
        os.remove(os.path.join(st["deploy_dir"], rel.replace("/", os.sep)))
        deleted.append(rel)
    stamp = {"time": time.time(), "copied": copied, "deleted": deleted}
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(os.path.join(config.DATA_DIR, "last_sync.json"), "w",
              encoding="utf-8") as f:
        json.dump(stamp, f, ensure_ascii=False, indent=2)
    return stamp
