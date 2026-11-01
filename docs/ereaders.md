# Getting books onto your devices

There are four ways to get a book from your library onto a device. Pick the row that matches yours.

| You have | Best option | Keeps progress in sync |
| --- | --- | --- |
| A Kobo with its own reader | [Kobo sync](kobo.md) | Yes |
| KOReader on any device | [KOReader](koreader.md), plus OPDS or download for the files | Yes |
| A Kindle | [Email](#send-to-a-kindle-or-any-device-by-email) | No |
| A PocketBook, or a device with an email address | [Email](#send-to-a-kindle-or-any-device-by-email) | No |
| A reading app on a phone or tablet | [OPDS](#reading-apps-opds) | No |
| Anything with a browser | [Read in the browser](using-scriptorium.md#reading-in-the-browser) | Yes, in Scriptorium |

You can also always download a file from a book's page and copy it across with a cable.

## Send to a Kindle or any device by email

Send to eReader emails a book to your device. It needs one setup by the administrator, and one by
each reader.

### 1. Set up the mail server (administrator)

Open *Settings → Email server*.

For a standard account, fill in your provider's outgoing mail (SMTP) details:

| Setting | Typical value |
| --- | --- |
| SMTP Hostname | `smtp.yourprovider.com` |
| SMTP Port | `587` |
| Encryption | STARTTLS |
| SMTP Login | Your email address |
| SMTP Password | Often an *app password*, not your normal one |
| From Email | The address books are sent from |

Press **Save and Send Test Email**. *Attachment Size Limit* sets the largest file to send.

To use Gmail with an app password, choose *Standard Email Account* with `smtp.gmail.com`, port 587
and STARTTLS. Google needs two-step verification on the account before it offers
[app passwords](https://support.google.com/accounts/answer/185833).

### 2. Add your device's address (every user)

Open *Profile → eReaders* and add your device's email address. Separate several addresses with
commas.

- **Ask before sending** lets you pick the address and format each time. With it off, books go to
  all the addresses.
- **Automatically send new books to my eReader(s)** emails every newly imported book.
  [*Settings → Automation → Import*](automation.md#import) sets how long to wait, so that metadata
  and conversion can finish first.

### Extra steps for a Kindle

Amazon only accepts mail from senders you approve.

1. Go to [Manage Your Content and Devices](https://www.amazon.com/myk) on Amazon, then
   *Preferences → Personal Document Settings*.
2. Under *Approved Personal Document E-mail List*, add the **From Email** of your mail server.
3. On the same page, find your device's *Send to Kindle* address, ending in `@kindle.com`, and add
   it to *Profile → eReaders*.

Then send a book in **EPUB**. Amazon accepts PDF too, but no longer accepts MOBI or AZW3. Amazon's
own limit is 50 MB per email.

Amazon rejects some EPUBs for small technical errors. The [EPUB fixer](automation.md#epub-fixer) is
on by default and repairs most of them.

## Reading apps (OPDS)

OPDS lets a reading app browse your library and download books over the network. Moon+ Reader,
KyBook, Panels, Librera, Thorium and KOReader itself all speak it.

In your app, add a catalogue with:

- **URL**: your library address followed by `/opds`, for example `http://192.168.1.50:8083/opds`
- **Username** and **password**: the ones you use for Scriptorium

You can choose the order books appear in under *Profile → Shelves & OPDS*.

> [!NOTE]
> Accounts that sign in with OAuth have no password until an administrator sets one, so they cannot
> use OPDS until then.

## Copying files by hand

Every book page has a **Download** button. The whole library is also a regular folder on your
server, but treat it as read-only: copying files out is fine, and changing them by hand is not. To
edit, use the web interface or [Calibre desktop](installation.md#using-calibre-desktop-alongside-scriptorium).
