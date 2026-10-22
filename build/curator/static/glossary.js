/* QudDE Kurator — Glossar + Anrede-Richtlinie (Terminologie-Konsistenz).
   Daten: build/curator/data/glossary.json. Prüfregeln K2 (Anrede), G1/G2
   (Begriff/Genus) lesen sie; die Szenen-Vorschau markiert Begriffe.
   Nutzt aus app.js: $, $$, api, esc, panes, GENDER_LABEL. */
"use strict";

const GLOSSAR = (() => {
  const post = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  let data = null;

  async function load() {
    const pane = $("#pane-glossar");
    try { data = await api("/api/glossary"); }
    catch (e) { pane.innerHTML = '<div class="placeholder">' + esc(e.message) + "</div>"; return; }
    render(pane);
    loadSuggestions();
  }

  function addrSelect(id, val) {
    return `<select id="${id}">${["Ihr", "Sie", "du"].map(f =>
      `<option ${f === val ? "selected" : ""}>${f}</option>`).join("")}</select>`;
  }

  function render(pane) {
    const rows = data.terms.map(t => `
      <tr>
        <td>${esc(t.en)}</td><td>${esc(t.de)}</td>
        <td>${esc(t.gender || "—")}${t.gender && t.gender !== t.lexicon_gender
          ? ` <span class="badge warning" title="Genus-Lexikon/Heuristik ergibt ${esc(t.lexicon_gender)} (${esc(t.lexicon_source)}) — die Token-Ebene (=object.dativ= …) würde so deklinieren">Lexikon: ${esc(t.lexicon_gender)}</span>
             <button class="ghost sm" data-lex="${esc(t.de)}" data-g="${esc(t.gender)}">ins Lexikon</button>` : ""}</td>
        <td>${esc(t.plural || "")}</td>
        <td class="sans">${esc((t.variants_forbidden || []).join(", "))}</td>
        <td class="sans mini">${esc(t.note || "")}</td>
        <td><button class="ghost sm" data-edit="${esc(t.en)}">bearbeiten</button>
            <button class="ghost sm danger" data-del="${esc(t.en)}">×</button></td>
      </tr>`).join("");
    pane.innerHTML = `
      <h2>Anrede-Richtlinie</h2>
      <p class="mini">Prüfregel K2 meldet Gesprächstexte, deren Anrede abweicht (du/Sie/Ihr-Heuristik).</p>
      <div class="btnrow">
        <label class="mini">NPC spricht Spieler an mit ${addrSelect("gl-player", data.policy.player_address)}</label>
        <label class="mini">Spieler-Antworten an NPC ${addrSelect("gl-choice", data.policy.choice_address)}</label>
        <button class="ghost" id="gl-policy">Richtlinie speichern</button>
      </div>
      <h2>Begriffe (${data.terms.length})</h2>
      <p class="mini">G1: Begriff steht im Englischen, die deutsche Festlegung fehlt (oder eine verbotene Variante steht da).
        G2: Artikel direkt vor dem Begriff passt in keinem Kasus zum Genus; Genitiv m/n ohne -s.</p>
      <div class="btnrow glform">
        <input type="text" id="gl-en" class="deval" placeholder="englisch (z. B. baetyl)">
        <input type="text" id="gl-de" class="deval" placeholder="deutsch (Baetyl)">
        <select id="gl-g"><option value="">Genus —</option>${Object.entries(GENDER_LABEL).map(([g, l]) =>
          `<option value="${g}">${esc(l)}</option>`).join("")}</select>
        <input type="text" id="gl-pl" class="deval" placeholder="Plural (optional)">
        <input type="text" id="gl-bad" class="deval" placeholder="verbotene Varianten, kommagetrennt">
        <input type="text" id="gl-note" class="deval" placeholder="Notiz">
        <button class="primary" id="gl-save">Begriff speichern</button>
      </div>
      <div id="gl-msg"></div>
      <table class="data">
        <tr><th>englisch</th><th>deutsch</th><th>Genus</th><th>Plural</th><th>verboten</th><th>Notiz</th><th></th></tr>
        ${rows || '<tr><td colspan="7" class="sans mini">Noch keine Begriffe — Vorschläge unten übernehmen.</td></tr>'}
      </table>
      <div id="gl-sugg"><div class="placeholder">Lade …</div></div>`;
    $("#gl-policy").onclick = () => save({ policy: { player_address: $("#gl-player").value, choice_address: $("#gl-choice").value } });
    $("#gl-save").onclick = () => save({ term: {
      en: $("#gl-en").value, de: $("#gl-de").value, gender: $("#gl-g").value, plural: $("#gl-pl").value,
      variants_forbidden: $("#gl-bad").value.split(","), note: $("#gl-note").value } });
    $$("[data-edit]", pane).forEach(b => b.onclick = () => fill(data.terms.find(t => t.en === b.dataset.edit)));
    $$("[data-del]", pane).forEach(b => b.onclick = async () => {
      if (!confirm("Begriff „" + b.dataset.del + "“ löschen?")) return;
      try { data = await api("/api/glossary", post("DELETE", { en: b.dataset.del })); render(pane); loadSuggestions(); }
      catch (e) { msg(e.message, "err"); }
    });
    $$("[data-lex]", pane).forEach(b => b.onclick = async () => {
      try {
        await api("/api/lexicon", post("POST", { noun: b.dataset.lex.toLowerCase(), gender: b.dataset.g }));
        load();
      } catch (e) { msg(e.message, "err"); }
    });
  }

  function fill(t) {
    if (!t) return;
    $("#gl-en").value = t.en; $("#gl-de").value = t.de; $("#gl-g").value = t.gender || "";
    $("#gl-pl").value = t.plural || ""; $("#gl-bad").value = (t.variants_forbidden || []).join(", ");
    $("#gl-note").value = t.note || "";
    $("#gl-en").focus();
  }

  function msg(text, kind) {
    const el = $("#gl-msg");
    if (el) el.innerHTML = `<div class="msg ${kind || "ok"}">${esc(text)}</div>`;
  }

  async function save(body) {
    try {
      data = await api("/api/glossary", post("POST", body));
      render($("#pane-glossar"));
      msg("Gespeichert — Prüfungen und Vorschau nutzen den neuen Stand.");
      loadSuggestions();
      if (typeof SCENES !== "undefined") SCENES.setGlossary(data);
    } catch (e) { msg(e.message, "err"); }
  }

  async function loadSuggestions() {
    const box = $("#gl-sugg");
    if (!box) return;
    let d;
    try { d = await api("/api/glossary/suggest"); }
    catch (e) { box.innerHTML = '<div class="placeholder">' + esc(e.message) + "</div>"; return; }
    const names = d.names || [];
    const namesHtml = names.length ? `
      <h2>Namen aus Kreaturen/Gegenständen (${names.length})</h2>
      <p class="mini">Englischer DisplayName → deutscher DisplayName, wenn der Name im englischen Korpus ≥3× vorkommt.
        „belegt“ = Anteil dieser Stellen, deren deutscher Wert den Namen auch enthält (niedrig = Übersetzung uneinheitlich
        oder falsche Zuordnung). Vorausgewählt: belegt ≥ 80 %.</p>
      <div class="btnrow"><button class="primary" id="gl-take-sel">Ausgewählte übernehmen</button>
        <button class="ghost sm" id="gl-sel-none">keine</button><button class="ghost sm" id="gl-sel-all">alle</button></div>
      <table class="data" id="gl-names">
        <tr><th></th><th>englisch</th><th>deutsch</th><th>Genus</th><th>×</th><th>belegt</th><th>Blueprint</th></tr>
        ${names.map((s, i) => `<tr>
          <td><input type="checkbox" data-i="${i}" ${s.attested >= 0.8 ? "checked" : ""}></td>
          <td>${esc(s.en)}</td>
          <td><input type="text" class="deval glinl" data-de="${i}" value="${esc(s.de)}"></td>
          <td><select data-g="${i}">${["m", "f", "n", "p"].map(g => `<option ${g === s.gender ? "selected" : ""}>${g}</option>`).join("")}</select>
            <span class="mini" title="Quelle der Genus-Vorbelegung">${esc(s.gender_source)}</span></td>
          <td>${s.count}</td>
          <td><span class="badge ${s.attested >= 0.8 ? "info" : "warning"}">${Math.round(100 * s.attested)} %</span></td>
          <td class="mini">${esc(s.blueprint || "")}${s.alternatives.length ? " · auch: " + esc(s.alternatives.join(", ")) : ""}</td>
        </tr>`).join("")}
      </table>` : "";
    box.innerHTML = namesHtml + (d.suggestions.length ? `<h2>Eingefärbte Begriffe</h2>
      <p class="mini">{{X|…}}-markierte Wörter der englischen Vorlagen mit den deutschen Spannen an gleicher Position —
        mehrere deutsche Varianten = Inkonsistenz-Kandidat.</p><table class="data">
      <tr><th>englisch</th><th>×</th><th>deutsche Varianten</th><th></th></tr>
      ${d.suggestions.map(s => `<tr>
        <td>${esc(s.en)}</td><td>${s.count}</td>
        <td class="sans">${s.de.map(x => `${esc(x.de)} <span class="mini">(${x.count})</span>`).join(" · ")
          || '<span class="mini">keine Zuordnung</span>'}
          ${s.de.length > 1 ? ' <span class="badge warning">uneinheitlich</span>' : ""}</td>
        <td><button class="ghost sm" data-take="${esc(s.en)}" data-de="${esc(s.de[0] ? s.de[0].de : "")}">übernehmen</button></td>
      </tr>`).join("")}</table>` : '<p class="mini">Keine weiteren Vorschläge.</p>');
    const take = $("#gl-take-sel");
    if (take) take.onclick = async () => {
      const terms = $$("#gl-names input[type=checkbox]:checked").map(cb => {
        const i = cb.dataset.i, s = names[i];
        return { en: s.en, de: $(`[data-de="${i}"]`).value.trim(), gender: $(`[data-g="${i}"]`).value,
                 note: "aus DisplayName " + (s.blueprint || "") };
      });
      if (!terms.length) return;
      if (!confirm(terms.length + " Begriffe ins Glossar übernehmen?")) return;
      await save({ terms });
    };
    const none = $("#gl-sel-none"), all = $("#gl-sel-all");
    if (none) none.onclick = () => $$("#gl-names input[type=checkbox]").forEach(c => { c.checked = false; });
    if (all) all.onclick = () => $$("#gl-names input[type=checkbox]").forEach(c => { c.checked = true; });
    $$("[data-take]", box).forEach(b => b.onclick = () =>
      fill({ en: b.dataset.take, de: b.dataset.de, gender: "", plural: "", variants_forbidden: [], note: "" }));
  }

  panes.glossar = load;
  return { load };
})();
