# -*- coding: utf-8 -*-
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Your year in books: a reader's year, told in slides.

`summarize` is pure and works on plain values; `collect` gathers them from the databases for one
user and year. What it can use:

- finished and started books (read status, Kobo and KOReader included),
- reading time measured by the Kobo,
- activity timestamps: web reader opens, downloads, Kobo and KOReader syncs, highlights,
- highlights and notes,
- books added to the library.
"""

from collections import Counter
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, abort, redirect, url_for
from flask_babel import gettext as _

from . import calibre_db, db, logger, ub
from .cw_login import current_user
from .usermanagement import user_login_required

log = logger.create()

year_review = Blueprint('year_review', __name__)

# Reading styles, decided in this order.
VORACIOUS_BOOKS = 24
SERIES_SHARE = 0.4
DEVOTEE_SHARE = 0.4
EXPLORER_GENRES = 5


def _local(moment):
    """A stored UTC datetime as the server's local time (the container's TZ)."""
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone()


def _in_year(moment, year):
    local = _local(moment)
    return local is not None and local.year == year


def longest_streak(days):
    """Longest run of consecutive dates in an iterable of datetime.date."""
    ordered = sorted(set(days))
    best = run = 0
    previous = None
    for day in ordered:
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    return best


def time_of_day(hours):
    """'morning', 'afternoon', 'evening' or 'night' from a Counter of local hours, or None."""
    if not hours:
        return None
    buckets = Counter()
    for hour, count in hours.items():
        if 5 <= hour < 12:
            buckets["morning"] += count
        elif 12 <= hour < 18:
            buckets["afternoon"] += count
        elif 18 <= hour < 23:
            buckets["evening"] += count
        else:
            buckets["night"] += count
    return buckets.most_common(1)[0][0]


def reading_style(finished):
    """The reader's style for the year, from the finished books (dicts with authors, tags, series)."""
    count = len(finished)
    if not count:
        return None
    if count >= VORACIOUS_BOOKS:
        return "voracious"
    if count >= 3 and sum(1 for book in finished if book["series"]) / count >= SERIES_SHARE:
        return "saga"
    authors = Counter(author for book in finished for author in book["authors"][:1])
    if count >= 3 and authors and authors.most_common(1)[0][1] / count >= DEVOTEE_SHARE:
        return "devotee"
    if len({tag for book in finished for tag in book["tags"]}) >= EXPLORER_GENRES:
        return "explorer"
    return "savourer"


def pick_quote(highlights):
    """The highlight of the year: one with a note if possible, of a length that reads well on a card."""
    candidates = [h for h in highlights if h.get("text") and 40 <= len(h["text"]) <= 280]
    if not candidates:
        candidates = [h for h in highlights if h.get("text")]
    if not candidates:
        return None
    candidates.sort(key=lambda h: (not h.get("note"), abs(len(h["text"]) - 140)))
    return candidates[0]


def summarize(year, finished, started, minutes, activity, highlights, added):
    """Everything the slides need, as JSON-ready values.

    finished / started: lists of book dicts {id, title, authors, tags, series, when (datetime)}
    minutes: reading minutes measured by the Kobo; activity: list of datetimes;
    highlights: list of {text, note, book_id, book_title, authors}; added: books added to the library.
    """
    finished = sorted(finished, key=lambda book: book["when"])
    moments = [_local(moment) for moment in activity if _in_year(moment, year)]
    moments += [_local(book["when"]) for book in finished]
    days = {moment.date() for moment in moments}
    months = [0] * 12
    for day in days:
        months[day.month - 1] += 1
    hours = Counter(moment.hour for moment in moments)
    weekdays = Counter(moment.weekday() for moment in moments)

    def tops(values, limit):
        return [{"name": name, "count": count} for name, count in Counter(values).most_common(limit)]

    def card(book):
        return {"id": book["id"], "title": book["title"], "authors": book["authors"][:2]}

    quote = pick_quote(highlights)
    return {
        "year": year,
        "finished": len(finished),
        "started": len(started),
        "minutes": int(minutes or 0),
        "books": [card(book) for book in finished[-30:]],
        "first": card(finished[0]) if finished else None,
        "last": card(finished[-1]) if len(finished) > 1 else None,
        "authors": tops([author for book in finished for author in book["authors"][:1]], 3),
        "genres": tops([tag for book in finished for tag in book["tags"]], 5),
        "series": len({series for book in finished for series in book["series"]}),
        "active_days": len(days),
        "days": sorted(day.isoformat() for day in days if day.year == year),
        "streak": longest_streak(days),
        "months": months,
        "busiest_month": months.index(max(months)) + 1 if any(months) else None,
        "time_of_day": time_of_day(hours),
        "weekday": weekdays.most_common(1)[0][0] if weekdays else None,
        "highlights": len(highlights),
        "quote": quote,
        "added": int(added or 0),
        "style": reading_style(finished),
    }


def has_story(summary):
    return bool(summary["finished"] or summary["started"] or summary["active_days"] or summary["highlights"])


