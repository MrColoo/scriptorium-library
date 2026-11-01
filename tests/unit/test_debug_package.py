# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""The debug package is made to be shared, so no credential or sync address may end up in it."""

import io
import json
import zipfile
from types import SimpleNamespace

import pytest
from flask import Flask

from cps import config_sql, debug_info

pytestmark = pytest.mark.unit

PRIVATE = {
    "mail_password_e": "smtp-secret", "mail_password": "old-secret", "mail_login": "me@example.com",
    "mail_gmail_token": {"refresh_token": "gmail-secret"}, "config_hardcover_token": "hardcover-secret",
    "config_goodreads_api_key": "goodreads-secret", "config_goodreads_api_secret_e": "goodreads-secret",
    "config_ldap_serv_password_e": "ldap-secret", "config_ldap_serv_password": "old-secret",
    "config_ldap_serv_username": "cn=admin", "config_limiter_uri": "redis://:redis-secret@host",
    "config_limiter_options": "password=redis-secret",
}
PUBLIC = {"config_port": 8083, "config_password_min_length": 8, "config_password_policy": True,
          "mail_server": "smtp.example.com"}


def test_every_credential_column_is_private():
    """A new secret setting must not slip through: its name has to match PRIVATE_SETTING."""
    for column in config_sql._Settings.__table__.columns:
        if any(word in column.name.lower() for word in ("secret", "token", "serv_password", "mail_password")):
            assert config_sql.PRIVATE_SETTING.search(column.name), column.name


def test_settings_leave_out_credentials():
    settings = config_sql.ConfigSQL.to_dict(SimpleNamespace(**PRIVATE, **PUBLIC, cli="x", _session="x"))
    assert settings == PUBLIC


@pytest.mark.parametrize("line, expected", [
    (b'GET /kobo/0123abcdef/v1/library/sync HTTP/1.1', b'GET /kobo/<redacted>/v1/library/sync HTTP/1.1'),
    (b'"/kobo/0123abcdef"', b'"/kobo/<redacted>"'),
    (b'GET /verify/9f8e7d HTTP/1.1', b'GET /verify/<redacted> HTTP/1.1'),
    (b'Remot Login request with token: 9f8e7d', b'Remot Login request with token: <redacted>'),
    (b'GET /kobo_auth/generate_auth_token/1 HTTP/1.1', b'GET /kobo_auth/generate_auth_token/1 HTTP/1.1'),
    (b'GET /book/42 HTTP/1.1', b'GET /book/42 HTTP/1.1'),
])
def test_redact_log(line, expected):
    assert debug_info.redact_log(line) == expected


def test_package_contents(tmp_path, monkeypatch):
    access_log = tmp_path / "access.log"
    access_log.write_bytes(b'GET /kobo/0123abcdef/v1/library/sync HTTP/1.1\n')
    monkeypatch.setattr(debug_info, "config", SimpleNamespace(
        config_logfile="/dev/stdout", config_access_logfile=str(access_log),
        to_dict=lambda: config_sql.ConfigSQL.to_dict(SimpleNamespace(**PRIVATE, **PUBLIC))))
    monkeypatch.setattr(debug_info, "collect_stats", lambda: {"Python": "3"})

    with Flask(__name__).test_request_context():
        response = debug_info.send_debug()
        response.direct_passthrough = False
        data = response.get_data()

    with zipfile.ZipFile(io.BytesIO(data)) as package:
        assert sorted(package.namelist()) == ["access.log", "libs.txt", "settings.txt"]
        assert json.loads(package.read("settings.txt")) == PUBLIC
        assert b"0123abcdef" not in package.read("access.log")
        assert b"secret" not in b"".join(package.read(name) for name in package.namelist())
