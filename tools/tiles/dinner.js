/* Dinner idea: a recipe idea with a photo, changing every so often. Tap it for the whole recipe. */
Tile("dinner", {
  title:"Dinner idea", cat:"Lists & food", cls:"m-dinner", every:60, size:[10, 12, 8, 6], feeds:["dinner"],
  desc:"A dinner idea with a photo, from TheMealDB, changing every half hour or so. Tap it to see the ingredients and steps. Can also list what's in season this month.",
  settings:{
    every:{type:"int", label:"Minutes per idea", default:30, min:5, max:1440},
    season:{type:"bool", label:"Also show what's in season", default:true}
  },
  css:`.m-dinner .ph{cursor:pointer;position:relative}
    .m-dinner .tapme{position:absolute;right:10px;top:10px;font-size:15px;padding:4px 10px;border-radius:12px;background:rgba(0,0,0,.45);color:#fff}
    #recipe{position:fixed;inset:0;z-index:7;background:rgba(6,8,12,.97);display:flex;gap:40px;padding:40px 48px;color:#e9ecf1}
    #recipe .l{flex:0 0 520px;display:flex;flex-direction:column;gap:18px;min-height:0}
    #recipe .img{flex:0 0 auto;width:520px;height:390px;border-radius:18px;background:#1c2128 center/cover no-repeat}
    #recipe h2{margin:0;font-size:40px;line-height:1.1;font-weight:600}
    #recipe .meta{color:#9aa3ad;font-size:20px}
    #recipe .r{flex:1;min-width:0;display:flex;flex-direction:column;gap:18px;min-height:0;overflow:hidden}
    #recipe .ing{columns:3;column-gap:28px;font-size:var(--rf);line-height:1.35;flex:none}
    #recipe .ing div{break-inside:avoid;padding:2px 0}
    #recipe .ing b{color:var(--accent);font-weight:500}
    #recipe .sh{font-size:15px;letter-spacing:.08em;text-transform:uppercase;color:#9aa3ad;flex:none}
    #recipe ol{margin:0;padding-left:1.4em;columns:2;column-gap:36px;column-fill:auto;font-size:var(--rf);line-height:1.4;flex:1;min-height:0;overflow:hidden}
    #recipe ol li{break-inside:avoid;margin-bottom:.5em}
    #recipe .btns{display:flex;gap:12px;margin-top:auto}
    #recipe button{font:inherit;font-size:22px;padding:12px 22px;border-radius:14px;border:0;background:#232a33;color:#e9ecf1}
    #recipe button.pri{background:var(--accent);color:#06121f;font-weight:600}`,

  render(el){
    const s = this.s, D = STATE.dinner && STATE.dinner.ideas && STATE.dinner.ideas.length ? STATE.dinner.ideas : null;
    const k = D ? Math.floor(Date.now() / ((s.every || 30) * 60e3)) % D.length : -1;
    const key = (D ? D[k].title : "") + "|" + new Date().getMonth() + "|" + s.season;
    if (el._key === key) return;
    el._key = key;
    let h = '<h3><span>' + (D ? "Dinner idea" : "In season") + '</span></h3>';
    if (D){
      const i = D[k];
      h += '<div class="ph" data-recipe="' + k + '"' + (i.thumb ? ' style="background-image:url(&quot;' + esc(i.thumb) + '&quot;)"' : "") + '>' +
        ((i.steps || []).length ? '<span class="tapme">Recipe ›</span>' : "") + '<div><b>' + esc(i.title) + '</b><span>' +
        esc([i.area, i.cat].filter(Boolean).join(" · ")) + '</span></div></div>';
    }
    if (s.season !== false){
      h += (D ? '<small>In season in ' + new Date().toLocaleDateString([], {month:"long"}) + '</small>' : "") +
        '<div class="chips' + (D ? "" : " big") + '">' + IN_SEASON[new Date().getMonth()].map(x => '<i>' + esc(x) + '</i>').join("") + '</div>';
    }
    el.innerHTML = h;
    if (!el._tap){ el._tap = true; el.addEventListener("click", e => { const p = e.target.closest("[data-recipe]"); if (p && !EDIT.on && !PREVIEW) recipeOpen(+p.dataset.recipe); }); }
  }
});

// the whole recipe over the screen; closes with Close, or by itself after 15 minutes
function recipeOpen(k){
  const D = (STATE.dinner && STATE.dinner.ideas) || [], i = D[k]; if (!i) return;
  recipeClose();
  const d = document.createElement("div"); d.id = "recipe";
  const ing = (i.ingredients || []).map(([m, n]) => '<div>' + (m ? '<b>' + esc(m) + '</b> ' : "") + esc(n) + '</div>').join("");
  const steps = (i.steps || []).map(x => '<li>' + esc(x) + '</li>').join("");
  d.innerHTML = '<div class="l"><div class="img" style="background-image:url(&quot;' + esc(i.big || i.thumb || "") + '&quot;)"></div><h2>' + esc(i.title) + '</h2>' +
    '<div class="meta">' + esc([i.area, i.cat].filter(Boolean).join(" · ")) + '</div>' +
    '<div class="btns"><button class="pri" data-r="close">Close</button>' + (D.length > 1 ? '<button data-r="next">Another idea</button>' : "") + '</div></div>' +
    '<div class="r">' + (ing ? '<div class="sh">Ingredients</div><div class="ing">' + ing + '</div>' : "") +
    (steps ? '<div class="sh">Steps</div><ol>' + steps + '</ol>' : '<div class="meta">This one came without steps. Tap Another idea.</div>') + '</div>';
  document.body.appendChild(d);
  d.addEventListener("pointerdown", e => e.stopPropagation());
  d.addEventListener("touchstart", e => e.stopPropagation(), {passive:true});
  d.addEventListener("click", e => { const b = e.target.closest("[data-r]"); if (!b) return; if (b.dataset.r === "next") recipeOpen((k + 1) % D.length); else recipeClose(); });
  // no scrolling: shrink the text until everything fits
  const ol = d.querySelector("ol"), r = d.querySelector(".r");
  const over = () => (ol && (ol.scrollHeight > ol.clientHeight + 2 || ol.scrollWidth > ol.clientWidth + 2)) || r.scrollHeight > r.clientHeight + 2;
  let f = 26; do { d.style.setProperty("--rf", f + "px"); f--; } while (f >= 12 && over());
  recipeClose.t = setTimeout(recipeClose, 15 * 60e3);
}
function recipeClose(){ clearTimeout(recipeClose.t); const d = document.getElementById("recipe"); if (d) d.remove(); }
