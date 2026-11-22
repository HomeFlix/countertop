# Languages

Countertop's dashboard can show its words in another language. Choose one in Controls under **Settings → Language and formats → Language**:

- **Automatic** follows the screen's own language. Dates and times use the device's settings, and the words are translated when Countertop has that language.
- **English** or **Français** uses that language on the dashboard whatever the device is set to. Dates, times and numbers follow it too, keeping the device's region when it speaks the same language (a Canadian French device stays `fr-CA`).

The 24-hour clock, the first day of the week and °C or °F are separate settings in the same place.

## What's translated so far

The dashboard's weather words, rain notes, sunrise, sunset and moon phases, the greeting, the default tile names, and the words in the clock, weather, forecast, calendar and countdown tiles. Day and month names come from the browser, so they're right in every language.

Not yet: Controls, the phone list page, the Mac app menu and the other tiles' words. Some content only comes in English from where Countertop gets it (dad jokes, the NASA picture, meal ideas, store deals) and the holiday countdowns are US holidays. Anything without a translation shows in English.

## How it works

Each language is one file in `tools/lang/`, named by its two-letter code (`fr.json`). It maps the English text to the translation:

```json
{
  "Partly cloudy": "Partiellement nuageux",
  "Rain likely around {time}": "Pluie probable vers {time}"
}
```

- The key is the English exactly as the code writes it. If the English changes, the old translation stops matching and the English shows until the file is updated.
- Keep every `{placeholder}`: the dashboard fills in the time, temperature or number.
- Keys starting with `_` are notes for translators and are ignored.

The dashboard looks words up with `tr("Partly cloudy")` or `tr("Rain likely around {time}", {time})`. Tiles use `this.t()`, which also checks the tile's own translations first (see [writing a tile](tile-api.md#words-in-other-languages)).

## Improve a translation or add a language

1. Edit `tools/lang/fr.json`, or copy it to a new file such as `tools/lang/de.json` and translate the values.
2. Run `node tests/check-lang.js` to see which words are still missing and whether any placeholder was dropped. It also lists words the code no longer uses.
3. For a new language, add it to the Language choices in `tools/countertop.py` (`SCHEMA["general"]`) and to `LANGS` in `tools/dash3.html`, with the region to use for dates in `langSetup()`.

Open a pull request. A native speaker's review is welcome on any language file.
