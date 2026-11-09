# -*- coding: utf-8 -*-
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""The built-in EPUB reader as a reading device, like the Kobo and KOReader.

- Position: the reader saves where you are (an EPUB CFI and a percentage). The percentage goes where
  KOReader's does, the Kobo reading state, so the book page, "Continue reading" and the read status
  follow it; the CFI is kept in the user's view settings so the reader reopens on the exact spot. The
  position is also written for KOReader, translated into its own notation (see epub_positions), so a
  KOReader device offers to continue from it. When the reader opens, it starts from the most recent
  position of the three, translating KOReader's back into a CFI.
- Highlights: stored with the Kobo and KOReader ones (source "web"), so the Highlights page shows them.
- Statistics: time spent on each page, added to the reading statistics (see reading_stats).
"""

import os
from datetime import datetime, timezone

from flask import Blueprint, abort, jsonify, request
from sqlalchemy import desc
from sqlalchemy.orm.attributes import flag_modified

from . import annotations, calibre_db, config, epub_positions, logger, ub
from .cw_login import current_user
from .usermanagement import user_login_required

log = logger.create()

web_reader = Blueprint('web_reader', __name__)

POSITIONS_KEY = "reader_positions"
MAX_POSITIONS = 300
MAX_CFI = 2048
COLORS = ("yellow", "green", "blue", "pink")  # as annotations.READER_COLORS
WEB_DEVICE = "Scriptorium"            # how the built-in reader appears to KOReader
WEB_DEVICE_ID = "scriptorium-web"
READER_FORMATS = ("epub", "kepub")


def _book_or_404(book_id):
    book = calibre_db.get_filtered_book(book_id)
    if not book:
        abort(404)
    return book


def _payload():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400)
    return data


def _clip(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else None


# ---------- Position ----------

def saved_position(user, book_id):
    """The built-in reader's own position for a book: {cfi, percent, when} or None."""
    entry = ((getattr(user, "view_settings", None) or {}).get(POSITIONS_KEY) or {}).get(str(int(book_id)))
    if not isinstance(entry, dict) or not entry.get("cfi"):
        return None
    try:
        when = datetime.fromisoformat(entry.get("at") or "")
    except ValueError:
        when = None
    return {"cfi": entry["cfi"], "percent": float(entry.get("percent") or 0), "when": when}


def remember_position(user, book_id, cfi, percent, now=None):
    """Keep the reader's position in the user's view settings, the most recent books only. The caller commits."""
    settings = dict(user.view_settings or {})
    positions = dict(settings.get(POSITIONS_KEY) or {})
    positions[str(int(book_id))] = {"cfi": cfi, "percent": round(percent, 2),
                                    "at": (now or datetime.now(timezone.utc)).isoformat()}
    if len(positions) > MAX_POSITIONS:
        positions = dict(sorted(positions.items(), key=lambda item: item[1].get("at") or "")[-MAX_POSITIONS:])
    settings[POSITIONS_KEY] = positions
    user.view_settings = settings
    flag_modified(user, "view_settings")


def book_file(book, book_format):
    """Path of the book's file in a format the reader opens, or None."""
    book_format = (book_format or "").lower()
    if book_format not in READER_FORMATS:
        return None
    for data in book.data:
        if data.format.lower() == book_format:
            path = os.path.join(config.get_book_path(), book.path, "{}.{}".format(data.name, book_format))
            return path if os.path.isfile(path) else None
    return None


def _koreader_record(user_id, book_id):
    from .progress_syncing.models import KOSyncProgress
    return (ub.session.query(KOSyncProgress)
            .filter(KOSyncProgress.user_id == int(user_id), KOSyncProgress.document == str(int(book_id)))
            .order_by(desc(KOSyncProgress.timestamp)).first())


def start_position(user, book_id, path=None):
    """Where the reader should open: the newest of its own position and the Kobo or KOReader progress.

    path is the file the reader shows: with it, KOReader's position is translated to an exact CFI.
    Returns {cfi or None, percent, source ('web', 'kobo' or 'koreader'), device} or None.
    """
    from .reading_overview import get_book_progress
    progress = get_book_progress(user, book_id)
    if not progress:
        return None
    if progress["source"] == "web":
        own = saved_position(user, book_id)
        return {"cfi": own["cfi"] if own else None, "percent": progress["percent"], "source": "web", "device": None}
    cfi = None
    if progress["source"] == "koreader" and path:
        record = _koreader_record(user.id, book_id)
        cfi = epub_positions.xpointer_to_cfi(path, record.progress) if record else None
    return {"cfi": cfi, "percent": progress["percent"], "source": progress["source"], "device": progress.get("device")}


def share_with_koreader(user, book_id, xpointer, percent):
    """Write the reader's position where KOReader reads it, so a device offers to continue from here.

    KOReader keeps one record per book, whichever device wrote it last; the plugin goes to the
    percentage when the XPointer does not exist in its copy of the book. The caller commits.
    """
    from .progress_syncing.models import KOSyncProgress
    from .progress_syncing.settings import is_koreader_sync_enabled
    if not is_koreader_sync_enabled():
        return
    record = _koreader_record(user.id, book_id)
    if record is None:
        record = KOSyncProgress(user_id=int(user.id), document=str(int(book_id)))
        ub.session.add(record)
    record.progress = xpointer or ""
    record.percentage = percent
    record.device = WEB_DEVICE
    record.device_id = WEB_DEVICE_ID
    record.timestamp = datetime.now(timezone.utc)


