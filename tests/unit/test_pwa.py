# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""The installable app: manifest, icons and service worker stay consistent and safe."""

import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

STATIC = Path(__file__).resolve().parents[2] / "cps" / "static"


def _manifest():
    return json.loads((STATIC / "manifest.webmanifest").read_text(encoding="utf-8"))


def test_manifest_icons_exist():
    manifest = _manifest()
    purposes = {icon["purpose"] for icon in manifest["icons"]}
    assert {"any", "maskable"} <= purposes
    for icon in manifest["icons"]:
        assert (STATIC / icon["src"]).is_file(), icon["src"]
    assert any(icon["sizes"] == "192x192" for icon in manifest["icons"])


def test_manifest_urls_are_relative_so_sub_path_installs_work():
    manifest = _manifest()
    for url in [manifest["start_url"], manifest["scope"], manifest["share_target"]["action"]] + \
               [shortcut["url"] for shortcut in manifest["shortcuts"]]:
        assert url.startswith("../"), url


def test_share_target_posts_files():
    target = _manifest()["share_target"]
    assert target["method"] == "POST" and target["enctype"] == "multipart/form-data"
    assert target["params"]["files"][0]["name"] == "file"


def test_service_worker_never_caches_pages():
    sw = (STATIC / "js" / "sw.js").read_text(encoding="utf-8")
    # Pages go to the network; only the offline page and /static/ files are cached.
    assert 'request.mode === "navigate"' in sw
    assert "fetch(request).catch" in sw
    assert 'SCOPE + "static/"' in sw
    assert "cache.put(request, response.clone())" in sw.split('SCOPE + "static/"')[1].split("return;")[0]
