/* QudDE Kurator — Playtest-Befunde: im Spiel gefunden → behoben → im nächsten Lauf bestätigt.
   Screenshot per Einfügen (Strg+V) oder Datei-Auswahl; bleibt lokal (data/findings/*.png).
   Nutzt aus app.js: $, $$, api, esc, panes. */
"use strict";

const FINDINGS = (() => {
  const LABEL = { open: "offen", verify: "zu verifizieren", closed: "bestätigt",
                  regressed: "wieder aufgetaucht", wontfix: "bleibt so" };
  const CLS = { open: "warning", verify: "info", closed: "ok", regressed: "error", wontfix: "info" };
  let shot = null;
  const post = (url, obj) => api(url, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(obj) });

  function readFile(file) {
    return new Promise((ok, bad) => {
      const r = new FileReader();
      r.onload = () => ok(r.result); r.onerror = bad;
      r.readAsDataURL(file);
    });
  }

  function row(f) {
    const acts = {
      open: [["verify", "Behoben → im Spiel prüfen"], ["wontfix", "Bleibt so"]],
      verify: [["closed", "Im Spiel bestätigt"], ["regressed", "Weiterhin falsch"]],
      regressed: [["verify", "Erneut behoben"], ["wontfix", "Bleibt so"]],
      closed: [["open", "Wieder öffnen"]], wontfix: [["open", "Wieder öffnen"]],
    }[f.status] || [];
    const hint = f.status === "verify"
      ? (f.played_since_fix ? '<span class="pill ok">seit dem Beheben gespielt</span>'
                            : '<span class="pill warn">noch nicht wieder gespielt</span>') : "";
    return `<li class="fd-row">
      <div class="fd-head"><span class="badge ${CLS[f.status] || "info"}">${esc(LABEL[f.status] || f.status)}</span>
        <b>${esc(f.text)}</b> ${hint}
        <span class="mini">${esc(f.created)}${f.where ? " · " + esc(f.where) : ""}</span></div>
      ${f.uid ? `<div class="mini fd-unit" data-uid="${esc(f.uid)}">Eintrag: ${esc((f.value || "").slice(0, 140))}
        ${f.changed_since_fix ? " · seit dem Beheben erneut geändert" : ""}</div>` : ""}
      ${f.screenshot ? `<a href="/api/findings/shot/${esc(f.screenshot)}" target="_blank"><img class="fd-shot" src="/api/findings/shot/${esc(f.screenshot)}" alt="Screenshot"></a>` : ""}
      <div class="btnrow">${acts.map(([s, l]) => `<button class="ghost sm" data-id="${esc(f.id)}" data-status="${s}">${esc(l)}</button>`).join("")}
        ${f.uid ? "" : `<input class="sm" data-link="${esc(f.id)}" placeholder="uid zuordnen (aus dem Editor)">`}</div>
    </li>`;
  }

  function render(pane, d) {
    const groups = ["regressed", "open", "verify", "closed", "wontfix"];
    const by = s => d.findings.filter(f => f.status === s);
    pane.innerHTML = `
      <h2>Neuer Befund aus dem Spiel</h2>
      <form class="fd-form">
        <input name="text" placeholder="Was ist falsch? (z. B. „von ihn“ beim Trinken aus einem Wasserschlauch)" required>
        <input name="where" placeholder="Wo? (Ort, Gespräch, Menü)">
        <input name="uid" placeholder="uid (optional — im Editor sichtbar)">
        <label class="ghost sm">Screenshot <input type="file" name="file" accept="image/png" hidden></label>
        <span class="mini" id="fd-shotinfo">oder Screenshot mit Strg+V einfügen</span>
        <button type="submit" class="primary">Befund speichern</button>
      </form>
      ${d.auto_regressed && d.auto_regressed.length ? `<div class="msg err">${d.auto_regressed.length} Befund(e) automatisch auf „wieder aufgetaucht“ gesetzt (String-Miss im neuesten Player.log).</div>` : ""}
      ${groups.map(s => by(s).length ? `<h2>${esc(LABEL[s])} (${by(s).length})</h2><ul class="fd-list">${by(s).map(row).join("")}</ul>` : "").join("")
        || '<p class="mini">Noch keine Befunde.</p>'}`;
    const form = $(".fd-form", pane);
    form.file.addEventListener("change", async () => {
      if (form.file.files[0]) { shot = await readFile(form.file.files[0]); $("#fd-shotinfo").textContent = "Screenshot angehängt ✓"; }
    });
    form.addEventListener("submit", async e => {
      e.preventDefault();
      try {
        await post("/api/findings", { text: form.text.value, where: form.where.value,
          uid: form.uid.value.trim() || null, screenshot: shot });
        shot = null; load();
      } catch (ex) { alert(ex.message); }
    });
    $$("[data-status]", pane).forEach(b => b.addEventListener("click", async () => {
      try { await post("/api/findings/update", { id: b.dataset.id, status: b.dataset.status }); load(); }
      catch (ex) { alert(ex.message); }
    }));
    $$("[data-link]", pane).forEach(i => i.addEventListener("change", async () => {
      try { await post("/api/findings/update", { id: i.dataset.link, uid: i.value.trim() }); load(); }
      catch (ex) { alert(ex.message); }
    }));
    $$(".fd-unit", pane).forEach(el => el.addEventListener("click", () => { location.hash = "#unit/" + el.dataset.uid; }));
  }

  document.addEventListener("paste", async e => {
    if (!$("#tab-playtest") || !$("#tab-playtest").classList.contains("active")) return;
    const item = [...(e.clipboardData || {}).items || []].find(i => i.type === "image/png");
    if (!item) return;
    shot = await readFile(item.getAsFile());
    const info = $("#fd-shotinfo");
    if (info) info.textContent = "Screenshot eingefügt ✓";
  });

  async function load() {
    const pane = $("#pane-playtest");
    try { render(pane, await api("/api/findings")); }
    catch (e) { pane.innerHTML = '<div class="placeholder">' + esc(e.message) + "</div>"; }
  }

  /* Verlauf im Editor: Git-Commits der Zeile + Vorschlags-Batches */
  async function history(el, uid) {
    el.innerHTML = '<div class="mini">Lade Verlauf …</div>';
    let h;
    try { h = await api("/api/history?uid=" + encodeURIComponent(uid)); }
    catch (e) { el.innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; return; }
    const props = h.proposals.map(p => `<li class="info"><span class="rule">${esc(p.batch)} · ${esc(p.rule || "")} · ${esc(p.status || "")}</span>
        ${esc((p.old || "").slice(0, 120))} → <b>${esc((p.new || "").slice(0, 160))}</b>${p.note ? ` <span class="mini">(${esc(p.note.slice(0, 120))})</span>` : ""}</li>`).join("");
    const commits = h.git.map(c => `<li class="info"><span class="rule">${esc(c.commit)} · ${esc(c.date)}</span>${esc(c.subject)}
        ${c.new ? `<div class="mini">→ ${esc(c.new.slice(0, 200))}</div>` : ""}</li>`).join("");
    el.innerHTML = (props ? `<h3 class="mini">Vorschläge</h3><ul class="lintlist">${props}</ul>` : "")
      + (commits ? `<h3 class="mini">Commits (neueste zuerst)</h3><ul class="lintlist">${commits}</ul>` : "")
      || '<div class="mini">Kein Verlauf gefunden (Eintrag nie über Vorschläge geändert, Zeile nicht in Git).</div>';
  }

  /* Konkordanz: englischer Begriff → alle deutschen Fassungen nebeneinander */
  async function concordance(el, term) {
    el.innerHTML = '<div class="mini">Suche …</div>';
    const d = await api("/api/concordance?q=" + encodeURIComponent(term));
    const rx = new RegExp("(" + term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig");
    el.innerHTML = `<p class="mini">${d.total} Einträge enthalten „${esc(d.term)}“${d.total > d.items.length ? ` (erste ${d.items.length})` : ""}.</p>
      <table class="data">${d.items.map(i => `<tr data-uid="${esc(i.uid)}" style="cursor:pointer">
        <td class="sans">${esc(i.english).replace(rx, "<mark>$1</mark>")}</td><td class="sans">${esc(i.value)}</td></tr>`).join("")}</table>`;
    $$("tr[data-uid]", el).forEach(tr => tr.addEventListener("click", () => { location.hash = "#unit/" + tr.dataset.uid; }));
  }

  panes.playtest = load;
  return { load, history, concordance };
})();
