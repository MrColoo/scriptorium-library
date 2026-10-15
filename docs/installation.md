# Installation

Scriptorium runs as one Docker container. You need Docker with Compose, and three folders on the host.

## The compose file

```yaml
services:
  scriptorium:
    image: ghcr.io/mrcoloo/scriptorium-library:latest
    container_name: scriptorium
    environment:
      - PUID=1000            # user and group that own the files on the host
      - PGID=1000
      - TZ=Europe/Rome       # used for schedules and timestamps
      # - HARDCOVER_TOKEN=…  # optional, see "Environment variables"
    volumes:
      - /srv/scriptorium/config:/config
      - /srv/scriptorium/ingest:/cwa-book-ingest
      - /srv/books/library:/calibre-library
      # - /srv/scriptorium/calibre-plugins:/config/.config/calibre/plugins
    ports:
      - 8083:8083
    restart: unless-stopped
```

Start it with `docker compose up -d` and open `http://<server>:8083`. The first login is
`admin` / `admin123`; Scriptorium asks for a new password before anything else.

Only ever change the **left** side of the volume and port mappings. The paths inside the container
(`/config`, `/cwa-book-ingest`, `/calibre-library`) are fixed.

## Volumes

Keep the three folders separate; do not put one inside another.

| Container path | What it holds |
| --- | --- |
| `/config` | `app.db` (users and settings), `cwa.db` (automation settings and statistics), logs, backups in `processed_books/`. Back this folder up. |
| `/cwa-book-ingest` | Drop zone. Every supported file placed here is imported and then **deleted** from the folder. Do not download into it directly: copy finished files in. |
| `/calibre-library` | The Calibre library (`metadata.db` plus the book folders). If it is empty, Scriptorium creates a library. If it contains several, Scriptorium mounts the largest one and logs which. |
| `/config/.config/calibre/plugins` | Optional. Your Calibre plugins, used during conversion. Copy `customize.py.json` to `/config/.config/calibre/` as well, or the plugins are not registered. |

`customize.py.json` lives in `~/.config/calibre/` on Linux, `~/Library/Preferences/calibre/` on
macOS and `%APPDATA%\calibre\` on Windows. If it is not there, you have no plugins configured and
can skip the plugins volume.

### Permissions

The container runs as `PUID:PGID`. The host folders must be owned by (or writable for) that user.
A folder owned by `root:root` is the most common cause of failed imports. Files you copy into the
ingest folder must be readable by the same user.

## Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `PUID`, `PGID` | `1000` | Owner of the files the container writes. |
| `TZ` | `UTC` | Time zone, e.g. `Europe/Rome`. |
| `CWA_PORT_OVERRIDE` | `8083` | Port the web server listens on inside the container. Below 1024 also needs `cap_add: [NET_BIND_SERVICE]`. |
| `HARDCOVER_TOKEN` | – | API key for [Hardcover](https://docs.hardcover.app/api/getting-started/) as a metadata provider. Can also be set in *Settings → Server & features*. |
| `NETWORK_SHARE_MODE` | `false` | Set to `true` when the library or config live on NFS/SMB. See below. |
| `CWA_WATCH_MODE` | `inotify` | `poll` forces polling for new files even on local disks. |
| `TRUSTED_PROXY_COUNT` | `1` | Number of reverse proxies in front of Scriptorium. See below. |
| `DISABLE_LIBRARY_AUTOMOUNT` | `false` | `true` skips the automatic library detection at start-up. |

## Network shares (NFS, SMB)

SQLite and inotify both struggle on network filesystems. With `NETWORK_SHARE_MODE=true`, Scriptorium:

- turns off SQLite write-ahead logging for `metadata.db` and `app.db`, which avoids
  "database is locked" errors and corruption on shares without proper locking;
- skips the recursive `chown` at start-up, which usually fails on shares;
- watches the ingest folder by polling instead of inotify events (a few seconds of extra latency).

Docker Desktop on Windows and macOS is detected automatically and uses polling as well. A local
disk is still faster and safer for `metadata.db`; if you can, keep the library local and only the
ingest folder on the share.

## Behind a reverse proxy

Scriptorium reads `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Host` and `X-Forwarded-Prefix`
from the proxy in front of it. If there is more than one hop (for example Cloudflare Tunnel →
nginx → Scriptorium), set `TRUSTED_PROXY_COUNT` to the number of proxies. If it is too low, Scriptorium sees a
different client address on every request and session protection logs users out.

When the site is served over HTTPS, enable *Settings → Server & features → Security → Use via
HTTPS* so cookies are marked `Secure`. Do not enable it on plain HTTP or you will not be able to
log in.

For the Kobo, the proxy must pass requests to `/kobo/` unchanged and allow large responses (cover
images, book downloads). Raise the body and buffer limits if syncs stop half-way (nginx:
`proxy_buffer_size 128k; proxy_buffers 4 256k; proxy_busy_buffers_size 256k;`).

## Migrating from Calibre-Web-Automated

See [Migrating from Calibre-Web-Automated](../README.md#migrating-from-calibre-web-automated) in the README: swap the image, keep the volumes.

## Migrating from Calibre-Web

1. Stop Calibre-Web.
2. Mount the same config folder (or a copy) as `/config`. It contains `app.db` with your users,
   settings, shelves and reading progress.
3. Mount the folder you used as `/books` as `/calibre-library`.
4. Start Scriptorium. If the interface does not load, try the port Calibre-Web used, then change it once
   everything works.

## Updating

```bash
docker compose pull && docker compose up -d
```

Scriptorium tells administrators in the interface when a newer image is available. Back up `/config`
before major version jumps.
