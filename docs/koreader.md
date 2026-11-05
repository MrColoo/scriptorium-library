# KOReader

[KOReader](https://koreader.rocks/) is free reading software for Kobo, Kindle, PocketBook, Android
and more. The Scriptorium Sync plugin keeps your reading position and highlights in step between
KOReader and the library, so you can stop on one device and continue on another, or in the browser.

## Enable it (administrator)

Turn on *Settings → Automation → Services → Enable KOReader Sync (Scriptorium Plugin)*.

The first start after enabling it computes a checksum for every book file, so KOReader's documents
can be matched to library books. On large libraries this takes a while and can briefly lock the
library. Enable it at a quiet time.

Then each user turns it on for themselves under *Profile → Devices → KOReader*. The steps below
appear right there, with your server address ready to copy. The full guide is on the **KOReader
sync** page (`/kosync`).

## Install the plugin

1. Download `koplugin.zip` from that page.
2. Connect the device to your computer and extract the zip straight into `koreader/plugins/` on the
   device. You should end up with `koreader/plugins/cwasync.koplugin/`.
3. Eject the device and restart KOReader.

## Sign in

Open a book, tap the top of the screen, open the **Tools** menu and choose **Scriptorium Sync**.
Enter:

- **Server URL**: your library address, exactly as shown under *Profile → Devices → KOReader*
  (for example `https://books.example.com`). Do not add `/kosync`: the plugin does that itself.
- **Username** and **password**: the same ones you use for the web interface.

## Get your books onto the device

The plugin syncs progress, not book files. Get the files in any of these ways, as long as they come
from the library:

- browse the [OPDS catalogue](ereaders.md#reading-apps-opds) from KOReader's own file browser;
- download them from the web interface;
- [send them by email](ereaders.md#send-to-a-kindle-or-any-device-by-email).

## How it works

- Progress is saved when you turn pages, close or switch books, or leave KOReader, and uploaded
  in the background. Without a connection the plugin retries once the device is back online.
- Books are matched by a checksum of the file, so the copy on the device must be one downloaded
  from the library. A file converted or edited elsewhere will not match.
- Progress updates the read status in the library: 0% is *unread*, anything in between is
  *reading*, 99% and above is *finished*.
- The book page shows it under *Reading progress*, with the device it came from, and the home page
  lists the book under *Continue reading*. *Profile → Devices → KOReader* shows the last sync, the
  device and how many books have progress.
- The percentage is also shared with Kobo sync, so a Kobo using its own reader picks it up.

## Highlights

Version 1.1 of the plugin also sends your highlights and notes, together with your progress. They
appear under *Highlights* in the sidebar, grouped by book, and can be exported as Markdown.
Deleting a highlight in KOReader deletes it in Scriptorium at the next sync. If you installed the
plugin before, download it again from *Profile → Devices → KOReader* and replace the old folder.

With KOReader on more than one device, for example a Kobo and a phone, each device's highlights are
kept side by side: a sync from one never removes the other's. Version 1.2 of the plugin tells two
devices of the same model apart too.

## Reading statistics

KOReader measures how long you read every page. Scriptorium can share those statistics between all
your KOReader devices and show them on the **Reading statistics** page in the sidebar: time read
today and this week, your current and best streak, a calendar of your reading year, the hours and
days you read most, your pace, and the time spent on each book with an estimate of the time left.

Turn it on once on each device: *Tools → Scriptorium Sync → Sync reading statistics*. It needs
plugin 1.2 or later, and KOReader's own *Reading statistics* and *Cloud storage* plugins, which are
on by default.

- The plugin points KOReader's statistics sync at your Scriptorium server, using the same sign-in.
  KOReader merges the statistics of every device on the device itself, so each one ends up with the
  same totals and streaks, and anything that shows KOReader's statistics on the device sees them too.
- Statistics sync when you open a book, every ten minutes or so while you read with the network on,
  and when you close a book. *Sync reading statistics now* does it right away.
- The first sync merges what each device already had. Nothing is lost.
- If statistics were already syncing to another cloud folder, the plugin asks before switching.
- Removing a book from KOReader's statistics removes it on your other devices at their next sync. This
  is how KOReader's sync works.

<details>
<summary><b>Setting it up by hand</b></summary>

Without the plugin, or to check the setup: in KOReader, add a WebDAV server under *Cloud storage*
with the address `https://your-server/kosync/webdav`, your Scriptorium username and password, then
pick it in *Reading statistics → Settings → Cloud sync*.
</details>

## KOReader on a Kobo

If you used Kobo sync before installing KOReader on the same device, press **Remove Kobo** in
*Profile → Devices*. The Kobo sync address stops working and Kobo features are hidden. Your reading
progress and read status are kept.

## Troubleshooting

**The plugin does not appear in the Tools menu.** Check that the folder is exactly
`koreader/plugins/cwasync.koplugin`, then enable it in *Settings → Tools → Plugin management*.

**Set Scriptorium Server does nothing.** Some KOReader add-ons that replace the menus, such as
ZenOS, ignored this entry in plugin 1.1. Download the plugin again (version 1.2 or later) and replace
the old folder.

**Sign-in fails.** Check the server URL, which must not end in `/kosync`, and that you can log in to
the web interface with the same username and password from the device's network. Accounts created
through OAuth have no password until an administrator sets one.

**Progress does not sync for one book.** The file on the device is probably not the library's
copy. Download it again from the library.

**Reading statistics stay empty.** Check that *Sync reading statistics* is ticked on the device, that
KOReader's *Reading statistics* plugin is enabled, and press *Sync reading statistics now* with the
network on. The page shows when the statistics were last updated.

**Nothing syncs.** Make sure KOReader Sync is on under *Settings → Automation → Services*, and that
the device can reach your server. Away from home you need [remote access](remote-access.md).

More help: [Troubleshooting](troubleshooting.md).
