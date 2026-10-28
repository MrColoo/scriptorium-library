# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""KOReader progress is stored where the book page and "Continue reading" look for it."""

import importlib
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from cps import ub

# The package re-exports the blueprint under the module's name, so import the module itself.
kosync_protocol = importlib.import_module("cps.progress_syncing.protocols.kosync")

pytestmark = pytest.mark.unit


@pytest.fixture
def session(monkeypatch):
    engine = create_engine("sqlite://")
    for module in (ub, kosync_protocol.ub):
        module.Base.metadata.create_all(engine)
    test_session = scoped_session(sessionmaker(bind=engine))
    # Other unit tests may reload cps modules, so patch the ub the module under test actually holds.
    for module in (ub, kosync_protocol.ub):
        monkeypatch.setattr(module, "session", test_session)
    yield test_session
    test_session.remove()


@pytest.fixture
def user(session):
    reader = ub.User(name="reader", email="reader@example.org", role=0, view_settings={})
    session.add(reader)
    session.commit()
    return reader


def _state(session, user, book_id):
    return session.query(ub.KoboReadingState).filter_by(user_id=user.id, book_id=book_id).first()


class TestKOReaderProgressIsStored:
    def test_first_sync_creates_reading_state(self, session, user):
        kosync_protocol.update_book_read_status(user, 7, 42.0)
        session.commit()
        state = _state(session, user, 7)
        assert state.current_bookmark.progress_percent == 42.0

    def test_book_already_marked_as_reading_gets_its_progress(self, session, user):
        # Opening a book in the web reader or marking it as reading creates the ReadBook row alone.
        session.add(ub.ReadBook(user_id=user.id, book_id=7, read_status=ub.ReadBook.STATUS_IN_PROGRESS))
        session.commit()
        kosync_protocol.update_book_read_status(user, 7, 55.0)
        session.commit()
        state = _state(session, user, 7)
        assert state is not None
        assert state.current_bookmark.progress_percent == 55.0
        assert state.statistics is not None

    def test_later_sync_updates_progress_and_moves_book_forward(self, session, user):
        kosync_protocol.update_book_read_status(user, 7, 10.0)
        session.commit()
        state = _state(session, user, 7)
        state.last_modified = datetime(2020, 1, 1)
        session.commit()
        kosync_protocol.update_book_read_status(user, 7, 30.0)
        session.commit()
        state = _state(session, user, 7)
        assert state.current_bookmark.progress_percent == 30.0
        assert state.last_modified.replace(tzinfo=None) > datetime(2025, 1, 1)
