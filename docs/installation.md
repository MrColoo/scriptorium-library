# Installation reference

Everything about deploying Scriptorium. New to Docker? Follow [Start here](start-here.md) instead.

## Requirements

- Docker with the Compose plugin, on `linux/amd64` or `linux/arm64`. 32-bit systems are not supported.
- About 600 MB for the compressed image, and room for your books.
- Three folders on the host.

The image exposes port 8083 and ships a healthcheck with a 120-second start period, so a first
start shows `starting` for a while.

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
      # - HARDCOVER_TOKEN=…  # optional, see the configuration reference
    volumes:
      - /srv/scriptorium/config:/config
      - /srv/scriptorium/ingest:/cwa-book-ingest
      - /srv/books/library:/calibre-library
      # - /srv/scriptorium/calibre-plugins:/config/.config/calibre/plugins
    ports:
      - 8083:8083
    restart: unless-stopped
```

Start it with `docker compose up -d` and open `http://<server>:8083`. The first page creates the
administrator account: choose a username and a password. Do it before you share the address, as
whoever opens it first creates that account. An upgrade from Calibre-Web or Calibre-Web-Automated
keeps your accounts and skips this page.

Only ever change the **left** side of the volume and port mappings. The paths inside the container
(`/config`, `/cwa-book-ingest`, `/calibre-library`) are fixed. All environment variables are in the
[configuration reference](configuration.md#environment-variables).

> [!TIP]
> For a server you care about, pin a version instead of `latest`. See
> [Choosing a version](updating-and-backups.md#choosing-a-version).

## Volumes

Keep the three folders separate. Do not put one inside another.

| Container path | What it holds |
| --- | --- |
| `/config` | `app.db` (users and settings), `cwa.db` (automation settings and statistics), logs, backups in `processed_books/`. Back this folder up. |
| `/cwa-book-ingest` | Drop zone. Every supported file placed here is imported and then **deleted** from the folder. Do not download into it directly: copy finished files in. |
| `/calibre-library` | The Calibre library (`metadata.db` plus the book folders). If it is empty, Scriptorium creates a library. If it contains several, Scriptorium mounts the largest one and logs which. |
| `/config/.config/calibre/plugins` | Optional. Your Calibre plugins, used during conversion. |

### Permissions

The container runs as `PUID:PGID`. At start-up it takes ownership of `/config`, the ingest folder
and the library, so the host folders end up owned by that user. This is the reason to set `PUID`
and `PGID` to your own account: otherwise you may not be able to add files to `ingest`.

Files you copy into the ingest folder must be readable by the same user. Run `id` on the host to
find the right numbers, and see [Troubleshooting](troubleshooting.md#books-in-the-ingest-folder-are-not-imported)
if imports fail.

### Calibre plugins

To use Calibre plugins during conversion, mount your plugins folder as in the compose file above
and copy `customize.py.json` to `/config/.config/calibre/`, or the plugins are not registered.

`customize.py.json` lives in `~/.config/calibre/` on Linux, `~/Library/Preferences/calibre/` on
macOS and `%APPDATA%\calibre\` on Windows. If it is not there, you have no plugins configured and
can skip this.

## Using an existing Calibre library

Point `/calibre-library` at the folder that contains `metadata.db`. Scriptorium uses it as it is,
without moving anything.

Scriptorium looks for `metadata.db` when it starts. If it finds several, it mounts the largest and
logs which, so keep one library per mount. To choose by hand in *Settings → Calibre library*, set
`DISABLE_LIBRARY_AUTOMOUNT=true`.

### Using Calibre desktop alongside Scriptorium

Your library stays a standard Calibre library, so you can open it in Calibre desktop. Two programs
must not write to `metadata.db` at once, though, and that risks corrupting it:

- close Calibre desktop before Scriptorium imports or edits anything, or stop Scriptorium first;
- never open the library over a network share in Calibre while Scriptorium is running.

After changes in Calibre, press *Reconnect Calibre Database* on the Settings page so that
Scriptorium notices them. *Settings → Scheduled tasks* can do this every night.

## Docker Desktop on Windows and macOS

Docker Desktop works and is detected automatically: Scriptorium watches folders by polling, because
file events are not reliable across its Linux VM. New books in `ingest` take a few seconds longer to
be picked up. Keep the three folders on the computer's own disk, not on a cloud-synced folder such as
OneDrive or iCloud Drive.

## Raspberry Pi

Use a **64-bit** operating system: the image has no 32-bit build. Check with `uname -m`, which must
print `aarch64`. Keep the library on an SSD rather than the SD card, for speed and to spare the
card. Everything works, but large conversions are slow.

## NAS

Scriptorium is a regular Docker container, so any NAS with Docker on an Intel, AMD or 64-bit ARM
processor can run it. These notes come from how each system works. The project has not been tested
on every model, so please report what you find.

**In every case:**

- Use a real folder path from the NAS, such as `/volume1/docker/scriptorium/config`, on the left
  side of the volumes.
- Set `PUID` and `PGID` to the user who owns those folders. They are often not `1000`.
- If the disks are local to the NAS, you do **not** need `NETWORK_SHARE_MODE`.

<details>
<summary><b>Synology (DSM)</b></summary>

1. Install **Container Manager** from Package Center.
2. In File Station, create `docker/scriptorium` with `config`, `ingest` and `library` inside.
3. In Container Manager, open *Project → Create*, set the path to that folder, and paste the compose
   file.
4. Find your IDs: connect over SSH and run `id`. On Synology, users often have a `uid` such as
   `1026` and the group `users` is `100`.

Use `/volume1/docker/scriptorium/...` paths in the file, or relative paths such as `./config`,
which work because the project folder is the working directory.
</details>

<details>
<summary><b>Unraid</b></summary>

Use the *Compose Manager* plugin, or add a container by hand with the same image, port and paths.
A common layout is `/mnt/user/appdata/scriptorium/config` for config and a share under
`/mnt/user/` for the library. Unraid's usual user is `nobody:users`, so `PUID=99` and `PGID=100`.

Keep `config` on a cache or pool drive. The `/mnt/user/` path goes through Unraid's share layer,
which databases dislike: if you see "database is locked", use the direct path, such as
`/mnt/cache/appdata/…`.
</details>

<details>
<summary><b>TrueNAS SCALE</b></summary>

Add it as a custom app, or run the compose file if your version supports it. Create a dataset for
each of the three folders, and give the user matching `PUID`/`PGID` write access. The default
application user is `apps` (`568`).
</details>

<details>
<summary><b>QNAP</b></summary>

Install **Container Station** and create an application from the compose file. Use full paths such as
`/share/Container/scriptorium/config`.
</details>

## Network shares (NFS, SMB)

SQLite and inotify both struggle on network filesystems. With `NETWORK_SHARE_MODE=true`, Scriptorium:

- turns off SQLite write-ahead logging for `metadata.db` and `app.db`, which avoids
  "database is locked" errors and corruption on shares without proper locking;
- skips the recursive `chown` at start-up, which usually fails on shares;
- watches the ingest folder by polling instead of inotify events, with a few seconds of extra
  latency.

A local disk is still faster and safer. If you can, keep `config` and the library local, and only
the ingest folder on the share.

With `CWA_WATCH_MODE=poll` you get polling alone, without the other changes. Use it for an ingest
folder on a share, or for tools that write into `ingest` from outside the host.

## Feeding the ingest folder from other tools

Anything that writes to the ingest folder works: a download client, Shelfmark, a `cp` from a cron
job. Two rules:

- **Finish first, move after.** Write to another folder and move the finished file in. A file still
  being written may be picked up early.
- **Use the same filesystem**, so that the move is instant.

Formats and timing are in [Automation](automation.md#import).

## Behind a reverse proxy

See [Remote access](remote-access.md).

## Migrating from Calibre-Web-Automated

Swap the image and keep the volumes. See
[Coming from Calibre-Web-Automated](../README.md#coming-from-calibre-web-automated) in the README.

## Migrating from Calibre-Web

1. Stop Calibre-Web.
2. Mount the same config folder (or a copy) as `/config`. It contains `app.db` with your users,
   settings, shelves and reading progress.
3. Mount the folder you used as `/books` as `/calibre-library`.
4. Start Scriptorium. If the interface does not load, try the port Calibre-Web used, then change it
   once everything works.

## Running on another port

To reach Scriptorium on host port 8080, change only the left side: `8080:8083`.

If something else uses 8083 inside the same network namespace, for example with `network_mode: host`,
set `CWA_PORT_OVERRIDE` to change the port inside the container. Below 1024 this also needs
`cap_add: [NET_BIND_SERVICE]`.

## Next

- [First steps](first-steps.md)
- [Remote access](remote-access.md)
- [Updating and backups](updating-and-backups.md)
