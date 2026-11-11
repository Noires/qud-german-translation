/* QudDE Kurator — Frontend (Vanilla JS, kein Build-Step). */
"use strict";

const $ = (sel, el) => (el || document).querySelector(sel);
const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));

async function api(path, opts) {
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch (e) { /* leer */ }
  if (!res.ok) {
    const msg = (data && data.error) ? data.error : ("HTTP " + res.status);
    const err = new Error(msg); err.status = res.status; err.data = data;
    throw err;
  }
  return data;
}
const esc = s => String(s == null ? "" : s)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;");

/* Token-/Farbcode-Hervorhebung für Monospace-Blöcke */
function hi(s) {
  return esc(s)
    .replace(/=([^=\s][^=]*)=/g, '<span class="token">=$1=</span>')
    .replace(/\{\{([^|{}]+)\|/g, '<span class="colorcode">{{$1|</span>')
    .replace(/\}\}/g, '<span class="colorcode">}}</span>');
}

/* ------------------------------------------------ Tabs */
const panes = {};
$("#tabs").addEventListener("click", e => {
  const btn = e.target.closest("button[data-tab]");
  if (!btn) return;
  $$("#tabs button").forEach(b => b.classList.toggle("active", b === btn));
  $$(".tabpane").forEach(p => p.classList.toggle("active", p.id === "tab-" + btn.dataset.tab));
  const loader = panes[btn.dataset.tab];
  if (loader) loader();
});

/* ------------------------------------------------ Übersetzungen */
const state = { offset: 0, limit: 100, selected: null, meta: null };

function reviewBadge(status) {
  if (status === "checked")
    return '<span class="badge" style="background:var(--green);color:#14161a" title="geprüft">✓</span>';
  if (status === "stale")
    return '<span class="badge warning" title="seit der Prüfung geändert — neu prüfen">✓?</span>';
  return "";
}

function updateReviewPill(summary) {
  const pill = $("#pill-review");
  if (!summary || !pill) return;
  pill.hidden = false;
  pill.textContent = "Geprüft: " + summary.checked + "/" + summary.total_units
    + (summary.stale ? " (+" + summary.stale + " veraltet)" : "");
  pill.className = "pill " + (summary.checked === summary.total_units ? "ok" : "");
}

async function loadMeta() {
  state.meta = await api("/api/meta");
  $("#pill-units").textContent = state.meta.unit_count + " Einheiten";
  updateReviewPill(state.meta.review);
  const ff = $("#f-file");
  state.meta.files.forEach(f => {
    const o = document.createElement("option"); o.value = f; o.textContent = f; ff.append(o);
  });
  const fc = $("#f-cat");
  state.meta.categories.forEach(c => {
    const o = document.createElement("option"); o.value = c; o.textContent = c; fc.append(o);
  });
}

function queryParams() {
  const p = new URLSearchParams();
  p.set("q", $("#q").value);
  p.set("mode", $("#mode").value);
  if ($("#f-file").value) p.set("file", $("#f-file").value);
  if ($("#f-cat").value) p.set("category", $("#f-cat").value);
  if ($("#f-untr").checked) p.set("flag", "untranslated");
  else if ($("#f-token").checked) p.set("flag", "hastoken");
  else if ($("#f-lint").checked) p.set("flag", "lint");
  if ($("#f-review").value) p.set("review", $("#f-review").value);
  p.set("offset", state.offset);
  p.set("limit", state.limit);
  return p;
}

async function search(resetOffset) {
  if (resetOffset) state.offset = 0;
  const list = $("#unitlist");
  list.innerHTML = '<div class="placeholder">Suche …</div>';
  let data;
  try { data = await api("/api/units?" + queryParams()); }
  catch (e) { list.innerHTML = '<div class="placeholder">' + esc(e.message) + "</div>"; return; }

  list.innerHTML = "";
  if (data.untranslated) {
    $("#count").textContent = data.total + " unübersetzte Einheiten (Manifest-Diff)"
      + (data.available ? "" : " — Spiel-Manifest nicht gefunden");
    data.untranslated.forEach(u => {
      const row = document.createElement("div");
      row.className = "unitrow";
      row.innerHTML = '<span class="en">' + hi(u.english || u.key.join(" · ")) + '</span>'
        + '<span class="de mini">— noch keine Übersetzung —</span>'
        + '<span class="badges"><span class="badge untranslated">offen</span>'
        + '<span class="filebadge">' + esc(u.file) + "</span></span>";
      row.addEventListener("click", () => showUntranslated(u));
      list.append(row);
    });
  } else {
    $("#count").textContent = data.total + " Treffer";
    data.units.forEach(u => {
      const row = document.createElement("div");
      row.className = "unitrow";
      row.dataset.uid = u.uid;
      row.innerHTML = '<span class="en">' + hi(u.english || u.key) + '</span>'
        + '<span class="de">' + hi(u.value) + '</span>'
        + '<span class="badges">' + reviewBadge(u.review)
        + '<span class="filebadge">' + esc(u.file) + "</span></span>";
      row.addEventListener("click", () => select(u.uid));
      list.append(row);
    });
  }
  if (data.total > state.offset + state.limit || state.offset > 0) {
    const nav = document.createElement("div");
    nav.className = "btnrow"; nav.style.padding = "10px";
    if (state.offset > 0) {
      const b = document.createElement("button"); b.className = "ghost"; b.textContent = "◀ zurück";
      b.onclick = () => { state.offset -= state.limit; search(false); }; nav.append(b);
    }
    if (data.total > state.offset + state.limit) {
      const b = document.createElement("button"); b.className = "ghost"; b.textContent = "weiter ▶";
      b.onclick = () => { state.offset += state.limit; search(false); }; nav.append(b);
    }
    list.append(nav);
  }
}

function showUntranslated(u) {
  const d = $("#detail");
  d.innerHTML = `
    <h2>Unübersetzte Einheit — ${esc(u.file)}</h2>
    <div class="enblock">${hi(u.english)}</div>
    <p class="mini">Manifest-Schlüssel: <code>${esc(JSON.stringify(u.key))}</code></p>
    ${u.is_strings
      ? `<div class="btnrow"><button class="primary" id="btn-create">Eintrag anlegen</button></div>
         <p class="mini">Legt einen neuen &lt;string&gt;-Eintrag mit byte-exakter englischer ID an.</p>`
      : `<p class="mini">Blueprint-Einheit — im entsprechenden &lt;object&gt;-Block der Datei ergänzen
         (Neuanlage über die UI gibt es derzeit nur für String-Tabellen).</p>`}
  `;
  const btn = $("#btn-create");
  if (btn) btn.onclick = () => createEntryDialog(u);
}

