# Scriptorium documentation

Everything you need to run Scriptorium and get the most out of it. Pick the path that sounds like
you.

## 🌱 I am new to self-hosting

Never run a server? You are in the right place. No experience needed.

1. **[Start here](start-here.md)**: from nothing to a working library, step by step.
2. **[First steps](first-steps.md)**: ten minutes of settings that make everything nicer.
3. **[Connect your e-reader](ereaders.md)**: pick your device and follow the guide.
4. **[Backups](updating-and-backups.md#backups)**: protect your library.

Stuck on a word? The [glossary](glossary.md) explains them all in plain language.

## 🐳 I already know Docker

1. **[Installation reference](installation.md)**: compose file, volumes, NAS, Raspberry Pi, network shares.
2. **[Configuration reference](configuration.md)**: every environment variable, path and setting.
3. **[Remote access](remote-access.md)**: Tailscale, Caddy, nginx, Traefik, Cloudflare Tunnel.
4. **[Updating and backups](updating-and-backups.md)**: version pinning, rollback, restore.

Coming from Calibre-Web-Automated? [Swap the image and keep your data](../README.md#coming-from-calibre-web-automated).

## 📖 I just want to read

Someone set this up for you? Have a look at **[Using Scriptorium](using-scriptorium.md)**, then
connect your [Kobo](kobo.md) or [KOReader](koreader.md).

## All guides

### Getting started

| Guide | What is in it |
| --- | --- |
| [Start here](start-here.md) | A complete walkthrough for beginners. |
| [First steps](first-steps.md) | What to set up right after installing. |
| [Glossary](glossary.md) | Self-hosting and ebook words, explained. |

### Using Scriptorium

| Guide | What is in it |
| --- | --- |
| [Using Scriptorium](using-scriptorium.md) | A tour: search, shelves, smart shelves, readers, highlights, your year in books, import, styles, the app. |
| [Getting books onto your devices](ereaders.md) | Which method suits your device. Email, Kindle and OPDS. |
| [Kobo](kobo.md) | Wireless sync of books, shelves, progress and highlights. |
| [KOReader](koreader.md) | Progress and highlights with the Scriptorium plugin. |

### Running a server

| Guide | What is in it |
| --- | --- |
| [Installation reference](installation.md) | Deployment details, NAS, existing libraries, migrations. |
| [Remote access](remote-access.md) | Reaching your library from anywhere, with HTTPS. |
| [Updating and backups](updating-and-backups.md) | Updates, versions, rollback, backups, moving servers, password reset. |
| [Automation](automation.md) | Import, conversion, metadata, duplicates and the EPUB fixer. |
| [Administration](administration.md) | Users, permissions, LDAP, OAuth, scheduled tasks, monitoring. |
| [Configuration reference](configuration.md) | Environment variables, paths, settings map, formats. |
| [Security](security.md) | Deploying safely, and how the app is hardened. |
| [Troubleshooting](troubleshooting.md) | Solutions by symptom, and frequently asked questions. |

### Contributing

| Guide | What is in it |
| --- | --- |
| [Development](development.md) | Running from source, tests, front-end conventions, translations. |
| [Releasing](releasing.md) | How versions are tagged, built and published. |

## Found a mistake?

These guides live in the repository, so a small correction is a welcome first contribution. Open an
[issue](https://github.com/MrColoo/scriptorium-library/issues) or a pull request.
