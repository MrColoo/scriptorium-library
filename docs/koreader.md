# KOReader

[KOReader](https://koreader.rocks/) runs on Kobo, Kindle, PocketBook, Android and more. The Scriptorium
Sync plugin keeps your reading position in step between KOReader and the library, so you can stop
on one device and continue on another (or in the browser).

## Enable it (administrator)

*Settings → Automation → Services → Enable KOReader Sync (Scriptorium Plugin).*

The first start after enabling it computes a checksum for every book file so KOReader's documents
can be matched to library books. On large libraries this takes a while and can briefly lock the
library; enable it at a quiet time.

Then each user turns it on for themselves: *Profile → Devices → KOReader*. The steps below appear
right there, with your server address ready to copy. The full guide is on the **KOReader sync**
page (`/kosync`).

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

## How it works

- Progress is saved when you turn pages, close or switch books, or leave KOReader, and uploaded
  in the background. Without a connection the plugin retries once the device is back online.
- Books are matched by a checksum of the file, so the copy on the device must be one downloaded
  from the library (via OPDS, the web interface or email). A file converted or edited elsewhere
  will not match.
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

## KOReader on a Kobo

If you used Kobo sync before installing KOReader on the same device, press **Remove Kobo** in
*Profile → Devices*. The Kobo sync address stops working and Kobo features are hidden; your reading
progress and read status are kept.

## Troubleshooting

**The plugin does not appear in the Tools menu.** Check that the folder is exactly
`koreader/plugins/cwasync.koplugin`, then enable it in *Settings → Tools → Plugin management*.

**Sign-in fails.** Check the server URL (including `/kosync`) and that you can log in to the web
interface with the same username and password from the device's network. Accounts created
through OAuth have no password until an administrator sets one.

**Progress does not sync for one book.** The file on the device is probably not the library's
copy. Download it again from the library.