function createEntryDialog(u) {
  renderCreateForm(u);
}

async function select(uid) {
  $$(".unitrow").forEach(r => r.classList.toggle("sel", r.dataset.uid === uid));
  state.selected = uid;
  const d = $("#detail");
  d.innerHTML = '<div class="placeholder">Lade …</div>';
  let u;
  try { u = await api("/api/units/" + uid); }
  catch (e) { d.innerHTML = '<div class="placeholder">' + esc(e.message) + "</div>"; return; }
  renderDetail(u);
}

function renderDetail(u) {
  const d = $("#detail");
  const enTokens = tokensIn(u.english || "");
  d.innerHTML = `
    <h2>${esc(u.file)} · ${esc(u.category || "")} ${u.line ? "· Zeile " + u.line : ""}</h2>
    <h2>Schlüssel (englische Vorlage)</h2>
    <div class="idblock">${hi(u.english || u.key)}<span class="lock">🔒 unveränderlich</span></div>
    <div class="idnote">Byte-exakter englischer Lookup-Schlüssel — wird nie verändert.
      ${u.context ? "Kontext: <code>" + esc(u.context) + "</code>" : ""}
      ${u.objname ? "Objekt: <code>" + esc(u.objname) + "</code> · <code>" + esc(u.elem) + (u.elemname ? "[" + esc(u.elemname) + "]" : "") + "@" + esc(u.attr) + "</code>" : ""}
    </div>
    ${u.english_manifest && u.english_manifest !== u.english ? `
      <h2>Englischer Originaltext (Manifest)</h2>
      <div class="enblock">${hi(u.english_manifest)}</div>` : ""}
    <h2>Deutscher Wert</h2>
    <textarea class="deval" id="deval" spellcheck="true">${esc(u.value)}</textarea>
    <div class="tokenpalette" id="palette"></div>
    <div class="btnrow">
      <button class="primary" id="btn-save">Speichern</button>
      <button class="ghost" id="btn-revert">Zurücksetzen</button>
      <button class="ghost" id="btn-mktest">Test aus Eintrag erstellen</button>
      <span class="mini" id="dirty"></span>
    </div>
    <div class="btnrow" id="reviewrow">
      ${u.review === "checked"
        ? `<span class="pill ok">✓ geprüft am ${esc(u.review_entry ? u.review_entry.date : "?")}</span>
           <button class="ghost" id="btn-review" data-checked="false">Prüfung aufheben</button>`
        : u.review === "stale"
        ? `<span class="pill warn">✓? veraltet — Wert wurde seit der Prüfung am ${esc(u.review_entry ? u.review_entry.date : "?")} geändert</span>
           <button class="primary" id="btn-review" data-checked="true">Erneut als geprüft markieren</button>
           <button class="ghost" id="btn-review-un" data-checked="false">Prüfung aufheben</button>`
        : `<button class="ghost" id="btn-review" data-checked="true">Als geprüft markieren</button>
           <span class="mini">Marke wird in build/curator/data/reviewed.json gespeichert (committbar) und verfällt automatisch, wenn der Wert geändert wird.</span>`}
    </div>
    <div id="savemsg"></div>
    <div id="lintbox">${renderLint(u.lint)}</div>
    <div id="ctxbox"></div>
    <details id="histbox"><summary class="mini">Verlauf — warum steht das so da?</summary><div></div></details>
    ${u.neighbors && u.neighbors.length ? `
      <h2>Nachbarn (${u.context ? "gleicher Kontext" : "gleiches Objekt"})</h2>
      <div class="neigh">${u.neighbors.map(n => `
        <div class="unitrow" data-uid="${n.uid}">
          <span class="en">${hi(n.english || n.key)}</span>
          <span class="de">${hi(n.value)}</span>
        </div>`).join("")}</div>` : ""}
  `;
  $$("#detail .neigh .unitrow").forEach(r =>
    r.addEventListener("click", () => select(r.dataset.uid)));

  const ta = $("#deval");
  const original = u.value;
  ta.addEventListener("input", () => {
    $("#dirty").textContent = ta.value === original ? "" : "ungespeicherte Änderung";
  });
  $("#btn-revert").onclick = () => { ta.value = original; $("#dirty").textContent = ""; $("#savemsg").innerHTML = ""; };
  $("#btn-save").onclick = () => saveUnit(u, original);
  $("#btn-mktest").onclick = () => makeTestFromUnit(u);
  const setReview = async (checked) => {
    if (ta.value !== original && checked &&
        !confirm("Es gibt ungespeicherte Änderungen — geprüft wird der GESPEICHERTE Wert. Fortfahren?")) return;
    try {
      const r = await api("/api/review", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ uid: u.uid, checked }) });
      updateReviewPill(r.summary);
      select(u.uid);
    } catch (e) {
      $("#savemsg").innerHTML = '<div class="msg err">' + esc(e.message) + "</div>";
    }
  };
  const rb = $("#btn-review");
  if (rb) rb.onclick = () => setReview(rb.dataset.checked === "true");
  const rbu = $("#btn-review-un");
  if (rbu) rbu.onclick = () => setReview(false);
  buildPalette(u, enTokens);
  if (typeof SCENES !== "undefined") SCENES.attachContext(u);
  const hb = $("#histbox");
  if (hb && typeof FINDINGS !== "undefined")
    hb.addEventListener("toggle", () => { if (hb.open) FINDINGS.history(hb.querySelector("div"), u.uid); });
}

function tokensIn(s) {
  const out = []; const re = /=([^=\s][^=]*)=/g; let m;
  while ((m = re.exec(s))) out.push(m[0]);
  return Array.from(new Set(out));
}

async function buildPalette(u, enTokens) {
  const pal = $("#palette");
  if (!pal) return;
  const groups = [];
  if (enTokens.length)
    groups.push({ title: "aus der englischen Vorlage", tokens: enTokens.map(t => ({ t, tip: "" })) });
  try {
    const reg = await api("/api/tokens");
    if (reg && reg.palette)
      groups.push({ title: "deutsche Grammatik-Tokens", tokens: reg.palette });
  } catch (e) { /* Phase 3 */ }
  pal.innerHTML = groups.map(g =>
    `<span class="mini" style="width:100%">${esc(g.title)}:</span>` +
    g.tokens.map(x =>
      `<button class="tokenchip" data-t="${esc(x.t)}" title="${esc(x.tip || "")}">${esc(x.t)}</button>`
    ).join("")).join("");
  $$(".tokenchip", pal).forEach(chip => chip.addEventListener("click", () => {
    const ta = $("#deval");
    const [s, e] = [ta.selectionStart, ta.selectionEnd];
    ta.setRangeText(chip.dataset.t, s, e, "end");
    ta.focus();
    ta.dispatchEvent(new Event("input"));
  }));
}

