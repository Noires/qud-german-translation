"""Zentrale Pfade und Einstellungen des QudDE Kurators.

Optionale Overrides in build/curator/config.json:
  { "game_example_dir": "...", "player_log": "...", "deploy_dir": "...", "port": 8371 }
"""
import json
import os

CURATOR_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(CURATOR_DIR, "..", ".."))
LANG_DE = os.path.join(REPO_ROOT, "languages", "lang-de")
CODE_CS = os.path.join(LANG_DE, "CODE", "VariableReplacers.de.cs")
GENDER_LEXICON = os.path.join(LANG_DE, "COQDE", "GenderLexicon.tsv")
VERBS_JSON = os.path.join(LANG_DE, "COQDE", "Verbs.json")
CURATOR_TESTS = os.path.join(LANG_DE, "COQDE", "CuratorTests.json")
DATA_DIR = os.path.join(CURATOR_DIR, "data")
STATIC_DIR = os.path.join(CURATOR_DIR, "static")

_DEFAULTS = {
    "game_example_dir": r"C:/Program Files (x86)/Steam/steamapps/common/Caves of Qud/CoQ_Data/StreamingAssets/Base/ExampleLanguage",
    "player_log": os.path.expandvars(r"%USERPROFILE%\AppData\LocalLow\Freehold Games\CavesOfQud\Player.log"),
    "deploy_dir": os.path.expandvars(r"%USERPROFILE%\AppData\LocalLow\Freehold Games\CavesOfQud\Mods\CavesOfQudGermanLang"),
    "port": 8371,
}


def load():
    cfg = dict(_DEFAULTS)
    p = os.path.join(CURATOR_DIR, "config.json")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


CFG = load()
