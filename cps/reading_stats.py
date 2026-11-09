# -*- coding: utf-8 -*-
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Reading statistics from KOReader, shared between devices and shown on their own page.

KOReader keeps its reading statistics in `statistics.sqlite3` and can sync that file through a
WebDAV folder: it downloads the copy on the server, merges it into its own on the device and uploads
the result. Scriptorium is that folder (`/kosync/webdav/`, with the same sign-in as KOReader sync),
so every device ends up with the statistics of all of them, and the page reads the latest copy.

Each user has one file in `<config>/reading_stats/`. Nothing is written to the app's databases.
The built-in reader keeps its own pages in a second file with the same layout (`<id>-web.sqlite3`),
written only by the server, and the page reads both.
The uploaded file comes from a device, so it is only ever opened read-only and immutable, with
SQLite's untrusted-schema protections on, and only its two plain tables are read.
"""

import os
import sqlite3
import tempfile
import threading
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, timedelta
from email.utils import formatdate
from xml.sax.saxutils import escape

from flask import Blueprint, Response, request, send_file, url_for
from flask_babel import format_date, gettext as _, ngettext

from . import calibre_db, constants, csrf, logger
from .cw_login import current_user
from .render_template import render_title_template
from .usermanagement import user_login_required

log = logger.create()

reading_stats = Blueprint('reading_stats', __name__)

FILE_NAME = "statistics.sqlite3"
MAX_BYTES = 64 * 1024 * 1024
SQLITE_HEADER = b"SQLite format 3\x00"
SESSION_GAP = 5 * 60          # seconds between page turns that still count as one sitting
HEATMAP_WEEKS = 53
LEVELS = (15 * 60, 30 * 60, 60 * 60)  # heatmap steps: under 15 min, 30 min, an hour, more

_write_lock = threading.Lock()
_cache = {}


# ---------- Storage ----------

def stats_dir():
    return os.path.join(constants.CONFIG_DIR, "reading_stats")


def stats_path(user_id):
    return os.path.join(stats_dir(), "{}.sqlite3".format(int(user_id)))


def web_stats_path(user_id):
    """Pages read in the built-in reader, in KOReader's layout."""
    return os.path.join(stats_dir(), "{}-web.sqlite3".format(int(user_id)))


def etag_for(path):
    try:
        info = os.stat(path)
    except OSError:
        return None
    return '"{:x}-{:x}"'.format(info.st_size, info.st_mtime_ns)


def _clean_etag(value):
    value = (value or "").strip()
    if value[:2] in ("W/", "w/"):
        value = value[2:]
    return value


def looks_like_statistics(path):
    """True when the file is a KOReader statistics database."""
    try:
        with closing(_open(path)) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if not {"book", "page_stat_data"} <= tables:
                return False
            conn.execute("SELECT id, title, authors, md5, pages FROM book LIMIT 1").fetchall()
            conn.execute("SELECT id_book, page, start_time, duration, total_pages FROM page_stat_data LIMIT 1").fetchall()
        return True
    except sqlite3.Error:
        return False


def _open(path, immutable=True):
    conn = sqlite3.connect("file:{}?mode=ro{}".format(path, "&immutable=1" if immutable else ""), uri=True)
    try:
        conn.execute("PRAGMA trusted_schema = OFF")
        conn.execute("PRAGMA cell_size_check = ON")
    except sqlite3.Error:
        pass
    return conn


def store_upload(user_id, stream, length, if_match=None):
    """Save an uploaded statistics file. Returns an HTTP status: 201/204, 412, 413 or 415."""
    if length is not None and length > MAX_BYTES:
        return 413
    os.makedirs(stats_dir(), exist_ok=True)
    handle, temp_path = tempfile.mkstemp(prefix=".upload-", dir=stats_dir())
    try:
        size = 0
        with os.fdopen(handle, "wb") as out:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_BYTES:
                    return 413
                out.write(chunk)
        with open(temp_path, "rb") as check:
            if check.read(len(SQLITE_HEADER)) != SQLITE_HEADER:
                return 415
        if not looks_like_statistics(temp_path):
            return 415
        path = stats_path(user_id)
        with _write_lock:
            current = etag_for(path)
            if if_match and _clean_etag(if_match) not in ("*", current):
                return 412
            if current:
                os.replace(path, path + ".prev")
            os.replace(temp_path, path)
            temp_path = None
        _cache.clear()
        return 204 if current else 201
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


# ---------- WebDAV, for KOReader's statistics sync ----------

