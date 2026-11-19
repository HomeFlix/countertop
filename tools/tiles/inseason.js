/* In season: fruit and vegetables at their best this month */
Tile("inseason", {
  title:"In season", cat:"Lists & food", cls:"m-dinner", every:3600, size:[10, 8, 8, 6],
  desc:"Fruit and vegetables at their best this month (for the northern US).",
  render(el){
    const m = new Date().getMonth();
    if (el._m === m) return; el._m = m;
    el.innerHTML = '<h3><span>In season in ' + esc(new Date().toLocaleDateString([], {month:"long"})) + '</span></h3><div class="chips big">' +
      IN_SEASON[m].map(x => '<i>' + esc(x) + '</i>').join("") + '</div>';
  }
});
