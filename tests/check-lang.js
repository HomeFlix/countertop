// Checks the translations in tools/lang/*.json against the words the dashboard and tiles ask for.
//   node tests/check-lang.js          list missing and unused words for every language
//   node tests/check-lang.js fr       just French
// Fails (exit 1) only when a catalog isn't valid JSON or a translation drops a {placeholder}, since a word
// without a translation still shows in English. See docs/languages.md.
const fs = require("node:fs");
const path = require("node:path");

const tools = path.join(__dirname, "..", "tools");
const langDir = path.join(tools, "lang");

// every string literal inside tr(...) or this.t(...), including both sides of a ?: inside the call
function wordsIn(src) {
  const out = new Set();
  const re = /(?:\btr|\.t)\(/g;
  let m;
  while ((m = re.exec(src))) {
    let i = m.index + m[0].length, depth = 1, args = "";
    while (i < src.length && depth > 0) {
      const c = src[i];
      if (c === '"' || c === "'" || c === "`") {           // copy a whole string so parentheses inside it don't count
        let j = i + 1;
        while (j < src.length && src[j] !== c) j += src[j] === "\\" ? 2 : 1;
        args += src.slice(i, j + 1); i = j + 1; continue;
      }
      if (c === "(") depth++;
      if (c === ")") depth--;
      if (c === "," && depth === 1) break;                  // only the first argument is the words
      args += c; i++;
    }
    for (const s of args.matchAll(/"((?:[^"\\]|\\.)*)"/g)) out.add(JSON.parse('"' + s[1] + '"'));
  }
  return out;
}

const sources = [path.join(tools, "dash3.html")]
  .concat(fs.readdirSync(path.join(tools, "tiles")).filter(f => f.endsWith(".js")).map(f => path.join(tools, "tiles", f)));
const used = new Set();
for (const f of sources) {
  const src = fs.readFileSync(f, "utf8");
  wordsIn(src).forEach(w => used.add(w));
  if (f.includes(path.sep + "tiles" + path.sep)) {
    // a tile's default name is shown through this.t(title)
    const t = /^\s*title:"([^"]+)"/m.exec(src) || /Tile\("\w+",\s*\{[^}]*?title:"([^"]+)"/.exec(src);
    if (t) used.add(t[1]);
  }
}
// words looked up by value rather than written in a tr() call
const dash = fs.readFileSync(path.join(tools, "dash3.html"), "utf8");
const W = /const WORDS = (\{[^}]*\})/.exec(dash);
if (W) Object.values(JSON.parse(W[1])).forEach(w => used.add(w));

const want = process.argv[2];
const langs = fs.readdirSync(langDir).filter(f => /^[a-z]{2}\.json$/.test(f)).map(f => f.slice(0, 2)).filter(l => !want || l === want);
let bad = 0;
for (const lang of langs) {
  let cat;
  try { cat = JSON.parse(fs.readFileSync(path.join(langDir, lang + ".json"), "utf8")); }
  catch (e) { bad++; console.error("✗ " + lang + ".json is not valid JSON: " + e.message); continue; }
  const holes = s => (s.match(/\{\w+\}/g) || []).sort().join(" ");
  for (const [en, tx] of Object.entries(cat)) {
    if (en.startsWith("_")) continue;                       // notes for translators
    if (typeof tx !== "string") { bad++; console.error("✗ " + lang + ': "' + en + '" is not text'); continue; }
    if (holes(en) !== holes(tx)) { bad++; console.error("✗ " + lang + ': "' + tx + '" should keep ' + (holes(en) || "no placeholders")); }
  }
  const missing = [...used].filter(w => !(w in cat)).sort();
  const unused = Object.keys(cat).filter(w => !w.startsWith("_") && !used.has(w)).sort();
  console.log(lang + ": " + (used.size - missing.length) + " of " + used.size + " words translated");
  if (missing.length) console.log("  missing (shown in English):\n" + missing.map(w => '    "' + w + '"').join("\n"));
  if (unused.length) console.log("  no longer used:\n" + unused.map(w => '    "' + w + '"').join("\n"));
}
if (bad) { console.error(bad + " problem" + (bad > 1 ? "s" : "")); process.exit(1); }
