/* Month: a calendar of the whole month with events, holidays, matches and weather */
Tile("month", {
  title:"Month", cat:"Calendar", card:false, cls:"m-month", every:300, size:[48, 32, 24, 16], feeds:["events", "wx", "team"], noFit:true,
  desc:"The whole month as a calendar: events, holidays, your teams' matches and the forecast. Best as a page of its own.",
  settings:{
    cals:{type:"source", kind:"calendars", multi:true, label:"Calendars", default:[]},
    teams:{type:"source", kind:"teams", multi:true, label:"Teams' matches", default:[]}
  },
  render(el){
    const now = new Date(), y = now.getFullYear(), m = now.getMonth();
      const s = this.s;
    const first = new Date(y, m, 1), startDow = (first.getDay() - (THEMEV.weekStart === "Monday" ? 1 : 0) + 7) % 7, days = new Date(y, m + 1, 0).getDate();
    const weeks = Math.ceil((startDow + days) / 7);
    if (!el.firstChild) el.innerHTML = '<div class="mh"><h1></h1></div><div class="grid"></div>';
    el.querySelector("h1").innerHTML = esc(now.toLocaleDateString([], {month:"long"})) + '<small>' + y + '</small>';
    const g = el.querySelector(".grid");
    g.style.gridTemplateRows = "30px repeat(" + weeks + ",1fr)";
    const wk = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]; if (THEMEV.weekStart === "Monday") wk.push(wk.shift());
    let h = wk.map(d => '<div class="hd">' + d + '</div>').join("");
    const t0 = startOfDay(now).getTime(), j = STATE.wx;
    for (let i = 0; i < weeks * 7; i++){
      const d = new Date(y, m, 1 - startDow + i), out = d.getMonth() !== m, k = dayKey(d);
      const cls = "cell" + (out ? " out" : "") + (d.getTime() < t0 ? " past" : "") + (k === dayKey(now) ? " today" : "");
      const chips = [];
      const hol = holidayOn(d); if (hol) chips.push('<div class="e hol">' + esc(hol) + '</div>');
      for (const {g:match, team} of teamMatchesOn(d, s.teams)) chips.push('<div class="e team">⚽ ' + (match.done ? "" : shortTime(new Date(match.date)) + " ") + esc(teamShort(team)) + (match.home ? " vs " : " @ ") + esc(match.opp) + '</div>');
      const evs = eventsOn(d, s.cals);
      evs.slice(0, 3).forEach(e => chips.push('<div class="e' + (e.allDay ? " allday" : "") + '">' + (e.allDay ? "" : esc(shortTime(evDate(e))) + " ") + esc(e.summary) + '</div>'));
      if (evs.length > 3) chips.push('<div class="more">+' + (evs.length - 3) + ' more</div>');
      let cw = "";
      if (j && j.daily){ const x = j.daily.time.findIndex(t => dayKey(new Date(t + "T00:00:00")) === k); if (x >= 0 && !out) cw = '<div class="cw">' + wx(j.daily.weather_code[x], false).g + " " + Math.round(j.daily.temperature_2m_max[x]) + "°</div>"; }
      h += '<div class="' + cls + '"><div class="n">' + d.getDate() + '</div>' + chips.join("") + cw + '</div>';
    }
    g.innerHTML = h;
  }
});
