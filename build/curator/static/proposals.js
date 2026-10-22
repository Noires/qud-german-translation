/* QudDE Kurator — Vorschlags-Warteschlange (Fix-Assistenten, du-Umstellung).
   Nichts wird ohne Annahme geschrieben; Annehmen = writer.save mit Alt-Wert-
   Prüfung. Pro Vorschlag: Wort-Diff + Szenen-Vorschau mit dem neuen Wert.
   Nutzt aus app.js: $, $$, api, esc, hi, panes, select; aus scenes.js: SCENES. */
"use strict";

const PROPOSALS = (() => {
  const post = body => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const P = { batch: null, data: null, filter: "open", cur: 0 };
  const STATE_LABEL = {
    open: "offen", gate: "Prüfung nicht bestanden", stale: "veraltet (Wert geändert)",
    accepted: "angenommen", rejected: "abgelehnt",
  };

  async function loadPane() {
    const pane = $("#pane-vorschlaege");
    let d;
    try { d = await api("/api/proposals"); }
    catch (e) { pane.innerHTML = '<div class="placeholder">' + esc(e.message) + "</div>"; return; }
    pane.innerHTML = `
      <div class="pqmaster">
        <h2>Batches</h2>
        <div id="pq-batches">${d.batches.map(b => {
          const c = b.counts, done = (c.accepted || 0) + (c.rejected || 0);
          return `<div class="unitrow${b.batch === P.batch ? " sel" : ""}" data-batch="${esc(b.batch)}">
            <span class="de">${esc(b.batch)}</span>
            <span class="badges"><span class="filebadge">${done}/${b.total}</span></span>
            <span class="en">${esc(b.note || b.rule || "")}
              <span class="bar thin"><i style="width:${b.total ? 100 * done / b.total : 0}%"></i></span>
              ${c.gate ? `<span class="badge warning">${c.gate} Prüfung</span>` : ""}
              ${c.stale ? `<span class="badge info">${c.stale} veraltet</span>` : ""}</span>
          </div>`;
        }).join("") || '<div class="placeholder">Noch keine Vorschläge.</div>'}</div>
        <h2>Assistenten</h2>
        ${Object.entries(d.generators).map(([k, label]) =>
          `<div class="btnrow"><button class="ghost" data-gen="${esc(k)}">Erzeugen: ${esc(label)}</button></div>`).join("")}
        <p class="mini">du-Umstellungs-Batches entstehen außerhalb der UI (Subagenten) und erscheinen hier.</p>
      </div>
      <div class="pqdetail" id="pq-detail"><div class="placeholder">Batch links wählen.</div></div>`;
    $$("[data-batch]", pane).forEach(r => r.onclick = () => openBatch(r.dataset.batch));
    $$("[data-gen]", pane).forEach(b => b.onclick = async () => {
      if (!confirm("Assistent ausführen? Ein bestehender Batch gleichen Namens wird ersetzt (Entscheidungen gehen verloren).")) return;
      try { const r = await api("/api/proposals/generate", post({ rule: b.dataset.gen })); P.batch = r.batch; }
      catch (e) { alert(e.message); return; }
      await loadPane();
      openBatch(P.batch);
    });
    if (P.batch) openBatch(P.batch, true);
  }

  async function openBatch(name, keepCur) {
    P.batch = name;
    $$("#pq-batches .unitrow").forEach(r => r.classList.toggle("sel", r.dataset.batch === name));
    try { P.data = await api("/api/proposals/" + encodeURIComponent(name)); }
    catch (e) { $("#pq-detail").innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; return; }
    if (!keepCur) P.cur = 0;
    renderBatch();
  }

  const visible = () => P.data.items.filter(i => P.filter === "all" || i.state === P.filter);

  function renderBatch() {
    const items = visible();
    const counts = {};
    for (const i of P.data.items) counts[i.state] = (counts[i.state] || 0) + 1;
    if (P.cur >= items.length) P.cur = Math.max(0, items.length - 1);
    const it = items[P.cur];
    $("#pq-detail").innerHTML = `
      <h2>${esc(P.data.batch)} <span class="mini">— ${esc(P.data.note || "")}</span></h2>
      <div class="btnrow">
        ${["open", "gate", "stale", "accepted", "rejected", "all"].map(f =>
          `<button class="ghost sm${P.filter === f ? " on" : ""}" data-f="${f}">${f === "all" ? "alle" : STATE_LABEL[f]} (${f === "all" ? P.data.items.length : counts[f] || 0})</button>`).join("")}
      </div>
      ${it ? `
        <div class="btnrow">
          <button class="ghost sm" id="pq-prev">◀</button>
          <span class="mini">${P.cur + 1} / ${items.length}</span>
          <button class="ghost sm" id="pq-next">▶</button>
          <span class="mini">Tasten: A annehmen · X ablehnen · E bearbeiten · J/K weiter/zurück</span>
        </div>
        <div class="pqitem">
          <div class="idnote">${esc(it.file || "")} · <code>${esc(it.context || it.key || "")}</code>
            · <a href="#" id="pq-open">im Editor öffnen</a> · Status: <b>${esc(STATE_LABEL[it.state] || it.state)}</b></div>
          ${it.op === "create" ? `<div class="mini"><span class="badge info">NEU</span> neuer Eintrag in ${esc(it.file)}</div>` : ""}
          ${it.english ? `<div class="enblock pqen">${hi(it.english)}</div>` : ""}
          <div class="pqdiff">${diffHtml(it.old_value, it.new_value)}</div>
          ${it.note ? `<p class="mini">${esc(it.note)}</p>` : ""}
          ${it.gate.length ? `<div class="msg warn">Prüfung: ${esc(it.gate.join(" · "))}
            ${it.status === "open" && !it.stale && it.gate.every(g => g.startsWith("noch ") && g.includes("-Form"))
              ? `<div class="btnrow"><button class="ghost sm" id="pq-force">Trotzdem annehmen — ist 3. Person / kein Spieler</button></div>` : ""}</div>` : ""}
          ${it.state === "stale" ? `<div class="msg warn">Der Wert wurde seit dem Vorschlag geändert — aktuell:
            <div class="enblock">${hi(it.current || "(Einheit fehlt)")}</div></div>` : ""}
          <textarea class="deval" id="pq-edit" hidden>${esc(it.new_value)}</textarea>
          <div class="btnrow">
            ${it.status === "open" ? `
              <button class="primary" id="pq-accept" ${it.state === "open" ? "" : "disabled"}>Annehmen</button>
              <button class="ghost" id="pq-reject">Ablehnen</button>
              <button class="ghost" id="pq-edit-btn">Bearbeiten</button>` :
              `<button class="ghost" id="pq-reopen">wieder öffnen</button>`}
            ${P.filter === "open" ? `<button class="ghost" id="pq-all">Alle ${items.length} sichtbaren annehmen</button>` : ""}
          </div>
          <div id="pq-msg"></div>
          <h2>Im Kontext (neuer Wert)</h2>
          <div id="pq-scene"><div class="placeholder">Lade …</div></div>
        </div>` : '<div class="placeholder">Keine Vorschläge in dieser Ansicht.</div>'}`;
    $$("[data-f]", $("#pq-detail")).forEach(b => b.onclick = () => { P.filter = b.dataset.f; P.cur = 0; renderBatch(); });
    if (!it) return;
    $("#pq-prev").onclick = () => step(-1);
    $("#pq-next").onclick = () => step(1);
    $("#pq-open").onclick = e => { e.preventDefault(); $('#tabs button[data-tab="uebersetzungen"]').click(); select(it.uid); };
    const acc = $("#pq-accept");
    if (acc) acc.onclick = () => decide(it, "accept");
    const rej = $("#pq-reject");
    if (rej) rej.onclick = () => decide(it, "reject");
    const eb = $("#pq-edit-btn");
    if (eb) eb.onclick = () => editMode(it);
    const fo = $("#pq-force");
    if (fo) fo.onclick = () => decide(it, "accept", undefined, true);
    const ro = $("#pq-reopen");
    if (ro) ro.onclick = () => decide(it, "reopen");
    const all = $("#pq-all");
    if (all) all.onclick = () => acceptAll(items);
    if (it.op === "create") renderNew($("#pq-scene"), it.new_value);
    else if (typeof SCENES !== "undefined" && it.current !== null)
      SCENES.renderInto($("#pq-scene"), it.uid, { [it.uid]: it.new_value });
  }

  /* Neuanlage: noch keine Einheit -> Vorlage über die Emulation auflösen und als
     Meldungsfenster zeigen (Spaltenbreite des Popup-Layouts) */
  async function renderNew(el, value) {
    let r;
    try { r = await api("/api/scenes/resolve", post({ template: value })); }
    catch (e) { el.innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; return; }
    const html = QUD.toHtml(r, { cols: 66, fg: "y" }).html;
    el.innerHTML = `<div class="scview"><div class="qscreen qpopup" style="--cols:66">
      <div class="qpopframe"><div class="qbody center"><div class="qslot focus">${html}</div></div>
      <div class="qbuttons"><span class="qbtn"><span style="color:${QUD.PALETTE.W}">[Leer]</span> Fortfahren</span></div>
      </div></div></div>`;
  }

  function editMode(it) {
    const ta = $("#pq-edit");
    ta.hidden = false;
    ta.focus();
    const b = $("#pq-edit-btn");
    b.textContent = "Bearbeitet annehmen";
    b.className = "primary";
    b.onclick = () => decide(it, "accept", ta.value);
    ta.addEventListener("input", () => {
      clearTimeout(editMode.t);
      editMode.t = setTimeout(() => it.op === "create" ? renderNew($("#pq-scene"), ta.value)
        : SCENES.renderInto($("#pq-scene"), it.uid, { [it.uid]: ta.value }), 250);
    });
  }

  function step(d) {
    const n = visible().length;
    if (!n) return;
    P.cur = (P.cur + d + n) % n;
    renderBatch();
  }

  async function decide(it, action, newValue, force) {
    try {
      await api(`/api/proposals/${encodeURIComponent(P.batch)}/decide`,
        post({ uid: it.uid, action, new_value: newValue, force: !!force }));
    } catch (e) { $("#pq-msg").innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; return; }
    await openBatch(P.batch, true);
  }

  async function acceptAll(items) {
    const ok = items.filter(i => i.state === "open");
    if (!confirm(`${ok.length} Vorschläge annehmen? Jeder wird einzeln über den Writer geschrieben (Alt-Wert-Prüfung).`)) return;
    let fail = 0;
    for (const i of ok) {
      try { await api(`/api/proposals/${encodeURIComponent(P.batch)}/decide`, post({ uid: i.uid, action: "accept" })); }
      catch (e) { fail++; }
    }
    await openBatch(P.batch, true);
    if (fail) $("#pq-msg").innerHTML = `<div class="msg warn">${fail} Vorschläge konnten nicht geschrieben werden (Wert geändert oder Prüfung).</div>`;
  }

  /* Wort-Diff (LCS über Wörter + Leerraum), Tokens bleiben ganze Wörter */
  function diffHtml(a, b) {
    const split = s => String(s || "").split(/(\s+)/).filter(x => x !== "");
    const x = split(a), y = split(b);
    const n = x.length, m = y.length;
    if (n * m > 400000) return `<div class="del">${esc(a)}</div><div class="ins">${esc(b)}</div>`;
    const L = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
    for (let i = n - 1; i >= 0; i--)
      for (let j = m - 1; j >= 0; j--)
        L[i][j] = x[i] === y[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    let i = 0, j = 0, out = "";
    while (i < n && j < m) {
      if (x[i] === y[j]) { out += esc(x[i]); i++; j++; }
      else if (L[i + 1][j] >= L[i][j + 1]) { out += `<del>${esc(x[i])}</del>`; i++; }
      else { out += `<ins>${esc(y[j])}</ins>`; j++; }
    }
    while (i < n) out += `<del>${esc(x[i++])}</del>`;
    while (j < m) out += `<ins>${esc(y[j++])}</ins>`;
    return out;
  }

  document.addEventListener("keydown", e => {
    if (!$("#tab-vorschlaege.active") || e.ctrlKey || e.metaKey || e.altKey) return;
    const t = e.target;
    if (t && (t.tagName === "TEXTAREA" || t.tagName === "INPUT" || t.tagName === "SELECT")) return;
    const k = e.key.toLowerCase();
    const click = id => { const b = $(id); if (b && !b.disabled) { e.preventDefault(); b.click(); } };
    if (k === "a") click("#pq-accept");
    else if (k === "x") click("#pq-reject");
    else if (k === "e") click("#pq-edit-btn");
    else if (k === "j") step(1);
    else if (k === "k") step(-1);
  });

  panes.vorschlaege = loadPane;
  /* Deep-Link #vorschlaege/<batch> */
  window.addEventListener("load", () => {
    const m = /^#vorschlaege\/([\w.-]+)$/.exec(location.hash);
    if (!m) return;
    P.batch = m[1];
    $('#tabs button[data-tab="vorschlaege"]').click();
  });
  return { diffHtml };
})();
