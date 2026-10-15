# Automation

Everything CWA does on its own is configured in *Settings → Automation*. The page is split into
Services, Import, Conversion, Metadata, Duplicates and Backups; each option has a short
explanation next to it. This guide explains how the pieces fit together.

## The life of a new book

1. A file lands in `/cwa-book-ingest` (copied there, uploaded through the web interface, or
   dropped in by another tool such as Shelfmark).
2. CWA waits until the file stops changing, then picks it up. Formats listed under
   *Import → Ignored formats* are left alone.
3. If it is not already in the **target format**, it is converted (unless its format is listed
   under *Conversion → Ignored formats*). Originals in a *Retained format* are kept next to the
   converted file.
4. The book is added to the library. If the same book is already there, *Import → Automerge*
   decides: keep both, discard the new one, or overwrite the library copy.
5. Optional follow-ups: metadata lookup, duplicate check, EPUB fixing, emailing it to your
   e-reader after the auto-send delay.
6. The file is removed from the ingest folder (and, with backups on, a copy is kept in
   `/config/processed_books`).

The **Refresh Library** button (circular arrow) in the top bar runs the ingest manually, for example after a
file was stuck. Files that fail to import are moved to `/config/processed_books/failed` with the
reason in the log.

## Conversion

- **Target format**: KEPUB for Kobo, EPUB for most other readers and for sending to Kindle.
- **Convert library** (*Settings → Library tools*) converts every book that is not in the target
  format yet, in one run. You can leave the page and come back; the run can be cancelled or
  scheduled for later, and every run's log is kept in the run archive.

## Metadata

- **Automatic fetching** looks new books up with the providers you enable, in the order you drag
  them into. **Smart application** only replaces a field when the new value is better (a longer
  description, a larger cover), and *Fields to update* limits what may change.
- **Cover & metadata enforcement**: when you edit a book in the web interface, the new cover and
  metadata are also written into the EPUB/AZW3 file, so e-readers show the same thing.
- **Hardcover auto-fetch** periodically matches books without a Hardcover ID. Matches above the
  confidence threshold are applied; the rest wait in *Settings → Library tools → Hardcover
  matches* for you to pick the right edition. Needs a Hardcover API key.

You can always fetch metadata by hand from a book's edit page (*Edit metadata → Fetch Metadata*).

## Duplicates

Books count as duplicates when all the selected criteria match (title and author by default;
language, series, publisher and format are optional). Different languages are never duplicates.

- The first time, run a **full scan** from *Duplicates* to build the index. After that, checks are
  incremental: after each import, on a cron schedule, or only when you press *Scan now*.
- On the *Duplicates* page you can delete copies, merge selected books (formats are moved into the
  first one), mark a group as *not a duplicate*, or resolve everything with a strategy after
  previewing exactly which books are kept and deleted.
- **Automatic resolution** applies a strategy on its own after a cooldown. Deleted books are backed
  up to `/config/processed_books/duplicate_resolutions` first, but treat it as permanent.
- *Keep highest quality format* follows the format ranking at the bottom of the section.

## EPUB fixer

Amazon's Send to Kindle rejects many EPUBs for small technical reasons (encoding declarations,
broken links, odd language tags). The fixer repairs them:

- automatically for every new EPUB, when *Enable CWA Kindle EPUB Fixer* is on;
- for the whole library or a single book from *Settings → Library tools → EPUB fixer*.

*Aggressive mode* also rewrites valid markup that often breaks on Kindle; it can change how some
books look. Originals are kept when *EPUB Fixer Auto-Backup* is on.

## Sending to e-readers

Each user adds their e-reader addresses on their profile. With *Automatically send new books*,
every imported book is emailed after the *auto-send delay*, giving metadata and conversion time to
finish. The administrator configures the mail server in *Settings → Email server*.

## Backups

| Setting | Folder in `/config/processed_books` |
| --- | --- |
| Import auto-backup | `imported` |
| Conversion auto-backup | `converted` |
| EPUB fixer auto-backup | `fixed_originals` |
| (always) failed imports | `failed` |
| (always) duplicate resolutions | `duplicate_resolutions` |

*Auto-zip backups* compresses these folders once a day. They are never pruned automatically;
clean them up when you need the space.

## Scheduled maintenance

*Settings → Scheduled tasks* sets the nightly window for thumbnail generation, the Calibre
database reconnect and other housekeeping. Running and finished jobs, including conversions and
email sends, are listed under *Tasks*.