def _webdav_user():
    from .progress_syncing.protocols.kosync import _require_kosync_enabled, authenticate_user
    if _require_kosync_enabled():
        return None, Response("KOReader sync is disabled", 503)
    user = authenticate_user()
    if not user:
        return None, Response("Unauthorized", 401, {"WWW-Authenticate": 'Basic realm="Scriptorium"'})
    return user, None


def _propfind_entry(href, path=None):
    if path is None:
        props = "<d:resourcetype><d:collection/></d:resourcetype>"
    else:
        info = os.stat(path)
        props = ("<d:resourcetype/><d:getcontentlength>{}</d:getcontentlength>"
                 "<d:getlastmodified>{}</d:getlastmodified><d:getetag>{}</d:getetag>"
                 "<d:getcontenttype>application/vnd.sqlite3</d:getcontenttype>").format(
            info.st_size, formatdate(info.st_mtime, usegmt=True), escape(etag_for(path)))
    return ("<d:response><d:href>{}</d:href><d:propstat><d:prop>{}</d:prop>"
            "<d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>").format(escape(href), props)


@csrf.exempt
@reading_stats.route("/kosync/webdav/", methods=["OPTIONS", "PROPFIND"], strict_slashes=False)
def webdav_folder():
    if request.method == "OPTIONS":
        return Response("", 200, {"DAV": "1", "Allow": "OPTIONS, PROPFIND, GET, HEAD, PUT"})
    user, error = _webdav_user()
    if error:
        return error
    folder = url_for("reading_stats.webdav_folder")
    entries = [_propfind_entry(folder)]
    path = stats_path(user.id)
    if request.headers.get("Depth", "1") != "0" and os.path.isfile(path):
        entries.append(_propfind_entry(folder + FILE_NAME, path))
    body = '<?xml version="1.0" encoding="utf-8"?><d:multistatus xmlns:d="DAV:">{}</d:multistatus>'.format(
        "".join(entries))
    return Response(body, 207, content_type="application/xml; charset=utf-8")


@csrf.exempt
@reading_stats.route("/kosync/webdav/<name>", methods=["OPTIONS", "PROPFIND", "GET", "HEAD", "PUT"])
def webdav_file(name):
    if request.method == "OPTIONS":
        return Response("", 200, {"DAV": "1", "Allow": "OPTIONS, PROPFIND, GET, HEAD, PUT"})
    user, error = _webdav_user()
    if error:
        return error
    if name != FILE_NAME:
        return Response("Only {} is kept here".format(FILE_NAME), 404 if request.method != "PUT" else 403)
    path = stats_path(user.id)
    if request.method == "PUT":
        status = store_upload(user.id, request.stream, request.content_length, request.headers.get("If-Match"))
        if status in (201, 204):
            log.info("Stored KOReader reading statistics for user %s", user.id)
        headers = {"ETag": etag_for(path)} if status in (201, 204) else {}
        return Response("", status, headers)
    if not os.path.isfile(path):
        return Response("", 404)
    if request.method == "PROPFIND":
        folder = url_for("reading_stats.webdav_folder")
        body = '<?xml version="1.0" encoding="utf-8"?><d:multistatus xmlns:d="DAV:">{}</d:multistatus>'.format(
            _propfind_entry(folder + FILE_NAME, path))
        return Response(body, 207, content_type="application/xml; charset=utf-8")
    headers = {"ETag": etag_for(path), "Cache-Control": "no-store"}
    if request.method == "HEAD":
        headers["Content-Length"] = str(os.path.getsize(path))
        return Response("", 200, headers, content_type="application/vnd.sqlite3")
    response = send_file(path, mimetype="application/vnd.sqlite3", conditional=False, etag=False, max_age=0)
    response.headers.update(headers)
    return response


# ---------- Reading the statistics ----------

def load(path, immutable=True):
    """(books, rows) from a statistics file: books by id, rows as (id_book, page, start, duration, total_pages)."""
    with closing(_open(path, immutable)) as conn:
        books = {}
        for book_id, title, authors, md5, pages in conn.execute(
                "SELECT id, title, authors, md5, pages FROM book"):
            books[book_id] = {"title": title or "", "authors": authors or "", "md5": md5, "pages": pages or 0}
        rows = conn.execute(
            "SELECT id_book, page, start_time, duration, total_pages FROM page_stat_data "
            "WHERE duration > 0 AND start_time > 0 ORDER BY start_time").fetchall()
    return books, rows


