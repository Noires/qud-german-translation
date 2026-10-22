"""HTTP-Routen der Szenen-Vorschau (In-Kontext-Prüfung)."""
from curator import convtree, grammar_emu, scenes
from curator.server import STORE, _manifest_english, route

try:
    from curator.review import REVIEW
except ImportError:
    REVIEW = None


def _lint_uids():
    try:
        from curator import lint
        return lint.get_engine(STORE).uids_with_findings(severity="error")
    except ImportError:
        return []


BUILDER = scenes.SceneBuilder(STORE, english_fn=_manifest_english, review=REVIEW,
                              lint_uids=_lint_uids)


_colors_cache = []


def _COLORS():
    if not _colors_cache:
        _colors_cache.append(scenes.load_colors())
    return _colors_cache[0]


def _opts(body):
    o = (body or {}).get("opts") or {}
    return {"lang": o.get("lang"), "roles": o.get("roles") or {},
            "pick": int(o.get("pick") or 0), "variant": int(o.get("variant") or 0),
            "choice_variants": o.get("choice_variants") or {}}


@route("GET", r"/api/scenes/meta")
def api_scenes_meta(m, q, body):
    return 200, {"available": convtree.TREE.available(), "base_dir": convtree.base_dir(),
                 "cols": scenes.cols(), "layouts": scenes.LAYOUTS,
                 "samples": grammar_emu.samples(), "colors": _COLORS()}


@route("GET", r"/api/scenes/conversations")
def api_scenes_conversations(m, q, body):
    STORE.refresh()
    if not convtree.TREE.available():
        return 200, {"available": False, "base_dir": convtree.base_dir(), "conversations": []}
    return 200, {"available": True, "filters": scenes.FILTERS,
                 "conversations": BUILDER.conversation_list(q.get("q", ""), q.get("filter", ""))}


@route("GET", r"/api/scenes/next")
def api_scenes_next(m, q, body):
    STORE.refresh()
    frm = (q.get("from") or "").split("/", 1)
    hit = BUILDER.next_scene(q.get("filter") or "open", frm[0] or None,
                             frm[1] if len(frm) > 1 else None)
    return 200, {"next": hit}


@route("GET", r"/api/scenes/graph")
def api_scenes_graph(m, q, body):
    STORE.refresh()
    g = BUILDER.graph(q.get("conversation", ""))
    if g is None:
        return 404, {"error": "Gespräch nicht gefunden."}
    return 200, g


@route("POST", r"/api/scenes/conversation")
def api_scene_conversation(m, q, body):
    STORE.refresh()
    body = body or {}
    sc = BUILDER.conversation(body.get("conversation", ""), body.get("node") or None,
                              _opts(body), body.get("drafts") or {})
    if sc is None:
        return 404, {"error": "Gespräch/Knoten nicht gefunden."}
    return 200, sc


@route("POST", r"/api/scenes/unit")
def api_scene_unit(m, q, body):
    body = body or {}
    sc = BUILDER.for_unit(body.get("uid", ""), _opts(body), body.get("layout") or None,
                          body.get("drafts") or {})
    if sc is None:
        return 404, {"error": "Einheit nicht gefunden — Index neu laden."}
    return 200, sc


@route("POST", r"/api/scenes/resolve")
def api_scene_resolve(m, q, body):
    body = body or {}
    return 200, grammar_emu.resolve(body.get("template", ""), ctx=body.get("roles") or {},
                                    pick=int(body.get("pick") or 0))


@route("POST", r"/api/scenes/samples")
def api_scene_samples(m, q, body):
    if not isinstance(body, dict) or not isinstance(body.get("objects"), dict):
        return 422, {"error": "objects/roles/tokens erwartet."}
    grammar_emu.save_samples(body)
    return 200, {"samples": grammar_emu.samples()}


# ------------------------------------------------------- Markierungen

from curator.flags import FLAGS  # noqa: E402

BUILDER.flags_fn = FLAGS.open_flags


