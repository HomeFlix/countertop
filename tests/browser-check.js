// Opens the dashboard, Controls and the phone list in headless Chromium with the demo settings and
// fails on any uncaught error or console.error. Outside addresses are blocked; the demo fixture answers
// the data feeds, so this needs no network.
// Needs Node, Python 3 and Playwright with Chromium. Run with: node tests/browser-check.js
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const net = require("node:net");
const { spawn } = require("node:child_process");
const { chromium } = require("playwright");

const root = path.join(__dirname, "..");
const fixtures = fs.readFileSync(path.join(root, "demo", "fixtures", "demo-data.js"), "utf8");

const freePort = () => new Promise(res => { const s = net.createServer().listen(0, () => { const p = s.address().port; s.close(() => res(p)); }); });
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), "countertop-check-"));
  for (const f of fs.readdirSync(path.join(root, "demo", "work"))) fs.copyFileSync(path.join(root, "demo", "work", f), path.join(data, f));
  const port = await freePort();
  const base = "http://127.0.0.1:" + port;
  const server = spawn(process.env.PYTHON || "python3", [path.join(root, "tools", "countertop.py"), "--port", String(port)],
    { env: { ...process.env, COUNTERTOP_DATA: data, COUNTERTOP_NO_UPDATE_CHECK: "1" }, stdio: ["ignore", "pipe", "pipe"] });
  let log = "";
  server.stdout.on("data", d => log += d);
  server.stderr.on("data", d => log += d);
  const problems = [];
  let browser;
  try {
    for (let i = 0; ; i++) {
      try { if ((await fetch(base + "/version")).ok) break; } catch (e) { /* not up yet */ }
      if (i > 50) throw new Error("server didn't start:\n" + log);
      await sleep(200);
    }
    browser = await chromium.launch();
    const pages = [
      ["dashboard", "/dash/content", { width: 1920, height: 1080 }],
      ["dashboard, portrait", "/dash/content", { width: 1080, height: 1920 }],
      ["controls", "/control", { width: 1280, height: 900 }],
      ["controls preview", "/dash/content?preview=1", { width: 960, height: 540 }],
      ["phone list", "/list", { width: 390, height: 844 }],
    ];
    // the same dashboard with Language set to French: the page says so, and the weather and dates use French words
    pages.push(["dashboard in French", "/dash/content", { width: 1920, height: 1080 }, async page => {
      const t = await page.evaluate(() => ({ lang: document.documentElement.lang, text: document.body.innerText }));
      if (t.lang !== "fr") throw new Error("html lang is " + JSON.stringify(t.lang) + ", not fr");
      const fr = Object.values(JSON.parse(fs.readFileSync(path.join(root, "tools", "lang", "fr.json"), "utf8"))).filter(w => w.length > 4 && !/[{]/.test(w));
      if (!fr.some(w => t.text.includes(w))) throw new Error("no French words on the screen");
    }, () => {
      const f = path.join(data, "dashboard.json"), d = JSON.parse(fs.readFileSync(f, "utf8"));
      d.modules.general.settings.lang = "Français";
      fs.writeFileSync(f, JSON.stringify(d));
    }]);
    for (const [name, url, viewport, check, before] of pages) {
      if (before) before();
      const context = await browser.newContext({ viewport });
      // The pages catch a tile that throws and post it to /report; the fixture answers fetch itself, so
      // wrap fetch once more and turn those reports into console errors this script sees.
      await context.addInitScript({ content: fixtures + `
        ;(() => { const f = window.fetch;
          window.fetch = function (u, o) {
            if (String(u).endsWith("/report") && o && o.body) {
              try { const b = JSON.parse(o.body); if (b.task === "js-error") console.error("reported: " + b.error); } catch (e) {}
            }
            return f.apply(this, arguments);
          }; })();` });
      await context.route("**/*", route => route.request().url().startsWith(base) || route.request().url().startsWith("data:")
        ? route.continue() : route.abort());
      const page = await context.newPage();
      page.on("pageerror", e => problems.push(name + ": " + (e.stack || e.message)));
      page.on("console", m => {
        if (m.type() === "error" && !/Failed to load resource|net::ERR_/.test(m.text())) problems.push(name + ": console.error " + m.text());
      });
      await page.goto(base + url, { waitUntil: "load" });
      await sleep(4000);                    // let tiles render and take a turn or two
      if (check) await check(page).catch(e => problems.push(name + ": " + e.message));
      console.log((problems.some(p => p.startsWith(name + ":")) ? "✗ " : "✓ ") + name);
      await context.close();
    }
  } finally {
    if (browser) await browser.close();
    server.kill();
    fs.rmSync(data, { recursive: true, force: true });
  }
  if (problems.length) {
    console.error("\n" + [...new Set(problems)].join("\n\n"));
    process.exit(1);
  }
}

main().catch(e => { console.error(e); process.exit(1); });
