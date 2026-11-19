// Schnucks receipt export: paste into the browser console on
// https://schnucks.com/account/purchases/in-store  (after scrolling / "load more" as far back as you want)
// It opens each receipt's detail page in a hidden frame (using your logged-in session), copies the
// page text, and downloads everything as schnucks_receipts.json. Nothing is sent anywhere else.
(async () => {
  const MAX = 80, WAIT = 4500;
  const links = [...new Set([...document.querySelectorAll('a[href*="/account/purchases/in-store/"]')]
    .map(a => a.href).filter(h => /\/in-store\/\d+/.test(h)))].slice(0, MAX);
  if (!links.length) { console.warn("No receipt links found. Are you on the in-store purchases page?"); return; }
  console.log("Found " + links.length + " receipts. This takes about " + Math.ceil(links.length * WAIT / 60000) + " min…");
  const out = [];
  for (const [i, url] of links.entries()) {
    const f = document.createElement("iframe");
    f.style.cssText = "position:fixed;left:-3000px;top:0;width:1200px;height:2000px";
    f.src = url; document.body.appendChild(f);
    await new Promise(r => setTimeout(r, WAIT));
    let text = "";
    try { text = f.contentDocument.body.innerText; } catch (e) { text = "ERROR " + e; }
    out.push({ id: url.split("/").pop(), url, text });
    f.remove();
    console.log((i + 1) + "/" + links.length, url, text.length + " chars");
  }
  const blob = new Blob([JSON.stringify({ store: "schnucks", exported: new Date().toISOString(), receipts: out }, null, 1)], { type: "application/json" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "schnucks_receipts.json"; a.click();
  console.log("Done. Move schnucks_receipts.json into the work/purchases/ folder next to tools/");
})();
