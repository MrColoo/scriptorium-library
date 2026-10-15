# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Reading-state summaries for the library home page and the Kobo settings page."""

from datetime import datetime, timezone

from flask_babel import format_timedelta

from . import calibre_db, db, logger, ub

log = logger.create()


def get_continue_reading(user_id, limit=6):
    """Books the user is reading, most recently touched first, with Kobo progress when known.

    Returns a list of dicts: {book, progress (int percent or None), minutes_left (int or None)}.
    Only books the user is allowed to see (common_filters) are returned.
    """
    try:
        rows = (ub.session.query(ub.ReadBook)
                .filter(ub.ReadBook.user_id == int(user_id),
                        ub.ReadBook.read_status == ub.ReadBook.STATUS_IN_PROGRESS)
                .all())
    except Exception as e:
        log.debug("Could not load reading state: %s", e)
        return []
    if not rows:
        return []

    states = {}
    for row in rows:
        state = row.kobo_reading_state
        touched = state.last_modified if state and state.last_modified else datetime.min
        progress = None
        minutes_left = None
        if state is not None:
            if state.current_bookmark is not None and state.current_bookmark.progress_percent is not None:
                progress = max(0, min(100, int(round(state.current_bookmark.progress_percent))))
            if state.statistics is not None and state.statistics.remaining_time_minutes:
                minutes_left = int(state.statistics.remaining_time_minutes)
        states[row.book_id] = (touched.replace(tzinfo=None), progress, minutes_left)

    try:
        books = (calibre_db.session.query(db.Books)
                 .filter(db.Books.id.in_(list(states.keys())))
                 .filter(calibre_db.common_filters())
                 .all())
    except Exception as e:
        log.debug("Could not load books for reading state: %s", e)
        return []

    items = [{"book": book, "progress": states[book.id][1], "minutes_left": states[book.id][2],
              "touched": states[book.id][0]} for book in books]
    items.sort(key=lambda item: item["touched"], reverse=True)
    return items[:limit]


def get_kobo_last_sync(user_id):
    """UTC datetime of the user's last Kobo sync, from CWA's activity log, or None."""
    try:
        from scripts.cwa_db import CWA_DB
        cwa_db = CWA_DB()
        row = cwa_db.cur.execute(
            "SELECT MAX(timestamp) FROM cwa_user_activity WHERE user_id = ? AND event_type = 'KOBO_SYNC'",
            (int(user_id),)).fetchone()
    except Exception as e:
        log.debug("Could not read Kobo sync activity: %s", e)
        return None
    if not row or not row[0]:
        return None
    try:
        return datetime.strptime(str(row[0])[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def humanize_since(moment):
    """'12 minutes ago' style text for a UTC datetime, in the user's locale."""
    if moment is None:
        return None
    delta = moment - datetime.now(timezone.utc)
    return format_timedelta(delta, add_direction=True, threshold=0.9)


def get_kobo_book_status(user, book_id, book_shelf_ids):
    """What the book page needs to show the Kobo card, or None when Kobo sync is off for this user.

    book_shelf_ids: ids of the shelves the book is on.
    """
    from . import config
    if not config.config_kobo_sync or not user.is_authenticated or user.is_anonymous:
        return None
    try:
        has_token = user.remote_auth_token.filter(ub.RemoteAuthToken.token_type == 1).first() is not None
        kobo_shelves = (ub.session.query(ub.Shelf)
                        .filter(ub.Shelf.user_id == int(user.id), ub.Shelf.kobo_sync == True)  # noqa: E712
                        .order_by(ub.Shelf.name).all())
        on_device = ub.session.query(ub.KoboSyncedBooks).filter(
            ub.KoboSyncedBooks.user_id == int(user.id), ub.KoboSyncedBooks.book_id == int(book_id)).first() is not None
    except Exception as e:
        log.debug("Could not load Kobo status for book %s: %s", book_id, e)
        return None
    shelf_ids = set(book_shelf_ids or [])
    return {
        "has_token": has_token,
        "only_shelves": bool(user.kobo_only_shelves_sync),
        "on_device": on_device,
        "kobo_shelves": kobo_shelves,
        "in_kobo_shelves": [shelf for shelf in kobo_shelves if shelf.id in shelf_ids],
    }
