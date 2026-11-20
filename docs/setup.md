# Set up Countertop

Run Countertop on a computer that stays on, then open the dashboard on a screen connected to the same home network. The layout is designed for the Echo Show 15 in Silk at 1920×1080. You can also open it in a modern browser on a tablet or monitor. Other Echo models may behave differently.

## Run it on a Mac

The easiest way is the **Countertop app**. It runs the server for you and lives in the menu bar.

1. From the [latest release](https://github.com/kizit/countertop/releases/latest), download **Countertop-…-mac-apple-silicon.zip** (M1 and newer) or **…-mac-intel.zip**. It needs macOS 13 or later.
2. Unzip it and drag **Countertop** into Applications, then open it.
3. The first time, macOS says it can't check the app for malicious software, because the app isn't signed by Apple. Click **Done**, open **System Settings > Privacy & Security**, scroll down and click **Open Anyway** next to Countertop. You only do this once.

A fork-and-knife icon appears in the menu bar. Its color tells you how things are: green is working, orange needs a look, red is stopped. The menu opens Controls, the dashboard and the grocery list page, restarts the server, and turns on **Open at Login**. Your settings are kept in `~/Library/Application Support/Countertop`. When a new version is out, the menu shows **Install Countertop v…**: it downloads the update, replaces the app and starts again by itself.

The app also has **Reminders Sync**, which keeps an Apple Reminders list on the dashboard (see [list sync](list-sync.md)). If your server runs on Docker or Unraid, you can use the app just for that: turn off **Run the Server on This Mac**.

### Or build it from the source

If you'd rather run Countertop from a copy of this repository (to follow `main`, or to change the code), install Git and the Xcode command line tools (`xcode-select --install`), then:

```sh
git clone https://github.com/kizit/countertop.git
cd countertop
zsh mac/build.sh
```

That builds Countertop.app into `~/Applications`. It runs the server from this folder with your `python3` and keeps settings in `work/`, so **Install Countertop v…** in the menu runs `git pull` for you (and rebuilds the app when it changed). You can also run `git pull` yourself and choose **Restart Server**.

## Run it on Linux

With Git and Python 3 installed:

```sh
git clone https://github.com/kizit/countertop.git
cd countertop
python3 tools/countertop.py --port 8090
```

Countertop prints the local dashboard and Controls addresses. To keep it running after you close the terminal, stop the first instance with Ctrl+C and run:

```sh
mkdir -p work
nohup python3 tools/countertop.py --port 8090 > work/server.log 2>&1 &
```

For a NAS, Raspberry Pi, or other Docker host, see [Docker and Unraid installation](install-docker-unraid.md).

## Open the dashboard and set it up

Use the IP address printed by the server in place of `SERVER-IP`.

| Open on | Address | Use it for |
| --- | --- | --- |
| Echo Show or other display | `http://SERVER-IP:8090/dash` | The full-screen dashboard |
| Computer | `http://SERVER-IP:8090/control` | Setup and a live preview |
| Phone | `http://SERVER-IP:8090/list` | The shared grocery list |

On an Echo Show, open Silk, bookmark the dashboard, and tap the page once to start the full-screen keep-alive. Saying **“Alexa, select”** works instead of the tap. If Silk opens its bookmarks instead, close them and say it again. Alexa still works. If Amazon returns to its home screen after an update or power outage, reopen Silk.

The first time you open Controls, a short setup guide asks for your location, a calendar and your grocery list. You can skip it and come back from **Controls → Status → Run the setup guide again**. Everything it sets also lives in **Controls → Setup**:

- **Location & units.** Search for your town and pick your temperature and time formats.
- **Calendars.** Add an iCal link for each calendar you want to see. In iCloud Calendar, open the calendar’s information, turn on **Public Calendar**, and use **Share Link**. Google Calendar calls its link **Secret address in iCal format** in the calendar’s settings. Keep those links private.
- **Lists.** Choose **This dashboard** to share a list across phones and screens. To show an Apple Reminders list or a list kept in another app, see [list sync](list-sync.md). Reading Reminders directly needs a Mac as the server; the iPhone Shortcut and the Mac helper work with any server.
- **Optional sources.** Add teams, shared photo albums, live cams, or the stores you shop at. For deals based on purchase history, put a CSV in `work/purchases/` with `date,store,brand,item,size,price` and an optional `regular` column. Without purchase history, deals can still match the list.

From Controls, choose **Edit dashboard on screen** to arrange your tiles. For ideas, browse the [tile gallery](screenshots/tile-gallery.png) or see the [dashboard editor](screenshots/editor.png) and [tile picker](screenshots/tile-store.png).

## Data and access

Your layout, calendar links, groceries, and purchase exports live in `work/` on the server, or in the data directory you mounted for Docker. Back up that directory when you move or update your setup. Anyone on the local network who can reach the dashboard can open Controls, so keep its port off the public internet.

Weather and some optional tiles depend on public data feeds. Their availability can change. There is no Countertop account or telemetry service. Twice a day the server asks GitHub for the newest release number so Controls can tell you about updates; nothing about your setup is sent, and you can turn it off in **Controls → Status** (or set `COUNTERTOP_NO_UPDATE_CHECK=1`).

## When something goes wrong

**Controls → Status** shows whether the screen is checking in, when the weather, calendars and list last loaded, and anything that needs a look. To report a bug, press **Download diagnostics** there and attach the file to a [bug report](https://github.com/kizit/countertop/issues/new?template=bug_report.yml). The file holds your settings, version and recent logs. Calendar, album and list links, sync keys, your location, ZIP code and network addresses are removed, and list items aren't included. Open it to check before you share it.

<details>
<summary>How the dashboard works</summary>

The Python server in [tools/countertop.py](../tools/countertop.py) serves the dashboard and handles local data. The `/dash` page keeps the display awake and reloads the dashboard when settings change. Calendar links are stored in the server’s data directory and are omitted from responses to the browser.

Tiles are JavaScript files in [tools/tiles](../tools/tiles). The editor uses each tile’s settings definition to build its controls. To try writing a tile, start with [note.js](../tools/tiles/note.js) and give the new tile a unique type name.

</details>

## Screenshots and credits

All README captures show genuine Countertop screens with fictional calendar, list, weather, and other demo data. Run `node demo/capture-readme.js` from the repository to regenerate the personalization gallery and the two feature GIFs. It needs Python 3, Node, Playwright with Chromium, and ffmpeg. It runs on an isolated demo server and saves any edits only there. The [older captures](../demo/screenshots.sh) have their own script.

Weather and air quality by [Open-Meteo](https://open-meteo.com). Radar by [RainViewer](https://www.rainviewer.com). Live basemap © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright). Weekly ads via Flipp. Sports data from ESPN and MLS. Planes from [adsb.lol](https://adsb.lol). Space photos from NASA APOD. “On this day” from Wikipedia. Jokes from icanhazdadjoke. The bundled [fonts](../tools/fonts) use the SIL Open Font License 1.1.

Countertop is an independent project. Echo, Echo Show, Alexa, and Silk are trademarks of Amazon.com, Inc.
