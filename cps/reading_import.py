# -*- coding: utf-8 -*-
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Import a reading history exported from Goodreads or The StoryGraph.

The CSV is parsed and matched against the library (by ISBN first, then by title and author), the
user reviews a preview, and only then are read statuses, dates and a "Want to read" shelf written.
Parsing and matching are pure functions; the preview is kept in a short-lived file between the two
requests so large histories do not have to travel back through the form.
"""

import csv
import io
import json
import os
import re
import secrets
import tempfile
import time
import unicodedata
from datetime import datetime, timezone

from flask import Blueprint, abort, flash, redirect, request, url_for
from flask_babel import gettext as _

from . import calibre_db, db, logger, ub
from .cw_login import current_user
from .render_template import render_title_template
from .usermanagement import user_login_required

log = logger.create()

reading_import = Blueprint('reading_import', __name__)

MAX_UPLOAD = 15 * 1024 * 1024
PREVIEW_TTL = 60 * 60
STATUSES = ("read", "reading", "to-read")


# ---------- Parsing ----------

def _clean_isbn(value):
    digits = re.sub(r"[^0-9Xx]", "", str(value or ""))
    return digits.upper() if len(digits) in (10, 13) else None


def isbn10_to_13(isbn):
    if not isbn or len(isbn) != 10:
        return isbn
    core = "978" + isbn[:9]
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(core))
    return core + str((10 - total % 10) % 10)


def _date(value):
    text = str(value or "").strip()
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y/%m", "%Y"):
        try:
            return datetime.strptime(text[:len(datetime.now().strftime(fmt))], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _rating(value):
    try:
        stars = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return stars if 0 < stars <= 5 else None


def _status(value):
    value = str(value or "").strip().lower()
    if value == "read":
        return "read"
    if value in ("currently-reading", "currently reading"):
        return "reading"
    if value in ("to-read", "to read", "want-to-read"):
        return "to-read"
    return None  # did-not-finish and custom shelves are left alone


def parse_csv(text):
    """(source, rows) from the text of a Goodreads or StoryGraph export. Raises ValueError otherwise.

    rows: [{title, authors, isbns, status, date, rating}] with status in STATUSES.
    """
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    headers = {h.strip() for h in (reader.fieldnames or [])}
    if {"Exclusive Shelf", "Author"} <= headers:
        source = "goodreads"
    elif {"Read Status", "Authors"} <= headers:
        source = "storygraph"
    else:
        raise ValueError("unknown format")
    rows = []
    for raw in reader:
        raw = {(k or "").strip(): (v or "").strip() for k, v in raw.items()}
        if source == "goodreads":
            authors = [raw.get("Author", "")] + [a.strip() for a in raw.get("Additional Authors", "").split(",")]
            isbns = [_clean_isbn(raw.get("ISBN13")), _clean_isbn(raw.get("ISBN"))]
            status = _status(raw.get("Exclusive Shelf"))
            when = _date(raw.get("Date Read"))
            rating = _rating(raw.get("My Rating"))
        else:
            authors = [a.strip() for a in raw.get("Authors", "").split(",")]
            isbns = [_clean_isbn(raw.get("ISBN/UID"))]
            status = _status(raw.get("Read Status"))
            when = _date(raw.get("Last Date Read"))
            rating = _rating(raw.get("Star Rating"))
        title = raw.get("Title", "")
        if not title or not status:
            continue
        rows.append({"title": title, "authors": [a for a in authors if a], "isbns": [i for i in isbns if i],
                     "status": status, "date": when, "rating": rating})
    return source, rows


# ---------- Matching ----------

def normalize_title(title):
    """Lowercase, no accents, no subtitle, no "(Series #1)", no punctuation or leading article."""
    text = unicodedata.normalize("NFKD", str(title or "")).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\(.*?\)|\[.*?\]", " ", text)
    text = re.split(r"[:;]| - ", text)[0]
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    words = text.split()
    if len(words) > 1 and words[0] in ("the", "a", "an", "il", "lo", "la", "i", "gli", "le", "l", "un", "una", "le", "les", "der", "die", "das", "el", "los", "las"):
        words = words[1:]
    return " ".join(words)


def surname(author):
    text = unicodedata.normalize("NFKD", str(author or "")).encode("ascii", "ignore").decode().lower()
    if "," in text:
        text = text.split(",")[0]
    words = re.sub(r"[^a-z ]+", " ", text).split()
    return words[-1] if words else ""


def build_index(books):
    """books: [{id, title, authors, isbns}] -> lookup tables for match()."""
    by_isbn, by_title = {}, {}
    for book in books:
        for isbn in book["isbns"]:
            clean = _clean_isbn(isbn)
            if clean:
                by_isbn.setdefault(isbn10_to_13(clean), book["id"])
        by_title.setdefault(normalize_title(book["title"]), []).append(
            (book["id"], {surname(a) for a in book["authors"]}))
    return {"isbn": by_isbn, "title": by_title}


def match(rows, index):
    """(matched, unmatched): matched rows gain book_id and how they were found ('isbn' or 'title')."""
    matched, unmatched = [], []
    for row in rows:
        book_id, how = None, None
        for isbn in row["isbns"]:
            book_id = index["isbn"].get(isbn10_to_13(isbn))
            if book_id:
                how = "isbn"
                break
        if not book_id:
            candidates = index["title"].get(normalize_title(row["title"]), [])
            wanted = {surname(a) for a in row["authors"]}
            for candidate, surnames in candidates:
                if not wanted or not surnames or wanted & surnames:
                    book_id, how = candidate, "title"
                    break
        if book_id:
            matched.append(dict(row, book_id=book_id, how=how))
        else:
            unmatched.append(row)
    return matched, unmatched


def plan(matched, current):
    """What applying would change. current maps book_id -> current read status (or missing).

    A finished book is never moved back to reading, and a book being read is not put on the
    want-to-read shelf. Duplicates in the export keep their first (most recent) row.
    """
    actions, seen = [], set()
    for row in matched:
        if row["book_id"] in seen:
            continue
        seen.add(row["book_id"])
        status = current.get(row["book_id"], ub.ReadBook.STATUS_UNREAD)
        if row["status"] == "read":
            action = "finish" if status != ub.ReadBook.STATUS_FINISHED else ("date" if row["date"] else None)
        elif row["status"] == "reading":
            action = "start" if status == ub.ReadBook.STATUS_UNREAD else None
        else:
            action = "shelve" if status == ub.ReadBook.STATUS_UNREAD else None
        if action:
            actions.append(dict(row, action=action))
    return actions


# ---------- Library and storage ----------

def _library_index():
    books = []
    query = calibre_db.session.query(db.Books).filter(calibre_db.common_filters())
    for book in query.all():
        books.append({"id": book.id, "title": book.title, "authors": [a.name for a in book.authors],
                      "isbns": [i.val for i in book.identifiers if (i.type or "").lower() in ("isbn", "isbn13", "isbn10")]
                      + ([book.isbn] if getattr(book, "isbn", None) else [])})
    return build_index(books)


def _preview_path(token):
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,64}", token or ""):
        return None
    return os.path.join(tempfile.gettempdir(), "scriptorium-import-{}.json".format(token))


def _save_preview(user_id, actions):
    for name in os.listdir(tempfile.gettempdir()):
        if name.startswith("scriptorium-import-"):
            path = os.path.join(tempfile.gettempdir(), name)
            try:
                if time.time() - os.path.getmtime(path) > PREVIEW_TTL:
                    os.remove(path)
            except OSError:
                pass
    token = secrets.token_urlsafe(24)
    with open(_preview_path(token), "w", encoding="utf-8") as handle:
        json.dump({"user_id": int(user_id), "actions": actions}, handle)
    return token


def _load_preview(token, user_id):
    path = _preview_path(token)
    if not path or not os.path.isfile(path) or time.time() - os.path.getmtime(path) > PREVIEW_TTL:
        return None, None
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("user_id") != int(user_id):
        return None, None
    return path, data.get("actions") or []


def _when(iso_date):
    if not iso_date:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(iso_date).replace(hour=12, tzinfo=timezone.utc)


def apply(user_id, actions):
    """Write the planned changes for one user. Returns counts per action."""
    counts = {"finish": 0, "date": 0, "start": 0, "shelve": 0}
    visible = {book.id for book in calibre_db.session.query(db.Books.id)
               .filter(db.Books.id.in_([a["book_id"] for a in actions])).filter(calibre_db.common_filters())}
    rows = {row.book_id: row for row in ub.session.query(ub.ReadBook).filter(ub.ReadBook.user_id == int(user_id))}
    shelf = None
    shelf_name = _("Want to read")
    for action in actions:
        book_id = int(action["book_id"])
        if book_id not in visible or action.get("action") not in counts:
            continue
        kind = action["action"]
        if kind == "shelve":
            if shelf is None:
                shelf = ub.session.query(ub.Shelf).filter(ub.Shelf.user_id == int(user_id),
                                                          ub.Shelf.name == shelf_name).first()
                if shelf is None:
                    shelf = ub.Shelf(name=shelf_name, user_id=int(user_id), is_public=0)
                    ub.session.add(shelf)
                    ub.session.flush()
            if not ub.session.query(ub.BookShelf).filter(ub.BookShelf.shelf == shelf.id,
                                                         ub.BookShelf.book_id == book_id).first():
                order = (ub.session.query(ub.BookShelf).filter(ub.BookShelf.shelf == shelf.id).count() or 0) + 1
                # Through the relationship: Calibre-Web's flush hook updates the shelf via book.ub_shelf.
                shelf.books.append(ub.BookShelf(book_id=book_id, order=order))
                counts[kind] += 1
            continue
        row = rows.get(book_id)
        if row is None:
            row = ub.ReadBook(user_id=int(user_id), book_id=book_id, read_status=ub.ReadBook.STATUS_UNREAD,
                              times_started_reading=0)
            ub.session.add(row)
            rows[book_id] = row
        when = _when(action.get("date"))
        if kind in ("finish", "date"):
            row.read_status = ub.ReadBook.STATUS_FINISHED
            row.times_started_reading = max(row.times_started_reading or 0, 1)
        else:
            row.read_status = ub.ReadBook.STATUS_IN_PROGRESS
            row.times_started_reading = max(row.times_started_reading or 0, 1)
            row.last_time_started_reading = when
        # last_modified carries the finishing date for read books (the onupdate default would overwrite it)
        ub.session.flush()
        row.last_modified = when
        counts[kind] += 1
    ub.session.commit()
    return counts


# ---------- Pages ----------

@reading_import.route("/import", methods=["GET"])
@user_login_required
def start():
    return render_title_template("reading_import.html", title=_("Import your reading history"), step="upload",
                                 page="import")


@reading_import.route("/import", methods=["POST"])
@user_login_required
def preview():
    upload = request.files.get("file")
    if not upload or not upload.filename:
        flash(_("Choose the CSV file you exported."), category="error")
        return redirect(url_for("reading_import.start"))
    raw = upload.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        flash(_("The file is too large."), category="error")
        return redirect(url_for("reading_import.start"))
    try:
        source, rows = parse_csv(raw.decode("utf-8-sig", errors="replace"))
    except (ValueError, csv.Error):
        flash(_("This does not look like a Goodreads or StoryGraph export."), category="error")
        return redirect(url_for("reading_import.start"))
    matched, unmatched = match(rows, _library_index())
    current = {row.book_id: row.read_status for row in
               ub.session.query(ub.ReadBook).filter(ub.ReadBook.user_id == int(current_user.id))}
    actions = plan(matched, current)
    token = _save_preview(current_user.id, actions)
    titles = {book.id: book for book in calibre_db.session.query(db.Books)
              .filter(db.Books.id.in_([a["book_id"] for a in actions] or [0])).all()}
    counts = {kind: sum(1 for a in actions if a["action"] == kind) for kind in ("finish", "date", "start", "shelve")}
    return render_title_template("reading_import.html", title=_("Import your reading history"), step="preview",
                                 source=source, total=len(rows), matched=len(matched), unmatched=unmatched,
                                 actions=actions, books=titles, counts=counts, token=token, page="import")


@reading_import.route("/import/apply", methods=["POST"])
@user_login_required
def apply_import():
    path, actions = _load_preview(request.form.get("token"), current_user.id)
    if path is None:
        flash(_("This preview has expired. Upload the file again."), category="error")
        return redirect(url_for("reading_import.start"))
    counts = apply(current_user.id, actions)
    try:
        os.remove(path)
    except OSError:
        pass
    flash(_("Imported: %(read)s finished, %(reading)s being read, %(shelved)s added to “%(shelf)s”.",
            read=counts["finish"] + counts["date"], reading=counts["start"], shelved=counts["shelve"],
            shelf=_("Want to read")), category="success")
    return redirect(url_for("reading_import.start"))
