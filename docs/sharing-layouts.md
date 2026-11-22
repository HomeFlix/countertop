# Sharing layouts, themes and effects

Open **Library** in Controls to see your saved layouts, the premade ones, every tile, your themes and the effects. **Share a layout** turns Main or any saved layout into a small `.countertop` file or a share code. A theme's page and your own effect's page have **Share** too. **Import a file** opens any of them.

The `countertop` field says what a file holds: `layout`, `theme` or `effect`.

## What a layout file holds

A `.countertop` file is JSON:

```json
{
  "countertop": "layout",
  "format": 1,
  "name": "Family planner",
  "description": "A month view beside the family agenda.",
  "made": "2026-11-21",
  "look": {"mode": "Light", "bg": "Color", "bgColor": "#e4dfed", "accent": "#76508a"},
  "pages": [{
    "name": "Family planner",
    "boxes": [
      {"x": 0, "y": 0, "w": 19, "h": 7, "tiles": [{"type": "clock", "settings": {"style": "Bold"}}]},
      {"x": 0, "y": 7, "w": 32, "h": 25, "tiles": [{"type": "month", "settings": {}}]}
    ]
  }]
}
```

Boxes sit on the 48 × 32 grid. A box with more than one tile has `every`, the seconds each tile shows before the next takes its turn. A share code is the same JSON, base64url-encoded, after `CT1.`.

## What is left out

When a layout is shared, these never go in the file:

- Settings of type `source`: which calendars, lists, teams, albums, cams, recipe services or Home Assistant a tile uses. Whoever opens the file picks their own under **Fill in from your setup**.
- Settings of type `entity` (Home Assistant devices).
- Settings a tile marks `share:false`, such as a note's text, countdown dates and picture links. Tile authors: add `share:false` to any setting that is likely to hold something personal.

A **Your own tile** keeps its code, and Share says so. It runs sealed off from the rest of the dashboard, as it always does.

## What importing checks

Opening a file never runs anything from it. Every tile type must be one this Countertop has; others are left out and listed. Each setting is checked against its type in the tile file (numbers are kept within their range, choices must be one of the choices, colors must be colors), and settings the tile doesn't have are dropped. Saved tile designs keep only numbers and short plain words. Nothing changes until you choose **Use on Main**, **Add as a new page** or **Save to My layouts**.

## Themes

A theme file holds a theme's settings and nothing else:

```json
{
  "countertop": "theme",
  "format": 1,
  "name": "Calm evening",
  "description": "Warmer and a little dimmer.",
  "made": "2026-11-22",
  "values": {"mode": "Dark", "accent": "#ff9f5a", "tiles": "See-through", "opacity": 55, "dim": 30, "fx": "Off"}
}
```

Each value is checked against the theme settings, the same way as a layout's `look`. A theme with a Photos background uses the photos of whoever opens it. Opening a theme shows it on the preview with your own pages. **Add to my themes** keeps it without changing the screen; **Add and use it** also puts it on the screen.

## Effects

Your own effects (Library → Effects → **New effect**) are plain data: emoji and how they move. There is no code, so an effect file can't run anything.

```json
{
  "countertop": "effect",
  "format": 1,
  "name": "Pumpkin fall",
  "description": "Pumpkins and bats for October.",
  "made": "2026-11-22",
  "effect": {"glyphs": ["🎃", "🦇", "🍬"], "motion": "fall", "size": "Big", "speed": "Slow", "spin": true, "from": "10-1", "to": "10-31"}
}
```

- `glyphs`: up to 8 emoji. Anything that isn't an emoji is dropped.
- `motion`: `fall`, `rise` (float up), `fly` (across the top) or `flutter` (wander around).
- `size`: `Small`, `Medium` or `Big`. `speed`: `Slow`, `Normal` or `Fast`. `spin`: whether falling emoji turn as they fall.
- `from` and `to`: an optional season, as month-day. Without one, it plays all year.

The built-in effects are drawn by code, so they can't be shared as files.
