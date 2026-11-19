/* Agenda: your next events as a list */
Tile("agenda", {
  title:"Agenda", cat:"Calendar", cls:"m-today", every:300, size:[12, 12, 8, 6], feeds:["events"],
  desc:"Your next events as a list, with the day and time. Repeating events show once, marked \"every Tue\". Uses the calendars you set up in Setup.",
  settings:{
    cals:{type:"source", kind:"calendars", multi:true, label:"Calendars", default:[]},
    count:{type:"int", label:"How many events", default:5, min:1, max:12},
    repeats:{type:"bool", label:"Show repeating events once", default:true}
  },
  render(el){
    const s = this.s, all = upcoming(s.cals), list = (s.repeats === false ? all : collapseRepeats(all)).slice(0, s.count || 5);
    const today = new Date().toDateString(), tmr = new Date(Date.now() + 86400e3).toDateString();
    const none = !(SOURCES.calendars || []).length;
    el.innerHTML = '<h3>' + esc(this.name) + '</h3>' + (list.length ? list.map(e => {
      const d = evDate(e), ds = d.toDateString();
      const p = ds === today ? "" : ds === tmr ? "Tmrw " : d.toLocaleDateString([], d - Date.now() > 6 * 86400e3 ? {month:"short", day:"numeric"} : {weekday:"short"}) + " ";
      return '<div class="li"' + (e.color ? ' style="--ec:' + esc(e.color) + '"' : "") + '><div class="t">' + p + (e.allDay ? "All day" : fmtTime(d)) + '</div><div class="s">' + esc(e.summary) +
        (e.rep ? '<span class="rep">' + esc(e.rep) + '</span>' : "") + '</div></div>';
    }).join("") : '<div class="empty">' + (none ? "Connect a calendar in Setup → Calendars" : "Nothing coming up") + '</div>');
  }
});
