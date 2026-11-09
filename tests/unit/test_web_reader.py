# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""The built-in reader as a reading device: its position, its reading time, and no audiobook uploads."""

import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from cps import config_sql, constants, reading_overview, reading_stats, ub, web_reader
from cps.progress_syncing.models import KOSyncProgress

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 9, 20, 0, tzinfo=timezone.utc)


@pytest.fixture
def session(monkeypatch):
    engine = create_engine("sqlite://")
    ub.Base.metadata.create_all(engine)
    test_session = scoped_session(sessionmaker(bind=engine))
    for module in (ub, reading_overview.ub):
        monkeypatch.setattr(module, "session", test_session)
    yield test_session
    test_session.remove()


def _user(**settings):
    return SimpleNamespace(id=1, is_anonymous=False, view_settings=dict(settings))


def _kobo(session, percent, when):
    state = ub.KoboReadingState(user_id=1, book_id=7, last_modified=when)
    state.current_bookmark = ub.KoboBookmark(progress_percent=percent, last_modified=when)
    session.add(state)
    session.commit()


class TestPosition:
    def test_remember_and_read_back(self, monkeypatch):
        monkeypatch.setattr(web_reader, "flag_modified", lambda *a: None)
        user = _user(theme="dark")
        web_reader.remember_position(user, 7, "epubcfi(/6/4!/4/2/1:0)", 41.237, now=NOW)
        assert user.view_settings["theme"] == "dark"
        assert web_reader.saved_position(user, 7) == {"cfi": "epubcfi(/6/4!/4/2/1:0)", "percent": 41.24, "when": NOW}
        assert web_reader.saved_position(user, 8) is None

    def test_only_the_most_recent_books_are_kept(self, monkeypatch):
        monkeypatch.setattr(web_reader, "flag_modified", lambda *a: None)
        monkeypatch.setattr(web_reader, "MAX_POSITIONS", 3)
        user = _user()
        for book in range(5):
            web_reader.remember_position(user, book, "epubcfi(/6/2)", 10, now=NOW + timedelta(minutes=book))
        assert sorted(user.view_settings["reader_positions"]) == ["2", "3", "4"]

    def test_the_newest_device_wins(self, session):
        _kobo(session, 62.0, NOW)
        user = _user(reader_positions={"7": {"cfi": "epubcfi(/6/2)", "percent": 30, "at": (NOW - timedelta(days=1)).isoformat()}})
        progress = reading_overview.get_book_progress(user, 7)
        assert (progress["source"], progress["percent"]) == ("kobo", 62.0)
        start = web_reader.start_position(user, 7)
        assert start == {"cfi": None, "percent": 62.0, "source": "kobo", "device": None}

    def test_the_readers_own_position_reopens_exactly(self, session):
        # The reader also writes its percentage into the Kobo bookmark: that copy is the reader's, not the Kobo's.
        _kobo(session, 55.5, NOW + timedelta(seconds=1))
        user = _user(reader_positions={"7": {"cfi": "epubcfi(/6/8!/4/2)", "percent": 55.5, "at": NOW.isoformat()}})
        assert reading_overview.get_book_progress(user, 7)["source"] == "web"
        assert web_reader.start_position(user, 7) == {"cfi": "epubcfi(/6/8!/4/2)", "percent": 55.5,
                                                      "source": "web", "device": None}

    def test_koreader_newer_than_the_reader(self, session):
        session.add(KOSyncProgress(user_id=1, document="7", progress="/body/p[3]", percentage=80.0,
                                   device="Kobo Libra", timestamp=NOW))
        session.commit()
        user = _user(reader_positions={"7": {"cfi": "epubcfi(/6/2)", "percent": 30, "at": (NOW - timedelta(hours=2)).isoformat()}})
        assert web_reader.start_position(user, 7) == {"cfi": None, "percent": 80.0, "source": "koreader",
                                                      "device": "Kobo Libra"}


