// Capture the personalization gallery and feature GIFs without replacing the overview.
// Needs Node, Playwright with Chromium, Python 3, and ffmpeg on PATH (or FFMPEG).
// Run from any directory: node demo/capture-readme.js [stills|designer|radar|phone|daynight|weather]
const assert = require("node:assert/strict");
const { spawn, execFileSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const { chromium } = require("playwright");
const { basemap, radarFrame } = require("./fixtures/radar-tiles");

const root = path.join(__dirname, "..");
const output = process.env.OUT || path.join(root, "docs", "screenshots");
const fixtures = fs.readFileSync(path.join(__dirname, "fixtures", "demo-data.js"), "utf8");
const baseline = JSON.parse(fs.readFileSync(path.join(__dirname, "work", "dashboard.json"), "utf8"));
const size = { width: 1920, height: 1080 };
// Use a documentation address in the UI; Playwright forwards it to the loopback server.
const demoOrigin = "http://192.0.2.20:8090";
const morning = "2026-11-19T09:24:00-07:00";
const afternoon = "2026-11-19T16:32:00-07:00";

function tile(mod, x, y, w, h) {
  return { id: "demo-" + mod, mod, x, y, w, h };
}

function configFor(scene) {
  const config = structuredClone(baseline);
  const { general, look, effects, tiles, pages } = config.modules;
  const main = pages.settings.items.find(page => page.id === "main");
  const set = (id, values) => Object.assign(tiles.settings.items.find(item => item.id === id).settings, values);

  if (scene === "atmospheric") {
    Object.assign(look.settings, { tiles: "See-through", opacity: 38, accent: "#ffcc91" });
    effects.settings.items = [
      { id: "sun", on: true },
      { id: "leaves", on: true, amount: "Some" },
    ];
    set("clock", { style: "Serif", align: "Center", color: "#ffead9", greeting: false, countdowns: false });
    set("weather", { style: "Compact", align: "Left", sun: false, air: false });
    set("dinner", { season: true });
    tiles.settings.items.push(
      { id: "evening-agenda", type: "agenda", name: "From now", settings: { count: 7 } },
      { id: "sunmoon", type: "sunmoon", settings: {} },
    );
    main.slots = [
      tile("clock", 0, 0, 48, 9),
      tile("evening-agenda", 1, 10, 14, 19),
      tile("dinner", 15, 10, 18, 19),
      tile("weather", 33, 10, 14, 7),
      tile("sunmoon", 33, 17, 14, 12),
    ];
  }

  if (scene === "minimal") {
    Object.assign(look.settings, {
      mode: "Light", bg: "Color", bgColor: "#f4f0e8", tiles: "See-through",
      opacity: 60, accent: "#376a63", fx: "Off",
    });
    general.settings.emoji = "Simple symbols";
    set("clock", {
      style: "Serif", align: "Center", ampm: false, color: "#223f3c", greeting: false, countdowns: false,
      design: { on: true, name: "Minimal clock", parts: {
        time: { x: 50, y: 8, s: 48, a: "c", f: "DM Serif Display", c: "#223f3c", w: 400 },
        date: { x: 50, y: 70, s: 8, a: "c", c: "#42625c", w: 500 },
      } },
    });
    set("weather", { style: "Minimal", align: "Center", air: false, sun: false });
    tiles.settings.items.push({ id: "essential-agenda", type: "agenda", name: "Coming up", settings: { count: 6 } });
    main.slots = [
      tile("clock", 1, 7, 23, 14),
      tile("weather", 2, 22, 21, 5),
      tile("essential-agenda", 25, 6, 21, 21),
    ];
  }

  if (scene === "phone") {
    look.settings.fx = "Off";
    set("grocery", { saleTag: false });
    main.slots = [
      tile("clock", 0, 0, 20, 8),
      tile("weather", 36, 0, 12, 8),
      tile("week", 0, 8, 48, 7),
      tile("hours", 0, 15, 24, 17),
      tile("grocery", 24, 15, 14, 17),
      tile("dinner", 38, 15, 10, 11),
      tile("hometeam", 38, 26, 10, 6),
    ];
  }

  if (scene === "daynight" || scene === "weather") {
    // Weather effects only, so each clip shows one thing.
    const seasonal = ["leaves", "halloween", "thanks", "xmas", "winter", "newyear", "valentine", "spring", "july4", "summer",
      "gust", "bats", "turkey", "santa", "flurry", "fireworks", "heartburst", "butterflies", "confetti"];
    effects.settings.items = [
      { id: "rain", on: true, amount: "Lots" },
      { id: "snow", on: true, amount: "Lots" },
      { id: "fog", on: true, amount: "Lots" },
      { id: "sun", on: true },
      { id: "stars", on: true, amount: "Lots" },
      ...seasonal.map(id => ({ id, on: false })),
    ];
  }
  if (scene === "weather") {
    // See-through tiles so the weather shows behind them, and the forecast in place of the
    // radar (the demo has no radar map for these clips).
    Object.assign(look.settings, { tiles: "See-through", opacity: 40 });
    const stack = main.slots.find(slot => slot.mod === "radar");
    Object.assign(stack, { mod: "hours", more: [] });
  }

  if (scene === "designer" || scene === "radar") look.settings.fx = "Off";
  return config;
}

function setup({ demoOrigin, scene, time, wx, label, labelX }) {
  window.__DEMO_SAVE_CONFIG = scene === "designer";
  window.__DEMO_REAL_NOTES = scene === "phone";
  if (wx) window.__DEMO_WX = wx;
  if (label) window.addEventListener("DOMContentLoaded", () => {
    // A caption for the reel, drawn over the empty middle of the header.
    const tag = document.createElement("div");
    tag.textContent = label;
    tag.style.cssText = "position:fixed;z-index:99999;left:" + (labelX || "50%") + ";top:70px;transform:translateX(-50%);padding:14px 34px;" +
      "border-radius:999px;background:rgba(10,14,20,.72);color:#fff;font:600 44px/1 system-ui,sans-serif;letter-spacing:.5px;" +
      "box-shadow:0 6px 24px rgba(0,0,0,.35);pointer-events:none";
    document.body.append(tag);
  });
  if (scene === "radar") {
    const seconds = new Date(time).getTime() / 1000;
    const frames = Array.from({ length: 8 }, (_, i) => ({
      time: seconds + (i - 5) * 600,
      path: "/demo-radar/" + i,
    }));
    window.__DEMO_RADAR = { host: demoOrigin, past: frames.slice(0, 6), nowcast: frames.slice(6) };
  }
  window.addEventListener("DOMContentLoaded", () => {
    const style = document.createElement("style");
    style.textContent = "#hint{display:none!important}";
    if (scene === "radar") style.textContent +=
      '.v-radar .osmc{font-size:0}.v-radar .osmc::after{content:"Fictional demo map";font-size:13px}';
    document.head.append(style);
    if (scene !== "designer") return;

    // Headless video omits the browser cursor. Mirror actual pointer input in
    // the capture only, so the movements and drag handles are easy to follow.
    const pointer = document.createElement("div");
    pointer.style.cssText = "position:fixed;z-index:99999;pointer-events:none;display:none;width:34px;height:38px";
    pointer.innerHTML = '<svg viewBox="0 0 34 38" aria-hidden="true"><path fill="#fff" stroke="#14283c" stroke-width="2.4" stroke-linejoin="round" d="M2 2l25 18-11 2 5 12-5 2-6-12-8 8z"/></svg>';
    document.body.append(pointer);
    document.addEventListener("pointermove", event => {
      pointer.style.display = "block";
      pointer.style.left = event.clientX + "px";
      pointer.style.top = event.clientY + "px";
    }, true);
  });
}

async function prepare(browser, base, scratch, scene, time, video = false, opts = {}) {
  fs.writeFileSync(path.join(scratch, "work", "dashboard.json"), JSON.stringify(configFor(scene)));
  const view = opts.viewport || size;
  const context = await browser.newContext({
    viewport: view,
    ...(opts.mobile ? { isMobile: true, hasTouch: true } : {}),
    timezoneId: "America/Denver",
    locale: "en-US",
    ...(video ? { recordVideo: { dir: scratch, size: view } } : {}),
  });
  await context.addInitScript({
    content: "window.__DEMO_TIME = " + JSON.stringify(time) + ";\n" +
      "(" + setup + ")(" + JSON.stringify({ demoOrigin, scene, time, wx: opts.wx, label: opts.label, labelX: opts.labelX }) + ");\n" + fixtures,
  });
  await context.route("**/*", async route => {
    const url = new URL(route.request().url());
    if (scene === "radar") {
      const map = url.pathname.match(/^\/(\d+)\/(\d+)\/(\d+)\.png$/);
      const radar = url.pathname.match(/^\/demo-radar\/(\d+)\/256\/(\d+)\/(\d+)\/(\d+)\/2\/1_1\.png$/);
      if (url.host === "tile.openstreetmap.org" && map) {
        return route.fulfill({ contentType: "image/svg+xml", body: basemap(...map.slice(1).map(Number)) });
      }
      if (url.origin === demoOrigin && radar) {
        const [frame, z, x, y] = radar.slice(1).map(Number);
        return route.fulfill({ contentType: "image/svg+xml", body: radarFrame(z, x, y, frame) });
      }
    }
    if (url.origin !== demoOrigin) return route.abort();
    const response = await route.fetch({ url: base + url.pathname + url.search });
    return route.fulfill({ response });
  });
  const page = await context.newPage();
  const start = performance.now();
  await page.clock.setFixedTime(new Date(time));
  await page.goto(demoOrigin + (opts.path || "/dash/content"));
  await page.locator(opts.ready || '[data-mod="weather"] [data-part="temp"]').first().waitFor();
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(1250);
  return { page, context, start, offset: (performance.now() - start) / 1000 };
}

async function captureStills(browser, base, scratch) {
  for (const [scene, time] of [["everyday", morning], ["atmospheric", afternoon], ["minimal", morning]]) {
    const { page, context } = await prepare(browser, base, scratch, scene, time);
    await page.screenshot({ path: path.join(output, scene + ".png") });
    await context.close();
  }
}

async function glide(page, x, y, duration = 600) {
  const steps = Math.ceil(duration / 18);
  const start = glide.position || { x, y };
  for (let step = 1; step <= steps; step++) {
    const t = step / steps;
    const ease = t * t * (3 - 2 * t);
    await page.mouse.move(start.x + (x - start.x) * ease, start.y + (y - start.y) * ease);
    await page.waitForTimeout(duration / steps);
  }
  glide.position = { x, y };
}

async function moveTo(page, selector, duration) {
  const locator = page.locator(selector).first();
  await locator.scrollIntoViewIfNeeded();
  const { x, y, width, height } = await locator.boundingBox();
  await glide(page, x + width / 2, y + height / 2, duration);
}

async function click(page, selector, duration) {
  await moveTo(page, selector, duration);
  await page.mouse.down();
  await page.mouse.up();
}

async function designer(page) {
  await page.waitForTimeout(1900);
  await moveTo(page, '[data-mod="clock"] [data-part="time"]', 300);
  await page.mouse.down();
  await page.waitForTimeout(780);
  await page.mouse.up();

  await page.waitForTimeout(550);
  await click(page, '[data-act="dznew"]', 650);
  const time = '#edfocus [data-dzp="time"]';
  const digits = page.locator(time);
  await digits.waitFor();
  const initial = await digits.boundingBox();
  await page.waitForTimeout(700);
  await moveTo(page, time);
  const original = glide.position;
  await page.mouse.down();
  await glide(page, original.x + 305, original.y - 36, 950);
  await page.mouse.up();
  assert.ok((await digits.boundingBox()).x - initial.x > 200, "Clock digits should move right");
  await page.waitForTimeout(750);

  await moveTo(page, '#edfocus [data-dzr="time"]', 440);
  const corner = glide.position;
  await page.mouse.down();
  await glide(page, corner.x + 70, corner.y + 39, 800);
  await page.mouse.up();
  assert.ok((await digits.boundingBox()).height > initial.height * 1.1, "Clock digits should grow");
  await page.waitForTimeout(650);
  await click(page, '[data-act="dzc"][data-v="#ffd36e"]', 680);
  await page.waitForTimeout(1150);
  await click(page, '[data-act="dzdone"]', 700);
  await page.waitForTimeout(450);

  const saved = page.waitForResponse(response => response.url().endsWith("/config") &&
    response.request().method() === "POST" && response.ok());
  await click(page, "#edsave", 520);
  const response = await saved;
  const config = response.request().postDataJSON();
  const design = config.modules.tiles.settings.items.find(item => item.id === "clock").settings.design;
  assert.equal(design.parts.time.c, "#ffd36e");
  await page.locator('[data-mod="clock"] .dz [data-part="time"]').waitFor();
  await page.waitForTimeout(2650);
}

async function radar(page) {
  await page.locator('[data-mod="hours"]:not(.stk-off) canvas').waitFor();
  await page.waitForTimeout(5000);
  await page.evaluate(async () => {
    // Change only the fixture's forecast. The usual weather reload and stack
    // tick decide whether and when the radar is shown.
    window.__DEMO_RAIN = true;
    await loadWeather();
  });
  const active = page.locator('[data-mod="radar"]:not(.stk-off)');
  await active.getByText(/Rain in about/).waitFor();
  await active.locator(".frames img").first().waitFor();
  await page.waitForFunction(() => {
    const imgs = [...document.querySelectorAll('[data-mod="radar"] .map img')];
    return imgs.length > 0 && imgs.every(img => img.complete && img.naturalWidth > 0);
  });
  await page.waitForTimeout(10400);
}

async function captureVideo(browser, base, scratch, scene, action, name) {
  const { page, context, offset } = await prepare(browser, base, scratch, scene, morning, true);
  const began = performance.now();
  const video = page.video();
  await action(page);
  const duration = (performance.now() - began) / 1000;
  assert.ok(duration <= 20, "The recording exceeded 20 seconds");
  await context.close();
  execFileSync(process.env.FFMPEG || "ffmpeg", [
    "-v", "error", "-y", "-ss", offset.toFixed(3), "-t", duration.toFixed(3), "-i", await video.path(), "-vf",
    "fps=10,scale=960:540:flags=lanczos,split[a][b];[a]palettegen=max_colors=160:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
    "-loop", "0", path.join(output, name + ".gif"),
  ], { stdio: "inherit" });
}

const GIF_PALETTE = "split[a][b];[a]palettegen=max_colors=" + (process.env.GIF_COLORS || 128) + ":stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle";

// One short clip of the dashboard at a given time and weather. Returns the video and the part to keep.
async function clip(browser, base, scratch, scene, time, seconds, opts) {
  const { page, context, start } = await prepare(browser, base, scratch, scene, time, true, opts);
  await page.waitForTimeout(1500);              // let effects fill the screen
  const from = (performance.now() - start) / 1000;
  await page.waitForTimeout(seconds * 1000);
  const video = page.video();
  await context.close();
  const file = path.join(scratch, scene + "-" + Math.random().toString(36).slice(2) + ".webm");
  fs.renameSync(await video.path(), file);
  return { file, from, seconds };
}

// Joins clips with short cross-fades into one looping GIF.
function reel(clips, name, fade = 0.5, crop = "") {
  const args = ["-v", "error", "-y"];
  clips.forEach(c => args.push("-ss", c.from.toFixed(3), "-t", c.seconds.toFixed(3), "-i", c.file));
  const parts = clips.map((c, i) => "[" + i + ":v]fps=" + (process.env.GIF_FPS || 8) + "," + crop + "scale=960:540:flags=lanczos,setpts=PTS-STARTPTS,format=yuv420p[v" + i + "]");
  let last = "v0", at = 0;
  for (let i = 1; i < clips.length; i++) {
    at += clips[i - 1].seconds - fade;
    parts.push("[" + last + "][v" + i + "]xfade=transition=fade:duration=" + fade + ":offset=" + at.toFixed(3) + "[x" + i + "]");
    last = "x" + i;
  }
  parts.push("[" + last + "]" + GIF_PALETTE);
  args.push("-filter_complex", parts.join(";"), "-loop", "0", path.join(output, name + ".gif"));
  execFileSync(process.env.FFMPEG || "ffmpeg", args, { stdio: "inherit" });
}

async function dayNight(browser, base, scratch) {
  const at = t => "2026-11-19T" + t + ":00-07:00";
  const clips = [];
  for (const [t, label] of [["07:05", "Sunrise"], ["12:30", "Midday"], ["16:35", "Sunset"]])
    clips.push(await clip(browser, base, scratch, "daynight", at(t), 2, { label }));
  clips.push(await clip(browser, base, scratch, "daynight", at("22:15"), 2.2, { label: "Bedtime", ready: ".m-nightclock, [data-mod=\"nightclock\"]" }));
  reel(clips, "day-to-night");
}

async function weatherReel(browser, base, scratch) {
  const clips = [];
  for (const [t, wx, label] of [
    ["10:10", { code: 63, day: true, temp: 44 }, "Rain"],
    ["13:40", { code: 73, day: true, temp: 29 }, "Snow"],
    ["11:30", { code: 0, day: true, temp: 58 }, "Sunny"],
    ["20:30", { code: 0, day: false, temp: 41 }, "Clear night"],
  ]) clips.push(await clip(browser, base, scratch, "weather", "2026-11-19T" + t + ":00-07:00", 1.8, { wx, label, labelX: "1200px" }));
  // Full size, top right quarter: the weather corner, where thin rain and snow stay visible.
  reel(clips, "weather-effects", 0.5, "crop=960:540:960:0,");
}

// A phone adds to the list; the kitchen screen picks it up. Both pages are recorded at once
// and placed side by side.
async function phoneList(browser, base, scratch) {
  fs.writeFileSync(path.join(scratch, "work", "notes.json"), JSON.stringify({ note: "", updated: 0,
    items: ["Milk", "Eggs", "Sourdough bread", "Coffee beans", "Bananas", "Spinach"].map((text, i) => ({ id: "n" + i, text, done: false })) }));
  const dash = await prepare(browser, base, scratch, "phone", morning, true);
  const phone = await prepare(browser, base, scratch, "phone", morning, true,
    { viewport: { width: 390, height: 844 }, mobile: true, path: "/list", ready: "#items li[data-id]" });
  await phone.page.addStyleTag({ content: "#tap{position:fixed;z-index:9;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;" +
    "background:rgba(255,255,255,.55);border:2px solid #fff;pointer-events:none;opacity:0;transition:opacity .15s}" });
  await phone.page.evaluate(() => { const d = document.createElement("div"); d.id = "tap"; document.body.append(d); });
  const tap = async selector => {
    const b = await phone.page.locator(selector).boundingBox();
    await phone.page.evaluate(([x, y]) => { const t = document.getElementById("tap");
      Object.assign(t.style, { left: x + "px", top: y + "px", opacity: 1 }); setTimeout(() => t.style.opacity = 0, 380); },
      [b.x + b.width / 2, b.y + b.height / 2]);
    await phone.page.tap(selector);
  };
  const t0 = performance.now();
  await phone.page.waitForTimeout(1200);
  await tap("#item");
  await phone.page.waitForTimeout(300);
  await phone.page.keyboard.type("Maple syrup", { delay: 85 });
  await phone.page.waitForTimeout(350);
  await tap("#add button");
  await phone.page.locator("#items li", { hasText: "Maple syrup" }).waitFor();
  await phone.page.waitForTimeout(900);
  // The dashboard checks the list every 30 seconds; ask now so the clip stays short.
  await dash.page.evaluate(() => loadNotes());
  await dash.page.locator('[data-mod="grocery"]', { hasText: "Maple syrup" }).waitFor();
  await phone.page.waitForTimeout(3000);
  const seconds = (performance.now() - t0) / 1000;
  const files = [];
  for (const side of [dash, phone]) {
    const video = side.page.video();
    await side.context.close();
    files.push({ file: await video.path(), from: (t0 - side.start) / 1000 });
  }
  // Kitchen screen at 1280x720 and the phone at 333x720 on a dark backdrop, then scaled to 960 wide.
  const filter = [
    "[0:v]fps=10,scale=1280:720:flags=lanczos,setpts=PTS-STARTPTS[d]",
    "[1:v]fps=10,scale=333:720:flags=lanczos,setpts=PTS-STARTPTS,pad=345:732:6:6:color=0x3a414c[p]",
    "color=c=0x0d1117:s=1700x780:r=10[bg]",
    "[bg][d]overlay=24:30:shortest=1[a]",
    "[a][p]overlay=1330:24[b]",
    "[b]scale=960:-2:flags=lanczos," + GIF_PALETTE,
  ].join(";");
  execFileSync(process.env.FFMPEG || "ffmpeg", ["-v", "error", "-y",
    "-ss", files[0].from.toFixed(3), "-t", seconds.toFixed(3), "-i", files[0].file,
    "-ss", files[1].from.toFixed(3), "-t", seconds.toFixed(3), "-i", files[1].file,
    "-filter_complex", filter, "-loop", "0", path.join(output, "phone-to-kitchen.gif")], { stdio: "inherit" });
}

async function main() {
  const which = process.argv[2];
  const scenes = ["stills", "designer", "radar", "phone", "daynight", "weather"];
  assert.ok(!which || scenes.includes(which), "Use one of: " + scenes.join(", "));
  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), "countertop-demo-"));
  fs.mkdirSync(output, { recursive: true });
  fs.cpSync(path.join(root, "tools"), path.join(scratch, "tools"), { recursive: true });
  fs.cpSync(path.join(__dirname, "work"), path.join(scratch, "work"), { recursive: true });
  const server = spawn("python3", ["-u", "-c", [
    "from tools.countertop import Handler, ThreadingHTTPServer",
    'server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)',
    "print(server.server_port)",
    "server.serve_forever()",
  ].join("\n")], { cwd: scratch, stdio: ["ignore", "pipe", "inherit"] });
  let browser;
  try {
    const port = await new Promise((resolve, reject) => {
      server.stdout.once("data", data => resolve(data.toString().trim()));
      server.once("error", reject);
      server.once("exit", code => reject(new Error("Demo server exited: " + code)));
    });
    const base = "http://127.0.0.1:" + port;
    browser = await chromium.launch({ args: ["--window-size=1920,1080"] });
    if (!which || which === "stills") await captureStills(browser, base, scratch);
    if (!which || which === "designer") await captureVideo(browser, base, scratch, "designer", designer, "clock-designer");
    if (!which || which === "radar") await captureVideo(browser, base, scratch, "radar", radar, "radar-takeover");
    if (!which || which === "phone") await phoneList(browser, base, scratch);
    if (!which || which === "daynight") await dayNight(browser, base, scratch);
    if (!which || which === "weather") await weatherReel(browser, base, scratch);
  } finally {
    if (browser) await browser.close();
    server.kill();
    fs.rmSync(scratch, { recursive: true, force: true });
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