function renderLint(lint) {
  if (!lint || !lint.length) return "";
  return `<h2>Prüf-Befunde</h2><ul class="lintlist">` + lint.map(f =>
    `<li class="${esc(f.severity)}"><span class="rule">${esc(f.rule)}</span>${esc(f.message)}</li>`
  ).join("") + "</ul>";
}

async function saveUnit(u, original) {
  const ta = $("#deval");
  const box = $("#savemsg");
  box.innerHTML = "";
  try {
    const res = await api("/api/units/" + u.uid, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ old_value: original, new_value: ta.value }),
    });
    box.innerHTML = '<div class="msg ok">Gespeichert — nur diese Stelle geändert.</div>';
    $("#dirty").textContent = "";
    $("#lintbox").innerHTML = renderLint(res.lint);
    select(u.uid);
  } catch (e) {
    const hint = e.status === 404 ? " (Schreib-Modul noch nicht aktiv — Phase 2)" : "";
    box.innerHTML = '<div class="msg err">' + esc(e.message) + esc(hint) + "</div>";
  }
}

const STRING_TABLE_FILES = ["Strings.de.xml", "Strings.Conversations.de.xml",
  "Strings.appendix.de.xml", "Strings.Extend.de.xml", "Untranslated.de.xml"];

function renderCreateForm(u) {
  const d = $("#detail");
  const ctx = u.context || "";
  const fileOpts = Array.from(new Set([u.file, ...STRING_TABLE_FILES]))
    .filter(f => (state.meta ? state.meta.files.includes(f) : true))
    .map(f => `<option value="${esc(f)}" ${f === u.file ? "selected" : ""}>${esc(f)}</option>`)
    .join("");
  d.innerHTML = `
    <h2>Neuen Eintrag anlegen — <select id="new-file">${fileOpts}</select></h2>
    <h2>Schlüssel (englische Vorlage)</h2>
    <div class="idblock">${hi(u.english)}<span class="lock">🔒 wird byte-exakt übernommen</span></div>
    <h2>Kontext</h2>
    <input type="text" id="new-ctx" style="width:100%" class="deval" value="${esc(ctx)}" placeholder="Context-Attribut">
    <h2>Deutscher Wert</h2>
    <textarea class="deval" id="new-val" placeholder="Übersetzung …"></textarea>
    <div class="btnrow">
      <button class="primary" id="btn-docreate">Eintrag anlegen</button>
    </div>
    <div id="savemsg"></div>`;
  $("#btn-docreate").onclick = async () => {
    try {
      await api("/api/units", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file: $("#new-file").value, context: $("#new-ctx").value,
          id: u.english, value: $("#new-val").value,
        }),
      });
      $("#savemsg").innerHTML = '<div class="msg ok">Eintrag angelegt.</div>';
    } catch (e) {
      const hint = e.status === 404 ? " (Schreib-Modul noch nicht aktiv — Phase 2)" : "";
      $("#savemsg").innerHTML = '<div class="msg err">' + esc(e.message) + esc(hint) + "</div>";
    }
  };
}

function makeTestFromUnit(u) {
  sessionStorage.setItem("mktest", JSON.stringify({
    template: u.value, object: u.objname || "", sourceUnit: u.uid,
    description: (u.english || u.key || "").slice(0, 80),
  }));
  $('#tabs button[data-tab="tests"]').click();
}

["q"].forEach(id => $("#" + id).addEventListener("keydown", e => {
  if (e.key === "Enter") search(true);
}));
["mode", "f-file", "f-cat", "f-review"].forEach(id =>
  $("#" + id).addEventListener("change", () => search(true)));
["f-untr", "f-token", "f-lint"].forEach(id =>
  $("#" + id).addEventListener("change", e => {
    if (e.target.checked)
      ["f-untr", "f-token", "f-lint"].filter(x => x !== id)
        .forEach(x => { $("#" + x).checked = false; });
    search(true);
  }));

/* ------------------------------------------------ Abdeckung */
panes.abdeckung = async function () {
  const pane = $("#pane-abdeckung");
  pane.innerHTML = '<div class="placeholder">Lade …</div>';
  let cov;
  try { cov = await api("/api/coverage"); }
  catch (e) { pane.innerHTML = '<div class="placeholder">' + esc(e.message) + "</div>"; return; }
  if (!cov.available) {
    pane.innerHTML = `<div class="msg warn">Spiel-Manifest nicht gefunden unter
      <code>${esc(cov.game_dir)}</code> — Pfad in build/curator/config.json
      als <code>game_example_dir</code> setzen.</div>`;
    return;
  }
  const hasReview = cov.totals.checked !== undefined;
  const rows = Object.entries(cov.files).sort()
    .map(([name, f]) => {
      const pct = f.units ? Math.floor(100 * f.covered / f.units) : 100;
      const rpct = f.units ? Math.floor(100 * (f.checked || 0) / f.units) : 0;
      return `<tr><td>${esc(name)}</td><td>${f.units}</td><td>${f.covered}</td>
        <td>${f.missing}</td>
        <td><div class="bar"><i style="width:${pct}%"></i></div></td><td>${pct} %</td>
        ${hasReview ? `
          <td>${f.checked || 0}${f.stale ? ` <span class="mini" title="veraltet geprüft">+${f.stale}?</span>` : ""}</td>
          <td><div class="bar"><i class="rev" style="width:${rpct}%"></i></div></td>
          <td>${rpct} %</td>` : ""}</tr>`;
    }).join("");
  const tpct = cov.totals.units ? Math.floor(100 * cov.totals.covered / cov.totals.units) : 100;
  const trpct = cov.totals.units ? Math.floor(100 * (cov.totals.checked || 0) / cov.totals.units) : 0;
  pane.innerHTML = `
    <h2>Abdeckung gegen das Spiel-Manifest (▶-Marker)</h2>
    <p class="mini">Übersetzt: ${cov.totals.covered} / ${cov.totals.units} Einheiten (${tpct} %)
      ${hasReview ? ` · Geprüft: ${cov.totals.checked} / ${cov.totals.units} (${trpct} %)${cov.totals.stale ? ` · ${cov.totals.stale} veraltet geprüft` : ""}` : ""}</p>
    <p class="mini">Eine Manifest-Einheit gilt erst als geprüft, wenn alle zugehörigen deutschen Einheiten
      (z. B. alle Absätze einer Beschreibung) als geprüft markiert sind.</p>
    <table class="data">
      <tr><th>Datei</th><th>Einheiten</th><th>übersetzt</th><th>offen</th><th></th><th></th>
        ${hasReview ? "<th>geprüft</th><th></th><th></th>" : ""}</tr>
      ${rows}
    </table>
    <div id="cov-diff"><div class="placeholder">Versionsvergleich lädt …</div></div>`;
  loadCoverageDiff();
};

