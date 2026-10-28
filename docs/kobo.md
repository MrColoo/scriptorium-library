# Kobo

Scriptorium can stand in for the Kobo Store as your device's sync server. After a one-time setup, tapping
**Sync** on the Kobo downloads new books, removes the ones you take off, creates collections from
your shelves and sends your reading progress back to the library.

## 1. Turn it on (administrator)

*Settings → Server & features → Features → Enable Kobo sync.*

- **Proxy unknown requests to Kobo Store** keeps the store working on the device (recommendations,
  purchases, your Kobo account). Leave it on unless you want the device fully offline from Kobo.
- **Kobo port**: only needed when the Kobo reaches Scriptorium on a different port than the browser does
  (for example through a port forward).

For the best experience on a Kobo, set *Settings → Automation → Conversion → target format* to
**KEPUB**: page numbers, reading statistics and faster page turns. EPUB books also sync; if
`kepubify` is configured they are converted to KEPUB on the fly when the Kobo downloads them.

## 2. Create your sync address (every user)

*Profile → Devices → Kobo → Create sync address.* (If Kobo is not listed there, turn it on with
the switch at the top of *Devices*.)

Open the profile page from an address the Kobo can reach — your server's LAN IP or domain, not
`localhost` — because the address is built from the one in your browser. Scriptorium warns you if it
looks wrong.

The address is personal: anyone who has it can download your books. If it leaks, press
**Regenerate** and paste the new one into the Kobo. **Revoke access** cuts the device off.

## 3. Paste it into the Kobo

1. Connect the Kobo to your computer with the USB cable.
2. Open `.kobo/Kobo/Kobo eReader.conf` in a plain-text editor. (`.kobo` is a hidden folder; on
   macOS press ⌘⇧. in Finder to show it.)
3. In the `[OneStoreServices]` section, replace the `api_endpoint=` line with the one you copied.
4. Save, eject the Kobo and tap **Sync**.

The profile page then shows when the device last synced and how many books it has.

## Choosing what to sync

On *Profile → Kobo* you choose between:

- **Whole library** — every compatible book (KEPUB or EPUB) goes to the device.
- **Only selected shelves** — only books on shelves with *Sync with Kobo* turned on. Those shelves
  appear as collections with the same name on the Kobo. Turn sync on from a shelf's edit page,
  or with *Add to Kobo* on a book's page.

Smart shelves can sync too, if the administrator enables *Settings → Automation → Sync Magic
Shelves to Kobo*. Their contents update as books match or stop matching the rules.

Removing a book from a synced shelf removes it from the device at the next sync; it stays in the
library.

## Reading progress

Your position, the read/unread status and the time spent reading flow from the Kobo to Scriptorium at
every sync. The book page shows them under *Reading progress*, and the home page lists what you are
reading under *Continue reading*.

If you also use KOReader, see [KOReader](koreader.md).

## No Kobo, or moving to KOReader

Every user picks the devices they read with in *Profile → Devices*. Turn Kobo off and its
shortcuts, setup steps and book-page card disappear for you; turn it back on at any time.

If you install KOReader on your Kobo, press **Remove Kobo** in the same place. The sync address
stops working, so the built-in reader and KOReader do not both sync, and Kobo features are hidden.
Books already on the device stay there, and your reading progress and read status are kept.

## Re-sending everything

*Profile → Devices → Kobo → Force full kobo sync* makes the next sync send every book again. Use it after
changing covers or metadata in bulk, or when the device and library have drifted apart.

## Troubleshooting

**Sync fails immediately.** Check the `api_endpoint` line: it must be the full address shown on
your profile, including `/kobo/<token>`, and reachable from the Kobo's Wi-Fi. Open the address in
a phone browser on the same network; you should get a response rather than a timeout.

**Sync starts, then stops half-way.** Usually a reverse proxy limit. Kobo requests and responses
carry large headers and bodies; with nginx add:

```nginx
proxy_buffer_size 128k;
proxy_buffers 4 256k;
proxy_busy_buffers_size 256k;
client_max_body_size 0;
```

**HTTPS with a self-signed certificate.** The Kobo rejects it. Use a certificate from a public
authority (Let's Encrypt) or plain HTTP on your LAN.

**A book does not appear.** It must have a KEPUB or EPUB file, must not be archived, and — with
*Only selected shelves* — must be on a synced shelf. Restrictions on your account (tags, languages)
apply to sync as well.

**The store stopped working.** Turn on *Proxy unknown requests to Kobo Store*. To go back to the
official store entirely, restore the original `api_endpoint=https://storeapi.kobo.com` line.
