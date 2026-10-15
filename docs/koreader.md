# KOReader

[KOReader](https://koreader.rocks/) runs on Kobo, Kindle, PocketBook, Android and more. The Scriptorium
Sync plugin keeps your reading position in step between KOReader and the library, so you can stop
on one device and continue on another (or in the browser).

## Enable it (administrator)

*Settings → Automation → Services → Enable KOReader Sync (Scriptorium Plugin).*

The first start after enabling it computes a checksum for every book file so KOReader's documents
can be matched to library books. On large libraries this takes a while and can briefly lock the
library; enable it at a quiet time.

## Install the plugin

The full, personalised instructions are on the **KOReader sync** page (*Profile → Using KOReader?
→ Set up KOReader*, or `/kosync`). In short:

1. Download `koplugin.zip` from that page.
2. Connect the device to your computer and extract the zip straight into `koreader/plugins/` on the
   device. You should end up with `koreader/plugins/cwasync.koplugin/`.
3. Eject the device and restart KOReader.

## Sign in

Open a book, tap the top of the screen, open the **Tools** menu and choose **Scriptorium Sync**.
Enter:

- **Server URL**: the address shown on the KOReader sync page (your library address followed by
  `/kosync`).
- **Username** and **password**: the same ones you use for the web interface.

## How it works

- Progress is saved when you turn pages, close or switch books, or leave KOReader, and uploaded
  in the background. Without a connection the plugin retries once the device is back online.
- Books are matched by a checksum of the file, so the copy on the device must be one downloaded
  from the library (via OPDS, the web interface or email). A file converted or edited elsewhere
  will not match.
- Progress updates the read status in the library: 0% is *unread*, anything in between is
  *reading*, 99% and above is *finished*. The position is also shared with the web reader and,
  as a percentage, with Kobo sync.

## Troubleshooting

**The plugin does not appear in the Tools menu.** Check that the folder is exactly
`koreader/plugins/cwasync.koplugin`, then enable it in *Settings → Tools → Plugin management*.

**Sign-in fails.** Check the server URL (including `/kosync`) and that you can log in to the web
interface with the same username and password from the device's network. Accounts created
through OAuth have no password until an administrator sets one.

**Progress does not sync for one book.** The file on the device is probably not the library's
copy. Download it again from the library.
