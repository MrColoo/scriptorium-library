# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Release notes are shown once per version, and the update notice only appears for a newer release."""

import json
from types import SimpleNamespace

import pytest

from cps import constants, releases, whats_new

pytestmark = pytest.mark.unit


def _notes(tmp_path, data):
    path = tmp_path / "release_notes.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


RELEASES = {"releases": [
    {"version": "v1.0.0", "title": {"en": "First", "it": "Prima"},
     "highlights": [{"title": {"en": "Styles", "it": "Stili"}, "text": "Colours"}]},
    {"version": "v1.2.0", "title": "Third", "highlights": [{"title": "Devices"}]},
    {"version": "v1.1.0", "title": "Second", "highlights": []},
    {"version": "not a version", "title": "Ignored"},
    "garbage",
]}


class TestVersions:
    @pytest.mark.parametrize("value, expected", [
        ("v1.2.3", (1, 2, 3)), ("1.2.3", (1, 2, 3)), ("V10.0.1-beta", (10, 0, 1)),
        ("", None), (None, None), ("latest", None), ("1.2", None),
    ])
    def test_parse(self, value, expected):
        assert releases.parse_version(value) == expected

    def test_is_newer(self):
        assert releases.is_newer("v1.10.0", "v1.9.9")
        assert not releases.is_newer("v1.0.0", "v1.0.0")
        assert not releases.is_newer("v0.9.0", "v1.0.0")
        assert not releases.is_newer(None, "v1.0.0")
        assert not releases.is_newer("v1.0.0", "dev")


class TestReleaseNotes:
    def test_load_keeps_valid_releases_newest_first(self, tmp_path):
        loaded = releases.load(_notes(tmp_path, RELEASES))
        assert [r["version"] for r in loaded] == ["v1.2.0", "v1.1.0", "v1.0.0"]

    def test_missing_or_broken_file(self, tmp_path):
        assert releases.load(str(tmp_path / "missing.json")) == []
        broken = tmp_path / "broken.json"
        broken.write_text("{nope", encoding="utf-8")
        assert releases.load(str(broken)) == []

    def test_shipped_notes_are_valid(self):
        loaded = releases.load()
        assert loaded, "cps/release_notes.json has no valid release"
        for release in loaded:
            assert releases.localize(release["title"], "en")
            assert release["highlights"]
            for item in release["highlights"]:
                assert releases.localize(item.get("title"), "en")
                assert releases.localize(item.get("title"), "it")

    def test_notes_for_patch_release_fall_back_to_its_minor(self, tmp_path):
        loaded = releases.load(_notes(tmp_path, RELEASES))
        assert releases.notes_for("v1.1.4", loaded)["version"] == "v1.1.0"
        assert releases.notes_for("v0.9.0", loaded) is None
        assert releases.notes_for("v0.0.0", loaded) is None

    def test_pending_once_per_version(self, tmp_path):
        loaded = releases.load(_notes(tmp_path, RELEASES))
        assert releases.pending("v1.2.0", None, loaded)["version"] == "v1.2.0"
        assert releases.pending("v1.2.0", "v1.1.0", loaded)["version"] == "v1.2.0"
        assert releases.pending("v1.2.0", "v1.2.0", loaded) is None
        assert releases.pending("v1.2.1", "v1.2.0", loaded) is None

    def test_localized(self, tmp_path):
        release = releases.notes_for("v1.0.0", releases.load(_notes(tmp_path, RELEASES)))
        italian = releases.localized(release, "it")
        assert italian["title"] == "Prima"
        assert italian["highlights"] == [{"title": "Stili", "text": "Colours", "icon": None}]
        assert releases.localized(release, "pt_BR")["title"] == "First"


def _user(admin=True, state=None):
    return SimpleNamespace(is_anonymous=False, name="admin", view_settings={"whats_new": state or {}},
                           role_admin=lambda: admin)


class TestUpdateNotice:
    @pytest.fixture(autouse=True)
    def versions(self, monkeypatch):
        monkeypatch.setattr(constants, "INSTALLED_VERSION", "v1.0.0")
        monkeypatch.setattr(whats_new, "_latest", {"version": None, "checked": 0.0, "running": False})

    def test_newer_release(self, monkeypatch):
        monkeypatch.setattr(constants, "STABLE_VERSION", "v1.1.0")
        notice = whats_new.update_notice(_user(), check=False)
        assert notice["version"] == "v1.1.0"
        assert notice["url"].endswith("/releases/tag/v1.1.0")
        assert notice["dismissed"] is False

    def test_same_or_older_release(self, monkeypatch):
        monkeypatch.setattr(constants, "STABLE_VERSION", "v1.0.0")
        assert whats_new.update_notice(_user(), check=False) is None
        whats_new._latest["version"] = "v0.9.0"
        assert whats_new.update_notice(_user(), check=False) is None

    def test_unknown_release(self, monkeypatch):
        monkeypatch.setattr(constants, "STABLE_VERSION", "v0.0.0")
        monkeypatch.setattr(constants, "INSTALLED_VERSION", "v0.0.0")
        assert whats_new.update_notice(_user(), check=False) is None

    def test_only_for_admins(self, monkeypatch):
        monkeypatch.setattr(constants, "STABLE_VERSION", "v1.1.0")
        assert whats_new.update_notice(_user(admin=False), check=False) is None

    def test_dismissed_for_this_version_only(self, monkeypatch):
        monkeypatch.setattr(constants, "STABLE_VERSION", "v1.1.0")
        assert whats_new.update_notice(_user(state={"update_dismissed": "v1.1.0"}), check=False)["dismissed"]
        whats_new._latest["version"] = "v1.2.0"
        assert not whats_new.update_notice(_user(state={"update_dismissed": "v1.1.0"}), check=False)["dismissed"]

    def test_background_check_updates_latest(self, monkeypatch):
        monkeypatch.setattr(constants, "STABLE_VERSION", "v1.0.0")

        class Response:
            status_code = 200

            @staticmethod
            def json():
                return {"tag_name": "v1.3.0"}

        monkeypatch.setattr(whats_new.requests, "get", lambda *args, **kwargs: Response())
        whats_new._fetch_latest()
        assert whats_new.latest_version(check=False) == "v1.3.0"

    def test_failed_check_keeps_known_version(self, monkeypatch):
        monkeypatch.setattr(constants, "STABLE_VERSION", "v1.1.0")
        whats_new.latest_version(check=False)

        def offline(*args, **kwargs):
            raise OSError("offline")

        monkeypatch.setattr(whats_new.requests, "get", offline)
        whats_new._fetch_latest()
        assert whats_new.latest_version(check=False) == "v1.1.0"


def test_notes_between_covers_every_skipped_release():
    notes = releases.from_data({"releases": [
        {"version": v, "title": v, "highlights": [{"title": v}],
         "quote": {"text": "q" + v, "author": "A"} if v == "v1.2.0" else None}
        for v in ("v1.0.0", "v1.1.0", "v1.2.0", "v1.3.0")]})
    between = releases.notes_between("v1.0.0", "v1.2.0", notes)
    assert [r["version"] for r in between] == ["v1.2.0", "v1.1.0"]
    assert releases.localized(between[0], "en")["quote"] == {"text": "qv1.2.0", "author": "A", "book": ""}
    assert releases.notes_between("v1.0.0", "nonsense", notes) == []
