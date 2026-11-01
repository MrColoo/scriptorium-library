# Configuration reference

A map of every setting. Guides explain how to use them; this page tells you where they are. For the
main Docker settings, see the [installation reference](installation.md).

## Environment variables

Set these under `environment:` in `docker-compose.yml`, then run `docker compose up -d`.

### Common

| Variable | Default | Purpose |
| --- | --- | --- |
| `PUID`, `PGID` | `1000` | Owner of the files the container writes. |
| `TZ` | `UTC` | Time zone, e.g. `Europe/Rome`. |
| `HARDCOVER_TOKEN` | – | API key for [Hardcover](https://docs.hardcover.app/api/getting-started/) as a metadata provider. A user's own token or the one in the settings wins over this. |
| `NETWORK_SHARE_MODE` | `false` | `true` when the library or config live on NFS or SMB. See [Network shares](installation.md#network-shares-nfs-smb). |
| `TRUSTED_PROXY_COUNT` | `1` | Number of reverse proxies in front of Scriptorium. See [More than one proxy](remote-access.md#more-than-one-proxy). |

### Advanced

| Variable | Default | Purpose |
| --- | --- | --- |
| `CWA_PORT_OVERRIDE` | `8083` | Port the web server listens on inside the container. Below 1024 also needs `cap_add: [NET_BIND_SERVICE]`. |
| `CWA_WATCH_MODE` | `inotify` | `poll` forces polling for new files, even on local disks. |
| `DISABLE_LIBRARY_AUTOMOUNT` | `false` | `true` skips the automatic library detection at start-up. |
| `SESSION_COOKIE_SECURE` | `false` | `true` marks session cookies `Secure`. Always on when OAuth or *Use via HTTPS* is enabled. |
| `COOKIE_PREFIX` | – | Prefix for cookie names. Useful when several apps share a domain. |
| `OAUTH_SSL_STRICT` | `1` | `0` skips certificate checks when talking to an OAuth provider. Only for a private provider with a self-signed certificate. |
| `SMTP_ALLOW_UNVERIFIED_SSL` | `false` | Allows a mail server with an unverified certificate. |
| `CWA_COVER_DOWNLOAD_MAX_BYTES` | – | Largest cover to download, in bytes. Overrides *Automation → Metadata → Cover File Max*. |
| `CWA_KOBO_COOKIE` | – | Cookie for the Kobo metadata provider, when Kobo blocks it. `KOBO_COOKIE` also works. |

> [!NOTE]
> Names starting with `CWA_` come from Calibre-Web-Automated, and are kept so that existing setups
> keep working. The same goes for the `/cwa-book-ingest` path and `cwa.db`.

## Where things are stored

| Path in the container | Contents |
| --- | --- |
| `/config/app.db` | Users, shelves, settings, reading progress, highlights. |
| `/config/cwa.db` | Automation settings and statistics. |
| `/config/calibre-web.log` | Main log. |
| `/config/access.log` | Web access log, if enabled. |
| `/config/convert-library.log`, `/config/epub-fixer.log` | Logs of the bulk tools. |
| `/config/processed_books/` | Automatic backups. See [Backups](automation.md#backups). |
| `/config/.config/calibre/` | Calibre's own settings and plugins. |
| `/calibre-library/metadata.db` | Your Calibre library's catalogue. |
| `/calibre-library/<Author>/<Book>/` | Book files and covers. |

## Settings map

Everything below is under **Settings** in the sidebar, for administrators.

### Automation

Explained in [Automation](automation.md).

| Tab | Settings |
| --- | --- |
| **Services** | Auto-Convert, Cover & Metadata Enforcement, Kindle EPUB Fixer and its aggressive mode, KOReader Sync, Sync Magic Shelves to Kobo, Archived Book Cleanup with its schedule, Update Notifications, Contribute Translations Notifications. |
| **Import** | Auto-Ingest Automerge, Ingest Processing Timeout, stale temp file cleanup, Auto-Send Delay, ignored formats. |
| **Conversion** | Target format, ignored and retained formats. |
| **Metadata** | Automatic fetching, Smart Application, fields to update, provider order, cover size limit. |
| **Hardcover** | Auto-fetch, schedule, confidence threshold, batch size, rate limit. |
| **Duplicates** | Detection criteria, automatic scans, notifications, automatic resolution, format ranking. |
| **Backups** | Import, conversion and EPUB fixer backups, Auto-Zip. |

### Server & features

| Tab | Settings |
| --- | --- |
| **Features** | Enable Uploads, Allowed Upload Fileformats, extension checks, Convert non-English characters in title and author, Embed Metadata, Anonymous Browsing, Public Registration, Magic Link Remote Login, Goodreads, Hardcover Sync. |
| **Kobo** | Enable Kobo sync, Proxy unknown requests to Kobo Store, Server External Port, Sync Kobo annotations to Hardcover. |
| **Login** | Standard, LDAP or OAuth login, reverse proxy authentication, Disable Standard Login. See [Administration](administration.md#sign-in-options). |
| **Security** | Use via HTTPS, OAuth group-based admin role management, Limit failed login attempts, password policy. |
| **Server** | Server Port, Update Channel, SSL certificate and key, Trusted Hosts, Log Level, log files. |
| **External binaries** | Paths to Calibre, kepubify and unrar. Found automatically in the Docker image. |

### Interface

Title, books per page, random books, authors shown, read status column, view restrictions, title
sorting, and the **default settings for new users**: language, permissions, visible sections and
allowed or denied tags.

### Other pages

| Page | Purpose |
| --- | --- |
| **Calibre library** | Library location. Set automatically unless you disabled automount. |
| **Email server** | Mail for Send to eReader and password resets, and which domains may register. See [Email](ereaders.md#1-set-up-the-mail-server-administrator). |
| **Scheduled tasks** | Nightly maintenance. See [Administration](administration.md#scheduled-tasks). |

### Library tools

| Tool | Purpose |
| --- | --- |
| **Convert library** | Convert every book to the target format. |
| **EPUB fixer** | Repair EPUBs in bulk. |
| **Duplicates** | Find and resolve duplicates. |
| **Hardcover matches** | Review uncertain Hardcover matches. |
| **Logs & history** | Logs of every automatic run. |
| **KOReader sync** | Plugin download and instructions. |
| Refresh Thumbnail Cache, Run Hardcover auto-fetch, Queue all books for metadata backup | One-off maintenance buttons. |

## Supported formats

**Imported from the ingest folder:** ACSM, AZW, AZW3, AZW4, CB7, CBC, CBR, CBZ, CHM, DJVU, DOCX, EPUB,
FB2, FBZ, HTML, HTMLZ, KEPUB, KFX, KFX-ZIP, LIT, LRF, MOBI, ODT, PDB, PDF, PML, PRC, RB, RTF, SNB,
TCR, TXT, TXTZ. Audiobooks: M4A, M4B, MP4.

**Automatic target format:** AZW3, EPUB, KEPUB, MOBI, PDF.

**Converting a single book:** AZW3, DOCX, EPUB, FB2, HTMLZ, LIT, LRF, MOBI, ODT, PDF, RTF, TXT.

**Read in the browser:** see [Reading in the browser](using-scriptorium.md#reading-in-the-browser).

DRM-protected books cannot be converted. ACSM files need a Calibre plugin that can handle them.

## Metadata providers

Amazon, Amazon Japan, ComicVine, DNB, Douban, Google Books, Hardcover, IBDB, Kobo, LitRes,
Lubimyczytac and Google Scholar. The default automatic order is IBDB, Google, DNB; change it under
*Automation → Metadata*.