/* Manifest-Versionsvergleich: was hat ein Spiel-Update geändert? */
async function loadCoverageDiff() {
  const box = $("#cov-diff");
  if (!box) return;
  let d;
  try { d = await api("/api/coverage/diff"); }
  catch (e) { box.innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; return; }
  const snap = d.snapshot;
  const list = (items, fmt) => items.length ? `<ul class="lintlist">${items.map(fmt).join("")}</ul>` : "";
  const keyTxt = k => esc(k.filter(x => x !== null && x !== "").join(" · "));
  box.innerHTML = `
    <h2>Versionsvergleich (Spiel-Updates)</h2>
    <p class="mini">Installiertes Spiel: Build <b>${esc(d.build || "?")}</b> ·
      Snapshot: ${snap ? `Build <b>${esc(snap.build || "?")}</b> vom ${esc(snap.created)}` : "noch keiner"}.
      Nach einem Spiel-Update zeigt der Vergleich neue Einträge (zu übersetzen), entfernte (deutsche
      Einträge verwaist) und geänderte englische Texte (deutsche ID veraltet → K1).</p>
    ${snap ? `<p class="mini">neu <b>${d.counts.added}</b> · entfernt <b>${d.counts.removed}</b> · geändert <b>${d.counts.changed}</b></p>
      ${list(d.added, a => `<li class="info"><span class="rule">neu · ${esc(a.file)}</span>${keyTxt(a.key)} — ${esc(a.english.slice(0, 100))}</li>`)}
      ${list(d.changed, c => `<li class="warning"><span class="rule">geändert · ${esc(c.file)}</span>${esc(c.old.slice(0, 80))} → ${esc(c.new.slice(0, 80))}</li>`)}
      ${list(d.removed, r => `<li class="error"><span class="rule">entfernt · ${esc(r.file)}</span>${keyTxt(r.key)}</li>`)}` : ""}
    <div class="btnrow"><button class="ghost" id="cov-snap">Snapshot vom aktuellen Stand übernehmen</button>
      <span class="mini">data/manifest_snapshot.json — committbar; nach erledigter Update-Nacharbeit neu setzen.</span></div>`;
  $("#cov-snap").onclick = async () => {
    if (snap && !confirm("Snapshot ersetzen? Der Vergleich startet dann bei Build " + (d.build || "?") + ".")) return;
    try { await api("/api/coverage/snapshot", { method: "POST" }); loadCoverageDiff(); }
    catch (e) { alert(e.message); }
  };
}

/* ------------------------------------------------ Platzhalter-Panes (Phasen 3–7) */
function paneLoader(name, endpoint, render) {
  panes[name] = async function () {
    const pane = $("#pane-" + name);
    pane.innerHTML = '<div class="placeholder">Lade …</div>';
    try {
      const data = await api(endpoint);
      render(pane, data);
    } catch (e) {
      pane.innerHTML = e.status === 404
        ? '<div class="placeholder">Noch nicht verfügbar (spätere Ausbaustufe).</div>'
        : '<div class="placeholder">' + esc(e.message) + "</div>";
    }
  };
}
paneLoader("pruefungen", "/api/lint/summary", (p, d) => renderLintPane(p, d));
paneLoader("lexikon", "/api/lexicon", (p, d) => renderLexiconPane(p, d));
paneLoader("verben", "/api/verbs", (p, d) => renderVerbsPane(p, d));
paneLoader("tests", "/api/tests", (p, d) => { renderTestsPane(p, d); wireAutoTests(); });
paneLoader("protokoll", "/api/playerlog", (p, d) => renderLogPane(p, d));

