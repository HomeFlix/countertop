/* List: a shopping or to-do list you add to from your phone */
Tile("list", {
  title:"List", cat:"Lists & food", cls:"m-groc", size:[12, 12, 8, 6], feeds:["notes", "sales"],
  desc:"A shopping or to-do list. Add items from your phone at this dashboard's /list page, or keep it in Apple Reminders (set up in Setup → Lists). Narrow boxes switch to two columns, then smaller text.",
  settings:{
    list:{type:"source", kind:"lists", label:"List", default:""},
    max:{type:"int", label:"Items to show", default:20, min:2, max:40},
    saleTag:{type:"bool", label:"Tag items that are on sale this week", default:true, needs:"deals"},
    deals:{type:"bool", label:"Fill spare room with deals on things you usually buy", default:false, needs:"deals"}
  },

  render(el){
    const d = STATE.notes, s = this.s, max = s.max || 12;
    let h = '<h3><span>' + esc(this.it.name || (d && d.list) || this.name) + '</span><small>' + (d && d.source === "reminders" ? "from Reminders" : "add from your phone: " + esc(location.host) + "/list") + '</small></h3>';
    if (!d){ el.innerHTML = h + '<div class="empty">Loading…</div>'; return; }
    if (d.note) h += '<div class="note">📌 ' + esc(d.note) + '</div>';
    const open = (d.items || []).filter(i => !i.done);
    h += open.length ? '<div class="gl">' + open.slice(0, max).map(i => { const dl = s.saleTag !== false && dealFor(i.text);
      return '<div class="gi"><i></i>' + esc(i.text) + (dl ? '<u>🏷 ' + esc(dl.price) + ' ' + esc(dl.store) + '</u>' : "") + '</div>'; }).join("") + '</div>' +
      (open.length > max ? '<div class="empty">+' + (open.length - max) + ' more</div>' : "")
      : '<div class="empty">' + (d.error ? "Reminders didn't answer yet" : "Nothing on the list 🎉") + '</div>';
    // spare room: extras that give way as the list grows
    const blocks = [];
    const SD = deals().filter(d => d.why !== "onlist");
    if (s.deals && SD.length){
      blocks.push('<div class="fb sl"><small>On sale · things you usually buy</small><div class="dl">' + SD.slice(0, 6).map(dealRow).join("") + '</div></div>');
    }
    h += '<div class="filler">' + blocks.join("") + '</div>';
    el.innerHTML = h;
    // narrow tile: one item per line; if that overflows, two columns; then smaller text
    el.classList.remove("two", "small");
    const gl = el.querySelector(".gl");
    if (gl && el.clientWidth < 600){
      el.classList.add("narrow");
      if (el.scrollHeight > el.clientHeight + 2) el.classList.add("two");
      if (el.scrollHeight > el.clientHeight + 2) el.classList.add("small");
    } else el.classList.remove("narrow");
    // show only the extras that fit; the list always wins
    const f = el.querySelector(".filler"), fb = [...f.children];
    requestAnimationFrame(() => {
      let room = f.clientHeight;
      fb.forEach(b => {
        b.hidden = false;
        if (b.classList.contains("sl")){                       // trim deals to fit before giving up the block
          const rows = [...b.querySelectorAll(".dr")];
          while (b.offsetHeight + 14 > room && rows.length > 2) rows.pop().remove();
        }
        const need = b.offsetHeight + 14; if (need > room) b.hidden = true; else room -= need;
        if (b.classList.contains("sl")) STATE.salesShown = b.hidden ? 0 : b.querySelectorAll(".dr").length;
      });
      if (!f.querySelector(".sl")) STATE.salesShown = 0;
    });
  }
});
