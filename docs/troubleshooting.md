# Troubleshooting

Find your symptom below. If nothing fits, [look at the logs](#look-at-the-logs) and
[ask for help](#getting-help).

Device problems are in the [Kobo](kobo.md#troubleshooting) and
[KOReader](koreader.md#troubleshooting) guides.

## Look at the logs

Logs tell you what actually happened, so this is always a good first step. From your `scriptorium`
folder:

```bash
docker compose logs --tail 100
```

To watch live while you try something, use `docker compose logs -f`, and press Ctrl+C to stop.

This shows start-up, imports and everything the app reports. In the web interface, *Settings → Check Service Status* shows whether the background services are running,
and *Settings → Library tools → Logs & history* has the log of each run.

## Installing and starting

### "permission denied" when running docker

On Linux, your user needs to be in the `docker` group:

```bash
sudo usermod -aG docker $USER
```

Log out and back in for it to take effect.

### "port is already allocated"

Something else is using port 8083. In `docker-compose.yml`, change the left number, for example
`8084:8083`, and open `http://localhost:8084`.

### "no matching manifest"

Your system is neither 64-bit Intel/AMD nor 64-bit ARM. On a Raspberry Pi, install the 64-bit
operating system. `uname -m` should print `aarch64` or `x86_64`.

### The container keeps restarting

Check the logs. The usual cause is a folder that cannot be written to. See
[Permissions](installation.md#permissions).

### `docker compose ps` says `starting` or `unhealthy`

The first start can take a few minutes while the library is prepared, and the healthcheck allows
for that. If it stays that way, check the logs.

## Reaching the page

### I cannot open the page

Work through this list:

1. Is it running? `docker compose ps` should show `healthy`.
2. Does it work on the server itself? Try `http://localhost:8083` there.
3. Are you using the right address? From another device, use the server's IP, not `localhost`.
4. Is your phone on the same Wi-Fi? Guest networks usually keep devices apart. Turn off mobile data
   while testing.
5. Is the firewall blocking it? On Ubuntu with `ufw`, run `sudo ufw allow 8083/tcp`. On Windows,
   allow Docker Desktop through the firewall when asked.
6. Are you on `http://`, not `https://`? Without a proxy, Scriptorium only speaks plain HTTP.

### The address stopped working after a restart

Your router gave the server a new address. Find the new one and
[reserve it](start-here.md#step-7-reach-it-from-your-other-devices).

### I keep getting logged out

Usually a proxy setting. Set `TRUSTED_PROXY_COUNT` to the number of proxies in front of Scriptorium.
See [More than one proxy](remote-access.md#more-than-one-proxy).

### I cannot sign in, and the password is right

If *Use via HTTPS* is on, sign-in only works over HTTPS. The same goes for OAuth. If you turned it on
without a working HTTPS address, turn it off from the command line and restart:

```bash
docker exec -u abc scriptorium python3 -c "import sqlite3; db = sqlite3.connect('/config/app.db'); db.execute('UPDATE settings SET config_use_https = 0'); db.commit()"
docker compose restart
```

Too many failed attempts also lock you out for a while, even with the right password. Wait a minute
or two and try again.

### I forgot my password

See [Resetting a password](updating-and-backups.md#resetting-a-password).

## Importing books

### Books in the ingest folder are not imported

1. Check permissions. The file must be readable by the `PUID` user. Compare with `ls -l ingest`.
2. Check the format. See [Supported formats](configuration.md#supported-formats). Ignored formats stay
   in the folder.
3. Check that you copied into the folder that is actually mounted: compare with `docker-compose.yml`.
4. On a network share, or if files arrive from outside the host, set `NETWORK_SHARE_MODE=true` or
   `CWA_WATCH_MODE=poll`.
5. Press the **Refresh Library** button in the top bar, and watch the logs.

### A book disappeared from the ingest folder but is not in the library

Look in `config/processed_books/failed`, which is where failed imports go. The reason is in the logs.
If the same book was already in the library, *Auto-Ingest Automerge* may have discarded it.

### Conversion fails or times out

Large PDFs and comics take time. Raise *Automation → Import → Ingest Processing Timeout*. DRM-protected
books cannot be converted.

### A new book has no cover or the wrong details

Automatic metadata is off by default. Turn it on as described in [First steps](first-steps.md#let-books-find-their-own-metadata),
or use *Edit → Fetch Metadata* on the book.

### "Database is locked"

Something else is writing to the same database, usually Calibre desktop or a network share.

- Close Calibre desktop while Scriptorium is working.
- If your library is on NFS or SMB, set `NETWORK_SHARE_MODE=true`.
- Temporary locks during large operations are normal, and clear on their own.

## Library

### My existing library is empty or not found

`metadata.db` must be inside the folder mounted as `/calibre-library`, directly or in a subfolder.
Check that the left side of the volume points to the right place. If you have several libraries,
the logs show which one was mounted.

### Changes I made in Calibre do not appear

Press *Reconnect Calibre Database* on the Settings page.

### Thumbnails are slow or missing

Press *Refresh Thumbnail Cache* on the Settings page. Thumbnails are also generated as you browse.

## Sending and syncing

### Send to eReader does nothing

Check *Tasks* in the sidebar for the error. Then:

- Press *Save and Send Test Email* in *Settings → Email server*.
- For Kindle, make sure the From Email is on [Amazon's approved list](ereaders.md#extra-steps-for-a-kindle).
- Check the *Attachment Size Limit*: books above it are not offered.

### The Install app option does not appear

Browsers only allow it over HTTPS. See [Remote access](remote-access.md).

### My year in books is empty

It needs reading data. Connect a device or [import your history](using-scriptorium.md#import-from-goodreads-or-the-storygraph).

### Reading statistics are empty

They come from KOReader. Turn on *Sync reading statistics* on each device, as described in
[KOReader](koreader.md#reading-statistics), and make sure KOReader sync is on under *Settings →
Automation → Services*.

### Highlights do not appear

Sync your device first. KOReader needs version 1.1 or newer of the plugin. On a Kobo, older
highlights may only arrive when the device sends them again.

## Updating

### The update button does not appear

The check runs every twelve hours and only for administrators. The server needs to reach
`api.github.com`. It is also off if *Automatically check for new updates* was unticked.

### Something broke after an update

[Go back to the previous version](updating-and-backups.md#going-back-to-an-earlier-version), and
please [report it](#getting-help).

## Frequently asked questions

**Does it replace Calibre desktop?** For most people, yes. You only need the desktop app for its
advanced editing tools, and your library stays compatible with it.

**Do I need to know Linux?** No. A few commands are enough, and they are all in these guides.

**Can it read books with DRM?** No. Books protected with DRM cannot be read or converted.

**Can I run it without Docker?** Docker is the supported way. Running from source is meant for
[development](development.md).

**Does it work with audiobooks?** Yes, with a player in the browser that remembers your position.
Drop M4B, M4A or MP4 files in `ingest`, or upload other audio formats.

**Does it send anything to the internet?** Only what you turn on, such as metadata lookups and Kobo
store requests, plus a check for new releases on GitHub, which you can turn off. There is no
telemetry, and no account with this project.

**How many users or books can it handle?** There is no fixed limit. Larger libraries mainly make
bulk operations, such as a full conversion or duplicate scan, take longer.

**Can two people share a Kobo?** A Kobo syncs with one sync address, so each device belongs to one
Scriptorium user. Everyone can have their own device.

## Getting help

Search the [issues](https://github.com/MrColoo/scriptorium-library/issues) first. If yours is new,
open one with:

- your Scriptorium version, from *About*;
- what you did, what you expected and what happened;
- how you run it: host system, reverse proxy, network shares;
- the relevant part of `docker compose logs`, and the *Download Debug Package* file if asked for it.
  Remove anything private before posting: the logs can contain your sync address.

For security problems, please follow [SECURITY.md](../SECURITY.md) instead of opening a public issue.