/* ------------------------------------------------ Prüfungen (Lint) */
function renderLintPane(p, d) {
  const sev = d.by_severity || {};
  const ruleNames = {
    T1: "Unbekanntes Token", T2: "Token der Vorlage fehlt im Deutschen",
    T3: "Token nur im Deutschen", T4: "Unausgewogene Delimiter ({{}} / =)",
    T5: "konjde-Infinitiv nicht in Verbs.json", T6: "Trennbares Präfix-Verb",
    B1: "Boolesches Attribut übersetzt", N1: "Naming⊇Strings-Substring",
    X1: "Entity-Fehler", X2: "Elementpfad nicht im Manifest",
    K1: "ID veraltet (Spieltext geändert — Wert greift nie)", K2: "Anrede weicht von der Richtlinie ab",
    K3: "konjde ohne Subjekt (Does → Name fehlt)", K4: "Possessiv ohne Kasus/Genus-Annotation",
    G1: "Glossar-Begriff fehlt / verbotene Variante", G2: "Artikel passt nicht zum Glossar-Genus",
    K5: "Weichen-Token mit englischen Argumenten", K6: "Objektpronomen ohne Dativ",
    K7: "Gleicher englischer Text, verschiedene Übersetzungen", P1: "Parität: Zahlen / Leerraum / Klammern",
  };
  const levels = d.levels || {};
  const levelSel = rule => `<select class="sm" data-level="${esc(rule)}" title="Schwere dieser Regel (error blockt das Speichern neuer Befunde)">
      ${["", "off", "info", "warning", "error"].map(l => `<option value="${l}" ${(levels[rule] || "") === l ? "selected" : ""}>${l || "Standard"}</option>`).join("")}
    </select>`;
  const groups = Object.entries(d.rules || {}).map(([rule, r]) => `
    <details class="group" ${r.severity === "error" ? "open" : ""}>
      <summary><span class="badge ${esc(r.severity)}">${esc(rule)}</span>
        ${esc(ruleNames[rule] || rule)} — ${r.count} Befund${r.count === 1 ? "" : "e"} ${levelSel(rule)}</summary>
      <ul class="lintlist">
        ${r.samples.map(f => `
          <li class="${esc(f.severity)}" ${f.uid ? `data-uid="${esc(f.uid)}" style="cursor:pointer"` : ""}>
            <span class="rule">${esc(f.file || "")}</span>${esc(f.message)}
            ${rule === "K1" ? `<button class="ghost sm" data-rekey="${esc(f.uid)}">Neu anlegen mit aktueller ID</button>` : ""}
            ${rule === "K7" && f.english ? `<button class="ghost sm" data-ignore-en="${esc(f.english)}" title="Verschiedene Übersetzungen sind hier gewollt (Kontext)">Varianten erlauben</button>` : ""}
          </li>`).join("")}
      </ul>
    </details>`).join("");
  p.innerHTML = `
    <h2>Prüf-Befunde über den gesamten Korpus</h2>
    <p class="mini">
      <span class="badge error">error</span> ${sev.error || 0} ·
      <span class="badge warning">warning</span> ${sev.warning || 0} ·
      <span class="badge info">info</span> ${sev.info || 0}
      — Klick auf einen Befund öffnet den Eintrag.</p>
    ${groups || '<p class="mini">Keine Befunde — Korpus sauber.</p>'}`;
  const post = (url, obj) => api(url, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(obj) });
  const reload = () => api("/api/lint/summary").then(nd => renderLintPane(p, nd));
  $$("#pane-pruefungen [data-level]").forEach(s => {
    s.addEventListener("click", e => e.stopPropagation());
    s.addEventListener("change", async () => {
      try { await post("/api/lint/level", { rule: s.dataset.level, level: s.value || null }); reload(); }
      catch (ex) { alert(ex.message || ex); }
    });
  });
  $$("#pane-pruefungen [data-ignore-en]").forEach(b =>
    b.addEventListener("click", async e => {
      e.stopPropagation();
      try { await post("/api/lint/ignore-inconsistent", { english: b.dataset.ignoreEn, ignore: true }); reload(); }
      catch (ex) { alert(ex.message || ex); }
    }));
  $$("#pane-pruefungen [data-rekey]").forEach(b =>
    b.addEventListener("click", async e => {
      e.stopPropagation();
      if (!confirm("Neuen Eintrag mit der aktuellen Spiel-ID anlegen (gleicher Context, gleicher Wert)? "
          + "Der alte Eintrag bleibt und wird als verwaist markiert.")) return;
      try {
        await api("/api/scenes/rekey", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ uid: b.dataset.rekey }) });
        b.replaceWith(Object.assign(document.createElement("span"), { className: "pill ok", textContent: "neu angelegt" }));
      } catch (err) { alert(err.message); }
    }));
  $$("#pane-pruefungen [data-uid]").forEach(li =>
    li.addEventListener("click", () => {
      $('#tabs button[data-tab="uebersetzungen"]').click();
      select(li.dataset.uid);
    }));
}
/* ------------------------------------------------ Lexikon */
const GENDER_LABEL = { m: "m (der)", f: "f (die)", n: "n (das)", p: "p (die, Plural)" };

function renderLexiconPane(p, d) {
  const lintHtml = (d.lint && d.lint.length)
    ? `<ul class="lintlist">${d.lint.map(f =>
        `<li class="${esc(f.severity)}"><span class="rule">${esc(f.rule)}</span>${esc(f.message)}
         ${f.twin ? ` <button class="ghost" data-twin="${esc(f.twin)}" data-g="${esc(f.gender)}">Zwilling anlegen</button>` : ""}</li>`).join("")}</ul>`
    : '<p class="mini">Keine Lexikon-Befunde.</p>';
  p.innerHTML = `
    <h2>Genus-Lexikon (GenderLexicon.tsv) — ${d.entries.length} Einträge</h2>
    <p class="mini">Einzige Genus-Quelle (Kontrakt: Genus-Fixes hierhin, nie in Code).
      Suffix-Vererbung: der längste Eintrag ≥3 Zeichen gewinnt (werkbank ← bank).</p>
    <div class="btnrow">
      <input type="text" id="lex-noun" class="deval" style="min-height:0;width:200px" placeholder="Nomen (klein, sichtbare Form)">
      <select id="lex-gender">${Object.entries(GENDER_LABEL).map(([g, l]) =>
        `<option value="${g}">${l}</option>`).join("")}</select>
      <button class="ghost" id="lex-preview">Konsequenzen prüfen</button>
      <button class="primary" id="lex-save">Eintrag speichern</button>
    </div>
    <div id="lex-msg"></div>
    <div id="lex-preview-box"></div>
    <h2>Befunde</h2>${lintHtml}
    <h2>Einträge</h2>
    <input type="text" id="lex-filter" class="deval" style="min-height:0;width:220px" placeholder="filtern …">
    <table class="data" id="lex-table">
      <tr><th>Nomen</th><th>Genus</th><th></th></tr>
      ${d.entries.map(e => `
        <tr data-noun="${esc(e.noun)}"><td>${esc(e.noun)}</td><td>${esc(e.gender)}</td>
          <td><button class="ghost danger" data-del="${esc(e.noun)}">löschen</button></td></tr>`).join("")}
    </table>`;
  $("#lex-filter").addEventListener("input", e => {
    const f = e.target.value.toLowerCase();
    $$("#lex-table tr[data-noun]").forEach(tr =>
      tr.style.display = tr.dataset.noun.includes(f) ? "" : "none");
  });
  $("#lex-preview").onclick = async () => {
    const noun = $("#lex-noun").value.trim(), g = $("#lex-gender").value;
    if (!noun) return;
    const box = $("#lex-preview-box");
    box.innerHTML = '<p class="mini">prüfe …</p>';
    try {
      const pv = await api(`/api/lexicon/preview?noun=${encodeURIComponent(noun)}&gender=${g}`);
      box.innerHTML = `
        <div class="msg ${pv.changes.length ? "warn" : "ok"}">
          ${pv.replaces ? `Ersetzt bestehenden Eintrag (${esc(pv.replaces)} → ${esc(pv.gender)}). ` : "Neuer Eintrag. "}
          ${pv.changes.length
            ? `${pv.changes.length} Kopf-Nomen ändern ihr Genus:`
            : "Keine bestehenden Anzeigenamen ändern ihr Genus."}
          ${pv.twin && pv.twin_present === false
            ? `<br>Faltungs-Zwilling „${esc(pv.twin)}“ fehlt noch — mit anlegen!` : ""}
        </div>
        ${pv.changes.map(c => `
          <p class="mini"><code>${esc(c.head)}</code>:
            ${esc(c.old.gender)} (${esc(c.old.source)}) → ${esc(c.new.gender)} (${esc(c.new.source)})
            — z. B. ${c.examples.map(esc).join(", ")}</p>`).join("")}`;
    } catch (e) { box.innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; }
  };
  $("#lex-save").onclick = async () => {
    try {
      await api("/api/lexicon", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ noun: $("#lex-noun").value, gender: $("#lex-gender").value }) });
      panes.lexikon();
    } catch (e) { $("#lex-msg").innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; }
  };
  $$("#pane-lexikon [data-del]").forEach(b => b.onclick = async () => {
    if (!confirm(`Eintrag „${b.dataset.del}“ löschen?`)) return;
    await api("/api/lexicon", { method: "DELETE", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ noun: b.dataset.del }) });
    panes.lexikon();
  });
  $$("#pane-lexikon [data-twin]").forEach(b => b.onclick = async () => {
    await api("/api/lexicon", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ noun: b.dataset.twin, gender: b.dataset.g }) });
    panes.lexikon();
  });
}