WEB_BOOK_OFFSET = 1_000_000  # keeps the built-in reader's books apart from KOReader's
MAX_PAGE_SECONDS = 120         # a page left open longer counts as two minutes, as in KOReader
MIN_PAGE_SECONDS = 3           # quicker page turns are skimming, not reading

_WEB_SCHEMA = """
CREATE TABLE IF NOT EXISTS book (id integer PRIMARY KEY autoincrement, title text, authors text, notes integer,
    last_open integer, highlights integer, pages integer, series text, language text, md5 text,
    total_read_time integer, total_read_pages integer);
CREATE UNIQUE INDEX IF NOT EXISTS book_title_authors_md5 ON book(title, authors, md5);
CREATE TABLE IF NOT EXISTS page_stat_data (id_book integer, page integer NOT NULL DEFAULT 0,
    start_time integer NOT NULL DEFAULT 0, duration integer NOT NULL DEFAULT 0, total_pages integer NOT NULL DEFAULT 0,
    UNIQUE (id_book, page, start_time), FOREIGN KEY(id_book) REFERENCES book(id));
CREATE INDEX IF NOT EXISTS page_stat_data_start_time ON page_stat_data(start_time);
"""


def store_web_pages(user_id, book, md5, pages, now=None):
    """Add pages read in the built-in reader. pages: [(page, start_time, duration, total_pages)]. Returns the count."""
    now = int(now or datetime.now().timestamp())
    rows = []
    for item in pages[:500]:
        try:
            page, start, duration, total = (int(value) for value in item)
        except (TypeError, ValueError):
            continue
        if page < 1 or total < 1 or not now - 7 * 86400 <= start <= now + 60 or duration < MIN_PAGE_SECONDS:
            continue
        rows.append((min(page, total), start, min(duration, MAX_PAGE_SECONDS), total))
    if not rows:
        return 0
    os.makedirs(stats_dir(), exist_ok=True)
    path = web_stats_path(user_id)
    title = book.title or _("Unknown book")
    authors = "\n".join(author.name for author in book.authors)
    key = md5 or "scriptorium-{}".format(book.id)
    with _write_lock, closing(sqlite3.connect(path)) as conn:
        conn.executescript(_WEB_SCHEMA)
        conn.execute("INSERT OR IGNORE INTO book (title, authors, md5, pages, notes, highlights, last_open, "
                     "total_read_time, total_read_pages) VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0)",
                     (title, authors, key, rows[-1][3]))
        book_id = conn.execute("SELECT id FROM book WHERE title = ? AND authors = ? AND md5 = ?",
                               (title, authors, key)).fetchone()[0]
        conn.executemany("INSERT OR IGNORE INTO page_stat_data VALUES (?, ?, ?, ?, ?)",
                         [(book_id, page, start, duration, total) for page, start, duration, total in rows])
        conn.execute("UPDATE book SET last_open = ?, pages = ? WHERE id = ?", (now, rows[-1][3], book_id))
        conn.commit()
    _cache.clear()
    return len(rows)


def load_all(user_id):
    """KOReader's statistics and the built-in reader's, as one (books, rows). A book read in both,
    recognised by its file checksum, is one book."""
    books, rows = {}, []
    if os.path.isfile(stats_path(user_id)):
        books, rows = load(stats_path(user_id))
    web = web_stats_path(user_id)
    if os.path.isfile(web):
        web_books, web_rows = load(web, immutable=False)
        by_md5 = {info["md5"]: book_id for book_id, info in books.items() if info["md5"]}
        mapping = {}
        for web_id, info in web_books.items():
            if info["md5"] in by_md5:
                mapping[web_id] = by_md5[info["md5"]]
            else:
                mapping[web_id] = WEB_BOOK_OFFSET + web_id
                books[mapping[web_id]] = info
        rows = sorted(list(rows) + [(mapping[row[0]],) + tuple(row[1:]) for row in web_rows if row[0] in mapping],
                      key=lambda row: row[2])
    return books, rows


def _streaks(days, today):
    """(current, best) runs of consecutive reading days. Today not read yet keeps yesterday's run."""
    ordered = sorted(days)
    best = run = 0
    previous = None
    for day in ordered:
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    current = 0
    day = today if today in days else today - timedelta(days=1)
    while day in days:
        current += 1
        day -= timedelta(days=1)
    return current, best


def _level(seconds):
    if seconds <= 0:
        return 0
    for index, limit in enumerate(LEVELS, 1):
        if seconds < limit:
            return index
    return len(LEVELS) + 1


