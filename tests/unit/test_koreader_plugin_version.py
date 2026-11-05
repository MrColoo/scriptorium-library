# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Devices that sync with an older KOReader plugin are noticed, so the user can be told to update it."""

import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from cps import constants, reading_overview

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]


def _user(**plugins):
    return SimpleNamespace(is_anonymous=False, view_settings={"koreader_plugins": plugins} if plugins else {})


def test_shipped_plugin_matches_the_constant():
    main = (REPO / "koreader" / "plugins" / "cwasync.koplugin" / "main.lua").read_text(encoding="utf-8")
    assert re.search(r'version = "([^"]+)",\s+-- Plugin version', main).group(1) == constants.KOREADER_PLUGIN_VERSION


def test_note_records_once_a_day(monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.attributes.flag_modified", lambda *a: None)
    user = SimpleNamespace(view_settings={"theme": "dark"})
    reading_overview.note_koreader_plugin(user, "id-1", "Kobo_libra2", None)
    entry = user.view_settings["koreader_plugins"]["id-1"]
    assert entry["version"] is None and entry["device"] == "Kobo_libra2"
    assert user.view_settings["theme"] == "dark"
    reading_overview.note_koreader_plugin(user, "id-1", "Kobo_libra2", constants.KOREADER_PLUGIN_VERSION)
    assert user.view_settings["koreader_plugins"]["id-1"]["version"] == constants.KOREADER_PLUGIN_VERSION


def test_outdated_devices():
    today = date(2026, 11, 5)
    user = _user(a={"version": None, "device": "Kobo", "seen": "2026-11-01"},
                 b={"version": "1.1.9", "device": "Phone", "seen": "2026-11-04"},
                 c={"version": constants.KOREADER_PLUGIN_VERSION, "device": "Tablet", "seen": "2026-11-04"},
                 d={"version": None, "device": "Old Kindle", "seen": "2026-01-01"})
    outdated = reading_overview.outdated_koreader_plugins(user, today=today)
    assert [item["device"] for item in outdated] == ["Kobo", "Phone"]
    assert reading_overview.outdated_koreader_plugins(_user(), today=today) == []
    assert reading_overview.outdated_koreader_plugins(SimpleNamespace(is_anonymous=True)) == []
