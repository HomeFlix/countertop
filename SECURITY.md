# Security

## Reporting a problem

Please don't report security problems in public issues, pull requests or discussions.

Report them privately on GitHub instead: open the [Security tab](https://github.com/kizit/countertop/security) and press **Report a vulnerability**. Only the maintainers can see the report.

Include what you can:

- what an attacker could do, and what they need first (for example, "anyone on the home network" or "someone who gets a person to import a shared layout"),
- the steps to make it happen,
- the Countertop version (shown in **Controls → Status**) and how it's installed (Mac app, Docker, Unraid, from a clone).

Countertop is volunteer-maintained, so we can't promise a turnaround, but we aim to reply within about a week, keep you posted while we work on a fix, and credit you in the release notes unless you'd rather we didn't. Please give us a reasonable time to release a fix before you talk about it publicly.

## Supported versions

Fixes go into the newest release. Docker and Unraid installs get it through `:latest`, and the Mac app offers it from its menu. Older versions don't get separate fixes.

## What Countertop protects, and what it doesn't

Countertop is built to run on a home network for one household. Knowing what it assumes helps you decide whether something is a vulnerability.

**By design, and not a vulnerability on its own:**

- Anyone who can reach Countertop on the home network can open Controls and change settings, without a password. The people in the house are the users.
- Countertop isn't meant to be reachable from the internet. If you put it there, anyone can change your dashboard.

**Is a vulnerability, please report it:**

- Secrets (calendar links, Home Assistant tokens, API keys) reaching a page, a log, the diagnostics file, a shared layout or anywhere else outside the server's `sources.json`.
- A shared layout, a Library item or a community tile that can read secrets or personal data, run code outside its sandbox, reach addresses on the home network, or change settings it shouldn't.
- Getting past the opt-in or confirmation for locks, garage doors or alarms.
- Reading or writing files outside the data folder, or running commands on the server.
- A web page on another site changing settings or triggering actions through a visitor's browser (cross-origin requests). Open access on the home network is intentional, but this is a separate concern, and reports are welcome.
- Anything that lets someone outside the home network reach Countertop or the household's data.

If you're not sure, report it privately anyway.