/* ------------------------------------------------ Verben */
function renderVerbsPane(p, d) {
  p.innerHTML = `
    <h2>Starke Verben (Verbs.json) — ${d.entries.length} Einträge</h2>
    <p class="mini">Nur unregelmäßige Verben brauchen Einträge; schwache konjugiert
      der Code selbst (Stamm+t). Trennbare Präfix-Verben sind tabu (Wortstellung).</p>
    <div class="btnrow">
      <input type="text" id="vb-inf" class="deval" style="min-height:0;width:160px" placeholder="Infinitiv (sehen)">
      <button class="ghost" id="vb-check">Schwach-Vorschau</button>
    </div>
    <div id="vb-preview"></div>
    <div class="btnrow">
      <input type="text" id="vb-en" class="deval" style="min-height:0;width:130px" placeholder="en (see)">
      <input type="text" id="vb-s3" class="deval" style="min-height:0;width:110px" placeholder="s3 (sieht)">
      <input type="text" id="vb-s2" class="deval" style="min-height:0;width:110px" placeholder="s2 du (siehst)">
      <input type="text" id="vb-p2" class="deval" style="min-height:0;width:110px" placeholder="p2 (seht)">
      <input type="text" id="vb-p3" class="deval" style="min-height:0;width:110px" placeholder="p3 (sehen)">
      <button class="primary" id="vb-save">Verb speichern</button>
    </div>
    <div id="vb-msg"></div>
    <h2>Einträge</h2>
    <input type="text" id="vb-filter" class="deval" style="min-height:0;width:220px" placeholder="filtern …">
    <table class="data" id="vb-table">
      <tr><th>inf</th><th>s3</th><th>s2 (du)</th><th>p2</th><th>p3</th><th>en</th><th></th></tr>
      ${d.entries.map(v => `
        <tr data-inf="${esc(v.inf)}"><td>${esc(v.inf)}</td><td>${esc(v.s3 || "")}</td><td>${esc(v.s2 || "")}</td>
          <td>${esc(v.p2 || "")}</td><td>${esc(v.p3 || "")}</td><td class="sans mini">${esc(v.en || "")}</td>
          <td><button class="ghost danger" data-del="${esc(v.inf)}">löschen</button></td></tr>`).join("")}
    </table>`;
  $("#vb-filter").addEventListener("input", e => {
    const f = e.target.value.toLowerCase();
    $$("#vb-table tr[data-inf]").forEach(tr =>
      tr.style.display = tr.dataset.inf.includes(f) ? "" : "none");
  });
  $("#vb-check").onclick = async () => {
    const inf = $("#vb-inf").value.trim();
    if (!inf) return;
    const box = $("#vb-preview");
    try {
      const pv = await api("/api/verbs/weak?inf=" + encodeURIComponent(inf));
      box.innerHTML = `
        <div class="msg ${pv.exists ? "ok" : "warn"}">
          Schwache Konjugation (er / du / ihr / sie): <code>${esc(pv.weak.s3)} / ${esc(pv.weak.s2)} / ${esc(pv.weak.p2)} / ${esc(pv.weak.p3)}</code>
          — stimmt das, ist <b>kein Eintrag nötig</b>; weicht die echte Form ab
          (z. B. sieht ≠ seht), Eintrag anlegen.
          ${pv.exists ? "<br>Eintrag existiert bereits." : ""}
          ${pv.separable ? `<br>⚠ Präfix „${esc(pv.separable.prefix)}-“ ist ${pv.separable.ambiguous ? "oft" : ""} trennbar — Kontrakt beachten.` : ""}
        </div>`;
    } catch (e) { box.innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; }
  };
  $("#vb-save").onclick = async () => {
    try {
      await api("/api/verbs", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          inf: $("#vb-inf").value, en: $("#vb-en").value,
          s3: $("#vb-s3").value, s2: $("#vb-s2").value, p2: $("#vb-p2").value, p3: $("#vb-p3").value,
        }) });
      panes.verben();
    } catch (e) { $("#vb-msg").innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; }
  };
  $$("#pane-verben [data-del]").forEach(b => b.onclick = async () => {
    if (!confirm(`Verb „${b.dataset.del}“ löschen?`)) return;
    await api("/api/verbs", { method: "DELETE", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ inf: b.dataset.del }) });
    panes.verben();
  });
}
/* ------------------------------------------------ Tests */
function wireAutoTests() {
  const b = $("#ts-auto");
  if (!b) return;
  b.onclick = async () => {
    if (!confirm("Alle ctx-auto-Tests neu erzeugen (alte werden ersetzt)? Danach: abgleichen + Spiel starten.")) return;
    try {
      const r = await api("/api/tests/auto", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      alert(r.count + " Tests angelegt.");
      panes.tests();
    } catch (e) { alert(e.message); }
  };
}

function renderTestsPane(p, d) {
  const prefill = JSON.parse(sessionStorage.getItem("mktest") || "null");
  sessionStorage.removeItem("mktest");
  const statusBadge = t =>
    t.result === "PASS" ? '<span class="badge" style="background:var(--green);color:#14161a">PASS</span>'
    : t.result === "FAIL" ? '<span class="badge error">FAIL</span>'
    : t.result === "ERROR" ? '<span class="badge warning">ERROR</span>'
    : '<span class="badge info">noch nicht ausgeführt</span>';
  p.innerHTML = `
    <h2>Kurator-Tests (CuratorTests.json) — ${d.tests.length} Tests</h2>
    <div class="btnrow">
      <button class="ghost" id="ts-auto" title="Erzeugt ctx-auto-Tests aus den häufigsten Grammatik-Tokens des Korpus; expected = Ausgabe der Vorschau-Emulation. FAIL im Spiel = Emulation weicht vom Spiel ab.">Emulation prüfen (ctx-auto-Tests erzeugen)</button>
      <span class="mini">${(() => { const a = d.tests.filter(t => t.id.startsWith("ctx-auto-"));
        if (!a.length) return "";
        const f = a.filter(t => t.result === "FAIL" || t.result === "ERROR").length;
        const ok = a.filter(t => t.result === "PASS").length;
        return `Emulation ↔ Spiel: ${ok} PASS, ${f} Abweichung${f === 1 ? "" : "en"}, ${a.length - ok - f} offen`; })()}</span>
    </div>
    <div class="msg ${d.synced ? (d.run_stale ? "warn" : "ok") : "warn"}">
      Tests laufen <b>im Spiel</b> beim Mod-Load — die UI führt selbst keine Grammatik aus.
      ${!d.deployed_exists ? "Testdatei ist noch nicht im Spiel-Ordner — im Tab „Protokoll & Abgleich“ abgleichen."
        : !d.synced ? "Testdatei weicht vom Spiel-Ordner ab — abgleichen, dann Spiel starten."
        : d.run_stale ? "Ergebnisse im Log sind VERALTET (Testdatei wurde seit dem Lauf geändert) — Spiel neu starten."
        : d.log_has_run ? "Ergebnisse aktuell (Log-Stand: " + fmtTime(d.log_mtime) + ")."
        : "Noch kein Lauf im Log — Spiel starten."}
    </div>
    <h2>Neuer / geänderter Test</h2>
    <div class="btnrow">
      <input type="text" id="t-id" class="deval" style="min-height:0;width:180px" placeholder="id (kebab-case)"
        value="${prefill ? esc(slugify(prefill.description)) : ""}">
      <input type="text" id="t-desc" class="deval" style="min-height:0;flex:1" placeholder="Beschreibung"
        value="${prefill ? esc(prefill.description) : ""}">
    </div>
    <div class="btnrow">
      <input type="text" id="t-subject" class="deval" style="min-height:0;width:170px" placeholder="subject (Snapjaw)" list="bp-list">
      <input type="text" id="t-object" class="deval" style="min-height:0;width:170px" placeholder="object (Torch)" list="bp-list"
        value="${prefill ? esc(prefill.object) : ""}">
      <datalist id="bp-list">${(d.blueprints || []).map(b => `<option value="${esc(b)}">`).join("")}</datalist>
    </div>
    <textarea id="t-template" class="deval" placeholder="Template mit Tokens, z. B. =object.a.dativ=">${prefill ? esc(prefill.template) : ""}</textarea>
    <textarea id="t-expected" class="deval" placeholder="Erwarteter deutscher Output (byte-genau)"></textarea>
    <div class="btnrow">
      <button class="primary" id="t-save">Test speichern</button>
      <span class="mini">subject/object leer = Snapjaw</span>
    </div>
    <div id="t-msg"></div>
    <h2>Bestehende Tests</h2>
    <table class="data">
      <tr><th>Status</th><th>id</th><th>Template</th><th>erwartet</th><th>object</th><th></th></tr>
      ${d.tests.map(t => `
        <tr>
          <td class="sans">${statusBadge(t)}${t.enabled === false ? ' <span class="mini">(deaktiviert)</span>' : ""}</td>
          <td>${esc(t.id)}</td><td>${hi(t.template)}</td><td>${hi(t.expected)}</td>
          <td>${esc(t.object || "")}</td>
          <td class="sans">
            <button class="ghost" data-edit="${esc(t.id)}">bearbeiten</button>
            <button class="ghost danger" data-del="${esc(t.id)}">löschen</button>
          </td>
        </tr>
        ${t.detail ? `<tr><td></td><td colspan="5" class="mini">${esc(t.detail)}</td></tr>` : ""}`).join("")}
    </table>`;
  $("#t-save").onclick = async () => {
    try {
      await api("/api/tests", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: $("#t-id").value, description: $("#t-desc").value,
          subject: $("#t-subject").value, object: $("#t-object").value,
          template: $("#t-template").value, expected: $("#t-expected").value,
          sourceUnit: prefill ? prefill.sourceUnit : "",
        }) });
      panes.tests();
    } catch (e) { $("#t-msg").innerHTML = '<div class="msg err">' + esc(e.message) + "</div>"; }
  };
  $$("#pane-tests [data-del]").forEach(b => b.onclick = async () => {
    if (!confirm(`Test „${b.dataset.del}“ löschen?`)) return;
    await api("/api/tests", { method: "DELETE", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: b.dataset.del }) });
    panes.tests();
  });
  $$("#pane-tests [data-edit]").forEach(b => b.onclick = () => {
    const t = d.tests.find(x => x.id === b.dataset.edit);
    if (!t) return;
    $("#t-id").value = t.id; $("#t-desc").value = t.description || "";
    $("#t-subject").value = t.subject || ""; $("#t-object").value = t.object || "";
    $("#t-template").value = t.template; $("#t-expected").value = t.expected;
    window.scrollTo(0, 0);
  });
}

