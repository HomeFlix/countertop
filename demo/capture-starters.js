// Renders the premade dashboard pictures in tools/starters/ (shown when picking a layout in setup and Add page)
// with the demo data. Run from the repo: node demo/capture-starters.js [everyday atmospheric ...]
// Needs Node, Playwright with Chromium, Python 3 and Pillow (python3 -m pip install pillow).
const { spawn, execFileSync } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path');
const { chromium } = require('playwright');

const root = path.join(__dirname, '..');
const OUT = process.env.OUT || path.join(root, 'tools', 'starters');
const FIX = fs.readFileSync(path.join(__dirname, 'fixtures', 'demo-data.js'), 'utf8');
const ALL = ['everyday', 'atmospheric', 'minimal', 'kitchen', 'weather', 'planner'];
const which = process.argv.slice(2).length ? process.argv.slice(2) : ALL;
const TIME = '2026-11-19T09:24:00-07:00';
const AT = { atmospheric: '2026-11-19T16:32:00-07:00' };   // the evening look is shown in the evening

(async () => {
  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'countertop-starters-'));
  fs.cpSync(path.join(root, 'tools'), path.join(scratch, 'tools'), { recursive: true });
  fs.cpSync(path.join(__dirname, 'work'), path.join(scratch, 'work'), { recursive: true });
  const server = spawn('python3', ['-u', '-c', 'from tools.countertop import Handler, ThreadingHTTPServer\nserver = ThreadingHTTPServer(("127.0.0.1", 0), Handler)\nprint(server.server_port)\nserver.serve_forever()'],
    { cwd: scratch, env: { ...process.env, COUNTERTOP_DATA: path.join(scratch, 'work'), COUNTERTOP_NO_UPDATE_CHECK: '1' }, stdio: ['ignore', 'pipe', 'inherit'] });
  const port = await new Promise((res, rej) => { server.stdout.once('data', d => res(d.toString().trim())); server.once('exit', c => rej(new Error('server exited ' + c))); });
  const base = 'http://127.0.0.1:' + port, host = new URL(base).host;
  const browser = await chromium.launch();
  try {
    const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, timezoneId: 'America/Denver', locale: 'en-US' });
    await ctx.addInitScript('window.__DEMO_SAVE_CONFIG = true;\n' + FIX);
    await ctx.route(u => new URL(u).host !== host, r => r.abort());
    await ctx.route(u => /^\/demo-food\/[a-z-]+\.jpg$/.test(new URL(u).pathname), r => r.fulfill({ contentType: 'image/jpeg',
      body: fs.readFileSync(path.join(__dirname, 'fixtures', 'food', new URL(r.request().url()).pathname.slice(11))) }));
    const saved = await (await fetch(base + '/config')).json();
    for (const id of which) {
      // put the starter on the main page, as "Use on Main" does, from a fresh copy of the demo settings
      await fetch(base + '/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ modules: saved.modules }) });
      const control = await ctx.newPage();
      await control.clock.setFixedTime(new Date(TIME));
      await control.goto(base + '/control');
      await control.waitForFunction(() => typeof installStarter === 'function' && typeof everyday !== 'undefined' && everyday);
      await control.evaluate(async key => {
        if (key === 'everyday') { const main = gpAll().find(p => p.id === 'main'); main.slots = []; }
        installStarter(key, true);
        const r = await fetch('/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ modules: mods }) });
        const j = await r.json();
        if (!r.ok || j.error) throw new Error('save failed ' + (j.error || r.status));
        const main = j.modules.pages.settings.items.find(p => p.id === 'main');
        if (key !== 'everyday' && !main.slots.some(s => /t0$/.test(s.mod || ''))) throw new Error(key + ' did not land on the main page');
      }, id);
      await control.close();
      const p = await ctx.newPage();
      await p.clock.setFixedTime(new Date(AT[id] || TIME));
      await p.goto(base + '/dash/content');
      await p.addStyleTag({ content: '#hint{display:none!important}' });
      await p.waitForTimeout(6000);
      await p.evaluate(() => { const t = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        for (let n = t.nextNode(); n; n = t.nextNode()) n.nodeValue = n.nodeValue.replace(/(127\.0\.0\.1|localhost):\d+/g, '192.168.1.20:8090'); });
      const png = path.join(scratch, id + '.png');
      await p.screenshot({ path: png });
      await p.close();
      execFileSync('python3', ['-c', 'import sys\nfrom PIL import Image\nImage.open(sys.argv[1]).convert("RGB").resize((1600, 900), Image.LANCZOS).save(sys.argv[2], "JPEG", quality=82, optimize=True, progressive=True)',
        png, path.join(OUT, id + '.jpg')]);
      console.log('wrote', path.join(OUT, id + '.jpg'));
    }
  } finally {
    await browser.close();
    server.kill();
    fs.rmSync(scratch, { recursive: true, force: true });
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
