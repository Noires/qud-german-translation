/* QudDE Kurator — Prüfrunde: alle Übersetzungen in Sichtbarkeits-Reihenfolge prüfen.
   Bereiche links (Fortschritt + Stichproben-Fehlerquote), rechts der aktuelle Eintrag
   mit Szenen-Vorschau. Tasten: G/Enter geprüft · M markieren (Textstelle vorher
   im deutschen Wert auswählen) · N/→ überspringen · B/← zurück · E im Editor öffnen.
   Nutzt aus app.js: $, $$, api, esc, panes, updateReviewPill; aus scenes.js: SCENES. */
"use strict";

const REVIEWQ = (() => {
  const R = { bucket: "", mode: "priority", n: 50, items: [], pos: 0, data: null, history: [] };
  const post = (url, obj) => api(url, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(obj) });

  async function load(keepPos) {
    const p = new URLSearchParams({ bucket: R.bucket, mode: R.mode, n: R.n, limit: 200 });
    R.data = await api("/api/review/queue?" + p);
    R.items = R.data.items;
    if (!keepPos) R.pos = 0;
    R.pos = Math.min(R.pos, Math.max(0, R.items.length - 1));
    render();
  }

  function pct(a, b) { return b ? Math.round(100 * a / b) : 0; }

  function bucketsHtml() {
    return R.data.buckets.map(b => {
      const s = b.sample, rate = s.error_rate == null ? "–" : Math.round(100 * s.error_rate) + " %";
      return `<li class="${R.bucket === b.id ? "active" : ""}" data-bucket="${esc(b.id)}">
        <div class="rq-bname">${esc(b.label)}</div>
        <div class="rq-bar"><span style="width:${pct(b.checked, b.total)}%"></span></div>
        <div class="mini">${b.checked} / ${b.total} geprüft · ${b.flagged} markiert
          ${b.lint ? ` · ${b.lint} mit Befund` : ""}${b.triaged ? ` · ${b.triaged} triagiert` : ""}</div>
        <div class="mini">Stichprobe ${s.checked + s.flagged}/${s.n} · Fehlerquote ${rate}</div>
      </li>`;
    }).join("");
  }

  function itemHtml(it) {
    const flags = [it.flagged ? '<span class="badge warning">⚑ markiert</span>' : "",
      it.status === "stale" ? '<span class="badge info">veraltet geprüft</span>' : "",
      it.lint ? '<span class="badge warning">Prüf-Befund</span>' : "",
      it.triage ? `<span class="badge info">Triage ${it.triage}</span>` : ""].join(" ");
    const cats = Object.entries(R.data.categories || {})
      .map(([k, v]) => `<option value="${esc(k)}">${esc(v)}</option>`).join("");
    return `
      <div class="rq-head mini">${esc(it.file)} · ${esc(it.context)} ${flags}
        <span class="rq-pos">${R.pos + 1} / ${R.data.pending}</span></div>
      <div class="rq-text en" title="Englische Vorlage">${esc(it.english || "")}</div>
      <div class="rq-text de" id="rq-de" title="Deutscher Wert — Textstelle auswählen und M drücken">${esc(it.value)}</div>
      <div class="rq-actions">
        <button data-act="ok" title="G / Enter">✓ Geprüft</button>
        <button class="ghost" data-act="mark" title="M — vorher Textstelle im deutschen Wert auswählen">⚑ Markieren</button>
        <button class="ghost" data-act="skip" title="N / →">Überspringen</button>
        <button class="ghost" data-act="back" title="B / ←">Zurück</button>
        <button class="ghost" data-act="edit" title="E">Im Editor öffnen</button>
      </div>
      <form class="rq-mark" hidden>
        <div class="mini">Stelle: <b id="rq-span">(ganzer Wert)</b></div>
        <select name="category">${cats}</select>
        <input name="note" placeholder="Notiz (was ist falsch, ggf. Vorschlag)">
        <button type="submit">Markierung speichern</button>
        <button type="button" class="ghost" data-act="cancel">Abbrechen</button>
      </form>
      <h2>Im Kontext</h2>
      <div id="rq-scene"><div class="placeholder">Lade Szene …</div></div>`;
  }

  function render() {
    const pane = $("#pane-pruefrunde");
    const it = R.items[R.pos];
    pane.innerHTML = `
      <div class="rq">
        <aside class="rq-side">
          <div class="rq-mode">
            <label><input type="radio" name="rqmode" value="priority" ${R.mode === "priority" ? "checked" : ""}> Priorität</label>
            <label><input type="radio" name="rqmode" value="sample" ${R.mode === "sample" ? "checked" : ""}> Stichprobe (${R.n}/Bereich)</label>
          </div>
          <ul class="rq-buckets">
            <li class="${R.bucket === "" ? "active" : ""}" data-bucket=""><div class="rq-bname">Alle Bereiche</div></li>
            ${bucketsHtml()}
          </ul>
          <p class="mini">Reihenfolge: offene Markierungen, Prüf-Befunde, LLM-Triage, dann Gesprächstiefe.
            Fehlerquote = markiert / bearbeitet in der Stichprobe.</p>
        </aside>
        <section class="rq-main">${it ? itemHtml(it)
          : '<div class="placeholder">Nichts mehr zu prüfen in dieser Auswahl. 🎉</div>'}</section>
      </div>`;
    wire(pane);
    if (it) SCENES.renderInto($("#rq-scene"), it.uid);
  }

  function spanOf() {
    const de = $("#rq-de"), sel = window.getSelection();
    if (!de || !sel || sel.isCollapsed || !de.contains(sel.anchorNode) || !de.contains(sel.focusNode)) return null;
    const r = sel.getRangeAt(0), pre = document.createRange();
    pre.selectNodeContents(de); pre.setEnd(r.startContainer, r.startOffset);
    const start = pre.toString().length, text = r.toString();
    return text ? { start, end: start + text.length, text } : null;
  }

  async function decide(act) {
    const it = R.items[R.pos];
    if (!it) return;
    if (act === "ok") {
      const res = await post("/api/review", { uid: it.uid, checked: true });
      if (res.summary) updateReviewPill(res.summary);
      if (it.flagged) await post("/api/flags", { uid: it.uid, status: "fixed" });
      R.history.push(R.pos);
      R.items.splice(R.pos, 1);
      R.data.pending -= 1;
      return load(true);
    }
    if (act === "skip") { R.history.push(R.pos); R.pos = Math.min(R.pos + 1, R.items.length - 1); return render(); }
    if (act === "back") { R.pos = Math.max(0, R.history.length ? R.history.pop() : R.pos - 1); return render(); }
    if (act === "edit") { location.hash = "#unit/" + it.uid; return; }
    if (act === "mark") {
      const span = spanOf(), f = $(".rq-mark");
      f.hidden = false; f.dataset.span = span ? JSON.stringify(span) : "";
      $("#rq-span").textContent = span ? `„${span.text}“ (${span.start}–${span.end})` : "(ganzer Wert)";
      f.note.focus();
    }
  }

  function wire(pane) {
    $$("[data-bucket]", pane).forEach(li => li.addEventListener("click", () => { R.bucket = li.dataset.bucket; R.history = []; load(); }));
    $$("input[name=rqmode]", pane).forEach(r => r.addEventListener("change", () => { R.mode = r.value; R.history = []; load(); }));
    $$(".rq-actions [data-act]", pane).forEach(b => b.addEventListener("click", () => decide(b.dataset.act).catch(e => alert(e.message))));
    const f = $(".rq-mark", pane);
    if (!f) return;
    f.querySelector("[data-act=cancel]").addEventListener("click", () => { f.hidden = true; });
    f.addEventListener("submit", async e => {
      e.preventDefault();
      const it = R.items[R.pos];
      try {
        await post("/api/flags", { uid: it.uid, note: f.note.value, category: f.category.value,
          span: f.dataset.span ? JSON.parse(f.dataset.span) : null });
        it.flagged = true;
        R.history.push(R.pos);
        R.pos = Math.min(R.pos + 1, R.items.length - 1);
        load(true);
      } catch (ex) { alert(ex.message); }
    });
  }

  document.addEventListener("keydown", e => {
    if (!$("#tab-pruefrunde") || !$("#tab-pruefrunde").classList.contains("active")) return;
    if (e.target.closest("input, textarea, select") || e.ctrlKey || e.altKey || e.metaKey) return;
    const map = { g: "ok", Enter: "ok", m: "mark", n: "skip", ArrowRight: "skip", b: "back", ArrowLeft: "back", e: "edit" };
    const act = map[e.key] || map[e.key.toLowerCase()];
    if (!act) return;
    e.preventDefault();
    decide(act).catch(ex => alert(ex.message));
  });

  panes.pruefrunde = () => load().catch(e => { $("#pane-pruefrunde").innerHTML = '<div class="placeholder">' + esc(e.message) + "</div>"; });
  return { R, load };
})();
