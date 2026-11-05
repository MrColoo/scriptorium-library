# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""KOReader's reading statistics are kept per user through WebDAV and summarised correctly."""

import io
import sqlite3
import time
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from flask import Flask

from cps import reading_stats

pytestmark = pytest.mark.unit

TODAY = date(2026, 11, 5)  # a Thursday


def _at(day, hour=21, minute=0):
    return int(time.mktime(datetime(day.year, day.month, day.day, hour, minute).timetuple()))


def _statistics_file(path, rows, books=((1, "Dune", "Frank Herbert", "abc", 400),)):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE book (id integer PRIMARY KEY autoincrement, title text, authors text, notes integer,
            last_open integer, highlights integer, pages integer, series text, language text, md5 text,
            total_read_time integer, total_read_pages integer);
        CREATE TABLE page_stat_data (id_book integer, page integer NOT NULL DEFAULT 0,
            start_time integer NOT NULL DEFAULT 0, duration integer NOT NULL DEFAULT 0,
            total_pages integer NOT NULL DEFAULT 0, UNIQUE (id_book, page, start_time));
    """)
    for book_id, title, authors, md5, pages in books:
        conn.execute("INSERT INTO book (id, title, authors, md5, pages) VALUES (?, ?, ?, ?, ?)",
                     (book_id, title, authors, md5, pages))
    conn.executemany("INSERT INTO page_stat_data VALUES (?, ?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(reading_stats.constants, "CONFIG_DIR", str(tmp_path))
    reading_stats._cache.clear()
    return tmp_path


class TestSummary:
    def test_totals_and_today(self):
        rows = [(1, page, _at(TODAY, 21, page), 60, 400) for page in range(1, 11)]
        rows += [(1, 11, _at(TODAY - timedelta(days=1)), 120, 400)]
        s = reading_stats.summarize({1: {"title": "Dune", "authors": "", "md5": "abc", "pages": 400}}, rows, today=TODAY)
        assert s["today"] == 600
        assert s["week"] == 720           # Monday 2 November to today
        assert s["total_seconds"] == 720
        assert s["pages"] == 11
        assert s["books"] == 1
        assert s["hours"][21] == 720
        assert s["weekdays"][3] == 600    # Thursday

    def test_streaks(self):
        days = [TODAY - timedelta(days=n) for n in (1, 2, 3, 10, 11, 12, 13, 14)]
        rows = [(1, i, _at(day), 60, 400) for i, day in enumerate(days)]
        s = reading_stats.summarize({}, rows, today=TODAY)
        assert s["current_streak"] == 3   # not read today yet, so yesterday's run still counts
        assert s["best_streak"] == 5
        s = reading_stats.summarize({}, rows, today=TODAY + timedelta(days=2))
        assert s["current_streak"] == 0

    def test_sessions_and_pace(self):
        start = _at(TODAY, 8)
        rows = [(1, 1, start, 60, 100), (1, 2, start + 70, 60, 100),       # one sitting
                (1, 3, start + 3600, 60, 100)]                              # an hour later: another
        s = reading_stats.summarize({}, rows, today=TODAY)
        assert s["sessions"] == 2
        assert s["longest_session"] == 120
        assert s["seconds_per_page"] == 60
        assert s["pages_per_hour"] == 60

    def test_books_progress_and_time_left(self):
        rows = [(1, page, _at(TODAY, 20, page), 30, 100) for page in range(1, 41)]
        s = reading_stats.summarize({1: {"title": "Dune", "authors": "Frank Herbert", "md5": "abc", "pages": 100}},
                                    rows, today=TODAY)
        book = s["book_list"][0]
        assert (book["title"], book["pages"], book["total_pages"]) == ("Dune", 40, 100)
        assert book["progress"] == pytest.approx(0.4)
        assert book["left"] == 60 * 30

    def test_calendar_levels_and_shape(self):
        rows = [(1, 1, _at(TODAY), 10 * 60, 100), (1, 2, _at(TODAY - timedelta(days=1)), 90 * 60, 100)]
        s = reading_stats.summarize({}, rows, today=TODAY)
        assert len(s["weeks"]) == reading_stats.HEATMAP_WEEKS and all(len(w) == 7 for w in s["weeks"])
        last_week = s["weeks"][-1]
        assert last_week[0]["date"].weekday() == 0
        assert last_week[3]["date"] == TODAY and last_week[3]["level"] == 1
        assert last_week[2]["level"] == 4
        assert last_week[4]["future"]
        assert len(s["last_30"]) == 30 and s["last_30"][-1]["date"] == TODAY
        assert len(s["months"]) == 12 and s["months"][-1]["date"] == date(2026, 11, 1)

    def test_empty(self):
        s = reading_stats.summarize({}, [], today=TODAY)
        assert s["total_seconds"] == 0 and s["current_streak"] == 0 and s["book_list"] == []

    def test_reading_from_a_file(self, config_dir):
        path = _statistics_file(str(config_dir / "s.sqlite3"), [(1, 1, _at(TODAY), 300, 400), (1, 2, 0, 50, 400)])
        books, rows = reading_stats.load(path)
        assert books[1]["md5"] == "abc"
        assert len(rows) == 1  # rows without a start time are ignored


class TestStorage:
    def test_upload_replaces_and_keeps_the_previous_copy(self, config_dir, tmp_path):
        data = open(_statistics_file(str(tmp_path / "a.sqlite3"), [(1, 1, _at(TODAY), 60, 400)]), "rb").read()
        assert reading_stats.store_upload(7, io.BytesIO(data), len(data)) == 201
        tag = reading_stats.etag_for(reading_stats.stats_path(7))
        assert reading_stats.store_upload(7, io.BytesIO(data), len(data), if_match="W/" + tag) == 204
        assert (config_dir / "reading_stats" / "7.sqlite3.prev").exists()

    def test_upload_from_a_device_that_missed_a_change_is_refused(self, config_dir, tmp_path):
        data = open(_statistics_file(str(tmp_path / "a.sqlite3"), []), "rb").read()
        reading_stats.store_upload(7, io.BytesIO(data), len(data))
        assert reading_stats.store_upload(7, io.BytesIO(data), len(data), if_match='"stale"') == 412

    def test_only_statistics_databases_are_accepted(self, config_dir, tmp_path):
        assert reading_stats.store_upload(7, io.BytesIO(b"not a database"), 14) == 415
        other = sqlite3.connect(str(tmp_path / "other.sqlite3"))
        other.execute("CREATE TABLE notes (id integer)")
        other.commit()
        other.close()
        data = open(tmp_path / "other.sqlite3", "rb").read()
        assert reading_stats.store_upload(7, io.BytesIO(data), len(data)) == 415
        assert reading_stats.store_upload(7, io.BytesIO(b""), reading_stats.MAX_BYTES + 1) == 413
        assert not list((config_dir / "reading_stats").glob(".upload-*"))

    def test_users_are_kept_apart(self, config_dir, tmp_path):
        data = open(_statistics_file(str(tmp_path / "a.sqlite3"), [(1, 1, _at(TODAY), 60, 400)]), "rb").read()
        reading_stats.store_upload(1, io.BytesIO(data), len(data))
        assert reading_stats.for_user(1, today=TODAY)["today"] == 60
        assert reading_stats.for_user(2, today=TODAY) is None


class TestWebDAV:
    @pytest.fixture
    def client(self, config_dir, monkeypatch):
        app = Flask(__name__)
        app.register_blueprint(reading_stats.reading_stats)
        monkeypatch.setattr(reading_stats, "_webdav_user", lambda: (SimpleNamespace(id=3), None))
        return app.test_client()

    def test_round_trip_like_koreader(self, client, tmp_path):
        assert client.get("/kosync/webdav/statistics.sqlite3").status_code == 404
        listing = client.open("/kosync/webdav/", method="PROPFIND", headers={"Depth": "1"})
        assert listing.status_code == 207 and b"<d:collection/>" in listing.data
        assert b"statistics.sqlite3" not in listing.data

        data = open(_statistics_file(str(tmp_path / "a.sqlite3"), [(1, 1, _at(TODAY), 60, 400)]), "rb").read()
        put = client.put("/kosync/webdav/statistics.sqlite3", data=data)
        assert put.status_code == 201 and put.headers["ETag"]

        got = client.get("/kosync/webdav/statistics.sqlite3")
        assert got.status_code == 200 and got.data == data and got.headers["ETag"] == put.headers["ETag"]
        assert client.put("/kosync/webdav/statistics.sqlite3", data=data,
                          headers={"If-Match": '"old"'}).status_code == 412
        assert client.put("/kosync/webdav/statistics.sqlite3", data=data,
                          headers={"If-Match": got.headers["ETag"]}).status_code == 204

        listing = client.open("/kosync/webdav/", method="PROPFIND", headers={"Depth": "1"})
        assert b"<d:href>/kosync/webdav/statistics.sqlite3</d:href>" in listing.data

    def test_other_files_are_refused(self, client):
        assert client.put("/kosync/webdav/evil.sh", data=b"x").status_code == 403
        assert client.get("/kosync/webdav/other.sqlite3").status_code == 404

    def test_sign_in_is_required(self, config_dir, monkeypatch):
        app = Flask(__name__)
        app.register_blueprint(reading_stats.reading_stats)
        import importlib
        kosync = importlib.import_module("cps.progress_syncing.protocols.kosync")
        monkeypatch.setattr(kosync, "_require_kosync_enabled", lambda: None)
        monkeypatch.setattr(kosync, "authenticate_user", lambda: None)
        response = app.test_client().open("/kosync/webdav/", method="PROPFIND")
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"].startswith("Basic")