@web_reader.route("/read/<int:book_id>/position", methods=["POST"])
@user_login_required
def save_position(book_id):
    book = _book_or_404(book_id)
    data = _payload()
    cfi = _clip(data.get("cfi"), MAX_CFI)
    try:
        percent = float(data.get("percent"))
    except (TypeError, ValueError):
        abort(400)
    if not cfi or not cfi.startswith("epubcfi(") or not 0 <= percent <= 100:
        abort(400)
    from .progress_syncing.protocols.kosync import update_book_read_status
    remember_position(current_user, book_id, cfi, percent)
    if percent > 0:  # the very start of a book says nothing about having read it, finished or not
        update_book_read_status(current_user, book_id, percent)  # read status and the shared percentage
        path = book_file(book, data.get("format"))
        share_with_koreader(current_user, book_id, epub_positions.cfi_to_xpointer(path, cfi) if path else None, percent)
    ub.session_commit()
    return "", 204


# ---------- Highlights ----------

DEVICE_SOURCES = ("koreader", "kobo")
MAX_DEVICE_HIGHLIGHTS = 1000


def highlights_for(user, book_id, path=None):
    """Highlights for the reader to draw: its own, and, given the book file, those made on a Kobo or in KOReader.

    A device's highlights are found in the file by their words (see epub_positions.highlight_ranges); the
    ones whose words are not found, in a copy of the book that differs, are left out. They can be read
    here but changed only on the device.
    """
    rows = ub.session.query(ub.ReaderAnnotation).filter(
        ub.ReaderAnnotation.user_id == int(user.id), ub.ReaderAnnotation.book_id == int(book_id)
    ).order_by(ub.ReaderAnnotation.created).all()
    own = [{"cfi": row.source_id, "color": row.color or "yellow", "note": row.note or "", "text": row.text or ""}
           for row in rows if row.source == "web"]
    if not path:
        return own
    devices = annotations._without_copies([row for row in rows if row.source in DEVICE_SOURCES and row.text])[:MAX_DEVICE_HIGHLIGHTS]
    ranges = epub_positions.highlight_ranges(path, [(row.text, row.position if row.source == "koreader" else None)
                                                    for row in devices])
    seen = {item["cfi"] for item in own}
    for row, cfi in zip(devices, ranges):
        if cfi and cfi not in seen:
            seen.add(cfi)
            own.append({"cfi": cfi, "color": annotations.reader_color(row.color), "note": row.note or "", "text": row.text,
                        "source": row.source})
    return own


@web_reader.route("/read/<int:book_id>/highlights", methods=["POST"])
@user_login_required
def save_highlight(book_id):
    """Create or change a highlight, identified by its CFI range."""
    from .annotations import MAX_SHORT, MAX_TEXT, _upsert
    _book_or_404(book_id)
    data = _payload()
    cfi = _clip(data.get("cfi"), MAX_SHORT)
    text = _clip(data.get("text"), MAX_TEXT)
    if not cfi or not cfi.startswith("epubcfi(") or not text:
        abort(400)
    color = data.get("color") if data.get("color") in COLORS else "yellow"
    row = ub.session.query(ub.ReaderAnnotation).filter(
        ub.ReaderAnnotation.user_id == int(current_user.id), ub.ReaderAnnotation.source == "web",
        ub.ReaderAnnotation.source_id == cfi).first()
    _upsert(current_user.id, book_id, "web", {
        "source_id": cfi, "text": text, "note": _clip(data.get("note"), MAX_TEXT) or None, "color": color,
        "chapter": _clip(data.get("chapter"), MAX_SHORT) or None, "position": cfi,
        "created": row.created if row else datetime.now(timezone.utc)})
    ub.session_commit("Highlight in book {} for user {}".format(book_id, current_user.id))
    return jsonify({"cfi": cfi, "color": color}), 200 if row else 201


@web_reader.route("/read/<int:book_id>/highlights/delete", methods=["POST"])
@user_login_required
def delete_highlight(book_id):
    cfi = _clip(_payload().get("cfi"), 500)
    if not cfi:
        abort(400)
    deleted = ub.session.query(ub.ReaderAnnotation).filter(
        ub.ReaderAnnotation.user_id == int(current_user.id), ub.ReaderAnnotation.book_id == int(book_id),
        ub.ReaderAnnotation.source == "web", ub.ReaderAnnotation.source_id == cfi).delete()
    ub.session_commit()
    return ("", 204) if deleted else ("", 404)


# ---------- Statistics ----------

def _library_checksum(book_id):
    """The KOReader checksum of the book's EPUB, so the same book read on a device and here is one book."""
    from .db import BookFormatChecksum
    try:
        row = (calibre_db.session.query(BookFormatChecksum.checksum)
               .filter(BookFormatChecksum.book == int(book_id))
               .order_by(desc(BookFormatChecksum.format == "EPUB"), desc(BookFormatChecksum.created)).first())
    except Exception as e:  # the table appears once KOReader sync has been enabled
        log.debug("No checksum for book %s: %s", book_id, e)
        return None
    return row[0] if row else None


@web_reader.route("/read/<int:book_id>/pages", methods=["POST"])
@user_login_required
def save_pages(book_id):
    """Pages read, as [[page, start_time, seconds, total_pages], ...] measured by the reader."""
    from . import reading_stats
    book = _book_or_404(book_id)
    pages = _payload().get("pages")
    if not isinstance(pages, list):
        abort(400)
    stored = reading_stats.store_web_pages(current_user.id, book, _library_checksum(book_id), pages)
    return jsonify({"stored": stored})
