/* Night clock: a big, quiet clock for the night page */
Tile("nightclock", {
  title:"Night clock", cat:"Time", card:false, cls:"m-nightw", every:1, size:[24, 16, 10, 6], feeds:["wx", "events"], noFit:true,
  desc:"A big, quiet clock in soft gray, with the moon, the temperature and your next event underneath. Made for the night page.",
  settings:{
    color:{look:true, type:"color", label:"Clock color", default:"#7c828c"},
    ampm:{type:"bool", label:"Show AM/PM", default:false},
    moon:{part:"info", type:"bool", label:"Moon, temperature and rain", default:true},
    next:{part:"next", type:"bool", label:"Next event (today or tomorrow)", default:true}
  },
  css:`.m-nightw{height:100%}
    .m-night{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;color:#7c828c;overflow:hidden}
    .m-night .t{font-weight:200;line-height:.9;letter-spacing:-.03em;white-space:nowrap}
    .m-night .s{color:#5b616b;margin-top:.45em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
    .m-night .s:empty{display:none}`,
  parts(){
    const d = new Date(), [a, b] = this.lines(d), txt = d.toLocaleTimeString([], {hour:"numeric", minute:"2-digit"});
    return [{id:"time", label:"Time", html:esc(this.s.ampm ? txt : txt.replace(/\s?[AP]M$/i, ""))}, {id:"info", label:"Moon, temperature and rain", html:esc(a), emoji:true}, {id:"next", label:"Next event", html:esc(b)}];
  },
  lines(d){
    const s = this.s, dz = designed(this); let a = "", b = "";
    if (dz || s.moon !== false){
      const rain = (STATE.rain || "").replace(/<[^>]+>/g, "");
      a = moon(d)[0] + "  " + (STATE.tempNow != null ? STATE.tempNow + "°" : "") + (rain && !/^Dry/.test(rain) ? "  ·  " + rain : "");
    }
    if (dz || s.next !== false){
      const t1 = startOfDay(d).getTime() + 86400e3, t2 = t1 + 86400e3;
      const e = (STATE.events || []).find(e => { const x = evDate(e).getTime(); return x > Date.now() && x < t2; });
      if (e){ const x = evDate(e); b = (x.getTime() >= t1 ? "Tomorrow" : "Today") + " " + (e.allDay ? "" : fmtTime(x) + " · ") + (e.summary || ""); }
    }
    return [a, b];
  },
  render(el){
    if (designed(this)) return designRender(el, this);
    const d = new Date(), s = this.s;
    if (!el.querySelector(":scope > .m-night")){ el.innerHTML = '<div class="m-night"><div class="t" data-part="time"></div><div class="s a" data-part="info"></div><div class="s b" data-part="next"></div></div>'; el._k = ""; }
    const h = el.clientHeight || 400, w = el.clientWidth || 600, big = Math.round(Math.min(h * .5, w / 3.3)), key = w + "x" + h;
    const t = el.querySelector(".t");
    if (el._k !== key){ el._k = key; t.style.fontSize = big + "px"; el.querySelectorAll(".s").forEach(x => { x.style.fontSize = Math.max(16, Math.round(big * .12)) + "px"; }); }
    t.style.color = s.color || "";
    const txt = d.toLocaleTimeString([], {hour:"numeric", minute:"2-digit"});
    t.textContent = s.ampm ? txt : txt.replace(/\s?[AP]M$/i, "");
    const [a, b] = this.lines(d);
    const A = el.querySelector(".a"), B = el.querySelector(".b");
    if (A.textContent !== a) A.textContent = a;
    if (B.textContent !== b) B.textContent = b;
  }
});