def _context_findings():
    """uid -> [Befund] der Kontext-/Glossar-Regeln (K*/G*)."""
    from curator import context_lint
    out = {}
    for f in context_lint.findings(STORE):
        out.setdefault(f["uid"], []).append(f)
    return out


BUILDER.findings_fn = _context_findings


@route("POST", r"/api/scenes/rekey")
def api_scenes_rekey(m, q, body):
    """K1-Behebung: neuen Eintrag mit der AKTUELLEN englischen ID anlegen
    (gleicher Context, alter Wert). Der alte Eintrag bleibt (der Writer löscht
    nie) und wird als verwaist markiert."""
    from curator import context_lint, writer
    STORE.refresh()
    try:
        new, u = context_lint.rekey(STORE, (body or {}).get("uid", ""))
    except LookupError as ex:
        return 404, {"error": str(ex.args[0])}
    except ValueError as ex:
        return 422, {"error": str(ex)}
    except writer.WriteError as ex:
        return ex.status, {"error": str(ex)}
    FLAGS.set(u, "verwaist: ID veraltet, Neuanlage mit aktueller ID erfolgt (%s) — "
                 "diesen alten Eintrag entfernen" % new.uid, kind="orphan")
    return 200, {"unit": new.to_json(), "old": u.uid}


@route("GET", r"/api/flags")
def api_flags(m, q, body):
    STORE.refresh()
    return 200, {"flags": FLAGS.list(STORE)}


@route("POST", r"/api/flags")
def api_flags_set(m, q, body):
    body = body or {}
    STORE.refresh()
    u = STORE.get(body.get("uid", ""))
    if u is None:
        return 404, {"error": "Einheit nicht gefunden — Index neu laden."}
    if body.get("clear"):
        FLAGS.clear(u.uid)
        return 200, {"flag": None}
    if body.get("status"):
        try:
            return 200, {"flag": FLAGS.set_status(u.uid, body["status"])}
        except (KeyError, ValueError) as ex:
            return 422, {"error": str(ex.args[0])}
    return 200, {"flag": FLAGS.set(u, body.get("note", ""))}


@route("POST", r"/api/units/delete")
def api_unit_delete(m, q, body):
    """Verwaiste String-Einträge löschen — NUR wenn als verwaist markiert (K1-Neuanlage)
    und ein Nachfolger mit gleichem Context existiert."""
    from curator import writer
    body = body or {}
    STORE.refresh()
    u = STORE.get(body.get("uid", ""))
    if u is None:
        return 404, {"error": "Einheit nicht gefunden — Index neu laden."}
    flag = FLAGS.load().get(u.uid) or {}
    if flag.get("kind") != "orphan":
        return 422, {"error": "Löschen nur für verwaiste Einträge (nach „Neu anlegen mit aktueller ID“)."}
    succ = [x for x in STORE.all_units() if x.uid != u.uid and x.file == u.file
            and x.context == u.context and x.kind == u.kind]
    if not succ:
        return 422, {"error": "Kein Nachfolger mit gleichem Context gefunden — Löschen verweigert."}
    try:
        key = writer.delete_string_entry(STORE, u.uid, body.get("expect_value"))
    except writer.WriteError as ex:
        return ex.status, {"error": str(ex)}
    FLAGS.clear(u.uid)
    return 200, {"deleted": key, "successor": succ[0].uid}


@route("POST", r"/api/scenes/cols")
def api_scenes_cols(m, q, body):
    """Kalibrierte Spaltenbreite je Layout in build/curator/config.json speichern."""
    import json
    import os
    from curator import config
    body = body or {}
    layout, cols = body.get("layout"), body.get("cols")
    if layout not in scenes.LAYOUTS or not isinstance(cols, int) or not 20 <= cols <= 200:
        return 422, {"error": "layout (conversation/popup/messagelog/card) und cols (20–200) erwartet."}
    p = os.path.join(config.CURATOR_DIR, "config.json")
    data = {}
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    data.setdefault("preview_cols", {})[layout] = cols
    tmp = p + ".curator-tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, p)
    config.CFG.setdefault("preview_cols", {})[layout] = cols
    return 200, {"cols": scenes.cols()}
