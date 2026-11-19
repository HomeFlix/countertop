/* Your own tile: HTML you paste (or have ChatGPT write), run in a sealed frame */
Tile("custom", {
  title:"Your own tile", cat:"Your own", cls:"m-mine", every:60, size:[12, 8, 4, 4],
  desc:"Paste HTML, CSS and JavaScript to make any tile you like, or have ChatGPT write it with the instructions in its settings. It runs sealed off: it can fetch public data but can't see or change the rest of the dashboard.",
  settings:{
    ask:{type:"text", label:"What should it show?", help:"Goes into the ChatGPT instructions below", placeholder:"e.g. days until summer vacation", default:""},
    html:{type:"code", label:"Code (HTML)", default:'<div style="display:grid;place-items:center;height:100%;font-size:40px">Hello 👋</div>'},
    every:{type:"int", label:"Reload every (minutes, 0 = never)", default:0, min:0, max:1440},
    taps:{type:"bool", label:"Let it respond to taps", default:false},
    frame:{type:"bool", label:"Show on a card", default:true},
    title:{type:"bool", label:"Show its name as a title", default:false}
  },
  doc(html){
    const cs = getComputedStyle(document.documentElement), v = k => cs.getPropertyValue(k).trim();
    return '<!doctype html><html><head><meta charset="utf-8"><style>:root{--fg:' + (v("--fg") || "#e9ecf1") + ';--dim:' + (v("--dim") || "#a9b1bb") +
      ';--accent:' + (v("--accent") || "#5aa9ff") + '}html,body{margin:0;height:100%;background:transparent;color:var(--fg);' +
      'font:22px/1.3 -apple-system,system-ui,"Segoe UI",Roboto,sans-serif;overflow:hidden}</style></head><body>' + (html || "") + '</body></html>';
  },
  render(el){
    const s = this.s, key = [s.html, s.title, s.taps, s.frame, this.name, THEME && THEME.id].join("\u0001");
    el.classList.toggle("bare", s.frame === false);
    if (el._k !== key){
      el._k = key; el._at = Date.now();
      el.innerHTML = (s.title ? '<h3>' + esc(this.name) + '</h3>' : "") + '<iframe class="mine" sandbox="allow-scripts" referrerpolicy="no-referrer" title="' + esc(this.name) + '"></iframe>';
      const f = el.querySelector("iframe");
      f.style.pointerEvents = s.taps ? "auto" : "none";
      f.srcdoc = this.doc(s.html);
    } else if (+s.every > 0 && Date.now() - el._at > s.every * 60e3){ el._at = Date.now(); el.querySelector("iframe").srcdoc = this.doc(s.html); }
  }
});
