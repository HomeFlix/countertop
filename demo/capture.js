// Takes the README screenshots from a demo server (see screenshots.sh). Every data feed is answered
// by fixtures/demo-data.js, and every request that leaves the demo server is blocked.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const BASE = process.env.BASE || 'http://127.0.0.1:8091';
const OUT = process.env.OUT || path.join(__dirname, '..', 'docs', 'screenshots');
const FIX = fs.readFileSync(path.join(__dirname, 'fixtures', 'demo-data.js'), 'utf8');
const HIDE = '#hint{display:none!important}';
async function open(b, url, {w=1920, h=1080, time='2026-11-19T09:24:00', dpr=1, nofx=false, wait=6000}={}){
  const ctx = await b.newContext({viewport:{width:w, height:h}, deviceScaleFactor:dpr, timezoneId:'America/Denver', locale:'en-US'});
  await ctx.addInitScript(FIX);
  const host = new URL(BASE).host;
  await ctx.route(u => new URL(u).host !== host, r => r.abort());
  const p = await ctx.newPage();
  await p.clock.setFixedTime(new Date(time + '-07:00'));
  await p.goto(BASE + url);
  await p.addStyleTag({content: HIDE + (nofx ? '#fx{display:none!important}' : '')});
  await p.waitForTimeout(wait);
  // the list hint shows the server's address; show a typical LAN address instead
  await p.evaluate(() => { for (const d of [document, ...[...document.querySelectorAll('iframe')].map(i => { try{ return i.contentDocument; }catch(e){ return null; } })]) if (d){
    const t = d.createTreeWalker(d.body, NodeFilter.SHOW_TEXT); for (let n = t.nextNode(); n; n = t.nextNode()) n.nodeValue = n.nodeValue.replace(/(127\.0\.0\.1|localhost)/g, '192.168.1.20'); } });
  return p;
}
const shot = (p, name, o) => p.screenshot(Object.assign({path: path.join(OUT, name + '.png')}, o || {}));
(async () => {
  fs.mkdirSync(path.join(OUT, 'tiles'), {recursive:true});
  const b = await chromium.launch();
  let p;
  p = await open(b, '/dash/content'); await shot(p, 'overview');
  await p.click('[data-recipe]'); await p.waitForTimeout(1500); await shot(p, 'recipe');
  p = await open(b, '/dash/content', {nofx:true}); await p.evaluate(() => dashGoPage('c:month')); await p.waitForTimeout(2500); await shot(p, 'month');
  await p.evaluate(() => dashGoPage('c:deals')); await p.waitForTimeout(2500); await shot(p, 'deals');
  p = await open(b, '/dash/content?night=1', {time:'2026-11-19T23:41:00'}); await shot(p, 'night');
  p = await open(b, '/dash/content?theme=tmwnx60ex', {time:'2026-11-19T16:32:00'}); await shot(p, 'look-glass');
  p = await open(b, '/dash/content', {nofx:true}); await p.evaluate(() => dashEdit(true)); await p.waitForTimeout(1200);
  await p.mouse.click(250, 120); await p.waitForTimeout(1200); await shot(p, 'editor');
  await p.click('text=Add another tile to this box'); await p.waitForTimeout(1500); await shot(p, 'tile-store');
  p = await open(b, '/dash/content', {nofx:true}); await p.evaluate(() => dashEdit(true)); await p.waitForTimeout(1200);
  await p.mouse.click(250, 120); await p.waitForTimeout(1000); await p.click('text=Customize the design'); await p.waitForTimeout(1500); await shot(p, 'designer');
  p = await open(b, '/control', {w:1600, h:1000}); await shot(p, 'controls');
  for (const [go, name] of [['mod:general', 'controls-location'], ['looks', 'controls-looks'], ['effects', 'controls-effects'], ['night', 'controls-night'], ['newpage', 'controls-newpage']]){
    await p.evaluate(g => document.querySelector('[data-go="' + g + '"]').click(), go); await p.waitForTimeout(1500); await shot(p, name);
    await p.evaluate(() => { const e = [...document.querySelectorAll('button,a')].find(x => /^‹/.test(x.textContent.trim())); if (e) e.click(); }); await p.waitForTimeout(800);
  }
  p = await open(b, '/list', {w:390, h:844, dpr:3}); await shot(p, 'phone-list-full');
  // single tiles for the gallery (the app's own ?solo= example mode)
  for (const t of ['agenda', 'forecast', 'countdown', 'nextevent', 'stocks', 'sunmoon', 'team', 'worldclock', 'planes', 'space', 'joke', 'onthisday']){
    p = await open(b, '/dash/content?solo=' + t, {nofx:true, wait:4500});
    const bb = await (await p.$('.slot')).boundingBox();
    await shot(p, 'tiles/' + t, {clip:{x:Math.max(0, bb.x - 16), y:Math.max(0, bb.y - 16), width:bb.width + 32, height:bb.height + 32}});
    await p.context().close();
  }
  await b.close();
})();
