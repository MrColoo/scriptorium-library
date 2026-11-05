# Updating and backups

## Updating

When a new release is out, administrators see a download button in the top bar. It opens the
highlights of the new version and the command to run. Scriptorium checks GitHub for new releases
every twelve hours.

Update in three steps, from the folder with your `docker-compose.yml`:

1. [Back up](#backups) your `config` folder.
2. Download the new image and restart on it:

   ```bash
   docker compose pull && docker compose up -d
   ```

3. Open Scriptorium. It takes a minute or two to start, and every user sees a short *What's new*.
4. If you use KOReader, check whether the release needs a newer plugin: Scriptorium shows *Update
   the KOReader plugin* on the home page when one of your devices is behind. See
   [Keeping the plugin up to date](koreader.md#keeping-the-plugin-up-to-date).

Your books and settings live outside the container, so replacing it does not touch them. Old images
take up disk space after a few updates. To clear unused ones:

```bash
docker image prune
```

To turn the check off, untick *Automatically check for new updates* in the update dialog.

> [!NOTE]
> The update is a command on purpose. Giving a web app control of Docker would be a serious
> security risk. If you want updates to run on their own, tools such as
> [Watchtower](https://containrrr.dev/watchtower/) can do it, at the price of updates arriving
> before you have read the notes or made a backup.

## Choosing a version

The tag after the image name decides what you get.

| Image tag | You get | Good for |
| --- | --- | --- |
| `:latest` | The newest release | Most home users |
| `:v1` | The newest `1.x.x` | Features and fixes, no breaking changes |
| `:v1.1` | The newest `1.1.x` | Fixes only |
| `:v1.1.0` | Exactly this version, forever | Servers you want to change only by hand |

Pre-releases such as `v1.2.0-rc.1` have their own tag, and never move the others.

All release tags are listed on the
[releases page](https://github.com/MrColoo/scriptorium-library/releases).

## Going back to an earlier version

Set the image to the version you want, then run the same command:

```yaml
image: ghcr.io/mrcoloo/scriptorium-library:v1.0.0
```

```bash
docker compose pull && docker compose up -d
```

Scriptorium has not changed its existing database tables so far, so this normally just works. If a
version does change them, the release notes will say so. Restoring the backup you took before
updating is always the safest way back.

## Backups

Everything that matters lives in two folders, `config` and `library`. Stop the container to get a
consistent copy of the databases:

```bash
docker compose stop
tar czf scriptorium-backup-$(date +%F).tar.gz config library
docker compose start
```

| Folder | What you would lose without it |
| --- | --- |
| `config` | Users, settings, shelves, reading progress, highlights, statistics. |
| `library` | The books, and their metadata. |

`config/processed_books` holds the automatic backups of your originals, and can grow large. To leave
it out, add `--exclude=config/processed_books` to the `tar` command.

> [!WARNING]
> A copy on the same disk is not a backup. Keep one on another disk, and one somewhere else: an
> external drive, another computer, or an encrypted cloud destination.

### Automatic backups

On Linux, a small script and a scheduled job do it for you. Save this as `backup.sh` in your
`scriptorium` folder, adjusting the two paths:

```bash
#!/bin/sh
cd /path/to/scriptorium || exit 1
docker compose stop
tar czf "/path/to/backups/scriptorium-$(date +%F).tar.gz" --exclude=config/processed_books config library
docker compose start

# Keep the last 8 archives
ls -1t /path/to/backups/scriptorium-*.tar.gz | tail -n +9 | xargs -r rm --
```

Make it executable with `chmod +x backup.sh`, and run `crontab -e` to add a line that runs it every
Sunday at 3:00:

```cron
0 3 * * 0 /path/to/scriptorium/backup.sh
```

For large libraries, tools such as [restic](https://restic.net) or
[BorgBackup](https://www.borgbackup.org) only store what changed. NAS systems also have their own
backup apps, such as Hyper Backup on Synology.

### Restoring

```bash
docker compose down
mv config config.old
mv library library.old
tar xzf scriptorium-backup-2026-11-01.tar.gz
docker compose up -d
```

If the copy is good, delete `config.old` and `library.old`. Try a restore once before you need one:
a backup you have never restored is only a hope.

## Moving to a new server

1. Stop Scriptorium on the old server and make a [backup](#backups).
2. Install Docker on the new server.
3. Copy the archive and `docker-compose.yml` across, and extract the archive.
4. Check `PUID` and `PGID`, then run `docker compose up -d`.

If the server's address changes, a few things point to the old one:

- **Kobo**: create the sync address again from the new address, and paste it into the device.
- **KOReader**: change the Server URL in the plugin.
- **OPDS apps and the installed app**: update the address, or reinstall.

With a domain name you can avoid all of this: just point it at the new server.

## Resetting a password

If you forget your password, there are three ways back.

- **Sign-in page**: enter your username and press the forgotten password link. This needs a working
  [mail server](ereaders.md#1-set-up-the-mail-server-administrator) and an email on your account.
- **Another administrator**: *Settings → Users*, open the user, and press *Reset user Password*.
- **Command line**, when you are locked out completely:

  ```bash
  docker exec -it -u abc -e CALIBRE_DBPATH=/config -w /app/calibre-web-automated \
    scriptorium python3 cps.py -s 'admin:New-Password-1'
  ```

  Replace `admin` with the username, and `scriptorium` with the container name if you changed it.
  The new password must meet the password policy: by default, at least 8 characters with a number,
  a lowercase and an uppercase letter, and a special character.
