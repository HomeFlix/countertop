**Find a look you like. Try it on your screen. Make it yours.**

Countertop now has one place for everything that changes how your dashboard looks: the **Library**. Layouts, tiles, themes and effects live side by side, each with a preview that uses your own weather, calendar and lists before anything changes. And you're not limited to what we ship: **Community** adds layouts, themes and effects that other people made.

![Browsing the Library and trying a layout on the screen](https://raw.githubusercontent.com/kizit/countertop/main/docs/screenshots/library-tour.gif)

## Find something that fits

Browse the premade dashboards, your saved layouts and every tile type in one full-screen view. Open a layout to see it with your own data, then press **Try it on the screen**: it shows on the display for two minutes and your own layout comes back by itself.

![The Library, with layouts to choose from](https://raw.githubusercontent.com/kizit/countertop/main/docs/screenshots/library-overview.png)

## Make it yours

Themes have their own page in the Library. Tap one to see it on the preview, **Use this theme** to put it on the screen (with Undo), or **Customize** to adjust it. Customizing is a draft: nothing changes on the screen until you press **Save**, and **Cancel** drops your changes.

Layouts now bring their colors along as a theme of their own, named after the layout, instead of writing over your Everyday theme.

Prefer your own effect? **Library → Effects → New effect** lets you choose emoji, how they move (fall, float up, fly across or wander), their size and speed, and an optional time of year. Pumpkin season, anyone?

![Previewing a theme, then a custom emoji effect](https://raw.githubusercontent.com/kizit/countertop/main/docs/screenshots/themes-effects.gif)

## Made by the community

**Library → Community** lists layouts, themes and effects people have shared in the [Countertop gallery](https://github.com/kizit/countertop-gallery). Open one to see it with your own pages. Nothing joins your Library until you press **Download**.

- **Updates.** If an author publishes a new version of something you downloaded, Community offers the update.
- **Remove.** Delete a download whenever you like.
- **Taken down.** If the gallery removes an item, Community tells you. Your copy keeps working until you remove it.
- **Submit yours.** Share a layout, theme or effect with **Submit yours**; every submission is checked and reviewed before it appears.
- **Nothing runs.** Gallery items are plain data (layouts, colors, emoji). They contain no code, and anything you download is checked the same way as a file from a friend. Layouts with a "Your own tile" aren't accepted yet.

Countertop only contacts the gallery when you open Community or press Refresh, and sends nothing about your setup.

![Browsing Community and downloading a theme](https://raw.githubusercontent.com/kizit/countertop/main/docs/screenshots/community-browse.gif)

## Keep it, share it, bring it back

Save a layout for later, or share a layout, theme or effect as a small `.countertop` file or a share code. **Import a file** shows you exactly what's in it before anything is added. Shared layouts leave out calendars, lists, other connected sources, your own text and Home Assistant devices, so whoever opens one connects their own.

[How sharing works](https://github.com/kizit/countertop/blob/main/docs/sharing-layouts.md)

![Importing a shared theme and previewing it first](https://raw.githubusercontent.com/kizit/countertop/main/docs/screenshots/share-import.png)

## Also in this release

- **Control Home Assistant from the screen.** Thermostats, lights, fans, blinds, media players and more have controls right on the Home and Sensor tiles. Locks, garage doors and alarms stay view-only unless you turn on **Allow locks, garage doors and alarms** for that tile, with an optional second tap to confirm. You can also rename entities per tile. See [Home Assistant](https://github.com/kizit/countertop/blob/main/docs/home-assistant.md). (thanks @RouXx67)
- **Lists you can use on the screen.** A list kept on the dashboard can be filled in and ticked off on the List tile or in Controls. A list can clear its ticks every night, and the new **Daily to-do** tile is a checklist for the day. (thanks @RouXx67)
- **Portrait pages.** On a tall screen the editor shows a portrait grid, so you can arrange each page for portrait. Your landscape layout is kept for when you turn the screen back. A new **Landscape** choice under Screen orientation keeps pages in landscape on a browser that reports a tall screen.
- **Saved layouts and full-screen pages.** Changing Main's layout keeps the old one in Saved layouts. Add page has full-screen choices: month calendar, the next hours, deals and a photo frame.
- **Immich albums.** The Photo frame tile and the Photos background can use an album from your own Immich server, next to iCloud Shared Albums. (thanks @RouXx67)
- **Meal ideas.** The dinner tile follows the time of day, from breakfast to dessert, and can add the ingredients you need to your list.
- **Tempo tile.** Today's and tomorrow's RTE Tempo color and price, read from your Home Assistant sensors. (thanks @RouXx67)
- **A French option.** The dashboard's weather, dates, times and tile names can be shown in French under Settings → Language and formats. Controls stays in English, and translations are kept small for now.
- **Settings backups.** Countertop keeps recent copies of your settings and restores the last good one if the file is ever damaged.
- **For contributors.** The repository now has contributing guides, a code of conduct, a security policy and an architecture overview. See [CONTRIBUTING](https://github.com/kizit/countertop/blob/main/CONTRIBUTING.md).

## Thanks

A big thank you to @RouXx67, who contributed Home Assistant control from the screen, the Daily to-do tile and editable lists, Immich photo albums and the Tempo tile. Contributions like these make Countertop better for everyone.

## Update

- **Mac:** use **Install Countertop** in the menu bar (or **Check for Updates**), or download the new app from the files below.
- **Unraid:** Docker tab → **Check for Updates** → **Apply Update**.
- **Docker:** `docker compose pull`, then `docker compose up -d`, keeping your data folder.
- **Linux:** see the [setup guide](https://github.com/kizit/countertop/blob/main/docs/setup.md#run-it-on-linux).

As with any bigger update, back up your data folder first. Countertop has no account and no tracking. The only routine network check is the twice-a-day look at the newest release number, which you can turn off in Controls → Status.

New here? Start with the [README](https://github.com/kizit/countertop#readme). Found a bug or have an idea? [Open an issue](https://github.com/kizit/countertop/issues).