function slugify(s) {
  return (s || "").toLowerCase()
    .replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
}
/* ------------------------------------------------ Protokoll & Abgleich */
function fmtTime(t) {
  return t ? new Date(t * 1000).toLocaleString("de-DE") : "—";
}

function renderLogPane(p, d) {
  if (!d.log.exists) {
    p.innerHTML = `<div class="msg warn">Player.log nicht gefunden unter
      <code>${esc(d.log.path)}</code> — Pfad in config.json (player_log) setzen.</div>`;
    return;
  }
  const stale = d.last_sync && d.log.mtime && d.log.mtime < d.last_sync.time;
  const st = d.selftests;
  const sumHtml = st.summaries.map(s =>
    `<span class="pill ${s.failed ? "err" : "ok"}">${esc(s.name)}: ${s.passed}✓${s.failed ? " " + s.failed + "✗" : ""}</span>`).join(" ");
  const curatorHtml = renderCuratorResults(d);
  p.innerHTML = `
    <h2>Player.log — Stand ${fmtTime(d.log.mtime)}</h2>
    ${stale ? `<div class="msg warn">Log ist ÄLTER als der letzte Abgleich (${fmtTime(d.last_sync.time)})
      — Ergebnisse stammen vom alten Stand. Spiel neu starten.</div>` : ""}

    <h2>[QudDE]-Selbsttests</h2>
    <p>${st.pass}× PASS, ${st.fail}× FAIL ${sumHtml}</p>
    ${st.fail_lines.length ? `<ul class="lintlist">${st.fail_lines.map(l =>
      `<li class="error">${esc(l)}</li>`).join("")}</ul>` : ""}

    <h2>Kurator-Tests</h2>
    ${curatorHtml}

    <h2>String-Misses</h2>
    <details class="group" ${d.new_misses.length ? "" : ""}>
      <summary>${d.benign_count} bekannte benigne Startup-Misses ✓ (DifficultyEvaluation, Message Log)</summary>
      <ul class="lintlist">${d.misses.filter(m => m.benign).map(m =>
        `<li class="info">Context="${esc(m.context)}" ID="${esc(m.id)}"</li>`).join("")}</ul>
    </details>
    ${d.new_misses.length ? `
      <p><span class="badge error">${d.new_misses.length} neue Misses</span> — diese Strings fielen im Spiel auf Englisch zurück:</p>
      <ul class="lintlist">${d.new_misses.map((m, i) => `
        <li class="error">Context="${esc(m.context)}" ID="${esc(m.id)}"
          ${m.uid ? `<button class="ghost" data-goto="${esc(m.uid)}">Eintrag öffnen (existiert — Wert prüfen)</button>`
                  : `<button class="ghost" data-create="${i}">Eintrag anlegen</button>`}
        </li>`).join("")}</ul>`
      : '<p class="mini">Keine neuen Misses — Baseline sauber.</p>'}

    <h2>MODWARN (deutscher Mod)</h2>
    ${d.modwarns_german.length ? `<ul class="lintlist">${d.modwarns_german.map(w =>
        `<li class="${w.compiler_warning ? "info" : "error"}">
          ${w.compiler_warning ? "<span class='rule'>Compiler-Warnung (benigne)</span>" : "<span class='rule'>XML/Schema!</span>"}
          ${esc(w.text.slice(0, 220))}</li>`).join("")}</ul>`
      : '<p class="mini">Keine.</p>'}
    <p class="mini">${d.modwarns_other_count} MODWARNs anderer Mods (ausgeblendet).</p>

    <h2>Deploy-Abgleich</h2>
    <div id="deploybox"><p class="mini">Lade …</p></div>`;
  $$("#pane-protokoll [data-goto]").forEach(b => b.onclick = () => {
    $('#tabs button[data-tab="uebersetzungen"]').click();
    select(b.dataset.goto);
  });
  $$("#pane-protokoll [data-create]").forEach(b => b.onclick = () => {
    const m = d.new_misses[Number(b.dataset.create)];
    $('#tabs button[data-tab="uebersetzungen"]').click();
    renderCreateForm({
      file: guessTargetFile(m.context), context: m.context,
      english: m.id, key: ["S", m.id], is_strings: true,
    });
  });
  loadDeployBox();
}

