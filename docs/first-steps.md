# First steps

Scriptorium works out of the box, but ten minutes of setup make it feel like yours. Do these in
order and skip whatever does not apply to you.

Administrators find everything below under **Settings** in the sidebar.

## Name your library

*Settings → Interface → Title* sets the name in the header and browser tab. If you came from
Calibre-Web-Automated, your old title is kept until you change it here.

## Pick your target format

This is the one decision that shapes everything else. Open *Settings → Automation → Conversion*
and set the **target format**:

| You read on | Choose | Why |
| --- | --- | --- |
| A Kobo with its own reader | **KEPUB** | Page numbers, reading statistics, faster page turns. |
| Anything else | **EPUB** | The default. The most compatible format, and what Kindle's email service wants. |

If your library already has books, run *Settings → Library tools → Convert library* once to convert
them too. It can take a while, and you can close the page while it runs.

## Turn on uploads

Uploading from the browser is off by default. Open *Settings → Server & features → Features* and
turn on **Enable Uploads**. An **Upload** button appears in the top bar.

Administrators can upload right away. Other users need **Allow Uploads** in their
[permissions](administration.md#permissions).

## Let books find their own metadata

Automatic metadata lookup is off by default, so a new book keeps what is in its file.

Open *Settings → Automation → Metadata*, turn on automatic fetching, and consider turning on
**Smart Application**, which only replaces a field when the new value is better.

For better matches, get a free [Hardcover](https://hardcover.app) API key and add it as your
*Hardcover API Token* under *Profile → Preferences*.

[How metadata works](automation.md#metadata)

## Set your own look

Under the account menu:

- **Customize** offers eleven ready-made styles, a *Surprise me* button and a palette editor.
- **Appearance** switches between System, Light and Dark.

Each user has their own choice, and it does not affect anyone else.

## Connect your reader

Choose the devices you read on in *Profile → Devices*. Shortcuts and setup steps appear only for
those you turn on.

| You have | Follow |
| --- | --- |
| A Kobo | [Kobo](kobo.md). Takes about two minutes, with one line to paste. |
| A device running KOReader | [KOReader](koreader.md) |
| A Kindle, or any device with an email address | [Kindle and email](ereaders.md#send-to-a-kindle-or-any-device-by-email) |
| A reading app on phone or tablet | [OPDS](ereaders.md#reading-apps-opds) |

## Install the app

On a phone, Scriptorium can live on your home screen like any other app. This needs HTTPS, so set
up [remote access](remote-access.md) first. See [Install it as an app](using-scriptorium.md#install-it-as-an-app).

## Invite your household

*Settings → Users → Add New User*. Everyone gets their own shelves, progress, highlights, devices
and style. Give each person only the [permissions](administration.md#permissions) they need.

## Bring your reading history

Coming from Goodreads or The StoryGraph? *Profile → Reading history → Import* brings your finished
books, dates and want-to-read list. [How it works](using-scriptorium.md#import-from-goodreads-or-the-storygraph)

## Set up a backup

Your library is worth protecting. It takes one command:
[Backups](updating-and-backups.md#backups).

## Decide how you will reach it from outside

At home, nothing more is needed. To use your library from anywhere, read
[Remote access](remote-access.md) and pick the option that suits you. Please do not simply forward
port 8083 on your router.
