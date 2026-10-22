/* QudDE Kurator — Qud-Textdarstellung für die Szenen-Vorschau.
   Parst Quds Farb-Markup ({{X|…}} verschachtelt, Shader aus Colors.xml,
   &X/^X Vorder-/Hintergrund), bricht auf eine feste Spaltenbreite um und
   rendert DOM-Spans, die klickbar bleiben (data-uid, data-tok).
   Token-Ausgaben kommen vom Server zwischen \u0001 … \u0002. */
"use strict";

const QUD = (() => {
  /* Quds 18 Farbbuchstaben (Visual Style, Wiki; k = Viridian-Hintergrund) */
  const PALETTE = {
    r: "#a64a2e", R: "#d74200", o: "#f15f22", O: "#e99f10",
    w: "#98875f", W: "#cfc041", g: "#009403", G: "#00c420",
    b: "#0048bd", B: "#0096ff", c: "#40a4b9", C: "#77bfcf",
    m: "#b154cf", M: "#da5bd6", y: "#b1c9c3", Y: "#ffffff",
    k: "#0f3b3a", K: "#155352",
  };
  const TS = "\u0001", TE = "\u0002";
  let COLORS = { solid: {}, shaders: {} };

  function setColors(c) { if (c) COLORS = c; }

  /* Shader-Name -> Funktion (index, länge) -> Farbbuchstabe | null */
  function shaderFor(name) {
    if (!name) return null;
    if (PALETTE[name] && name.length === 1) return () => name;
    const solid = COLORS.solid[name];
    if (solid) return () => solid;
    let sh = COLORS.shaders[name];
    const inline = /^([A-Za-z](?:-[A-Za-z])*) (sequence|alternation|solid|bordered)$/.exec(name);
    if (!sh && inline) sh = { type: inline[2], colors: inline[1].split("-") };
    if (!sh) return null;
    const cs = sh.colors.filter(x => PALETTE[x]);
    if (!cs.length) return null;
    switch (sh.type) {
      case "sequence": return i => cs[i % cs.length];
      case "alternation": return (i, n) => cs[Math.min(cs.length - 1, Math.floor(i * cs.length / Math.max(n, 1)))];
      case "bordered": return (i, n) => (i === 0 || i === n - 1) ? (cs[1] || cs[0]) : cs[0];
      default: return () => cs[0];
    }
  }

  /* Text -> Zellen [{ch, fg, bg, tok, nl}] */
  function parse(text, defaultFg) {
    const cells = [];
    const stack = []; // {fn, start, depth}
    let amp = null, ampDepth = -1, caret = null, tok = -1, tokN = -1;
    let unknownMarkup = [];
    const s = text || "";
    for (let i = 0; i < s.length; i++) {
      const c = s[i];
      if (c === TS) { tok = ++tokN; continue; }
      if (c === TE) { tok = -1; continue; }
      if (c === "{" && s[i + 1] === "{") {
        const bar = s.indexOf("|", i + 2);
        const close = s.indexOf("}}", i + 2);
        const name = bar > 0 ? s.slice(i + 2, bar) : "";
        if (bar > 0 && (close < 0 || bar < close) && !/[{}\n]/.test(name)) {
          const fn = shaderFor(name);
          if (!fn) unknownMarkup.push(name);
          stack.push({ fn, start: cells.length, depth: stack.length + 1 });
          i = bar;
          continue;
        }
      }
      if (c === "}" && s[i + 1] === "}" && stack.length) {
        const fr = stack.pop();
        const n = cells.length - fr.start;
        let k = 0;
        for (let j = fr.start; j < cells.length; j++) {
          const cell = cells[j];
          if (cell.nl) continue;
          if (fr.fn && cell.cd < fr.depth) { cell.fg = fr.fn(k, n); cell.cd = fr.depth; }
          k++;
        }
        i++;
        continue;
      }
      if (c === "&" && i + 1 < s.length) {
        const x = s[i + 1];
        if (x === "&") { push("&"); i++; continue; }
        if (PALETTE[x]) { amp = x; ampDepth = stack.length; i++; continue; }
      }
      if (c === "^" && i + 1 < s.length) {
        const x = s[i + 1];
        if (x === "^") { push("^"); i++; continue; }
        if (PALETTE[x]) { caret = x === "k" ? null : x; i++; continue; }
      }
      if (c === "\r") continue;
      push(c);
    }
    function push(ch) {
      const cell = { ch, fg: amp || defaultFg, bg: caret, tok,
                     cd: amp ? ampDepth + 0.5 : 0, nl: ch === "\n" };
      cells.push(cell);
    }
    cells.unknownMarkup = unknownMarkup;
    cells.unclosed = stack.length;
    return cells;
  }

  /* Zellen -> Zeilen (Wortumbruch an Leerzeichen, harte Umbrüche an \n) */
  function wrap(cells, cols) {
    const lines = [];
    let line = [], word = [];
    const flushWord = () => {
      if (!word.length) return;
      // führende Leerzeichen am Zeilenanfang fallen weg (wie Quds Umbruch)
      while (!line.length && word.length && word[0].ch === " ") word.shift();
      if (line.length + trimEnd(word).length > cols && line.length) {
        lines.push(trimEndArr(line));
        line = [];
        while (word.length && word[0].ch === " ") word.shift();
      }
      while (word.length > cols) { // überlanges Wort: hart teilen + markieren
        const part = word.splice(0, cols);
        part.overflow = true;
        lines.push(part);
      }
      line = line.concat(word);
      word = [];
    };
    for (const cell of cells) {
      if (cell.nl) { flushWord(); lines.push(trimEndArr(line)); line = []; continue; }
      if (cell.ch === " ") { flushWord(); word.push(cell); continue; }
      if (word.length && word[word.length - 1].ch === " ") flushWord();
      word.push(cell);
    }
    flushWord();
    lines.push(trimEndArr(line));
    return lines;
  }
  const trimEnd = w => { let n = w.length; while (n && w[n - 1].ch === " ") n--; return w.slice(0, n); };
  const trimEndArr = l => { const t = trimEnd(l); t.overflow = l.overflow; return t; };

  const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  const HOW_LABEL = {
    emu: "Mod-Replacer emuliert", approx: "Spiel-Replacer angenähert", spice: "Gewürz (HistorySpice)",
    sample: "Stichprobe (Tabelle)", unknown: "unbekannt — nicht aufgelöst", en: "englischer Fallback des Spiels",
    raw: "Token (unaufgelöst)",
  };

  /* render -> HTML-Zeilen. opts: {cols, fg, tokens} */
  function toHtml(render, opts) {
    const cells = parse(render.text, opts.fg || "y");
    const lines = wrap(cells, opts.cols || 9999);
    const toks = render.tokens || [];
    const html = lines.map(line => {
      let out = "", run = "", key = null, cur = null;
      const close = () => {
        if (!run) return;
        const c = cur;
        const style = `color:${PALETTE[c.fg] || PALETTE.y}` + (c.bg ? `;background:${PALETTE[c.bg]}` : "");
        if (c.tok >= 0 && toks[c.tok]) {
          const t = toks[c.tok];
          out += `<span class="qtok how-${esc(t.how)}" data-tok="${c.tok}" style="${style}" title="${esc(t.src + "  →  " + (HOW_LABEL[t.how] || t.how))}">${run}</span>`;
        } else out += `<span style="${style}">${run}</span>`;
        run = "";
      };
      for (const c of line) {
        const k = c.fg + "|" + c.bg + "|" + c.tok;
        if (k !== key) { close(); key = k; cur = c; }
        run += esc(c.ch);
      }
      close();
      return `<div class="qline${line.overflow ? " overflow" : ""}">${out || "&nbsp;"}</div>`;
    }).join("");
    return { html, lines: lines.length, unknownMarkup: cells.unknownMarkup, unclosed: cells.unclosed,
             width: Math.max(0, ...lines.map(l => l.length)) };
  }

  function visible(text) {
    return parse(text, "y").filter(c => !c.nl).map(c => c.ch).join("");
  }

  return { PALETTE, setColors, parse, wrap, toHtml, visible, HOW_LABEL };
})();