function guessTargetFile(context) {
  return /^Conversation/.test(context || "")
    ? "Strings.Conversations.de.xml" : "Strings.de.xml";
}

function renderCuratorResults(d) {
  const c = d.curator;
  if (!c.header && !c.results.length)
    return '<p class="mini">Noch keine Kurator-Tests im Log — Tests im Tab „Tests“ anlegen, abgleichen, Spiel starten.</p>';
  const n = { PASS: 0, FAIL: 0, ERROR: 0 };
  c.results.forEach(r => { n[r.status] = (n[r.status] || 0) + 1; });
  return `
    <p><span class="pill ${n.FAIL || n.ERROR ? "err" : "ok"}">${n.PASS}✓ ${n.FAIL}✗ ${n.ERROR}⚠</span></p>
    ${c.results.filter(r => r.status !== "PASS").map(r =>
      `<ul class="lintlist"><li class="error"><span class="rule">${esc(r.id)}</span>${esc(r.detail)}</li></ul>`).join("")}`;
}

async function loadDeployBox() {
  const box = $("#deploybox");
  if (!box) return;
  try {
    const s = await api("/api/deploy/status");
    renderDeployBox(box, s);
  } catch (e) {
    box.innerHTML = e.status === 404
      ? '<p class="mini">Abgleich folgt in Phase 7.</p>'
      : '<div class="msg err">' + esc(e.message) + "</div>";
  }
}
function renderDeployBox(box, s) {
  if (!s.exists) {
    box.innerHTML = `<div class="msg warn">Deploy-Ordner nicht gefunden:
      <code>${esc(s.deploy_dir)}</code></div>`;
    return;
  }
  const diffs = [...s.changed.map(f => ["geändert", f]),
                 ...s.missing.map(f => ["fehlt im Spiel-Ordner", f]),
                 ...s.surplus.map(f => ["überzählig im Spiel-Ordner", f])];
  updateDeployPill(s);
  box.innerHTML = s.in_sync
    ? `<p><span class="pill ok">Abgleich: identisch (${s.identical} Dateien)</span></p>`
    : `<p><span class="pill warn">${diffs.length} Datei(en) abweichend</span></p>
       <table class="data">${diffs.map(([k, f]) =>
         `<tr><td class="sans mini">${esc(k)}</td><td>${esc(f)}</td></tr>`).join("")}</table>
       <div class="btnrow">
         <button class="primary" id="btn-sync">Abgleichen (Repo → Spiel-Ordner)</button>
         <span class="mini">kopiert Geändertes/Fehlendes, löscht Überzähliges nur unter languages/</span>
       </div>
       <div id="syncmsg"></div>`;
  const btn = $("#btn-sync");
  if (btn) btn.onclick = async () => {
    const ops = diffs.map(([k, f]) => `${k}: ${f}`).join("\n");
    if (!confirm("Diese Operationen ausführen?\n\n" + ops)) return;
    try {
      const r = await api("/api/deploy/sync", { method: "POST" });
      $("#syncmsg").innerHTML = `<div class="msg ok">Abgeglichen: ${r.copied.length} kopiert,
        ${r.deleted.length} gelöscht. Jetzt Spiel starten, um Tests/Log zu aktualisieren.</div>`;
      loadDeployBox();
    } catch (e) {
      $("#syncmsg").innerHTML = '<div class="msg err">' + esc(e.message) + "</div>";
    }
  };
}

async function updateDeployPill(s) {
  const pill = $("#pill-deploy");
  pill.hidden = false;
  pill.textContent = s.in_sync ? "Deploy ✓" :
    "Deploy: " + (s.changed.length + s.missing.length + s.surplus.length) + " abweichend";
  pill.className = "pill " + (s.in_sync ? "ok" : "warn");
}

/* ------------------------------------------------ Start */
(async function init() {
  try { await loadMeta(); } catch (e) { $("#pill-units").textContent = "Server-Fehler"; }
  search(true);
  try { updateDeployPill(await api("/api/deploy/status")); } catch (e) { /* Phase 7 */ }
})();
