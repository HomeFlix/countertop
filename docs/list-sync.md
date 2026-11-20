# Keeping the grocery list in another app

The List tile can show a list that lives somewhere else. In **Controls > Setup > Lists**, pick how the list is kept:

| Kept in | How it works | Updates | Needs |
|---|---|---|---|
| **This dashboard** | Add and tick items on the phone page at `/list` | Instantly | Nothing |
| **Apple Reminders** | The server reads the Reminders app itself | Every 2 minutes | The server runs on a Mac |
| **Sent from another app** | A helper or Shortcut sends the list to the server | Seconds to minutes | One of the options below |

"Sent from another app" works wherever the server runs (Docker, Unraid, Linux, a Mac). On the dashboard the list is read-only: you tick things off in the app that keeps the list.

## 1. Set up the list

1. Open **Controls > Setup > Lists**, open your list (or add one), set **Kept in** to **Sent from another app**, and save.
2. Open it again and copy its **Sync key**. Anyone on your network who has this key can replace the list, so keep it to yourself. To change it, clear the field and save, and a new one is made.

## 2a. Apple Reminders through a Mac (recommended for Reminders)

**Countertop List Sync** is a small background app for any Mac that stays on. macOS tells it about every change to the list, including items added on an iPhone or with Siri that arrive through iCloud, and it sends the list within a few seconds. It also resends every 10 minutes in case the server restarted.

```sh
zsh tools/listsync/build.sh            # asks for the server address, the sync key and the Reminders list name
```

It needs the Xcode command line tools (`xcode-select --install`). The first time it runs, macOS asks whether it may use Reminders: click **Allow**. It then starts at every login.

- Watch it work: `tail -f ~/Library/Logs/countertop-listsync.log`
- Change the settings: `zsh tools/listsync/build.sh --setup`
- Remove it: `zsh tools/listsync/build.sh --remove`

## 2b. Apple Reminders from an iPhone (no Mac)

iOS can't run a Shortcut when a reminder is added, so this one runs when you close Reminders, plus at a few set times to catch things you added with Siri. Your phone has to be on your home Wi-Fi to reach the server.

**The Shortcut** (Shortcuts app > **+**, name it "Send Grocery List"):

1. **Find Reminders** where **List** is *Grocery* and **Is Not Completed**.
2. **Get Contents of URL**: `http://<server-ip>:8090/lists/push`
   - Method: **POST**
   - Request Body: **JSON**, with three Text fields:
     - `key`: your sync key
     - `text`: the **Reminders** variable from step 1 (one item per line)
     - `via`: `iPhone`

**The automations** (Shortcuts > Automation > **+**):

- **App** > Reminders > **Is Closed** > Run Immediately > Send Grocery List.
- Optional: **Time of Day** automations (for example 7 AM, noon and 5 PM) > Run Immediately > Send Grocery List.

## 2c. Anything else (scripts, other list apps, Home Assistant)

Send the whole list as JSON. Each send replaces the list.

```sh
curl -X POST http://<server-ip>:8090/lists/push \
  -H 'Content-Type: application/json' \
  -d '{"key": "<sync key>", "items": ["Milk", "Eggs", {"id": "abc", "text": "Bread"}], "via": "my script"}'
```

- `items`: a list of names, or objects with an `id` and `text`. Instead of `items` you can send `text` with one item per line.
- `via`: optional; the tile shows it as "from …".
- Answers `{"ok": true, "count": 3}`, or a 403 if the key is wrong.