def summarize(books, rows, today=None):
    """Everything the page shows, from plain values. Times are in the server's time zone."""
    today = today or date.today()
    per_day = defaultdict(int)
    per_hour = [0] * 24
    per_weekday = [0] * 7
    per_book = {}
    sessions = []
    session = None
    pages_seen = set()

    for book_id, page, start, duration, total_pages in rows:
        moment = datetime.fromtimestamp(start)
        day = moment.date()
        per_day[day] += duration
        per_hour[moment.hour] += duration
        per_weekday[moment.weekday()] += duration
        pages_seen.add((book_id, page))
        entry = per_book.setdefault(book_id, {"seconds": 0, "pages": set(), "turns": 0, "first": start,
                                              "last": start, "total_pages": 0})
        entry["seconds"] += duration
        entry["pages"].add(page)
        entry["turns"] += 1
        entry["last"] = max(entry["last"], start + duration)
        if total_pages:
            entry["total_pages"] = total_pages
        if session and start - session["end"] <= SESSION_GAP:
            session["end"] = max(session["end"], start + duration)
            session["seconds"] += duration
        else:
            session = {"start": start, "end": start + duration, "seconds": duration}
            sessions.append(session)

    total_seconds = sum(per_day.values())
    turns = len(rows)
    reading_days = set(day for day, seconds in per_day.items() if seconds > 0)
    current_streak, best_streak = _streaks(reading_days, today)
    week_start = today - timedelta(days=today.weekday())

    def between(first, last=today):
        return sum(seconds for day, seconds in per_day.items() if first <= day <= last)

    # Calendar: whole weeks, Monday first, ending with the current week.
    start = week_start - timedelta(weeks=HEATMAP_WEEKS - 1)
    weeks = []
    for week in range(HEATMAP_WEEKS):
        days = []
        for offset in range(7):
            day = start + timedelta(days=week * 7 + offset)
            seconds = per_day.get(day, 0)
            days.append({"date": day, "seconds": seconds, "level": _level(seconds), "future": day > today})
        weeks.append(days)

    last_30 = [{"date": today - timedelta(days=29 - i), "seconds": per_day.get(today - timedelta(days=29 - i), 0)}
               for i in range(30)]

    months = []
    year, month = today.year, today.month
    for _i in range(12):
        first = date(year, month, 1)
        following = date(year + (month == 12), month % 12 + 1, 1)
        months.insert(0, {"date": first, "seconds": between(first, following - timedelta(days=1))})
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)

    seconds_per_turn = total_seconds / turns if turns else 0
    book_list = []
    for book_id, entry in per_book.items():
        info = books.get(book_id, {})
        total_pages = entry["total_pages"] or info.get("pages") or 0
        read = len(entry["pages"])
        progress = min(1.0, read / total_pages) if total_pages else None
        pace = entry["seconds"] / entry["turns"] if entry["turns"] else seconds_per_turn
        left = None
        if progress is not None and progress < 0.99 and entry["turns"] >= 5:
            left = max(0, total_pages - read) * pace
        book_list.append({
            "id": book_id, "title": info.get("title") or _("Unknown book"),
            "authors": ", ".join(name for name in (info.get("authors") or "").split("\n") if name),
            "md5": info.get("md5"), "seconds": entry["seconds"], "pages": read, "total_pages": total_pages,
            "progress": progress, "left": left, "first": datetime.fromtimestamp(entry["first"]),
            "last": datetime.fromtimestamp(entry["last"]),
        })
    book_list.sort(key=lambda item: item["last"], reverse=True)

    return {
        "total_seconds": total_seconds,
        "pages": len(pages_seen),
        "books": len(per_book),
        "reading_days": len(reading_days),
        "today": per_day.get(today, 0),
        "week": between(week_start),
        "month": between(today.replace(day=1)),
        "year": between(today.replace(month=1, day=1)),
        "average_day": total_seconds / len(reading_days) if reading_days else 0,
        "current_streak": current_streak,
        "best_streak": best_streak,
        "first_day": min(reading_days) if reading_days else None,
        "weeks": weeks,
        "last_30": last_30,
        "months": months,
        "hours": per_hour,
        "weekdays": per_weekday,
        "sessions": len(sessions),
        "average_session": sum(s["seconds"] for s in sessions) / len(sessions) if sessions else 0,
        "longest_session": max((s["seconds"] for s in sessions), default=0),
        "seconds_per_page": seconds_per_turn,
        "pages_per_hour": 3600 / seconds_per_turn if seconds_per_turn else 0,
        "book_list": book_list,
    }