# ---------- Gathering ----------

def _activity_from_cwa_db(user_id, year):
    try:
        from scripts.cwa_db import CWA_DB
        rows = CWA_DB().cur.execute(
            "SELECT timestamp FROM cwa_user_activity WHERE user_id = ? AND event_type IN "
            "('READ', 'DOWNLOAD', 'KOBO_SYNC', 'EMAIL') AND timestamp >= ? AND timestamp < ?",
            (int(user_id), "{}-12-31".format(year - 1), "{}-01-02".format(year + 1))).fetchall()
    except Exception as e:
        log.debug("Could not read activity: %s", e)
        return []
    moments = []
    for (value,) in rows:
        try:
            moments.append(datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc))
        except ValueError:
            continue
    return moments


def collect(user, year):
    """Gather one user's year from app.db, cwa.db and the library, then summarize it."""
    from .progress_syncing.models import KOSyncProgress
    user_id = int(user.id)
    read_rows = ub.session.query(ub.ReadBook).filter(ub.ReadBook.user_id == user_id).all()
    finished_when = {row.book_id: row.last_modified for row in read_rows
                     if row.read_status == ub.ReadBook.STATUS_FINISHED and _in_year(row.last_modified, year)}
    started_ids = {row.book_id for row in read_rows if _in_year(row.last_time_started_reading, year)}

    book_ids = set(finished_when) | started_ids
    books = {}
    if book_ids:
        for book in calibre_db.session.query(db.Books).filter(db.Books.id.in_(list(book_ids))) \
                .filter(calibre_db.common_filters()).all():
            books[book.id] = {"id": book.id, "title": book.title,
                              "authors": [author.name for author in book.authors],
                              "tags": [tag.name for tag in book.tags],
                              "series": [series.name for series in book.series]}
    finished = [dict(books[book_id], when=when) for book_id, when in finished_when.items() if book_id in books]
    started = [books[book_id] for book_id in started_ids if book_id in books]

    minutes = 0
    activity = _activity_from_cwa_db(user_id, year)
    for state in ub.session.query(ub.KoboReadingState).filter(ub.KoboReadingState.user_id == user_id).all():
        if _in_year(state.last_modified, year) and state.statistics and state.statistics.spent_reading_minutes:
            minutes += state.statistics.spent_reading_minutes
    activity += [row.timestamp for row in ub.session.query(KOSyncProgress.timestamp)
                 .filter(KOSyncProgress.user_id == user_id).all()]

    highlights = []
    for row in ub.session.query(ub.ReaderAnnotation).filter(ub.ReaderAnnotation.user_id == user_id).all():
        moment = row.created or row.updated
        if not _in_year(moment, year):
            continue
        activity.append(moment)
        highlights.append({"text": row.text, "note": row.note, "book_id": row.book_id})
    quote_books = {h["book_id"] for h in highlights}
    if quote_books:
        titles = {book.id: (book.title, [a.name for a in book.authors]) for book in
                  calibre_db.session.query(db.Books).filter(db.Books.id.in_(list(quote_books)))
                  .filter(calibre_db.common_filters()).all()}
        highlights = [dict(h, book_title=titles[h["book_id"]][0], authors=titles[h["book_id"]][1][:2])
                      for h in highlights if h["book_id"] in titles]

    start = datetime(year, 1, 1)
    added = calibre_db.session.query(db.Books.id).filter(db.Books.timestamp >= start,
                                                        db.Books.timestamp < datetime(year + 1, 1, 1)).count()
    return summarize(year, finished, started, minutes, activity, highlights, added)


def available_years(user):
    """Years with reading activity for the user, newest first (always includes the current year)."""
    years = {date.today().year}
    for row in ub.session.query(ub.ReadBook.last_modified, ub.ReadBook.last_time_started_reading) \
            .filter(ub.ReadBook.user_id == int(user.id)).all():
        for moment in row:
            local = _local(moment)
            if local:
                years.add(local.year)
    return sorted(years, reverse=True)


@year_review.route("/year")
@user_login_required
def current_year():
    return redirect(url_for("year_review.show", year=date.today().year))


@year_review.route("/year/<int:year>")
@user_login_required
def show(year):
    from flask import render_template
    if not 1970 <= year <= date.today().year + 1:
        abort(404)
    from flask_babel import format_date
    summary = collect(current_user, year)
    years = available_years(current_user)
    months = [format_date(date(year, month, 1), "LLL") for month in range(1, 13)]
    busiest = format_date(date(year, summary["busiest_month"], 1), "LLLL") if summary["busiest_month"] else None
    # 2024-01-01 was a Monday, so weekday n is 2024-01-(n+1).
    weekday = format_date(date(2024, 1, summary["weekday"] + 1), "EEEE") if summary["weekday"] is not None else None
    return render_template("year.html", summary=summary, years=years, has_story=has_story(summary),
                           user_name=current_user.name, months=months, busiest_month=busiest, weekday=weekday,
                           hours=round(summary["minutes"] / 60), title=_("Your %(year)s in books", year=year))
