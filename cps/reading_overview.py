# -*- coding: utf-8 -*-
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Reading-state summaries for the library home page and the Kobo settings page."""

from datetime import datetime, timezone

from flask_babel import format_timedelta
from sqlalchemy import desc, func

from . import calibre_db, db, logger, ub
from .progress_syncing.models import KOSyncProgress

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
    from . import devices
    if not user.is_authenticated or user.is_anonymous or not devices.shows(user, "kobo"):
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


def kobo_overview(user):
    """Everything the Kobo section of a profile needs, or None when Kobo sync is disabled."""
    from flask import request, url_for
    from . import config
    if not config.config_kobo_sync or user is None or user.is_anonymous:
        return None
    token = None
    try:
        token = (ub.session.query(ub.RemoteAuthToken)
                 .filter(ub.RemoteAuthToken.user_id == int(user.id), ub.RemoteAuthToken.token_type == 1)
                 .first())
    except Exception as e:
        log.debug("Could not load Kobo token: %s", e)
    host = request.host.rsplit(":", 1)[0] if ":" in request.host and not request.host.endswith("]") else request.host
    local_host = host.startswith("127.") or host.lower() == "localhost" or host in ("[::1]", "::1")
    books_on_device = 0
    try:
        books_on_device = ub.session.query(ub.KoboSyncedBooks).filter(ub.KoboSyncedBooks.user_id == int(user.id)).count()
    except Exception as e:
        log.debug("Could not count Kobo synced books: %s", e)
    kobo_shelves = []
    try:
        kobo_shelves = (ub.session.query(ub.Shelf)
                        .filter(ub.Shelf.user_id == int(user.id)).order_by(ub.Shelf.name).all())
    except Exception as e:
        log.debug("Could not load shelves: %s", e)
    return {
        "token": token.auth_token if token else None,
        "endpoint": url_for("kobo.TopLevelEndpoint", auth_token=token.auth_token, _external=True) if token else None,
        "local_host": local_host,
        "proxy": bool(config.config_kobo_proxy),
        "last_sync": humanize_since(get_kobo_last_sync(user.id)),
        "books_on_device": books_on_device,
        "only_shelves": bool(user.kobo_only_shelves_sync),
        "shelves": kobo_shelves,
    }


def _as_utc(moment):
    if moment is None:
        return None
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _koreader_records(user_id):
    return ub.session.query(KOSyncProgress).filter(KOSyncProgress.user_id == int(user_id))


def koreader_overview(user):
    """What the KOReader section of a profile needs: last sync, device name and books synced."""
    overview = {"last_sync": None, "device": None, "books": 0}
    if user is None or getattr(user, "is_anonymous", True):
        return overview
    try:
        latest = _koreader_records(user.id).order_by(desc(KOSyncProgress.timestamp)).first()
        overview["books"] = (ub.session.query(func.count(KOSyncProgress.id))
                             .filter(KOSyncProgress.user_id == int(user.id)).scalar() or 0)
        if latest is not None:
            overview["last_sync"] = humanize_since(_as_utc(latest.timestamp))
            overview["device"] = latest.device
    except Exception as e:
        log.debug("Could not read KOReader progress: %s", e)
    return overview


def get_book_progress(user, book_id):
    """The latest reading progress for a book and where it came from, or None.

    Returns {percent (0-100 float), source ('kobo' or 'koreader'), device (str or None), when (datetime)}.
    Otherwise the newer of the Kobo bookmark and the KOReader record wins.
    """
    if user is None or getattr(user, "is_anonymous", True):
        return None
    candidates = []
    try:
        state = (ub.session.query(ub.KoboReadingState)
                 .filter(ub.KoboReadingState.user_id == int(user.id), ub.KoboReadingState.book_id == int(book_id))
                 .first())
        if state is not None and state.current_bookmark is not None \
                and state.current_bookmark.progress_percent is not None:
            bookmark = state.current_bookmark
            candidates.append({"percent": float(bookmark.progress_percent), "source": "kobo", "device": None,
                               "when": _as_utc(bookmark.last_modified or state.last_modified)})
        record = (_koreader_records(user.id)
                  .filter(KOSyncProgress.document == str(int(book_id)))
                  .order_by(desc(KOSyncProgress.timestamp)).first())
        if record is not None:
            candidates.append({"percent": float(record.percentage), "source": "koreader",
                               "device": record.device, "when": _as_utc(record.timestamp)})
    except Exception as e:
        log.debug("Could not load reading progress for book %s: %s", book_id, e)
        return None
    if not candidates:
        return None
    if len(candidates) == 2 and abs(candidates[0]["percent"] - candidates[1]["percent"]) < 0.01:
        # KOReader also writes its percentage into the Kobo bookmark, a moment after its own record:
        # the same value in both places is KOReader's.
        return candidates[1]
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    return max(candidates, key=lambda c: c["when"] or oldest)


def get_koreader_last_sync(user_id):
    """UTC datetime of the user's last KOReader sync, or None."""
    try:
        latest = (ub.session.query(func.max(KOSyncProgress.timestamp))
                  .filter(KOSyncProgress.user_id == int(user_id)).scalar())
    except Exception as e:
        log.debug("Could not read KOReader sync time: %s", e)
        return None
    if isinstance(latest, str):
        try:
            latest = datetime.fromisoformat(latest[:26])
        except ValueError:
            return None
    return _as_utc(latest)
