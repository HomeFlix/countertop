/* Home: lights, switches, doors and sensors from Home Assistant, with switches you can tap */
const HA = {
  TAP:{light:"toggle", switch:"toggle", fan:"toggle", input_boolean:"toggle", scene:"run", script:"run"},
  ICON:{light:"💡", switch:"🔌", fan:"🌀", input_boolean:"🔘", scene:"🎬", script:"▶️", lock:"🔒", climate:"🌡️", water_heater:"🚿", media_player:"🎵",
    vacuum:"🧹", lawn_mower:"🌱", weather:"⛅", alarm_control_panel:"🛡️", camera:"📷", person:"🧑", device_tracker:"🧑", humidifier:"💧", valve:"🚰",
    siren:"🚨", update:"⬆️", calendar:"📅", todo:"📝", sun:"☀️"},
  DC:{door:"🚪", garage_door:"🚗", garage:"🚗", window:"🪟", opening:"🚪", motion:"🏃", occupancy:"🏃", presence:"🏠", moisture:"💧", smoke:"🔥", gas:"⚠️",
    carbon_monoxide:"⚠️", temperature:"🌡️", humidity:"💧", power:"⚡", energy:"⚡", battery:"🔋", illuminance:"☀️", carbon_dioxide:"🌫️", pm25:"🌫️",
    shade:"🪟", blind:"🪟", curtain:"🪟", shutter:"🪟", plug:"🔌", outlet:"🔌", connectivity:"📶", problem:"⚠️", safety:"⚠️", sound:"🔊", vibration:"📳"},
  icon(o){
    if (o.domain === "lock") return o.state === "locked" ? "🔒" : "🔓";
    if (o.domain === "cover") return o.dc === "garage" ? "🚗" : o.dc === "door" || o.dc === "gate" ? "🚪" : "🪟";
    return this.DC[o.dc] || this.ICON[o.domain] || "•";
  },
  cap(t){ t = String(t == null ? "" : t).replace(/_/g, " "); return t.charAt(0).toUpperCase() + t.slice(1); },
  num(v){ const n = parseFloat(v); if (!isFinite(n) || String(v).trim() === "" || /[^\d.\-e+]/i.test(String(v).trim())) return null;
    return Math.abs(n) >= 100 ? Math.round(n).toLocaleString() : (Math.round(n * 10) / 10).toString(); },
  // the state in plain words, the way you'd say it in the kitchen
  text(o){
    const s = o.state, dc = o.dc;
    if (s === "unavailable" || s === "missing") return s === "missing" ? "Not found" : "Unavailable";
    if (s === "unknown") return o.domain === "scene" || o.domain === "script" ? "" : "Unknown";
    if (o.domain === "binary_sensor"){
      const on = s === "on", W = {door:["Open", "Closed"], garage_door:["Open", "Closed"], window:["Open", "Closed"], opening:["Open", "Closed"],
        motion:["Motion", "Clear"], occupancy:["Someone there", "Clear"], presence:["Home", "Away"], moisture:["Wet", "Dry"], smoke:["Smoke!", "Clear"],
        gas:["Gas!", "Clear"], carbon_monoxide:["CO!", "Clear"], battery:["Low", "OK"], plug:["Plugged in", "Unplugged"], connectivity:["Connected", "Offline"],
        problem:["Problem", "OK"], lock:["Unlocked", "Locked"]}[dc] || ["On", "Off"];
      return on ? W[0] : W[1];
    }
    if (o.domain === "person" || o.domain === "device_tracker") return s === "home" ? "Home" : s === "not_home" ? "Away" : this.cap(s);
    if (o.domain === "climate" || o.domain === "water_heater") return (o.current != null ? this.num(o.current) + "°" : "") + (o.target != null ? " → " + this.num(o.target) + "°" : "") || this.cap(s);
    if (o.domain === "weather") return (o.temp != null ? this.num(o.temp) + (o.unit || "°") + " · " : "") + this.cap(s.replace("partlycloudy", "partly cloudy").replace("clear-night", "clear"));
    if (o.domain === "media_player") return o.media || this.cap(s);
    const n = this.num(s);
    if (n != null) return n + (o.unit ? (/^°|%$/.test(o.unit) ? "" : " ") + o.unit : "");
    return this.cap(s);
  },
  // worth a glance: a door left open, a lock left unlocked, water on the floor
  alert(o){
    const s = o.state;
    if (o.domain === "lock") return s === "unlocked" || s === "open" || s === "jammed";
    if (o.domain === "cover") return (o.dc === "garage" || o.dc === "door" || o.dc === "gate") && s !== "closed";
    if (o.domain === "binary_sensor") return s === "on" && /^(door|garage_door|window|opening|moisture|smoke|gas|carbon_monoxide|problem|safety|lock)$/.test(o.dc);
    if (o.domain === "alarm_control_panel") return s === "triggered";
    return false;
  },
  isOn(o){ return ["on", "open", "playing", "home", "unlocked"].includes(o.state); },
  ago(iso){
    const t = Date.parse(iso); if (!t) return "";
    const m = Math.round((Date.now() - t) / 60e3);
    return m < 1 ? "just now" : m < 60 ? m + " min ago" : m < 1440 ? Math.round(m / 60) + " h ago" : Math.round(m / 1440) + " d ago";
  },
  url(t, ids){ return "/ha/states?src=" + encodeURIComponent(t.s.src || "") + "&ids=" + encodeURIComponent(ids.join(",")); },
  setup(t){ return !(SOURCES.homeassistant || []).length; }
};

