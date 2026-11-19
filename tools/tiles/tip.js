/* Kitchen tip: a short cooking fact */
Tile("tip", {
  title:"Kitchen tip", cat:"Fun", cls:"m-fun", every:5, size:[10, 6, 8, 6],
  desc:"A short kitchen tip or food fact, changing every minute or two.",
  settings:{ every:{type:"int", label:"Seconds per tip", default:90, min:20, max:3600} },
  render(el){
    if (!funDue(el, this.s)) return;
    const P = FALLBACK.filter(f => f.h === "Kitchen fact");
    el._i = ((el._i == null ? Math.floor(Math.random() * P.length) : el._i) + 1) % P.length;
    funShow(el, {h:"Kitchen tip", t:P[el._i].t});
  }
});
