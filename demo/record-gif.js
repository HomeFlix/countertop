// Records the animated overview (docs/screenshots/overview.gif) from a demo server (see screenshots.sh).
// Needs ffmpeg. Same fake data and blocked outside requests as capture.js.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), { execFileSync } = require('child_process');
const BASE = process.env.BASE || 'http://127.0.0.1:8091';
const OUT = process.env.OUT || path.join(__dirname, '..', 'docs', 'screenshots');
const FIX = fs.readFileSync(path.join(__dirname, 'fixtures', 'demo-data.js'), 'utf8');
(async () => {
  const tmp = fs.mkdtempSync(path.join(require('os').tmpdir(), 'ct-gif-'));
  const b = await chromium.launch();
  const ctx = await b.newContext({viewport:{width:1920, height:1080}, timezoneId:'America/Denver', locale:'en-US',
    recordVideo:{dir:tmp, size:{width:1920, height:1080}}});
  await ctx.addInitScript(FIX);
  const host = new URL(BASE).host;
  await ctx.route(u => new URL(u).host !== host, r => r.abort());
  const p = await ctx.newPage();
  await p.clock.setFixedTime(new Date('2026-11-19T09:24:00-07:00'));
  const t0 = Date.now();
  await p.goto(BASE + '/dash/content');
  await p.addStyleTag({content:'#hint{display:none!important}'});
  await p.waitForTimeout(7000);
  await p.evaluate(() => { const t = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = t.nextNode(); n; n = t.nextNode()) n.nodeValue = n.nodeValue.replace(/(127\.0\.0\.1|localhost)/g, '192.168.1.20'); });
  const start = (Date.now() - t0) / 1000 + 1;
  await p.waitForTimeout(7000);
  const video = await p.video().path();
  await ctx.close(); await b.close();
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-ss', String(start), '-t', '6', '-i', video, '-vf',
    'fps=12,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=192:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle',
    path.join(OUT, 'overview.gif')]);
  fs.rmSync(tmp, {recursive:true, force:true});
})();
