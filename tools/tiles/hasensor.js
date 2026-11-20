/* Sensor: one reading from Home Assistant, big enough to read across the room */
Tile("hasensor", {
  title:"Sensor", cat:"Home", size:[6, 6, 4, 4], every:5, needs:"homeassistant",
  takeover:"Take over the box when it needs a look (a door left open, a lock left unlocked, water on the floor)",
  desc:"One reading from Home Assistant in big type: the temperature outside, whether the garage door is open, the dryer's power. Doors left open and locks left unlocked turn orange.",
  settings:{
    src:{type:"source", kind:"homeassistant", label:"Home Assistant", default:""},
    entity:{type:"entity", label:"What to show", default:""},
    icon:{type:"bool", label:"Show an icon", default:true},
    changed:{type:"bool", label:"Show how long ago it changed", default:true}
  },
  css:`.m-hasensor{display:flex;flex-direction:column}
    .m-hasensor .bv{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;gap:6px;min-height:0}
    .m-hasensor .ic{font-size:44px;line-height:1}
    .m-hasensor .v{font-size:72px;font-weight:300;line-height:1.05;max-width:100%;overflow:hidden;text-overflow:ellipsis}
    .m-hasensor .v.long{font-size:48px}
    .m-hasensor .n{font-size:24px;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
    .m-hasensor .n small{display:block;font-size:17px}
    .m-hasensor.alert .v{color:#ffb74d}
    .m-hasensor.gone .v{opacity:.45}
    .m-hasensor .msg{font-size:16px;color:#ffb74d;text-align:center}`,
  cls:"m-hasensor",
  has(){ return true; },
  state(){ const d = this._fd && this._fd.data; return d && (d.states || [])[0]; },
  urgent(){ const o = this.state(); return !!(o && HA.alert(o)); },
  render(el){
    const s = this.s;
    if (HA.setup(this)){ el.innerHTML = '<h3>' + esc(this.name) + '</h3><div class="empty">Set up Home Assistant in Controls → Setup</div>'; return; }
    if (!s.entity){ el.innerHTML = '<h3>' + esc(this.name) + '</h3><div class="empty">Pick what to show in this tile\'s settings</div>'; return; }
    const d = tileData(this, HA.url(this, [s.entity]), 5), o = d && (d.states || [])[0];
    if (!o){ el.innerHTML = '<div class="empty">Loading…</div>'; return; }
    const v = HA.text(o) || HA.cap(o.state), ago = s.changed !== false && o.changed ? HA.ago(o.changed) : "";
    el.classList.toggle("alert", HA.alert(o)); el.classList.toggle("gone", o.state === "unavailable" || o.state === "missing");
    el.innerHTML = '<div class="bv">' + (s.icon !== false ? '<div class="ic">' + HA.icon(o) + '</div>' : "") + '<div class="v' + (v.length > 9 ? " long" : "") + '">' + esc(v) + '</div>' +
      '<div class="n">' + esc(this.it.name || o.name) + (ago ? '<small>' + esc(ago) + '</small>' : "") + '</div></div>' + (d.error ? '<div class="msg">' + esc(d.error) + '</div>' : "");
  }
});