class TestKOReaderPositions:
    @pytest.fixture
    def epub(self, tmp_path):
        import zipfile
        path = tmp_path / "book.epub"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("META-INF/container.xml", '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                       '<rootfiles><rootfile full-path="content.opf"/></rootfiles></container>')
            z.writestr("content.opf", '<package xmlns="http://www.idpf.org/2007/opf"><metadata/><manifest>'
                       '<item id="c" href="c.xhtml"/></manifest><spine><itemref idref="c"/></spine></package>')
            z.writestr("c.xhtml", '<html xmlns="http://www.w3.org/1999/xhtml"><head/><body><p>A</p><p>B</p></body></html>')
        return str(path)

    def test_the_readers_position_is_written_for_koreader(self, session, monkeypatch):
        import cps.progress_syncing.settings as settings
        monkeypatch.setattr(settings, "is_koreader_sync_enabled", lambda: True)
        user = _user()
        web_reader.share_with_koreader(user, 7, "/body/DocFragment[1]/body/p[2]", 42.0)
        session.commit()
        record = session.query(KOSyncProgress).one()
        assert (record.document, record.progress, record.percentage, record.device, record.device_id) == \
            ("7", "/body/DocFragment[1]/body/p[2]", 42.0, "Scriptorium", "scriptorium-web")
        # Not a KOReader device of the user's: the book page keeps its own source.
        assert reading_overview.get_book_progress(user, 7) is None
        # A later KOReader sync takes the same record over, as it does between devices.
        web_reader.share_with_koreader(user, 7, None, 43.0)
        session.commit()
        assert session.query(KOSyncProgress).count() == 1 and session.query(KOSyncProgress).one().progress == ""

    def test_nothing_is_written_when_koreader_sync_is_off(self, session, monkeypatch):
        import cps.progress_syncing.settings as settings
        monkeypatch.setattr(settings, "is_koreader_sync_enabled", lambda: False)
        web_reader.share_with_koreader(_user(), 7, "/body/DocFragment[1]/body/p[2]", 42.0)
        assert session.query(KOSyncProgress).count() == 0

    def test_koreaders_position_opens_on_the_same_paragraph(self, session, epub):
        session.add(KOSyncProgress(user_id=1, document="7", progress="/body/DocFragment[1]/body/p[2]",
                                   percentage=80.0, device="Kobo Libra", device_id="libra", timestamp=NOW))
        session.commit()
        start = web_reader.start_position(_user(), 7, epub)
        assert start == {"cfi": "epubcfi(/6/2!/4/4)", "percent": 80.0, "source": "koreader", "device": "Kobo Libra"}


class TestReadingTime:
    @pytest.fixture(autouse=True)
    def config_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(reading_stats.constants, "CONFIG_DIR", str(tmp_path))
        reading_stats._cache.clear()

    def _book(self):
        return SimpleNamespace(id=7, title="Moby-Dick", authors=[SimpleNamespace(name="Herman Melville")])

    def test_pages_are_stored_and_cleaned(self):
        now = int(time.time())
        pages = [[10, now - 600, 45, 300],       # kept
                 [11, now - 500, 900, 300],      # an open page: counted as two minutes
                 [12, now - 400, 1, 300],        # skimmed past: dropped
                 [13, now - 30 * 86400, 60, 300],  # too old to be a real page turn: dropped
                 ["x", now, 10, 300]]            # junk: dropped
        assert reading_stats.store_web_pages(1, self._book(), "abc", pages, now=now) == 2
        books, rows = reading_stats.load_all(1)
        assert [info["title"] for info in books.values()] == ["Moby-Dick"]
        assert [(row[1], row[3]) for row in rows] == [(10, 45), (11, 120)]

    def test_the_same_book_on_koreader_and_in_the_reader_is_one_book(self, tmp_path):
        import sqlite3
        now = int(time.time())
        path = reading_stats.stats_path(1)
        (tmp_path / "reading_stats").mkdir(exist_ok=True)
        conn = sqlite3.connect(path)
        conn.executescript(reading_stats._WEB_SCHEMA)
        conn.execute("INSERT INTO book (id, title, authors, md5, pages) VALUES (3, 'Moby Dick', 'H. Melville', 'abc', 600)")
        conn.execute("INSERT INTO page_stat_data VALUES (3, 1, ?, 60, 600)", (now - 3600,))
        conn.commit()
        conn.close()
        reading_stats.store_web_pages(1, self._book(), "abc", [[5, now - 60, 30, 300]], now=now)
        reading_stats.store_web_pages(1, SimpleNamespace(id=9, title="Emma", authors=[]), None, [[1, now - 50, 30, 100]], now=now)
        books, rows = reading_stats.load_all(1)
        assert sorted(row[0] for row in rows) == [3, 3, reading_stats.WEB_BOOK_OFFSET + 2]
        summary = reading_stats.for_user(1)
        assert summary["books"] == 2 and summary["total_seconds"] == 120


def test_audiobooks_cannot_be_uploaded():
    config = SimpleNamespace(config_upload_formats="epub,mp3,pdf,m4b,flac")
    assert config_sql.ConfigSQL.upload_formats(config) == ["epub", "pdf"]
    assert not constants.EXTENSIONS_AUDIO & constants.EXTENSIONS_UPLOAD
