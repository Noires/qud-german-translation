// Tests für static/qudrender.js (Markup-Parser + Umbruch).
// Start: node build/curator/tests/qudrender.test.js
"use strict";
const fs = require("fs");
const path = require("path");
const assert = require("assert");

const src = fs.readFileSync(path.join(__dirname, "..", "static", "qudrender.js"), "utf8");
const QUD = new Function(src + "; return QUD;")();
QUD.setColors({ solid: { gold: "W" }, shaders: {
  rainbow: { type: "alternation", colors: ["r", "R", "W", "G", "B", "b", "m"] },
  emote: { type: "solid", colors: ["w"] },
  spiked: { type: "bordered", colors: ["R", "Y"] },
} });

const chars = cells => cells.filter(c => !c.nl).map(c => c.ch).join("");
const fgs = cells => cells.filter(c => !c.nl).map(c => c.fg).join("");
const lines = (s, cols) => QUD.wrap(QUD.parse(s, "y"), cols).map(l => l.map(c => c.ch).join(""));
let n = 0;
const t = (name, fn) => { fn(); n++; };

t("&-Codes setzen Vordergrund, &y setzt zurück", () => {
  const c = QUD.parse("&C=level=&y Stufe", "y");
  assert.strictEqual(chars(c), "=level= Stufe");
  assert.strictEqual(fgs(c), "CCCCCCCyyyyyy");
});

t("^-Hintergrund + verschachteltes Markup aus Strings.de.xml", () => {
  const c = QUD.parse("^k{{y| (=colorname=)}}", "Y");
  assert.strictEqual(chars(c), " (=colorname=)");
  assert.ok(c.every(x => x.fg === "y"));
});

t("Verschachtelung: innere Farbe gewinnt, äußere gilt danach weiter", () => {
  const c = QUD.parse("{{W|ab {{R|cd}} ef}}", "y");
  assert.strictEqual(chars(c), "ab cd ef");
  assert.strictEqual(fgs(c), "WWWRRWWW");
});

t("Escapes && und ^^", () => {
  assert.strictEqual(chars(QUD.parse("A && B ^^ C", "y")), "A & B ^ C");
});

t("Shader: alternation verteilt Farben über die Länge, bordered färbt Ränder", () => {
  const c = QUD.parse("{{rainbow|abcdefg}}", "y");
  assert.strictEqual(fgs(c), "rRWGBbm");
  assert.strictEqual(fgs(QUD.parse("{{spiked|abcd}}", "y")), "YRRY");
  assert.strictEqual(fgs(QUD.parse("{{gold|ab}}", "y")), "WW");
});

t("Unbekanntes Markup wird gemeldet, offene Klammer gezählt", () => {
  assert.deepStrictEqual(QUD.parse("{{nonsense|x}}", "y").unknownMarkup, ["nonsense"]);
  assert.strictEqual(QUD.parse("{{W|offen", "y").unclosed, 1);
});

t("Wortumbruch an Leerzeichen, Absätze bleiben", () => {
  assert.deepStrictEqual(lines("eins zwei drei vier\n\nfünf", 10), ["eins zwei", "drei vier", "", "fünf"]);
});

t("Überlanges Wort wird hart geteilt und markiert", () => {
  const L = QUD.wrap(QUD.parse("Donaudampfschiff", "y"), 6);
  assert.strictEqual(L.length, 3);
  assert.ok(L[0].overflow);
});

t("Token-Marker werden zu data-tok-Spans", () => {
  const r = QUD.toHtml({ text: "Hallo \u0001Das Krokodil\u0002.", tokens: [{ src: "=subject.T=", out: "Das Krokodil", how: "emu" }] }, { cols: 40 });
  assert.ok(/data-tok="0"[^>]*>Das Krokodil</.test(r.html));
  assert.strictEqual(r.lines, 1);
});

console.log(n + " qudrender-Tests OK");
