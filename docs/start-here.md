# Start here

This guide takes you from nothing to a working library, one step at a time. You do not need to
have run a server before. If you can copy and paste a few commands, you can do this. Set aside
about 20 minutes, most of it waiting for downloads.

Already comfortable with Docker? The [installation reference](installation.md) is quicker.

## What you are building

Scriptorium is a program that runs on a computer you control and looks after your ebooks. You open
it from a web browser, on the same machine or on any phone, tablet or e-reader in your home.

"Self-hosting" just means that: the app runs on your own hardware instead of on a company's
servers. Your books and reading history stay with you, and there is no subscription.

You will install two things:

- **Docker**, a free tool that runs apps in a sealed box called a *container*. It means you do not
  have to install Scriptorium's many dependencies by hand, and nothing gets scattered around your
  system.
- **Scriptorium**, which Docker downloads for you.

New words are explained in the [glossary](glossary.md).

## What you need

**A computer that stays on.** The library is only reachable while this computer is running.

| Option | Good to know |
| --- | --- |
| An old laptop or mini PC | Cheap, quiet and plenty fast. A great first server. |
| A NAS (Synology, QNAP, Unraid, TrueNAS…) | Often already on all day. See [NAS notes](installation.md#nas). Needs Docker support and an Intel, AMD or 64-bit ARM processor. |
| A Raspberry Pi 4 or 5 | Works with a 64-bit operating system. Imports and conversions are slower. |
| Your everyday computer | Fine for trying it out. The library goes offline when the computer sleeps. |
| A rented server (VPS) | Reachable from anywhere, but your library is then on the public internet, so read [Remote access](remote-access.md) first. |

As a guide, plan for at least 2 GB of memory, and a few gigabytes of disk space for the app plus
room for your books. Conversions are the demanding part; everything else is light.

## Step 1: Install Docker

<details>
<summary><b>Linux (Ubuntu, Debian, Fedora and others)</b></summary>

Docker's official script installs Docker and the Compose plugin:

```bash
curl -fsSL https://get.docker.com | sudo sh
```

Let your user run Docker without `sudo`, then log out and back in:

```bash
sudo usermod -aG docker $USER
```

The [Docker Engine install guide](https://docs.docker.com/engine/install/) has the manual steps if
you prefer them.
</details>

<details>
<summary><b>Windows 10 or 11</b></summary>

1. Install [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/).
   Accept the WSL 2 option when asked.
2. Restart if asked, then open Docker Desktop and wait until it says it is running.
3. Open **PowerShell** for the commands below.

Docker Desktop has to be running for Scriptorium to work. Turn on *Start Docker Desktop when you
sign in* in its settings.
</details>

<details>
<summary><b>macOS</b></summary>

1. Install [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/).
   Pick the version for your chip: Apple silicon or Intel.
2. Open Docker Desktop and wait until it says it is running.
3. Open the **Terminal** app for the commands below.

Docker Desktop has to be running for Scriptorium to work. Turn on *Start Docker Desktop when you
sign in* in its settings.
</details>

Check that it worked:

```bash
docker compose version
```

You should see a version number. If you get "command not found", Docker is not installed yet, or
on Linux you may need to log out and back in.

## Step 2: Make a home for Scriptorium

Create a folder and three folders inside it. This keeps everything in one place, which also makes
backups easy.

```bash
mkdir scriptorium
cd scriptorium
mkdir config ingest library
```

| Folder | What it is for |
| --- | --- |
| `config` | Your users, settings and logs. |
| `ingest` | The inbox. Books you put here are imported, then **removed from this folder**. |
| `library` | Your finished, organised library. |

> [!NOTE]
> Stay inside the `scriptorium` folder for all the commands below. If you close the terminal, go
> back with `cd scriptorium` first.

## Step 3: Get the configuration file

A file called `docker-compose.yml` tells Docker what to run. Download it:

```bash
curl -O https://raw.githubusercontent.com/MrColoo/scriptorium-library/main/docker-compose.yml
```

Open it in a text editor. Only the first few settings matter for now:

```yaml
- PUID=1000
- PGID=1000
- TZ=Europe/London
```

- **`TZ`** is your time zone, used for schedules and dates. Pick yours from
  [this list](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones), for example
  `Europe/Rome` or `America/New_York`.
- **`PUID` and `PGID`** say which user owns the files Scriptorium creates. On Linux and macOS, run
  `id` to see your own numbers (`uid` and `gid`) and put them here. On Windows, leave them as they are.

> [!TIP]
> Keep the indentation exactly as it is. In this file, spaces carry meaning.

## Step 4: Start it

```bash
docker compose up -d
```

Docker downloads Scriptorium (about 600 MB) and starts it. `-d` means "in the background", so you
get your terminal back. The first start takes a couple of minutes while the library is prepared.

To see how it is doing:

```bash
docker compose ps
```

When the status says `healthy`, it is ready.

## Step 5: Create your account

Open **http://localhost:8083** in a browser on the same computer. If Scriptorium runs on another
machine, use that machine's address instead (see [Step 7](#step-7-reach-it-from-your-other-devices)).

The first time, Scriptorium asks you to create your account:

- **Username**: the name you will sign in with.
- **Password**: at least 8 characters, with a number, a lowercase and an uppercase letter, and a
  special character. A bar shows how strong it is, and each rule turns green once it is met. Keep it
  somewhere safe.

Then the library opens with a short tour of the main features. You can skip it and see it again
from your profile.

## Step 6: Add your first book

Copy any ebook file (EPUB, PDF, MOBI and many others) into the `ingest` folder. Do not move a file
you have no other copy of: `ingest` is emptied as books are imported.

Wait a few seconds, then refresh the page. Your book is in the library, with its cover, and
converted to EPUB if it was in another format. That is the whole workflow: from now on, anything
you put in `ingest` takes care of itself.

You can also upload from the browser, once uploads are turned on. See
[First steps](first-steps.md#turn-on-uploads).

> [!TIP]
> Already have a Calibre library? Stop Scriptorium with `docker compose down`, copy your library
> into the `library` folder so that `metadata.db` sits directly inside it, and run
> `docker compose up -d` again. See [Using an existing Calibre library](installation.md#using-an-existing-calibre-library).

## Step 7: Reach it from your other devices

Your phone and e-reader need the server's address on your home network. It looks like
`192.168.1.50`.

<details>
<summary><b>Find the address on Linux</b></summary>

```bash
hostname -I
```

Use the first address shown.
</details>

<details>
<summary><b>Find the address on Windows</b></summary>

```powershell
ipconfig
```

Look for *IPv4 Address* under your Wi-Fi or Ethernet adapter.
</details>

<details>
<summary><b>Find the address on macOS</b></summary>

Open *System Settings → Network*, select your connection and read the IP address there.
</details>

On your phone, connected to the same Wi-Fi, open `http://192.168.1.50:8083` with your own address.

**Make the address permanent.** Home routers can hand out a different address after a restart,
which would break your bookmarks and your e-reader's sync. Open your router's settings, find
*DHCP reservation* (sometimes *static lease* or *address reservation*) and reserve the current
address for your server.

If the page does not load from your phone, see [Troubleshooting](troubleshooting.md#i-cannot-open-the-page).

## You did it

Scriptorium restarts on its own after a reboot, as long as Docker starts too. On Linux it does by
default; with Docker Desktop, turn on the option mentioned in Step 1.

Three commands are worth remembering, all run from the `scriptorium` folder:

| To | Run |
| --- | --- |
| Stop Scriptorium | `docker compose stop` |
| Start it again | `docker compose start` |
| See what it is doing | `docker compose logs -f` (press Ctrl+C to leave) |

Next:

1. Work through [First steps](first-steps.md): ten minutes of settings that make everything nicer.
2. Connect your e-reader: [Kobo](kobo.md), [KOReader](koreader.md) or
   [Kindle and others](ereaders.md).
3. Set up [backups](updating-and-backups.md#backups). You will be glad you did.