def for_user(user_id, today=None):
    """The summary for a user, or None before any reading was measured (KOReader or the built-in reader)."""
    paths = [path for path in (stats_path(user_id), web_stats_path(user_id)) if os.path.isfile(path)]
    if not paths:
        return None
    key = (tuple(etag_for(path) for path in paths), today or date.today())
    cached = _cache.get(user_id)
    if cached and cached[0] == key:
        return cached[1]
    try:
        summary = summarize(*load_all(user_id), today=today)
    except sqlite3.Error as e:
        log.warning("Could not read the reading statistics of user %s: %s", user_id, e)
        return None
    summary["synced"] = datetime.fromtimestamp(max(os.path.getmtime(path) for path in paths))
    _cache[user_id] = (key, summary)
    return summary


# ---------- The page ----------

@reading_stats.app_template_filter("reading_time")
def reading_time(seconds):
    """'2 h 05 min', '45 min', '< 1 min'."""
    minutes = int(round((seconds or 0) / 60))
    if minutes < 1:
        return _("< 1 min")
    hours, minutes = divmod(minutes, 60)
    if not hours:
        return _("%(minutes)s min", minutes=minutes)
    return _("%(hours)s h %(minutes)02d min", hours=hours, minutes=minutes)


def library_books(book_list):
    """Library books for the statistics' books ({id, md5}), matched by file checksum, that the user may see."""
    from .progress_syncing.protocols.kosync import get_book_by_checksum
    from . import db
    ids = {}
    for item in book_list[:200]:
        if item["md5"]:
            book_id = get_book_by_checksum(item["md5"])[0]
            if book_id:
                ids[item["id"]] = book_id
    if not ids:
        return {}
    visible = {b.id: b for b in calibre_db.session.query(db.Books)
               .filter(db.Books.id.in_(set(ids.values()))).filter(calibre_db.common_filters()).all()}
    return {stats_id: visible[book_id] for stats_id, book_id in ids.items() if book_id in visible}


def _bars(values, height=120):
    """Bar heights in px for a small chart, and the largest value."""
    top = max(values) if values and max(values) > 0 else 0
    return [round(value / top * height) if top else 0 for value in values], top


@reading_stats.route("/reading-stats")
@user_login_required
def page():
    from .progress_syncing.settings import is_koreader_sync_enabled
    summary = for_user(current_user.id)
    context = {"summary": summary, "kosync_enabled": is_koreader_sync_enabled(),
               "server_url": request.host_url.rstrip("/") + request.script_root}
    if summary:
        library = library_books(summary["book_list"])
        day_heights, day_top = _bars([d["seconds"] for d in summary["last_30"]])
        month_heights, _top = _bars([m["seconds"] for m in summary["months"]])
        hour_heights, _top = _bars(summary["hours"], 80)
        weekday_heights, _top = _bars(summary["weekdays"], 80)
        average = sum(d["seconds"] for d in summary["last_30"]) / 30
        context.update(
            library=library,
            day_heights=day_heights,
            day_average=round(average / day_top * 120) if day_top else 0,
            average_30=average,
            month_heights=month_heights,
            month_labels=[format_date(m["date"], "LLL") for m in summary["months"]],
            hour_heights=hour_heights,
            weekday_heights=weekday_heights,
            weekday_labels=[format_date(date(2024, 1, n + 1), "EEE") for n in range(7)],
            month_marks=_month_marks(summary["weeks"]),
            busiest_hour=summary["hours"].index(max(summary["hours"])) if any(summary["hours"]) else None,
            busiest_weekday=format_date(date(2024, 1, summary["weekdays"].index(max(summary["weekdays"])) + 1), "EEEE")
            if any(summary["weekdays"]) else None,
            streak_text=ngettext("%(num)s day", "%(num)s days", summary["current_streak"]),
            best_text=ngettext("%(num)s day", "%(num)s days", summary["best_streak"]),
        )
    return render_title_template("reading_stats.html", page="reading_stats", title=_("Reading statistics"), **context)


def _month_marks(weeks):
    """Labels above the calendar: (week index, short month) where a month starts."""
    marks = []
    previous = None
    for index, week in enumerate(weeks):
        month = week[0]["date"].month
        if month != previous:
            if previous is not None or week[0]["date"].day <= 7:
                marks.append((index, format_date(week[0]["date"], "LLL")))
            previous = month
    return marks
