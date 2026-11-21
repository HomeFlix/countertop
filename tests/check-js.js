// Syntax-checks every script the server sends to a browser: inline <script> blocks in tools/*.html and
// every file in tools/tiles/. One typo in these blanks the screen, so CI runs this on every pull request.
// Run with: node tests/check-js.js
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

const tools = path.join(__dirname, "..", "tools");
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "countertop-js-"));
const jobs = [];
for (const f of fs.readdirSync(tools).filter(f => f.endsWith(".html")).sort()) {
  const html = fs.readFileSync(path.join(tools, f), "utf8");
  const re = /<script(\s[^>]*)?>([\s\S]*?)<\/script>/gi;
  let m, n = 0;
  while ((m = re.exec(html))) {
    if (/\bsrc=/.test(m[1] || "") || /type=["']?(?!text\/javascript|module)/i.test(m[1] || "")) continue;
    n++;
    // keep line numbers: pad with the lines before the script so errors point at the .html line
    const before = html.slice(0, m.index + m[0].indexOf(">") + 1).split("\n").length - 1;
    const file = path.join(tmp, f + "." + n + ".js");
    fs.writeFileSync(file, "\n".repeat(before) + m[2]);
    jobs.push([f + " (script " + n + ")", file]);
  }
}
for (const f of ["keep.js", "schnucks_export.js"]) if (fs.existsSync(path.join(tools, f))) jobs.push([f, path.join(tools, f)]);
const tiles = path.join(tools, "tiles");
for (const f of fs.readdirSync(tiles).filter(f => f.endsWith(".js")).sort()) jobs.push(["tiles/" + f, path.join(tiles, f)]);

let bad = 0;
for (const [name, file] of jobs) {
  try {
    execFileSync(process.execPath, ["--check", file], { stdio: "pipe" });
  } catch (e) {
    bad++;
    console.error("✗ " + name + "\n" + String(e.stderr).replaceAll(file, name));
  }
}
fs.rmSync(tmp, { recursive: true, force: true });
console.log(bad ? bad + " of " + jobs.length + " scripts have syntax errors" : "✓ " + jobs.length + " scripts parse");
process.exit(bad ? 1 : 0);
