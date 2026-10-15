# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Profile picture storage: only small raster images are accepted, writes are atomic."""

import base64
import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "cwa_profile_pictures", Path(__file__).resolve().parents[2] / "cps" / "profile_pictures.py")
pp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(pp)

PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 32).decode()


@pytest.fixture(autouse=True)
def config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CWA_DB_PATH", str(tmp_path))
    pp._cache["mtime"] = None
    return tmp_path


def test_round_trip(config_dir):
    pp.set_picture("alice", PNG)
    assert pp.get("alice")[0] == "image/png"
    assert json.loads((config_dir / "user_profiles.json").read_text())["alice"] == PNG
    assert pp.version("alice")
    assert pp.remove_picture("alice") is True
    assert pp.get("alice") is None
    assert pp.remove_picture("alice") is False


@pytest.mark.parametrize("uri, reason", [
    ("data:image/svg+xml;base64," + base64.b64encode(b"<svg onload=alert(1)>").decode(), "unsupported"),
    ("javascript:alert(1)", "unsupported"),
    ("data:image/png;base64,not base64!", "invalid"),
    ("data:image/png;base64,", "invalid"),
    ("data:image/png;base64," + base64.b64encode(b"0" * (pp.MAX_IMAGE_BYTES + 1)).decode(), "too_large"),
])
def test_rejects_bad_images(uri, reason):
    with pytest.raises(pp.ProfilePictureError) as err:
        pp.set_picture("bob", uri)
    assert str(err.value) == reason
    assert pp.load_all() == {}


def test_corrupt_file_does_not_block_updates(config_dir):
    (config_dir / "user_profiles.json").write_text("{not json")
    assert pp.load_all() == {}
    pp.set_picture("carol", PNG)
    assert set(pp.load_all()) == {"carol"}
