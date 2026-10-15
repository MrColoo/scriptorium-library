# Calibre-Web Automated

A self-hosted library for your e-books that looks after itself. Drop a file in a folder and it is
imported, converted, tagged and on your Kobo by the next sync. Built on
[Calibre-Web](https://github.com/janeczku/calibre-web) and [Calibre](https://calibre-ebook.com/),
packaged as a single Docker container.

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/crocodilestick)
· [Discord](https://discord.gg/EjgSeek94R)

## What it does

**Your library, automated**
- **Ingest folder.** Anything you drop into `/cwa-book-ingest` is imported into the library and
  removed from the folder. Duplicates are detected on the way in.
- **Conversion.** New books are converted to the format you choose (KEPUB for Kobo, EPUB for most
  other readers); you decide which originals to keep. A one-click tool converts the whole library.
- **Metadata.** New books are looked up on Hardcover, Google Books, Amazon, Kobo, DNB, ComicVine
  and other providers; edits you make in the web interface are written back into the files, so e-readers
  show the same cover and details.
- **Duplicates.** A fast index finds books added twice. Merge them, keep the best copy by your own
  format ranking, or let CWA resolve them for you.
- **Backups.** Every imported, converted or repaired file can be kept in `/config/processed_books`.

**Reading**
- **Kobo sync.** Books, shelves and reading progress stay in step with your Kobo. Sync the whole
  library or only the shelves you pick. [Set it up →](docs/kobo.md)
- **KOReader sync.** A plugin keeps your position in step between KOReader and the library.
  [Set it up →](docs/koreader.md)
- **Send to eReader.** Email books to a Kindle, PocketBook or any address, automatically for new
  books if you like. The EPUB fixer repairs files that Amazon would otherwise reject.
- **In the browser.** EPUB, PDF, comics (CBZ/CBR/CBT), plain text and DjVu readers, and an
  audiobook player that remembers where you stopped.

**Organising**
- **Smart shelves** fill themselves from rules (author, tags, rating, read status, dates…) and can
  appear on your Kobo as collections.
- **Bulk editing** in a spreadsheet-style table, plus metadata search from several providers on
  every book.
- **Statistics** on reading, downloads, imports, conversions and API usage.
- **Users and access**: roles, per-user tag and language restrictions, OAuth/OIDC, LDAP and
  reverse-proxy login, magic-link sign-in from another device.

## Quick start

```yaml
# docker-compose.yml
services:
  calibre-web-automated:
    image: crocodilestick/calibre-web-automated:latest
    container_name: calibre-web-automated
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Rome
    volumes:
      - ./config:/config                   # settings, users, logs
      - ./ingest:/cwa-book-ingest          # drop books here; files are removed after import
      - ./library:/calibre-library         # your Calibre library (created if empty)
    ports:
      - 8083:8083
    restart: unless-stopped
```

```bash
docker compose up -d
```

Open `http://<your-server>:8083` and sign in as `admin` / `admin123`. You will be asked to choose a
new password straight away.

Then:
1. **Settings → Automation**: pick your target format (KEPUB if you read on a Kobo) and what
   happens to duplicates.
2. **Profile → Kobo**: create your sync address and paste it into the Kobo. [Guide](docs/kobo.md)
3. Drop a book into the ingest folder and watch it appear.

The [installation guide](docs/installation.md) covers every volume and environment variable,
network shares, reverse proxies and migrating from Calibre-Web.

## Documentation

| Guide | |
| --- | --- |
| [Installation](docs/installation.md) | Volumes, environment variables, network shares, reverse proxies, migration |
| [Kobo](docs/kobo.md) | Sync setup, choosing what to sync, store proxy, troubleshooting |
| [KOReader](docs/koreader.md) | Progress sync plugin |
| [Automation](docs/automation.md) | Ingest, conversion, metadata, duplicates, EPUB fixer, backups |
| [Security](docs/security.md) | How the app is hardened and how to deploy it safely |
| [Development](docs/development.md) | Running from source, tests, front-end structure, translations |

## Coming from Calibre-Web?

Point `/config` at your existing Calibre-Web config folder (or a copy of it) and `/calibre-library`
at the folder you used as `/books`. Users, settings, shelves and reading progress are carried over.
Details in [Installation → Migrating](docs/installation.md#migrating-from-calibre-web).

## Related projects

- [Shelfmark](https://github.com/calibrain/shelfmark) — search and download books straight into
  your ingest folder.
- [Calibre-Web Companion](https://github.com/doen1el/calibre-web-companion) — Android app for
  browsing and downloading from your library.

## Contributing

Bug reports, ideas and pull requests are welcome; the [Discord](https://discord.gg/EjgSeek94R) is
the quickest place to talk. Start with [Development](docs/development.md).

CWA is free and open source (GPL-3.0). If it saves you time, you can support it on
[Ko-fi](https://ko-fi.com/crocodilestick).
