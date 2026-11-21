// The tile API end to end: two Daily to-do tiles on the dashboard keep separate lists, an item added and ticked on
// the screen is saved on the server and survives a reload, and the Controls preview can't change anything.
// Needs Node, Python 3 and Playwright with Chromium. Run with: node tests/tile-data-check.js
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const net = require("node:net");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const { chromium } = require("playwright");

const root = path.join(__dirname, "..");
const freePort = () => new Promise(res => { const s = net.createServer().listen(0, () => { const p = s.address().port; s.close(() => res(p)); }); });
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), "countertop-tiles-"));
  for (const f of fs.readdirSync(path.join(root, "demo", "work"))) fs.copyFileSync(path.join(root, "demo", "work", f), path.join(data, f));
  // put two Daily to-do tiles on the main page
  const cfgFile = path.join(data, "dashboard.json"), cfg = JSON.parse(fs.readFileSync(cfgFile, "utf8"));
  const m = cfg.modules;
  m.tiles.settings.items.push({ id: "daily_a", type: "daily", name: "Morning", settings: {} }, { id: "daily_b", type: "daily", name: "Evening", settings: {} });
  const main = m.pages.settings.items.find(p => p.id === "main");
  main.slots = [{ id: "sa", x: 0, y: 0, w: 24, h: 32, mod: "daily_a" }, { id: "sb", x: 24, y: 0, w: 24, h: 32, mod: "daily_b" }];
  fs.writeFileSync(cfgFile, JSON.stringify(cfg));

  const port = await freePort(), base = "http://127.0.0.1:" + port;
  const server = spawn(process.env.PYTHON || "python3", [path.join(root, "tools", "countertop.py"), "--port", String(port)],
    { env: { ...process.env, COUNTERTOP_DATA: data, COUNTERTOP_NO_UPDATE_CHECK: "1" }, stdio: ["ignore", "pipe", "pipe"] });
  let log = "";
  server.stdout.on("data", d => log += d);
  server.stderr.on("data", d => log += d);
  const stored = async () => (await (await fetch(base + "/tile-data?since=0")).json()).tiles;
  let browser;
  try {
    for (let i = 0; ; i++) {
      try { if ((await fetch(base + "/version")).ok) break; } catch (e) { /* not up yet */ }
      if (i > 50) throw new Error("server didn't start:\n" + log);
      await sleep(200);
    }
    browser = await chromium.launch();
    const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
    await ctx.route("**/*", r => r.request().url().startsWith(base) ? r.continue() : r.abort());
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", e => errors.push(e.message));
    await page.goto(base + "/dash/content");
    const A = page.locator('[data-mod="daily_a"]'), B = page.locator('[data-mod="daily_b"]');
    await A.locator(".add input").waitFor();

    await A.locator(".add input").fill("Water the plants");
    await A.locator(".add button").click();
    await A.locator(".add input").fill("Walk the dog");
    await A.locator(".add input").press("Enter");
    await A.locator(".di", { hasText: "Water the plants" }).click();
    await sleep(500);
    let t = await stored();
    assert.deepEqual(t.daily_a.items.map(i => [i.text, i.done]), [["Water the plants", true], ["Walk the dog", false]]);
    assert.equal(t.daily_b, undefined, "the second tile's list must stay empty");
    assert.equal(await B.locator(".di").count(), 0);
    console.log("✓ add and tick on the screen; the other tile is untouched");

    await page.reload();
    await A.locator(".di").first().waitFor();
    assert.equal(await A.locator(".di.done").count(), 1);
    assert.match(await A.locator(".di").first().innerText(), /Walk the dog/);     // ticked items move down
    console.log("✓ survives a reload");

    await A.locator(".di", { hasText: "Walk the dog" }).locator("[data-rm]").click();
    await sleep(500);
    assert.deepEqual((await stored()).daily_a.items.map(i => i.text), ["Water the plants"]);
    console.log("✓ delete");

    // a new day: ticks clear once, items stay
    const day = new Date(); day.setDate(day.getDate() + 1);
    await page.clock.install({ time: day });
    await page.reload();
    await A.locator(".di").first().waitFor();
    await sleep(800);
    t = await stored();
    assert.deepEqual(t.daily_a.items.map(i => i.done), [false]);
    console.log("✓ ticks clear on a new day");

    const pv = await ctx.newPage();
    await pv.goto(base + "/dash/content?preview=1");
    const PA = pv.locator('[data-mod="daily_a"]');
    await PA.locator(".di").first().waitFor();
    await PA.locator(".di").first().click({ force: true });
    await sleep(500);
    assert.deepEqual((await stored()).daily_a.items.map(i => i.done), [false], "the preview must not write");
    console.log("✓ the Controls preview shows the list but can't change it");

    const res = await fetch(base + "/tile-data/not_a_tile", { method: "POST", headers: { "Content-Type": "application/json" }, body: '{"op":"set","key":"a","value":1}' });
    assert.equal(res.status, 404);
    assert.deepEqual(errors, []);
  } finally {
    if (browser) await browser.close();
    server.kill();
    fs.rmSync(data, { recursive: true, force: true });
  }
}

main().catch(e => { console.error(e); process.exit(1); });
