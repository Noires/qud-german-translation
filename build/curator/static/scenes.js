/* QudDE Kurator — Szenen-Vorschau (In-Kontext-Prüfung).
   Zeigt Übersetzungen in nachgebauten Qud-Fenstern (Gespräch, Popup,
   Nachrichtenlog, Look-Karte), zusammen mit den Nachbar-Bausteinen, mit
   emulierten Grammatik-Tokens (Server: grammar_emu) und Umbruch auf die
   Spaltenbreite. Klick auf einen Baustein öffnet ihn im Editor.
   Nutzt aus app.js: $, $$, api, esc, hi, panes, select, updateReviewPill. */
"use strict";

const SCENES = (() => {
  const S = {
    meta: null,
    opts: { roles: {}, pick: 0, variant: 0, choice_variants: {} },
    view: "de",            // de | en | both
    overlay: true,         // Status-Markierungen an den Bausteinen
    colsOverride: {},      // layout -> cols
    layout: null,          // Layout-Override für String-Szenen
    trail: [],             // [{conversation, node}]
    current: null,         // {kind:"conv", conversation, node} | {kind:"unit", uid}
    scene: null,
    sel: null,             // uid des Bausteins im Editor
    drafts: {},
    ctxUnit: null,         // Einheit des Übersetzungen-Tabs (Kontext-Panel)
  };
  const TS = "\u0001", TE = "\u0002";
  const STATUS_LABEL = {
    untranslated: "unübersetzt", translated: "übersetzt", checked: "geprüft",
    stale: "veraltet geprüft", lint: "Prüf-Befund (error)",
    staleid: "ID veraltet — Spiel zeigt Englisch",
  };

  async function ensureMeta() {
    if (S.meta) return S.meta;
    S.meta = await api("/api/scenes/meta");
    QUD.setColors(S.meta.colors);
    try { setGlossary(await api("/api/glossary")); } catch (e) { /* ohne Glossar */ }
    return S.meta;
  }

  /* Glossar-Begriffe in der gerenderten Bühne markieren (Textknoten-Ebene;
     Begriffe, die über einen Farbwechsel laufen, bleiben unmarkiert) */
  function setGlossary(g) {
    S.glossary = g;
    const alts = [];
    for (const t of (g && g.terms) || [])
      for (const f of [t.de, t.plural]) if (f) alts.push(f.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    S.termRx = alts.length
      ? new RegExp("(^|[^\\p{L}])(" + alts.sort((a, b) => b.length - a.length).join("|") + ")(?![\\p{L}])", "giu")
      : null;
  }

  function markTerms(root) {
    if (!root || !S.termRx) return;
    const terms = S.glossary.terms;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const hits = [];
    while (walker.nextNode()) {
      const n = walker.currentNode;
      if (n.parentElement.closest(".qslot") && n.nodeValue.trim()) hits.push(n);
    }
    for (const n of hits) {
      const txt = n.nodeValue;
      S.termRx.lastIndex = 0;
      if (!S.termRx.test(txt)) continue;
      S.termRx.lastIndex = 0;
      const frag = document.createDocumentFragment();
      let pos = 0, m;
      while ((m = S.termRx.exec(txt))) {
        const start = m.index + m[1].length;
        frag.append(txt.slice(pos, start));
        const t = terms.find(x => [x.de, x.plural].some(f => f && f.toLowerCase() === m[2].toLowerCase()));
        const span = document.createElement("span");
        span.className = "gterm";
        span.textContent = m[2];
        if (t) span.title = `Glossar: ${t.en} → ${t.de}${t.gender ? " (" + t.gender + ")" : ""}`
          + `${t.plural ? ", Pl. " + t.plural : ""}${t.note ? " — " + t.note : ""}`;
        frag.append(span);
        pos = start + m[2].length;
      }
      frag.append(txt.slice(pos));
      n.replaceWith(frag);
    }
  }

  /* ------------------------------------------------ Rendering */

  const rawRender = s => {
    const tokens = [];
    const text = String(s || "").replace(/=([^=\s][^=]*?)=/g, m => {
      tokens.push({ src: m, out: m, how: "raw" });
      return TS + m + TE;
    });
    return { text, tokens };
  };

  function slotRender(slot, lang) {
    if (lang === "en" || !slot.de) return rawRender(slot.en);
    return slot.render;
  }

  /* Baustein + angehängte Tags (z. B. {{K|[Ende]}}) zu einem Render verbinden */
  function joinRender(a, tags, lang) {
    let text = a.text, tokens = a.tokens.slice();
    for (const t of tags || []) {
      const r = slotRender(t, lang);
      text += " " + r.text;
      tokens = tokens.concat(r.tokens);
    }
    return { text, tokens };
  }

  function colsFor(layout, sc) {
    return S.colsOverride[layout] || sc.cols || 60;
  }

  function slotHtml(slot, render, cols, extraCls, fg) {
    if (!slot) return "";
    const r = QUD.toHtml(render, { cols, fg });
    const cls = ["qslot", "st-" + slot.status, extraCls || ""];
    if (slot.uid && slot.uid === S.sel) cls.push("sel");
    if (slot.uid && slot.uid === S.ctxFocus) cls.push("focus");
    if (slot.draft) cls.push("draft");
    if (slot.flag) cls.push("flagged");
    if ((slot.findings || []).some(f => f.rule !== "K1" && f.severity !== "info")) cls.push("hasfind");
    const key = slot.uid ? `data-uid="${esc(slot.uid)}"` : `data-path="${esc(slot.path || "")}"`;
    return `<div class="${cls.join(" ")}" ${key} title="${esc(STATUS_LABEL[slot.status] || slot.status)}${slot.match === "id" ? " · nur über die ID gefunden (anderer Context)" : ""}">${r.html}</div>`;
  }

  function sceneHtml(sc, lang) {
    const cols = colsFor(sc.layout, sc);
    if (sc.layout === "conversation") return convHtml(sc, lang, cols);
    if (sc.layout === "popup") return popupHtml(sc, lang, cols);
    if (sc.layout === "messagelog") return logHtml(sc, lang, cols);
    if (sc.layout === "book") return bookHtml(sc, lang, cols);
    if (sc.layout === "journal") return journalHtml(sc, lang, cols);
    if (sc.layout === "spicelist") return spiceHtml(sc, lang, cols);
    return cardHtml(sc, lang, cols);
  }

  /* Buch: eine Seite sichtbar (die mit dem Fokus, sonst S.bookPage), Blättern ◀ ▶ */
  function bookHtml(sc, lang, cols) {
    const n = sc.body.length;
    if (sc._page === undefined) {
      const f = sc.body.findIndex(s => s.uid === sc.focus);
      sc._page = f >= 0 ? f : 0;
    }
    const p = Math.min(Math.max(sc._page, 0), Math.max(n - 1, 0));
    const page = sc.body[p];
    const title = sc.title ? slotHtml(sc.title, slotRender(sc.title, lang), cols, "title", "W") : "";
    return `<div class="qscreen qbook" style="--cols:${cols}">
      <div class="qcardtitle">${title || `<div class="qline mini">${esc(sc.group || "")}</div>`}</div>
      <div class="qbody">${page ? slotHtml(page, slotRender(page, lang), cols, "", "y") : ""}</div>
      <div class="qpager"><span class="qnav" data-page="-1">◀</span> Seite ${p + 1} / ${n} <span class="qnav" data-page="1">▶</span></div>
    </div>`;
  }

  /* Quest-Journal: Titel + beschriftete Abschnitte (Erfolg, Schritte …) */
  function journalHtml(sc, lang, cols) {
    const title = sc.title ? slotHtml(sc.title, slotRender(sc.title, lang), cols, "title", "W")
      : `<div class="qline" style="color:${QUD.PALETTE.W}">${esc((sc.group || "").replace(/^quest\[|\]$/g, ""))}</div>`;
    const body = sc.body.map(s => `${s.label ? `<div class="qline qlabel">${esc(s.label)}</div>` : ""}${slotHtml(s, slotRender(s, lang), cols, "", "y")}`)
      .join('<div class="qline">&nbsp;</div>');
    return `<div class="qscreen qjournal" style="--cols:${cols}">
      <div class="qcardtitle">${title}</div><div class="qbody">${body}</div></div>`;
  }

  /* Gewürz-Liste (HistorySpice): alle Varianten eines Eintrags, Fokus hervorgehoben */
  function spiceHtml(sc, lang, cols) {
    const rows = sc.body.map(s => `<div class="qlogline${s.uid === sc.focus ? "" : " ctx"}"><span class="qlogmark">${esc(s.label || "•")}</span>${slotHtml(s, slotRender(s, lang), cols - 5, "", "y")}</div>`).join("");
    return `<div class="qscreen qlog" style="--cols:${cols}">
      <div class="qline qlabel">${esc(sc.group || "")}</div>${rows}</div>`;
  }

  function convHtml(sc, lang, cols) {
    let n = 0;
    const choices = sc.choices.map(c => {
      const global = c.origin.startsWith("global:");
      if (global && !S.showGlobal) return "";
      n++;
      const r = joinRender(slotRender(c, lang), c.tags, lang);
      const num = `<span class="qnum" data-goto="${esc(c.target || "")}" title="${c.target ? "Antwort wählen → " + esc(c.target) : "kein Ziel"}">[${n}]</span>`;
      const vari = c.variants > 1 ? `<span class="qvar" data-cv="${esc(c.id)}" title="Antwort-Variante ${c.variant + 1}/${c.variants} — weiter">↻</span>` : "";
      return `<div class="qchoice${global ? " global" : ""}">${num}${slotHtml(c, r, cols - 4, "", "y")}${vari}</div>`;
    }).join("");
    return `<div class="qscreen qconv" style="--cols:${cols}">
      <div class="qtitlebar"><span>${esc(sc.speaker)}</span></div>
      <div class="qbody">${slotHtml(sc.npc, slotRender(sc.npc || {}, lang), cols, "npc", "y")}</div>
      <div class="qsep"></div>
      <div class="qchoices">${choices || '<div class="qline mini">— keine Antworten —</div>'}</div>
    </div>`;
  }

  function popupHtml(sc, lang, cols) {
    return `<div class="qscreen qpopup" style="--cols:${cols}">
      <div class="qpopframe">
        <div class="qbody center">${slotHtml(sc.main, slotRender(sc.main, lang), cols, "", "y")}</div>
        <div class="qbuttons"><span class="qbtn"><span style="color:${QUD.PALETTE.W}">[Leer]</span> Fortfahren</span></div>
      </div></div>`;
  }

  function logHtml(sc, lang, cols) {
    const lines = (sc.lines.length ? sc.lines : [sc.main]).map(s =>
      `<div class="qlogline${s.uid === sc.focus ? "" : " ctx"}"><span class="qlogmark">::</span>${slotHtml(s, slotRender(s, lang), cols - 3, "", "y")}</div>`).join("");
    return `<div class="qscreen qlog" style="--cols:${cols}">${lines}</div>`;
  }

  function cardHtml(sc, lang, cols) {
    const title = sc.title ? slotHtml(sc.title, slotRender(sc.title, lang), cols, "title", "Y") : "";
    const body = sc.body.map(s => slotHtml(s, slotRender(s, lang), cols, "", "y")).join('<div class="qline">&nbsp;</div>');
    return `<div class="qscreen qcard" style="--cols:${cols}">
      <div class="qcardtitle">${title || `<div class="qline mini">${esc(sc.group || "")}</div>`}</div>
      <div class="qbody">${body}</div></div>`;
  }

  /* Alle Bausteine einer Szene (für Liste, Prüfen, Befunde) */
  function slotsOf(sc) {
    if (!sc) return [];
    if (sc.layout === "conversation") {
      const out = sc.npc ? [sc.npc] : [];
      for (const c of sc.choices) {
        if (c.origin.startsWith("global:") && !S.showGlobal) continue;
        out.push(c, ...(c.tags || []));
      }
      return out;
    }
    if (["card", "book", "journal", "spicelist"].includes(sc.layout)) return [sc.title, ...sc.body].filter(Boolean);
    if (sc.layout === "messagelog" && sc.lines.length) return sc.lines;
    return [sc.main];
  }

  function issuesOf(slot) {
    const out = [];
    const toks = (slot.render && slot.render.tokens) || [];
    const unk = toks.filter(t => t.how === "unknown");
    const en = toks.filter(t => t.how === "en");
    if (unk.length) out.push(`<span class="badge warning" title="${esc(unk.map(t => t.src).join(" "))}">${unk.length}× Token unbekannt</span>`);
    if (en.length) out.push(`<span class="badge error" title="${esc(en.map(t => t.src).join(" "))}">${en.length}× englischer Fallback</span>`);
    if (slot.de && slot.en) {
      const a = QUD.visible(rawRender(slot.en).text).length, b = QUD.visible(slot.render.text).length;
      if (a > 0) {
        const pct = Math.round(100 * (b - a) / a);
        if (Math.abs(pct) >= 40) out.push(`<span class="badge info" title="sichtbare Länge DE ggü. EN">${pct > 0 ? "+" : ""}${pct} %</span>`);
      }
    }
    if (slot.match === "staleid") out.push('<span class="badge error" title="Die englische ID des Eintrags stimmt nicht mehr mit dem Spieltext überein — der deutsche Wert wird nie angezeigt">ID veraltet</span>');
    if (slot.match === "id") out.push('<span class="badge info" title="kein Eintrag mit diesem Context — Spiel nutzt den Wert nur, wenn es ID-Fallback hat">nur ID</span>');
    for (const f of slot.findings || []) {
      if (f.rule === "K1") continue; // als „ID veraltet" schon oben
      out.push(`<span class="badge ${f.severity === "info" ? "info" : "warning"}" title="${esc(f.message)}">${esc(f.rule)}</span>`);
    }
    if (slot.flag) out.push(`<span class="badge warning" title="${esc(slot.flag.note || "")}">⚑ markiert</span>`);
    return out.join(" ");
  }

  function slotListHtml(sc) {
    return slotsOf(sc).map(s => `
      <div class="slotrow st-${esc(s.status)}${s.uid === S.sel ? " sel" : ""}" ${s.uid ? `data-uid="${esc(s.uid)}"` : `data-path="${esc(s.path || "")}"`}>
        <span class="dot"></span>
        <span class="role">${esc(s.role)}</span>
        <span class="txt">${esc(QUD.visible((s.de ? s.render : rawRender(s.en)).text).slice(0, 90))}</span>
        <span class="iss">${issuesOf(s)}</span>
      </div>`).join("");
  }

  function stageHtml(sc) {
    if (S.view === "both")
      return `<div class="qpair"><div><div class="mini">Englisch (Vorlage)</div>${sceneHtml(sc, "en")}</div>
              <div><div class="mini">Deutsch (emuliert)</div>${sceneHtml(sc, "de")}</div></div>`;
    return sceneHtml(sc, S.view);
  }

  /* ------------------------------------------------ Steuerleiste */

  function controlsHtml(sc, inCtx) {
    const meta = S.meta, sm = meta.samples;
    const objOpts = (sel, filt) => Object.entries(sm.objects).filter(([, o]) => filt(o))
      .map(([id, o]) => `<option value="${esc(id)}" ${id === sel ? "selected" : ""}>${esc(o.label || id)}</option>`).join("");
    const role = r => S.opts.roles[r] || sm.roles[r];
    const notPart = o => !o.part;
    let extra = "";
    if (sc && sc.layout === "conversation") {
      if (sc.variants.length > 1 && !inCtx)
        extra += `<span class="ctl">Text-Variante <button class="ghost sm" data-act="var-">◀</button>
          ${sc.variant + 1}/${sc.variants.length} <button class="ghost sm" data-act="var+">▶</button></span>`;
      if (sc.siblings.length > 1 && !inCtx)
        extra += `<label class="ctl">Knoten <select data-act="sibling">${sc.siblings.map(s =>
          `<option value="${esc(s.id)}" ${s.id === sc.node ? "selected" : ""} title="${esc(condText(s.cond))}">${esc(s.id)}${Object.keys(s.cond).length ? " · " + esc(condText(s.cond)).slice(0, 50) : ""}</option>`).join("")}</select></label>`;
      extra += `<label class="ctl chk"><input type="checkbox" data-act="global" ${S.showGlobal ? "checked" : ""}> Basis-Antworten (Handel, Wasserritual …)</label>`;
    }
    if (sc && (sc.layout === "popup" || sc.layout === "messagelog"))
      extra += `<label class="ctl">Darstellung <select data-act="layout">
        <option value="popup" ${sc.layout === "popup" ? "selected" : ""}>Popup</option>
        <option value="messagelog" ${sc.layout === "messagelog" ? "selected" : ""}>Nachrichtenlog</option></select></label>`;
    const cols = sc ? colsFor(sc.layout, sc) : "";
    return `
      <div class="seg" data-act="view">
        <button data-v="de" class="${S.view === "de" ? "on" : ""}">DE</button>
        <button data-v="en" class="${S.view === "en" ? "on" : ""}">EN</button>
        <button data-v="both" class="${S.view === "both" ? "on" : ""}">EN | DE</button>
      </div>
      <label class="ctl">subject <select data-role="subject">${objOpts(role("subject"), notPart)}</select></label>
      <label class="ctl">object <select data-role="object">${objOpts(role("object"), notPart)}</select></label>
      <label class="ctl">Spieler <select data-role="player">${objOpts(role("player"), notPart)}</select></label>
      <button class="ghost sm" data-act="pick" title="Zufallsauswahl der Gewürz-Texte (=spice…!random=) neu würfeln">⟳ Würfeln</button>
      ${inCtx ? "" : `<button class="ghost sm" data-act="calib" title="Spiel-Screenshot über die Vorschau legen und die Spaltenbreite angleichen">📷 Kalibrieren</button>`}
      <label class="ctl">Breite <input type="number" min="20" max="160" value="${cols}" data-act="cols" style="width:56px"></label>
      <label class="ctl chk"><input type="checkbox" data-act="overlay" ${S.overlay ? "checked" : ""}> Status zeigen</label>
      ${extra}`;
  }

  function condText(c) {
    return Object.entries(c || {}).map(([k, v]) => k + "=" + v).join(", ");
  }

  function legendHtml() {
    return `<div class="legend mini">
      <span><i class="lg st-untranslated"></i>unübersetzt</span><span><i class="lg st-translated"></i>übersetzt</span>
      <span><i class="lg st-checked"></i>geprüft</span><span><i class="lg st-stale"></i>veraltet</span>
      <span><i class="lg st-lint"></i>Befund</span><span><i class="lg st-staleid"></i>ID veraltet</span><span><i class="lg sel"></i>im Editor</span>
      · Tokens: <span class="qtok how-emu">emuliert</span> <span class="qtok how-approx">angenähert</span>
      <span class="qtok how-sample">Stichprobe</span> <span class="qtok how-spice">Gewürz</span>
      <span class="qtok how-unknown">unbekannt</span> <span class="qtok how-en">engl. Fallback</span>
      · <span class="overflow-demo">roter Rand</span>&nbsp;= Wort länger als Zeile</div>`;
  }

  /* ------------------------------------------------ Szenen-Tab */

  async function loadPane() {
    const pane = $("#pane-szenen");
    try { await ensureMeta(); }
    catch (e) { pane.innerHTML = '<div class="placeholder">' + esc(e.message) + "</div>"; return; }
    if (!pane.dataset.ready) {
      pane.dataset.ready = "1";
      pane.innerHTML = `
        <div class="scmaster">
          <div class="searchbar">
            <input type="text" id="sc-q" placeholder="Gespräch suchen … (Enter)" autocomplete="off">
            <select id="sc-filter" title="Gespräche filtern">
              <option value="">alle</option>
              <option value="open">offen (unübersetzt/ungeprüft)</option>
              <option value="untranslated">unübersetzt</option>
              <option value="unchecked">ungeprüft</option>
              <option value="findings">mit Befund</option>
              <option value="address">Anrede-Mix (K2)</option>
              <option value="staleid">ID veraltet (K1)</option>
              <option value="flagged">markiert ⚑</option>
            </select>
            <select id="sc-sort"><option value="name">Name</option><option value="open">meiste offen</option></select>
            <button class="primary sm" id="sc-next" title="Nächste Szene, die zum Filter passt (Taste N)">Nächste ▶</button>
            <span class="count" id="sc-count"></span>
          </div>
          <div class="unitlist" id="sc-list"></div>
        </div>
        <div class="scstage">
          <div class="sctoolbar" id="sc-toolbar"></div>
          <div class="sctrail mini" id="sc-trail"></div>
          <details class="scgraph" id="sc-graphbox"><summary>Knotenkarte <span class="mini" id="sc-graphinfo"></span></summary>
            <div id="sc-graph"><div class="placeholder">Gespräch wählen.</div></div></details>
          <div class="sccalib" id="sc-calib" hidden>
            <b>Kalibrieren:</b> Screenshot derselben Szene aus dem Spiel laden (bleibt lokal im Browser),
            mit Größe/Deckkraft/Versatz ausrichten, dann „Breite“ oben anpassen, bis die Zeilenumbrüche übereinstimmen.
            <div class="btnrow">
              <input type="file" accept="image/*" id="sc-cal-file">
              <label class="mini">Größe <input type="range" id="sc-cal-scale" min="0.2" max="1.5" step="0.01" value="0.6"></label>
              <label class="mini">Deckkraft <input type="range" id="sc-cal-op" min="0" max="1" step="0.05" value="0.45"></label>
              <label class="mini">x <input type="number" id="sc-cal-x" value="0" style="width:60px"></label>
              <label class="mini">y <input type="number" id="sc-cal-y" value="0" style="width:60px"></label>
              <button class="primary sm" id="sc-cal-save">Breite für dieses Layout speichern</button>
              <span class="mini" id="sc-cal-msg"></span>
            </div>
          </div>
          <div class="sccalwrap"><img id="sc-cal-img" alt="" hidden>
          <div class="scview ${S.overlay ? "overlay" : ""}" id="sc-view"><div class="placeholder">Gespräch links wählen — oder im Tab „Übersetzungen“ einen Eintrag öffnen und dort „Im Kontext“ nutzen.</div></div>
          </div>
          ${legendHtml()}
          <div class="scactions btnrow" id="sc-actions"></div>
          <div class="scslots" id="sc-slots"></div>
        </div>
        <div class="sceditor" id="sc-editor"><div class="placeholder">Baustein in der Vorschau anklicken.</div></div>`;
      $("#sc-q").addEventListener("keydown", e => { if (e.key === "Enter") loadList(); });
      for (const id of ["sc-filter", "sc-sort"]) {
        try { const v = localStorage.getItem(id); if (v !== null) $("#" + id).value = v; } catch (e) { /* egal */ }
        $("#" + id).addEventListener("change", () => {
          try { localStorage.setItem(id, $("#" + id).value); } catch (e) { /* egal */ }
          loadList();
        });
      }
      $("#sc-next").onclick = () => nextScene();
      const gb = $("#sc-graphbox");
      try { gb.open = localStorage.getItem("sc-graph") !== "0"; } catch (e) { gb.open = true; }
      gb.addEventListener("toggle", () => {
        try { localStorage.setItem("sc-graph", gb.open ? "1" : "0"); } catch (e) { /* egal */ }
        if (gb.open && S.current && S.current.kind === "conv") loadGraph(S.current.conversation);
      });
      document.addEventListener("keydown", onKey);
      wireCalibration();
      wireStage($("#sc-view"), uid => selectSlot(uid), target => gotoNode(target), refresh);
      wireStage($("#sc-slots"), uid => selectSlot(uid), null, refresh);
      wireToolbar($("#sc-toolbar"), () => refresh(), () => S.scene);
      loadList();
    }
  }

  async function loadList() {
    const list = $("#sc-list");
    list.innerHTML = '<div class="placeholder">Lade …</div>';
    let d;
    const qs = new URLSearchParams({ q: $("#sc-q").value, filter: $("#sc-filter").value });
    try { d = await api("/api/scenes/conversations?" + qs); }
    catch (e) { list.innerHTML = '<div class="placeholder">' + esc(e.message) + "</div>"; return; }
    if (!d.available) {
      list.innerHTML = `<div class="msg warn">Spiel-Gespräche nicht gefunden unter <code>${esc(d.base_dir)}</code> —
        <code>game_base_dir</code> in build/curator/config.json setzen.</div>`;
      return;
    }
    const convs = d.conversations.slice();
    if ($("#sc-sort").value === "open") convs.sort((a, b) => b.open - a.open || a.id.localeCompare(b.id));
    $("#sc-count").textContent = convs.length + " Gespräche";
    list.innerHTML = convs.map(c => {
      const pt = c.texts ? 100 * c.translated / c.texts : 100;
      const pc = c.texts ? 100 * c.checked / c.texts : 0;
      const rules = c.rules.filter(r => r !== "K4");
      const cur = S.current && S.current.conversation === c.id;
      return `<div class="unitrow${cur ? " sel" : ""}" data-conv="${esc(c.id)}">
        <span class="de">${esc(c.id)}</span>
        <span class="badges">${rules.map(r => `<span class="badge ${r === "K1" ? "error" : "warning"}" title="${esc(ruleTitle(r))}">${esc(r)}</span>`).join("")}
          ${c.flagged ? `<span class="badge warning" title="markiert">⚑${c.flagged}</span>` : ""}
          <span class="filebadge" title="übersetzt / geprüft / gesamt">${c.translated}/${c.checked}/${c.texts}</span></span>
        <span class="en"><span class="bar thin two" title="übersetzt ${Math.floor(pt)} % · geprüft ${Math.floor(pc)} %">
          <i style="width:${pt}%"></i><b style="width:${pc}%"></b></span></span>
      </div>`;
    }).join("") || '<div class="placeholder">Keine Gespräche für diesen Filter.</div>';
    $$("#sc-list .unitrow").forEach(r => r.addEventListener("click", () => {
      S.trail = [];
      openConversation(r.dataset.conv, null);
    }));
  }

  async function openConversation(conv, node, opts) {
    S.current = { kind: "conv", conversation: conv, node };
    if (!opts || !opts.keepVariant) { S.opts.variant = 0; S.opts.choice_variants = {}; }
    await refresh();
    if (S.scene) {
      const last = S.trail[S.trail.length - 1];
      if (!last || last.node !== S.scene.node || last.conversation !== conv)
        S.trail.push({ conversation: conv, node: S.scene.node });
      S.current.node = S.scene.node;
      renderTrail();
    }
    $$("#sc-list .unitrow").forEach(r => r.classList.toggle("sel", r.dataset.conv === conv));
    if (S.graph && S.graph.conversation === conv) paintGraph(); else loadGraph(conv);
    setHash("conv/" + encodeURIComponent(conv) + "/" + encodeURIComponent(S.current.node || ""));
  }

  /* Deep-Links: #szenen/conv/<Gespräch>/<Knoten> bzw. #szenen/unit/<uid> */
  function setHash(h) {
    try { history.replaceState(null, "", "#szenen/" + h); } catch (e) { /* egal */ }
  }

  async function fromHash() {
    const u = /^#unit\/([0-9a-f]{16})$/.exec(location.hash);
    if (u) { select(u[1]); return; }
    const tab = /^#tab\/(\w+)$/.exec(location.hash);
    if (tab) { const b = $(`#tabs button[data-tab="${tab[1]}"]`); if (b) b.click(); return; }
    const m = /^#szenen\/(conv|unit)\/([^/]*)(?:\/(.*))?$/.exec(location.hash);
    if (!m) return;
    if (m[1] === "unit") { openUnit(m[2]); return; }
    $('#tabs button[data-tab="szenen"]').click();
    await loadPane();
    openConversation(decodeURIComponent(m[2]), m[3] ? decodeURIComponent(m[3]) : null);
  }

  async function openUnit(uid) {
    $('#tabs button[data-tab="szenen"]').click();
    await loadPane();
    S.trail = [];
    S.current = { kind: "unit", uid };
    S.sel = uid;
    await refresh();
    if (S.scene && S.scene.layout === "conversation") {
      S.current = { kind: "conv", conversation: S.scene.conversation, node: S.scene.node };
      S.trail = [{ conversation: S.scene.conversation, node: S.scene.node }];
      renderTrail();
    }
    if (uid) selectSlot(uid);
    setHash("unit/" + uid);
  }

  function renderTrail() {
    const el = $("#sc-trail");
    if (!el) return;
    el.innerHTML = S.trail.map((t, i) =>
      `<a href="#" data-i="${i}">${esc(t.conversation)}·${esc(t.node)}</a>`).join(" › ");
    $$("a", el).forEach(a => a.onclick = e => {
      e.preventDefault();
      const i = +a.dataset.i;
      const t = S.trail[i];
      S.trail = S.trail.slice(0, i);
      openConversation(t.conversation, t.node);
    });
  }

  async function fetchScene(cur, drafts) {
    const opts = { ...S.opts };
    if (cur.kind === "conv")
      return api("/api/scenes/conversation", post({ conversation: cur.conversation, node: cur.node, opts, drafts }));
    return api("/api/scenes/unit", post({ uid: cur.uid, layout: S.layout, opts, drafts }));
  }

  const post = body => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

  async function refresh() {
    if (!S.current) return;
    const view = $("#sc-view");
    let sc;
    try { sc = await fetchScene(S.current, S.drafts); }
    catch (e) { if (view) view.innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; return; }
    S.scene = sc;
    paint();
  }

  function paint() {
    const sc = S.scene;
    if (!sc || !$("#sc-view")) return;
    const keepFocus = S.ctxFocus;
    S.ctxFocus = null;
    $("#sc-toolbar").innerHTML = controlsHtml(sc);
    const gb = $("#sc-graphbox");
    if (gb) gb.hidden = sc.layout !== "conversation";
    $("#sc-view").innerHTML = stageHtml(sc);
    $("#sc-view").classList.toggle("overlay", S.overlay);
    markTerms($("#sc-view"));
    $("#sc-slots").innerHTML = `<h2>Bausteine dieser Szene</h2>` + slotListHtml(sc);
    const slots = slotsOf(sc).filter(s => s.uid);
    const open = slots.filter(s => s.status !== "checked");
    $("#sc-actions").innerHTML = slots.length
      ? `<button class="ghost" id="sc-checkall" ${open.length ? "" : "disabled"}>Szene als geprüft markieren (${open.length} offen)</button>
         <span class="mini">markiert alle übersetzten Bausteine dieser Ansicht in reviewed.json</span>` : "";
    const b = $("#sc-checkall");
    if (b) b.onclick = () => checkAll(open);
    S.ctxFocus = keepFocus;
  }

  async function checkAll(slots) {
    if (Object.keys(S.drafts).length &&
        !confirm("Es gibt ungespeicherte Entwürfe — geprüft werden die GESPEICHERTEN Werte. Fortfahren?")) return;
    let summary = null;
    for (const s of slots) {
      const r = await api("/api/review", post({ uid: s.uid, checked: true }));
      summary = r.summary;
    }
    if (summary) updateReviewPill(summary);
    refresh();
  }

  async function gotoNode(target) {
    if (!target || !S.scene || S.scene.layout !== "conversation") return;
    if (target === "End") { flash("Ende des Gesprächs (End)."); return; }
    if (!S.scene.nodes.includes(target) && !(await nodeExists(S.scene.conversation, target))) {
      flash("Ziel „" + target + "“ ist dynamisch (C#) oder in einer anderen Konversation — nicht navigierbar.");
      return;
    }
    openConversation(S.scene.conversation, target);
  }

  async function nodeExists(conv, node) {
    try { await api("/api/scenes/conversation", post({ conversation: conv, node, opts: S.opts })); return true; }
    catch (e) { return false; }
  }

  function flash(msg) {
    const el = $("#sc-actions");
    if (!el) return;
    const d = document.createElement("div");
    d.className = "msg warn";
    d.textContent = msg;
    el.prepend(d);
    setTimeout(() => d.remove(), 3500);
  }

  /* Klicks in der Bühne: Baustein -> Editor; [n] -> navigieren; ↻ -> Variante */
  function wireStage(el, onSlot, onGoto, rerender) {
    el.addEventListener("click", e => {
      const nav = e.target.closest(".qnav");
      if (nav) {
        const sc = el.id === "ctx-view" ? S.ctxScene : S.scene;
        if (sc) { sc._page = (sc._page || 0) + (+nav.dataset.page); el.id === "ctx-view" ? repaintCtx() : paint(); }
        return;
      }
      const num = e.target.closest(".qnum");
      if (num && onGoto) { onGoto(num.dataset.goto); return; }
      const cv = e.target.closest(".qvar");
      if (cv) {
        const id = cv.dataset.cv;
        S.opts.choice_variants[id] = (S.opts.choice_variants[id] || 0) + 1;
        rerender();
        return;
      }
      const slot = e.target.closest("[data-uid]");
      if (slot) { onSlot(slot.dataset.uid); return; }
      const miss = e.target.closest("[data-path]");
      if (miss && S.scene && el.id !== "ctx-view") showMissing(miss.dataset.path);
    });
  }

  function wireToolbar(el, after, getScene) {
    el.addEventListener("click", e => {
      const v = e.target.closest("[data-v]");
      if (v) { S.view = v.dataset.v; after(); return; }
      const a = e.target.closest("[data-act]");
      if (!a || a.tagName === "SELECT" || a.tagName === "INPUT") return;
      if (a.dataset.act === "pick") { S.opts.pick++; after(); }
      if (a.dataset.act === "calib") { const c = $("#sc-calib"); if (c) c.hidden = !c.hidden; }
      if (a.dataset.act === "var+" || a.dataset.act === "var-") {
        const sc = getScene();
        const n = sc.variants.length;
        S.opts.variant = (sc.variant + (a.dataset.act === "var+" ? 1 : n - 1)) % n;
        after();
      }
    });
    el.addEventListener("change", e => {
      const t = e.target;
      if (t.dataset.role) { S.opts.roles[t.dataset.role] = t.value; after(); return; }
      const act = t.dataset.act;
      if (act === "cols") { const sc = getScene(); if (sc) S.colsOverride[sc.layout] = Math.max(20, +t.value || 60); after(); }
      if (act === "overlay") { S.overlay = t.checked; after(); }
      if (act === "global") { S.showGlobal = t.checked; after(); }
      if (act === "layout") { S.layout = t.value; after(); }
      if (act === "sibling" && S.current && S.current.kind === "conv") {
        S.current.node = t.value; S.opts.variant = 0; after();
      }
    });
  }

  /* ------------------------------------------------ Review-Workflow */

  const RULE_TITLES = {
    K1: "ID veraltet — Wert greift nie", K2: "Anrede weicht von der Richtlinie ab",
    K3: "konjde ohne Subjekt", K4: "Possessiv ohne Annotation",
    G1: "Glossar-Begriff fehlt", G2: "Artikel passt nicht zum Glossar-Genus",
  };
  const ruleTitle = r => RULE_TITLES[r] || r;

  async function nextScene() {
    const filt = $("#sc-filter").value || "open";
    const from = S.current && S.current.kind === "conv" ? S.current.conversation + "/" + S.current.node : "";
    let d;
    try { d = await api("/api/scenes/next?" + new URLSearchParams({ filter: filt, from })); }
    catch (e) { flash(e.message); return; }
    if (!d.next) { flash("Keine weitere Szene für diesen Filter — alles erledigt."); return; }
    if (!S.current || S.current.conversation !== d.next.conversation) S.trail = [];
    S.sel = null;
    openConversation(d.next.conversation, d.next.node);
  }

  async function loadGraph(conv) {
    const box = $("#sc-graphbox");
    if (!box || !box.open) { S.graph = null; return; }
    try { S.graph = await api("/api/scenes/graph?conversation=" + encodeURIComponent(conv)); }
    catch (e) { $("#sc-graph").innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; return; }
    paintGraph();
  }

  /* Ebenen-Layout: Spalte = BFS-Tiefe ab den Startknoten, unerreichbare
     Knoten in einer eigenen letzten Spalte; Kanten als SVG-Kurven. */
  function paintGraph() {
    const g = S.graph, el = $("#sc-graph");
    if (!g || !el) return;
    const cols = {};
    for (const n of g.nodes) {
      const k = n.depth === null ? "x" : n.depth;
      (cols[k] = cols[k] || []).push(n);
    }
    const keys = Object.keys(cols).filter(k => k !== "x").map(Number).sort((a, b) => a - b);
    if (cols.x) keys.push("x");
    const W = 150, H = 24, GX = 44, GY = 6;
    const pos = {};
    keys.forEach((k, ci) => cols[k].forEach((n, ri) => { pos[n.id] = { x: ci * (W + GX), y: ri * (H + GY) }; }));
    const width = keys.length * (W + GX), height = Math.max(1, ...keys.map(k => cols[k].length)) * (H + GY) + 40;
    const cur = S.current && S.current.node;
    const edges = g.edges.map(e => {
      const a = pos[e.from], b = pos[e.to];
      if (!a || !b) return "";
      const hot = (e.from === cur || e.to === cur ? " hot" : "") + (e.global ? " glob" : "");
      if (b.x <= a.x) { // Rück-/Querkante: Bogen unter den Kästen
        const ya = a.y + H, yb = b.y + H;
        return `<path class="gedge back${hot}" d="M${a.x + W / 2},${ya} C${a.x + W / 2},${Math.max(ya, yb) + 30} ${b.x + W / 2},${Math.max(ya, yb) + 30} ${b.x + W / 2},${yb}"/>`;
      }
      const x1 = a.x + W, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2;
      return `<path class="gedge${hot}" d="M${x1},${y1} C${x1 + GX / 2},${y1} ${x2 - GX / 2},${y2} ${x2},${y2}"/>`;
    }).join("");
    const boxes = g.nodes.map(n => {
      const p = pos[n.id];
      const tip = `${n.id} — ${n.translated}/${n.texts} übersetzt, ${n.checked} geprüft`
        + (n.rules.length ? " · " + n.rules.join(", ") : "")
        + (n.depth === null ? " · kein Weg vom Start" : "")
        + (Object.keys(n.cond).length ? " · " + condText(n.cond) : "");
      return `<div class="gnode st-${esc(n.status)}${n.id === cur ? " cur" : ""}${n.depth === null ? " unreach" : ""}"
        data-node="${esc(n.id)}" style="left:${p.x}px;top:${p.y}px;width:${W}px;height:${H}px"
        title="${esc(tip)}">${esc(n.id)}${n.ends ? " ⏎" : ""}</div>`;
    }).join("");
    const unreach = g.nodes.filter(n => n.depth === null).length;
    $("#sc-graphinfo").textContent = `— ${g.nodes.length} Knoten, ${g.edges.length} Übergänge`
      + (unreach ? `, ${unreach} ohne Weg vom Start` : "");
    el.innerHTML = `<div class="gwrap" style="width:${width}px;height:${height}px">
      <svg width="${width}" height="${height}">${edges}</svg>${boxes}</div>`;
    $$(".gnode", el).forEach(b => b.onclick = () => openConversation(g.conversation, b.dataset.node));
  }

  /* Kalibrieren: Screenshot als halbtransparente Ebene über der Bühne */
  function wireCalibration() {
    const img = $("#sc-cal-img");
    const apply = () => {
      img.style.opacity = $("#sc-cal-op").value;
      img.style.transform = `translate(${+$("#sc-cal-x").value || 0}px, ${+$("#sc-cal-y").value || 0}px) scale(${$("#sc-cal-scale").value})`;
    };
    $("#sc-cal-file").addEventListener("change", e => {
      const f = e.target.files[0];
      if (!f) return;
      if (img.src) URL.revokeObjectURL(img.src);
      img.src = URL.createObjectURL(f);
      img.hidden = false;
      apply();
    });
    for (const id of ["sc-cal-scale", "sc-cal-op", "sc-cal-x", "sc-cal-y"])
      $("#" + id).addEventListener("input", apply);
    $("#sc-cal-save").onclick = async () => {
      const sc = S.scene;
      if (!sc) return;
      const cols = colsFor(sc.layout, sc);
      try {
        const r = await api("/api/scenes/cols", post({ layout: sc.layout, cols }));
        S.meta.cols = r.cols;
        $("#sc-cal-msg").textContent = `${sc.layout}: ${cols} Spalten gespeichert (config.json).`;
      } catch (e) { $("#sc-cal-msg").textContent = e.message; }
    };
  }

  /* Tastatur im Szenen-Tab: 1–9 Antwort · ←/→ Variante · N nächste · R geprüft · F markieren */
  function onKey(e) {
    if (!$("#tab-szenen.active") || e.ctrlKey || e.metaKey || e.altKey) return;
    const t = e.target;
    if (t && (t.tagName === "TEXTAREA" || t.tagName === "INPUT" || t.tagName === "SELECT" || t.isContentEditable)) return;
    const sc = S.scene;
    if (/^[1-9]$/.test(e.key) && sc && sc.layout === "conversation") {
      const n = $$("#sc-view .qnum")[+e.key - 1];
      if (n) { e.preventDefault(); gotoNode(n.dataset.goto); }
      return;
    }
    if ((e.key === "ArrowRight" || e.key === "ArrowLeft") && sc && sc.variants && sc.variants.length > 1) {
      e.preventDefault();
      const k = sc.variants.length;
      S.opts.variant = (sc.variant + (e.key === "ArrowRight" ? 1 : k - 1)) % k;
      refresh();
      return;
    }
    const k = e.key.toLowerCase();
    if (k === "n") { e.preventDefault(); nextScene(); }
    else if (k === "r") { const b = $("#sc-checkall"); if (b && !b.disabled) { e.preventDefault(); b.click(); } }
    else if (k === "f") { const b = $("#sc-flag"); if (b) { e.preventDefault(); b.click(); } }
  }

  /* ------------------------------------------------ Editor (Szenen-Tab) */

  async function selectSlot(uid) {
    S.sel = uid;
    paint();
    const ed = $("#sc-editor");
    ed.innerHTML = '<div class="placeholder">Lade …</div>';
    let u;
    try { u = await api("/api/units/" + uid); }
    catch (e) { ed.innerHTML = '<div class="placeholder">' + esc(e.message) + "</div>"; return; }
    const slot = slotsOf(S.scene).find(s => s.uid === uid);
    const value = S.drafts[uid] !== undefined ? S.drafts[uid] : u.value;
    ed.innerHTML = `
      <h2>${esc(u.file)} ${u.line ? "· Zeile " + u.line : ""}</h2>
      <div class="idblock">${hi(u.english || u.english_manifest || u.key)}<span class="lock">🔒</span></div>
      ${u.context ? `<div class="idnote">Kontext: <code>${esc(u.context)}</code></div>` : ""}
      ${slot && slot.match === "staleid" ? `<div class="msg err">ID veraltet: Das Spiel zeigt heute<div class="enblock">${hi(slot.en)}</div>
        — dieser Eintrag hat aber die alte ID (oben). Der deutsche Wert greift nie. Abhilfe: neuen Eintrag mit der
        aktuellen ID anlegen, den alten danach entfernen.
        <div class="btnrow"><button class="primary" id="sc-rekey">Neu anlegen mit aktueller ID</button></div></div>` : ""}
      ${slot && slot.cond && Object.keys(slot.cond).length ? `<div class="idnote">Bedingung: <code>${esc(condText(slot.cond))}</code></div>` : ""}
      <h2>Deutscher Wert</h2>
      <textarea class="deval" id="sc-deval" spellcheck="true">${esc(value)}</textarea>
      <div class="btnrow">
        <button class="primary" id="sc-save">Speichern</button>
        <button class="ghost" id="sc-revert">Verwerfen</button>
        <span class="mini" id="sc-dirty">${S.drafts[uid] !== undefined ? "Entwurf — Vorschau zeigt ihn bereits" : ""}</span>
      </div>
      <div class="btnrow">
        ${u.review === "checked" ? `<span class="pill ok">✓ geprüft</span>` :
          `<button class="ghost" id="sc-review">${u.review === "stale" ? "Erneut als geprüft markieren" : "Als geprüft markieren"}</button>`}
        <button class="ghost" id="sc-flag">${slot && slot.flag ? "⚑ Markierung bearbeiten" : "⚑ Passt nicht — markieren"}</button>
        <button class="ghost" id="sc-mktest" title="Aktuelle Vorschau als In-Game-Test speichern (CuratorTests.json)">Im Spiel bestätigen</button>
      </div>
      ${slot && slot.flag ? `<div class="msg warn">⚑ ${esc(slot.flag.note || "(ohne Notiz)")} <span class="mini">— ${esc(slot.flag.date)}</span>
        <div class="btnrow">
          <button class="ghost sm" data-fstate="fixed">✓ erledigt</button>
          <button class="ghost sm" data-fstate="wontfix">verworfen</button>
          <button class="ghost sm" id="sc-unflag">Markierung löschen</button>
          ${slot.flag.kind === "orphan" ? `<button class="ghost sm danger" id="sc-delete" title="Verwaisten Eintrag aus der Datei entfernen (Nachfolger mit aktueller ID existiert)">Verwaisten Eintrag löschen</button>` : ""}
        </div></div>` : ""}
      ${tokenTable(slot)}
      <div id="sc-msg"></div>
      <div id="sc-lint">${renderLint(u.lint)}</div>`;
    const ta = $("#sc-deval");
    ta.addEventListener("input", () => {
      if (ta.value === u.value) delete S.drafts[uid]; else S.drafts[uid] = ta.value;
      $("#sc-dirty").textContent = S.drafts[uid] !== undefined ? "Entwurf — Vorschau aktualisiert live" : "";
      debounceRefresh();
    });
    $("#sc-revert").onclick = () => { delete S.drafts[uid]; selectSlot(uid); refresh(); };
    $("#sc-save").onclick = async () => {
      try {
        await api("/api/units/" + uid, post({ old_value: u.value, new_value: ta.value }));
        delete S.drafts[uid];
        await refresh();
        selectSlot(uid);
      } catch (e) { $("#sc-msg").innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; }
    };
    const rv = $("#sc-review");
    if (rv) rv.onclick = async () => {
      const r = await api("/api/review", post({ uid, checked: true }));
      updateReviewPill(r.summary);
      await refresh(); selectSlot(uid);
    };
    $("#sc-flag").onclick = async () => {
      const note = prompt("Was passt im Kontext nicht? (Ton, Kasus, Länge …)", slot && slot.flag ? slot.flag.note : "");
      if (note === null) return;
      await api("/api/flags", post({ uid, note }));
      await refresh(); selectSlot(uid);
    };
    const uf = $("#sc-unflag");
    if (uf) uf.onclick = async () => { await api("/api/flags", post({ uid, clear: true })); await refresh(); selectSlot(uid); };
    $$("[data-fstate]", ed).forEach(b => b.onclick = async () => {
      await api("/api/flags", post({ uid, status: b.dataset.fstate }));
      await refresh(); selectSlot(uid);
    });
    const del = $("#sc-delete");
    if (del) del.onclick = async () => {
      if (!confirm("Verwaisten Eintrag endgültig aus " + u.file + " entfernen? (git kann ihn wiederherstellen)")) return;
      try {
        const r = await api("/api/units/delete", post({ uid, expect_value: u.value }));
        await refresh();
        selectSlot(r.successor);
      } catch (e) { $("#sc-msg").innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; }
    };
    $("#sc-mktest").onclick = () => makeTest(u, slot, ta.value);
    const rk = $("#sc-rekey");
    if (rk) rk.onclick = async () => {
      try {
        const r = await api("/api/scenes/rekey", post({ uid }));
        await refresh();
        selectSlot(r.unit.uid);
      } catch (e) { $("#sc-msg").innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; }
    };
  }

  function tokenTable(slot) {
    const toks = slot && slot.render ? slot.render.tokens : [];
    if (!toks || !toks.length) return "";
    return `<h2>Tokens in dieser Vorschau</h2><table class="data toktab">` + toks.map(t =>
      `<tr><td>${esc(t.src)}</td><td class="sans">→ <span class="qtok how-${esc(t.how)}">${esc(QUD.visible(t.out))}</span></td>
       <td class="sans mini">${esc(QUD.HOW_LABEL[t.how] || t.how)}</td></tr>`).join("") + "</table>";
  }

  /* „Im Spiel bestätigen": Vorschau -> CuratorTests.json-Eintrag. Das Spiel
     rendert denselben Wert mit echten Objekten; PASS bestätigt die Emulation. */
  async function makeTest(u, slot, value) {
    const sm = S.meta.samples;
    const pickObj = r => sm.objects[S.opts.roles[r] || sm.roles[r]] || {};
    const subj = pickObj("subject"), obj = pickObj("object");
    const toks = slot && slot.render ? slot.render.tokens : [];
    const bad = toks.filter(t => !["emu"].includes(t.how));
    if (!subj.blueprint || !obj.blueprint) {
      $("#sc-msg").innerHTML = '<div class="msg warn">Für einen In-Game-Test müssen subject und object Stichproben mit Blueprint sein (Schnappkiefer, Krokodil, Ziege, Leuchtfisch, Fackel …).</div>';
      return;
    }
    const r = await api("/api/scenes/resolve", post({ template: value, roles: S.opts.roles, pick: S.opts.pick }));
    const expected = r.text.replace(/[\u0001\u0002]/g, "");
    if (bad.length && !confirm("Diese Tokens sind nur angenähert/Stichprobe und werden im Spiel anders aufgelöst:\n\n"
        + bad.map(t => t.src + " (" + (QUD.HOW_LABEL[t.how] || t.how) + ")").join("\n")
        + "\n\nDer Test wird dann vermutlich FAILen. Trotzdem anlegen?")) return;
    const id = "ctx-" + (u.uid.slice(0, 8)) + "-" + (S.opts.roles.subject || sm.roles.subject);
    try {
      await api("/api/tests", post({
        id, description: "Szenen-Vorschau: " + QUD.visible(rawRender(u.english || "").text).slice(0, 60),
        template: value, subject: subj.blueprint, object: obj.blueprint,
        expected, enabled: true, sourceUnit: u.uid,
      }));
      $("#sc-msg").innerHTML = `<div class="msg ok">Test <code>${esc(id)}</code> angelegt — erwartet: „${esc(expected)}“.
        Deploy abgleichen + Spiel starten, Ergebnis im Tab „Tests“.</div>`;
    } catch (e) { $("#sc-msg").innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; }
  }

  function showMissing(path) {
    const slot = slotsOf(S.scene).find(s => !s.uid && s.path === path);
    const ed = $("#sc-editor");
    if (!slot || !ed) return;
    const file = (path || "").startsWith("Conversation ") ? "Strings.Conversations.de.xml" : "Strings.de.xml";
    ed.innerHTML = `
      <h2>Unübersetzter Baustein</h2>
      <div class="idblock">${hi(slot.en)}<span class="lock">🔒</span></div>
      <div class="idnote">Kontext: <code>${esc(path)}</code></div>
      <h2>Deutscher Wert — neuer Eintrag in ${esc(file)}</h2>
      <textarea class="deval" id="sc-newval" placeholder="Übersetzung …"></textarea>
      <div class="btnrow"><button class="primary" id="sc-create">Eintrag anlegen</button></div>
      <div id="sc-msg"></div>`;
    $("#sc-create").onclick = async () => {
      try {
        await api("/api/units", post({ file, context: path, id: slot.en, value: $("#sc-newval").value }));
        await refresh();
        $("#sc-msg").innerHTML = '<div class="msg ok">Eintrag angelegt.</div>';
      } catch (e) { $("#sc-msg").innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; }
    };
  }

  let timer = null;
  function debounceRefresh() {
    clearTimeout(timer);
    timer = setTimeout(() => refresh(), 250);
  }

  /* ------------------------------------------------ „Im Kontext" im Übersetzungen-Tab */

  async function attachContext(u) {
    const box = $("#ctxbox");
    if (!box) return;
    S.ctxUnit = u;
    S.ctxFocus = u.uid;
    try { await ensureMeta(); } catch (e) { return; }
    box.innerHTML = `
      <details class="incontext" ${localStorage.getItem("ctx-closed") ? "" : "open"}>
        <summary>Im Kontext <span class="mini">— so erscheint der Eintrag im Spiel (emuliert)</span></summary>
        <div class="sctoolbar" id="ctx-toolbar"></div>
        <div class="scview ${S.overlay ? "overlay" : ""}" id="ctx-view"><div class="placeholder">Lade …</div></div>
        <div class="btnrow"><button class="ghost" id="ctx-open">In „Szenen“ öffnen ▸</button>
          <span class="mini" id="ctx-info"></span></div>
      </details>`;
    const det = $("details.incontext", box);
    det.addEventListener("toggle", () => {
      try { det.open ? localStorage.removeItem("ctx-closed") : localStorage.setItem("ctx-closed", "1"); } catch (e) { /* egal */ }
    });
    wireStage($("#ctx-view"), uid => { if (uid !== u.uid) select(uid); }, null, () => refreshContext());
    wireToolbar($("#ctx-toolbar"), () => refreshContext(), () => S.ctxScene);
    $("#ctx-open").onclick = () => openUnit(u.uid);
    const ta = $("#deval");
    if (ta) ta.addEventListener("input", () => {
      clearTimeout(attachContext.t);
      attachContext.t = setTimeout(() => refreshContext(ta.value), 250);
    });
    refreshContext();
  }

  function repaintCtx() {
    const view = $("#ctx-view");
    if (!view || !S.ctxScene) return;
    view.innerHTML = stageHtml(S.ctxScene);
    markTerms(view);
  }

  async function refreshContext(draft) {
    const u = S.ctxUnit;
    const view = $("#ctx-view");
    if (!u || !view) return;
    if (draft === undefined) { const ta = $("#deval"); draft = ta ? ta.value : undefined; }
    const drafts = (draft !== undefined && draft !== u.value) ? { [u.uid]: draft } : {};
    let sc;
    try { sc = await api("/api/scenes/unit", post({ uid: u.uid, layout: S.layout, opts: S.opts, drafts })); }
    catch (e) { view.innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; return; }
    S.ctxScene = sc;
    $("#ctx-toolbar").innerHTML = controlsHtml(sc, true);
    view.innerHTML = stageHtml(sc);
    view.classList.toggle("overlay", S.overlay);
    markTerms(view);
    const me = slotsOf(sc).find(s => s.uid === u.uid);
    $("#ctx-info").innerHTML = me ? issuesOf(me) : "";
  }

  /* Prüfungen-Tab: Markierungen aus der Vorschau als eigene Gruppe */
  const origLint = panes.pruefungen;
  panes.pruefungen = async function () {
    await origLint();
    let d;
    try { d = await api("/api/flags"); } catch (e) { return; }
    const pane = $("#pane-pruefungen");
    const box = document.createElement("details");
    box.className = "group";
    box.open = d.flags.some(f => f.status === "open");
    const open = d.flags.filter(f => f.status === "open");
    const closed = d.flags.filter(f => f.status !== "open");
    const STATE = { open: "", fixed: " · ✓ erledigt", wontfix: " · verworfen" };
    box.innerHTML = `<summary><span class="badge warning">⚑</span> Im Kontext markiert — ${open.length} offen${closed.length ? ", " + closed.length + " geschlossen" : ""}</summary>
      <ul class="lintlist">${open.concat(closed).map(f => `
        <li class="${f.status === "open" ? "warning" : "info"}" data-uid="${esc(f.uid)}" style="cursor:pointer${f.status === "open" ? "" : ";opacity:.6"}">
          <span class="rule">${esc(f.file)}${f.kind === "orphan" ? " · verwaist" : ""}${STATE[f.status] || ""}</span>${esc(f.note || "(ohne Notiz)")}
          <span class="mini">— ${esc((f.value || "").slice(0, 80))}${f.changed ? " · seitdem geändert" : ""}${f.exists ? "" : " · Einheit existiert nicht mehr"}</span>
        </li>`).join("") || '<li class="info">Noch nichts markiert — in der Szenen-Vorschau „⚑ Passt nicht“ nutzen.</li>'}</ul>`;
    const h = pane.querySelector("h2");
    if (h && h.nextSibling) h.parentNode.insertBefore(box, h.nextSibling.nextSibling); else pane.append(box);
    $$("[data-uid]", box).forEach(li => li.addEventListener("click", () => openUnit(li.dataset.uid)));
  };

  /* Mini-Vorschau für andere Tabs (Vorschläge): Szene der Einheit mit Entwurf rendern,
     Fokus-Baustein markiert, nicht interaktiv. */
  async function renderInto(el, uid, drafts) {
    await ensureMeta();
    let sc;
    try { sc = await api("/api/scenes/unit", post({ uid, opts: S.opts, drafts: drafts || {} })); }
    catch (e) { el.innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; return; }
    const keep = [S.ctxFocus, S.sel];
    S.ctxFocus = uid; S.sel = null;
    el.innerHTML = `<div class="scview overlay">${sceneHtml(sc, "de")}</div>`;
    [S.ctxFocus, S.sel] = keep;
    markTerms(el);
  }

  panes.szenen = loadPane;
  window.addEventListener("load", fromHash);
  return { attachContext, openUnit, slotsOf, rawRender, setGlossary, renderInto, S };
})();
