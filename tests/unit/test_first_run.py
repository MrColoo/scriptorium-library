# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""First run: no shipped admin account unless asked for, the setup page until an account exists, the welcome tour."""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from cps import constants, first_run, magic_shelf, ub

pytestmark = pytest.mark.unit


@pytest.fixture
def session(monkeypatch):
    engine = create_engine("sqlite://")
    ub.Base.metadata.create_all(engine)
    test_session = scoped_session(sessionmaker(bind=engine))
    monkeypatch.setattr(ub, "session", test_session)
    first_run._reset()
    yield test_session
    test_session.remove()
    first_run._reset()


@pytest.mark.parametrize("value, wanted", [("true", True), ("1", True), ("YES", True), ("on", True),
                                           ("", False), ("false", False), ("0", False), (None, False)])
def test_the_shipped_admin_only_when_asked(monkeypatch, value, wanted):
    if value is None:
        monkeypatch.delenv(first_run.DEFAULT_ADMIN_ENV, raising=False)
    else:
        monkeypatch.setenv(first_run.DEFAULT_ADMIN_ENV, value)
    assert first_run.default_admin_requested() is wanted


@pytest.mark.parametrize("asked, names", [(False, ["Guest"]), (True, ["Guest", "admin"])])
def test_a_new_database(tmp_path, monkeypatch, asked, names):
    monkeypatch.setenv(first_run.DEFAULT_ADMIN_ENV, "true" if asked else "false")
    monkeypatch.setattr(ub, "_healthcheck_app_db", lambda path: None)
    monkeypatch.setattr(ub, "create_system_magic_shelves_for_user", lambda user_id: 0, raising=False)
    monkeypatch.setattr(magic_shelf, "create_system_magic_shelves", lambda user_id: 0)
    # init_db replaces the module's session and path: put them back afterwards
    monkeypatch.setattr(ub, "session", ub.session)
    monkeypatch.setattr(ub, "app_DB_path", getattr(ub, "app_DB_path", None), raising=False)
    ub.init_db(str(tmp_path / "app.db"))
    try:
        assert sorted(user.name for user in ub.session.query(ub.User).all()) == names
    finally:
        ub.session.close()


def test_setup_is_needed_until_an_account_exists(session):
    session.add(ub.User(name="Guest", role=constants.ROLE_ANONYMOUS, email="guest@example.org"))
    session.commit()
    assert first_run.needs_setup()
    session.add(ub.User(name="Lucas", role=constants.ADMIN_USER_ROLES))
    session.commit()
    assert not first_run.needs_setup()
    session.query(ub.User).filter(ub.User.name == "Lucas").delete()
    session.commit()
    assert not first_run.needs_setup()  # once set up, never asked again while running


def test_the_welcome_tour_for_new_accounts_only():
    existing = SimpleNamespace(is_anonymous=False, view_settings={"theme": "dark"})
    assert not first_run.shows_welcome(existing)
    new = SimpleNamespace(is_anonymous=False, view_settings=None)
    first_run.mark_for_welcome(new)
    assert first_run.shows_welcome(new)
    assert not first_run.shows_welcome(SimpleNamespace(is_anonymous=True, view_settings={"welcome_tour": "pending"}))
    assert not first_run.shows_welcome(None)
