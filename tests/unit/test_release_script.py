# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""scripts/release.py: release notes are validated, rendered and released from a clean, dated commit."""

import copy
import importlib.util
import json
import subprocess
from datetime import date
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("release_script", ROOT / "scripts" / "release.py")
release = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release)

READY = {
    "version": "v2.0.0", "date": "2026-11-01",
    "title": {"en": "Big things", "it": "Grandi cose"},
    "highlights": [{"icon": "sparkles", "title": {"en": "A", "it": "A"}, "text": {"en": "Does A.", "it": "Fa A."}}],
    "quote": {"text": {"en": "Quote.", "it": "Citazione."}, "author": "Someone", "book": {"en": "Book", "it": "Libro"}},
}


def _data(entry=READY):
    return {"releases": [copy.deepcopy(entry)]}


@pytest.mark.parametrize("tag", ["v1.2.3", "v0.1.0", "v10.0.0-rc.1"])
def test_valid_tags(tag):
    release.check_tag(tag)


@pytest.mark.parametrize("tag", ["1.2.3", "v1.2", "v01.2.3", "v1.2.3 ", "latest", ""])
def test_invalid_tags(tag):
    with pytest.raises(release.ReleaseError):
        release.check_tag(tag)


def test_shipped_notes_are_ready_for_every_release():
    data = release.load_notes()
    for entry in data["releases"]:
        assert release.problems(data, entry["version"]) == [], entry["version"]


def test_ready_entry_has_no_problems():
    assert release.problems(_data(), "v2.0.0") == []


def test_template_is_not_ready():
    data = {"releases": [release.template("v2.1.0")]}
    issues = release.problems(data, "v2.1.0", need_date=False)
    assert any("title" in issue for issue in issues)
    assert any("quote" in issue for issue in issues)


def test_missing_italian_unknown_icon_and_date_are_reported():
    entry = copy.deepcopy(READY)
    entry["highlights"][0]["title"].pop("it")
    entry["highlights"][0]["icon"] = "no-such-icon"
    entry["date"] = ""
    issues = release.problems(_data(entry), "v2.0.0")
    assert any("highlight 1 title: missing 'it'" in issue for issue in issues)
    assert any("not in the sprite" in issue for issue in issues)
    assert any("date" in issue for issue in issues)


def test_missing_entry():
    assert "no entry" in release.problems(_data(), "v9.0.0")[0]


def test_render():
    text = release.render(_data(), "v2.0.0")
    assert text.startswith("## Big things\n")
    assert "- **A** — Does A." in text
    assert "> Quote.\n> — Someone, *Book*" in text
    assert "ghcr.io/mrcoloo/scriptorium-library:v2.0.0` (also `latest`)" in text
    assert "<summary>🇮🇹 In italiano</summary>" in text and "## Grandi cose" in text


def test_render_prerelease_is_not_latest():
    entry = dict(copy.deepcopy(READY), version="v2.0.0-rc.1")
    assert "(also `latest`)" not in release.render(_data(entry), "v2.0.0-rc.1")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    def run(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    run("init", "-q", "-b", "main")
    run("config", "user.email", "test@example.org")
    run("config", "user.name", "Test")
    notes = tmp_path / "cps" / "release_notes.json"
    notes.parent.mkdir()
    entry = dict(copy.deepcopy(READY), date="")
    old = dict(copy.deepcopy(READY), version="v1.0.0")
    notes.write_text(json.dumps({"releases": [entry, old]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run("add", ".")
    run("commit", "-q", "-m", "init")
    run("tag", "-a", "v1.0.0", "-m", "v1.0.0")
    monkeypatch.setattr(release, "ROOT", str(tmp_path))
    monkeypatch.setattr(release, "NOTES_PATH", str(notes))
    return tmp_path, run


def _git(path, *args):
    return subprocess.run(["git", *args], cwd=path, check=True, capture_output=True, text=True).stdout.strip()


def test_prepare_dates_commits_and_tags(repo):
    path, _ = repo
    release.prepare("v2.0.0", today=date(2026, 11, 2))
    notes = json.loads((path / "cps" / "release_notes.json").read_text(encoding="utf-8"))
    assert notes["releases"][0]["date"] == "2026-11-02"
    assert _git(path, "log", "-1", "--format=%s") == "Release v2.0.0"
    assert _git(path, "cat-file", "-t", "v2.0.0") == "tag"  # annotated
    assert _git(path, "status", "--porcelain") == ""


def test_prepare_refuses_dirty_tree_old_version_and_existing_tag(repo):
    path, run = repo
    (path / "stray.txt").write_text("x")
    with pytest.raises(release.ReleaseError, match="commit or stash"):
        release.prepare("v2.0.0")
    (path / "stray.txt").unlink()
    with pytest.raises(release.ReleaseError, match="already exists"):
        release.prepare("v1.0.0")
    notes = path / "cps" / "release_notes.json"
    data = json.loads(notes.read_text(encoding="utf-8"))
    data["releases"].append(dict(copy.deepcopy(READY), version="v3.0.0"))
    notes.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run("commit", "-q", "-am", "notes for v3.0.0")
    run("tag", "-a", "v3.0.0", "-m", "v3.0.0")
    with pytest.raises(release.ReleaseError, match="not newer than the latest release v3.0.0"):
        release.prepare("v2.0.0")


def test_upstream_tags_are_not_scriptorium_releases(repo):
    path, run = repo
    run("tag", "-a", "v4.0.8", "-m", "Calibre-Web-Automated v4.0.8")  # fetched from upstream, no notes
    release.prepare("v2.0.0", today=date(2026, 11, 2))
    assert _git(path, "cat-file", "-t", "v2.0.0") == "tag"


def test_prepare_refuses_other_branches(repo):
    path, run = repo
    run("checkout", "-q", "-b", "feature")
    with pytest.raises(release.ReleaseError, match="main branch"):
        release.prepare("v2.0.0")


def test_prepare_tags_without_an_empty_commit_when_already_dated(repo):
    path, run = repo
    notes = path / "cps" / "release_notes.json"
    data = json.loads(notes.read_text(encoding="utf-8"))
    data["releases"][0]["date"] = "2026-11-02"
    notes.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run("commit", "-q", "-am", "notes ready")
    head = _git(path, "rev-parse", "HEAD")
    release.prepare("v2.0.0", today=date(2026, 11, 2))
    assert _git(path, "rev-parse", "v2.0.0^{commit}") == head
    assert _git(path, "log", "-1", "--format=%s") == "notes ready"
