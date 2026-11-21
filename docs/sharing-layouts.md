# Sharing layouts

Open **Library** in Controls (under Pages) to see your saved layouts, the premade ones and every tile. **Share a layout** turns Main or any saved layout into a small `.countertop` file or a share code. **Import a file** opens one.

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
