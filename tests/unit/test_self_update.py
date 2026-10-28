# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""One-click updates: backups are real copies, the webhook is called safely, notes cover the gap."""

import os
import sqlite3

import pytest
import requests

from cps import releases, self_update

pytestmark = pytest.mark.unit


def _db(path, rows):
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE t (v TEXT)")
        con.executemany("INSERT INTO t VALUES (?)", [(r,) for r in rows])
    return str(path)


def test_backup_copies_databases_and_keeps_the_last_five(tmp_path):
    app_db = _db(tmp_path / "app.db", ["a", "b"])
    cwa_db = _db(tmp_path / "cwa.db", ["c"])
    root = tmp_path / "backups"
    root.mkdir()
    for i in range(6):
        (root / "pre-update-0.9.{}-2026010{}-000000".format(i, i)).mkdir()
    folder = self_update.backup_databases(str(root), "v1.0.0", sources=[app_db, cwa_db])
    assert os.path.basename(folder).startswith("pre-update-1.0.0-")
    with sqlite3.connect(os.path.join(folder, "app.db")) as con:
        assert [r[0] for r in con.execute("SELECT v FROM t")] == ["a", "b"]
    assert os.path.isfile(os.path.join(folder, "cwa.db"))
    assert len([n for n in os.listdir(root) if n.startswith("pre-update-")]) == 5
    assert os.path.isdir(folder)


def test_backup_works_while_the_database_is_open(tmp_path):
    app_db = _db(tmp_path / "app.db", ["x"])
    with sqlite3.connect(app_db) as busy:
        busy.execute("INSERT INTO t VALUES ('y')")  # uncommitted write in progress
        folder = self_update.backup_databases(str(tmp_path / "b"), "v1.0.0", sources=[app_db])
    with sqlite3.connect(os.path.join(folder, "app.db")) as con:
        assert con.execute("SELECT count(*) FROM t").fetchone()[0] >= 1


class _Response:
    def __init__(self, status):
        self.status_code = status


def test_webhook_sends_the_token_and_accepts_success():
    seen = {}

    def post(url, headers, timeout):
        seen.update(url=url, headers=headers)
        return _Response(200)

    assert self_update.call_webhook("http://watchtower:8080/v1/update", "secret", post=post) is None
    assert seen["headers"]["Authorization"] == "Bearer secret"


@pytest.mark.parametrize("status, fragment", [(401, "token"), (500, "HTTP 500")])
def test_webhook_errors_are_reported(status, fragment):
    assert fragment in self_update.call_webhook("http://x", post=lambda *a, **k: _Response(status))


def test_dropped_connection_while_updating_counts_as_started():
    def post(*args, **kwargs):
        raise requests.exceptions.ReadTimeout()
    assert self_update.call_webhook("http://x", post=post) is None


def test_unreachable_service_is_an_error():
    def post(*args, **kwargs):
        raise requests.exceptions.ConnectionError()
    assert "Could not reach" in self_update.call_webhook("http://x", post=post)


def test_configured_only_with_a_webhook(monkeypatch):
    monkeypatch.delenv(self_update.WEBHOOK_ENV, raising=False)
    assert not self_update.configured()
    monkeypatch.setenv(self_update.WEBHOOK_ENV, "http://watchtower:8080/v1/update")
    assert self_update.configured()


def test_notes_between_covers_every_skipped_release():
    notes = releases.from_data({"releases": [
        {"version": v, "title": v, "highlights": [{"title": v}],
         "quote": {"text": "q" + v, "author": "A"} if v == "v1.2.0" else None}
        for v in ("v1.0.0", "v1.1.0", "v1.2.0", "v1.3.0")]})
    between = releases.notes_between("v1.0.0", "v1.2.0", notes)
    assert [r["version"] for r in between] == ["v1.2.0", "v1.1.0"]
    assert releases.localized(between[0], "en")["quote"] == {"text": "qv1.2.0", "author": "A", "book": ""}
    assert releases.notes_between("v1.0.0", "nonsense", notes) == []
