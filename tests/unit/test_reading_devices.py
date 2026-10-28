# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""KOReader progress reaches the interface, and each user's device choice decides what is shown."""

import importlib
from datetime import datetime, timedelta, timezone

import pytest
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from cps import devices, reading_overview, ub

# The package re-exports the blueprint under the module's name, so import the module itself.
kosync_protocol = importlib.import_module("cps.progress_syncing.protocols.kosync")
# The model the code under test queries (another test may have reloaded the module).
KOSyncProgress = reading_overview.KOSyncProgress

pytestmark = pytest.mark.unit


@pytest.fixture
def session(monkeypatch):
    engine = create_engine("sqlite://")
    for module in (ub, devices.ub, reading_overview.ub, kosync_protocol.ub):
        module.Base.metadata.create_all(engine)
    test_session = scoped_session(sessionmaker(bind=engine))
    # Other unit tests may reload cps modules, so patch the ub each module under test actually holds.
    for module in (ub, devices.ub, reading_overview.ub, kosync_protocol.ub):
        monkeypatch.setattr(module, "session", test_session)
    yield test_session
    test_session.remove()


@pytest.fixture
def user(session):
    reader = ub.User(name="reader", email="reader@example.org", role=0, view_settings={})
    session.add(reader)
    session.commit()
    return reader


@pytest.fixture
def app_context():
    with Flask(__name__).app_context():
        yield


class TestBookProgressSource:
    def _kosync(self, session, user, book_id, percent, when, device="Kobo_libra2"):
        session.add(KOSyncProgress(user_id=user.id, document=str(book_id), progress="/body/p[1]",
                                   percentage=percent, device=device, timestamp=when))
        session.commit()

    def _bookmark(self, session, user, book_id, percent, when):
        state = ub.KoboReadingState(user_id=user.id, book_id=book_id, last_modified=when)
        state.current_bookmark = ub.KoboBookmark(progress_percent=percent, last_modified=when)
        session.add(state)
        session.commit()

    def test_no_progress(self, session, user):
        assert reading_overview.get_book_progress(user, 7) is None

    def test_koreader_newer_than_kobo(self, session, user):
        now = datetime.now(timezone.utc)
        self._bookmark(session, user, 7, 20.0, now - timedelta(days=2))
        self._kosync(session, user, 7, 64.0, now)
        progress = reading_overview.get_book_progress(user, 7)
        assert progress["source"] == "koreader"
        assert progress["percent"] == 64.0
        assert progress["device"] == "Kobo_libra2"

    def test_kobo_newer_than_koreader(self, session, user):
        now = datetime.now(timezone.utc)
        self._kosync(session, user, 7, 64.0, now - timedelta(days=2))
        self._bookmark(session, user, 7, 80.0, now)
        progress = reading_overview.get_book_progress(user, 7)
        assert progress["source"] == "kobo"
        assert progress["percent"] == 80.0

    def test_koreader_copy_in_bookmark_is_attributed_to_koreader(self, session, user):
        # The copy is written right after KOReader's own record, so it is slightly newer.
        when = datetime(2026, 10, 1, 12, 0, 0)
        self._kosync(session, user, 7, 40.0, when)
        self._bookmark(session, user, 7, 40.0, when + timedelta(milliseconds=70))
        progress = reading_overview.get_book_progress(user, 7)
        assert progress["source"] == "koreader"
        assert progress["device"] == "Kobo_libra2"

    def test_koreader_overview(self, session, user):
        now = datetime.now(timezone.utc)
        self._kosync(session, user, 7, 10.0, now - timedelta(hours=3), device="old")
        self._kosync(session, user, 8, 50.0, now, device="Kindle")
        overview = reading_overview.koreader_overview(user)
        assert overview["books"] == 2
        assert overview["device"] == "Kindle"
        assert overview["last_sync"]


class TestDeviceChoices:
    def test_defaults(self, session, user):
        assert devices.choices(user) == {"kobo": True, "koreader": False}

    def test_koreader_on_by_default_once_used(self, session, user):
        session.add(KOSyncProgress(user_id=user.id, document="7", progress="x", percentage=1.0, device="d"))
        session.commit()
        assert devices.choices(user)["koreader"] is True

    def test_saved_choice_wins(self, session, user):
        devices._save(user, "kobo", False)
        session.commit()
        assert devices.choices(user) == {"kobo": False, "koreader": False}
        devices._save(user, "koreader", True)
        session.commit()
        assert devices.choices(user) == {"kobo": False, "koreader": True}

    def test_invalid_saved_values_fall_back_to_defaults(self, session, user):
        user.view_settings = {"devices": {"kobo": "yes", "koreader": 1}}
        assert devices.choices(user) == {"kobo": True, "koreader": False}
        user.view_settings = {"devices": "kobo"}
        assert devices.choices(user) == {"kobo": True, "koreader": False}

    def test_shown_only_when_enabled_by_admin(self, session, user, app_context, monkeypatch):
        monkeypatch.setattr(devices, "available", lambda device: device == "koreader")
        devices._save(user, "koreader", True)
        assert devices.shows(user, "koreader") is True
        assert devices.shows(user, "kobo") is False

    def test_anonymous_sees_no_device(self, app_context):
        class Anonymous:
            is_anonymous = True
        assert devices.shows(Anonymous(), "kobo") is False