Tile("ha", {
  title:"Home", cat:"Home", size:[10, 12, 6, 6], every:5, needs:"homeassistant",
  desc:"Lights, switches, doors and sensors from Home Assistant. Tap a light or switch to turn it on or off, or a scene to run it. Locks, garage doors and alarms are shown but can't be changed from the screen.",
  settings:{
    src:{type:"source", kind:"homeassistant", label:"Home Assistant", default:""},
    entities:{type:"entity", multi:true, label:"Things to show", help:"In the order you want them", default:[]},
    taps:{type:"bool", label:"Let taps switch lights and run scenes", default:true},
    changed:{type:"bool", label:"Show how long ago doors and sensors changed", default:true}
  },
  css:`.m-ha .hl{display:grid;grid-template-columns:1fr;gap:0 28px;align-content:start}
    .slot:not(.narrow) > .m-ha.wide .hl{grid-template-columns:1fr 1fr}
    .m-ha .hr{display:grid;grid-template-columns:40px minmax(0,1fr) auto;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid rgba(255,255,255,.06)}
    .m-ha .ic{font-size:28px;text-align:center}
    .m-ha .nm{font-size:25px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .m-ha .nm small{display:block;font-size:16px;color:var(--dim)}
    .m-ha .st{font-size:24px;color:var(--dim);white-space:nowrap;text-align:right}
    .m-ha .hr.alert .st,.m-ha .hr.alert .nm{color:#ffb74d}
    .m-ha .hr.off .ic{opacity:.45} .m-ha .hr.gone{opacity:.45}
    .m-ha .tg{width:70px;height:40px;border-radius:20px;background:rgba(255,255,255,.16);position:relative;transition:background .2s}
    .m-ha .tg::after{content:"";position:absolute;top:4px;left:4px;width:32px;height:32px;border-radius:50%;background:#fff;transition:transform .2s}
    .m-ha .tg.on{background:var(--accent)} .m-ha .tg.on::after{transform:translateX(30px)}
    .m-ha .hr.busy .tg,.m-ha .hr.busy .run{opacity:.5}
    .m-ha .run{font-size:20px;padding:7px 18px;border-radius:20px;background:rgba(255,255,255,.14)}
    .m-ha [data-ha]{cursor:pointer}
    .m-ha .msg{font-size:17px;color:#ffb74d;margin-top:6px}`,
  cls:"m-ha",
  has(){ return true; },
  render(el){
    const s = this.s, ids = (s.entities || []).filter(Boolean);
    let h = '<h3>' + esc(this.name) + '</h3>';
    if (HA.setup(this)){ el.innerHTML = h + '<div class="empty">Set up Home Assistant in Controls → Setup</div>'; return; }
    if (!ids.length){ el.innerHTML = h + '<div class="empty">Pick what to show in this tile\'s settings</div>'; return; }
    const d = tileData(this, HA.url(this, ids), 5);
    if (!d){ el.innerHTML = h + '<div class="empty">Loading…</div>'; return; }
    const opt = this._opt = this._opt || {}, now = Date.now();
    h += '<div class="hl">' + (d.states || []).map(o0 => {
      const p = opt[o0.id], o = p && p.until > now ? Object.assign({}, o0, {state:p.state}) : o0;
      const tap = s.taps !== false && HA.TAP[o.domain], gone = o.state === "unavailable" || o.state === "missing";
      const sub = s.changed !== false && !tap && o.changed && /^(binary_sensor|lock|cover|person|device_tracker)$/.test(o.domain) ? HA.ago(o.changed)
        : o.domain === "light" && o.state === "on" && o.level != null ? o.level + "%" : "";
      let right;
      if (tap === "toggle" && !gone) right = '<span class="tg' + (o.state === "on" ? " on" : "") + '"></span>';
      else if (tap === "run" && !gone) right = '<span class="run">Run</span>';
      else right = '<span class="st">' + esc(HA.text(o)) + '</span>';
      return '<div class="hr' + (HA.alert(o) ? " alert" : "") + (tap === "toggle" && o.state !== "on" ? " off" : "") + (gone ? " gone" : "") + (p && p.until > now ? " busy" : "") + '"' +
        (tap && !gone ? ' data-ha="' + esc(o.id) + '"' : "") + '><span class="ic">' + HA.icon(o) + '</span><span class="nm">' + esc(o.name) + (sub ? '<small>' + esc(sub) + '</small>' : "") + '</span>' + right + '</div>';
    }).join("") + '</div>';
    if (d.error) h += '<div class="msg">' + esc(d.error) + '</div>';
    if (this._msg && this._msg.until > now) h += '<div class="msg">' + esc(this._msg.text) + '</div>';
    el.innerHTML = h;
    el.classList.toggle("wide", el.clientWidth > 820 && ids.length > 4);
    if (!el._tap){ el._tap = true; el.addEventListener("click", e => { const r = e.target.closest("[data-ha]"); if (r && !EDIT.on && !PREVIEW) this.tap(r.dataset.ha); }); }
  },
  tap(id){
    const c = this._fd, st = c && c.data && (c.data.states || []).find(o => o.id === id); if (!st) return;
    const dom = id.split(".")[0], opt = this._opt = this._opt || {};
    if (HA.TAP[dom] === "toggle") opt[id] = {state: st.state === "on" ? "off" : "on", until: Date.now() + 5000};       // show it switched right away
    else opt[id] = {state: st.state, until: Date.now() + 1500};
    render(this.id);
    fetch("/ha/call", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({src:c.data.src || this.s.src || "", entity:id})})
      .then(r => r.json().then(j => { if (!r.ok || j.error) throw new Error(j.error || r.status); return j; }))
      .then(j => { if (j.state){ const i = c.data.states.findIndex(o => o.id === id); if (i >= 0) c.data.states[i] = j.state; } delete opt[id]; },
        e => { delete opt[id]; this._msg = {text:"Didn't work: " + (e.message || e), until: Date.now() + 6000}; })
      .finally(() => { c.at = 0; render(this.id); });
  }
});
