# -*- coding: utf-8 -*-
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Version numbers and the release notes shipped with the app (``cps/release_notes.json``).

Pure functions, no Flask: what's new for a version, and whether one version is newer than another.

The notes file lists releases, newest first or in any order::

    {"releases": [{"version": "v1.1.0", "date": "2026-11-15",
                   "title": {"en": "...", "it": "..."},
                   "highlights": [{"icon": "sparkles", "title": {"en": "..."}, "text": {"en": "..."}}],
                   "quote": {"text": {"en": "...", "it": "..."}, "author": "...", "book": "..."}}]}

Every text is either a plain string or a dict of translations keyed by locale ("en" is the fallback).
"icon" names a symbol of the app's icon sprite. "quote" is a short line from a book that fits the
release; use public-domain works or very short quotations.
"""

import json
import os
import re

NOTES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "release_notes.json")

_VERSION_RE = re.compile(r"^\s*[vV]?(\d+)\.(\d+)\.(\d+)")
_cache = {"path": None, "mtime": None, "releases": []}


def parse_version(value):
    """(major, minor, patch) for strings like "v1.2.3" or "1.2.3-beta", or None."""
    match = _VERSION_RE.match(str(value or ""))
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def is_newer(candidate, current):
    """True only when both versions are valid and candidate is strictly newer."""
    a, b = parse_version(candidate), parse_version(current)
    return a is not None and b is not None and a > b


def localize(value, locale="en"):
    """Pick the text for a locale from a string or a {locale: text} dict."""
    if isinstance(value, str):
        return value
    if not isinstance(value, dict) or not value:
        return ""
    locale = str(locale or "en")
    for key in (locale, locale.split("_")[0], "en"):
        if isinstance(value.get(key), str) and value[key]:
            return value[key]
    return next((text for text in value.values() if isinstance(text, str)), "")


def _clean(release):
    if not isinstance(release, dict) or parse_version(release.get("version")) is None:
        return None
    highlights = [item for item in release.get("highlights") or []
                  if isinstance(item, dict) and (item.get("title") or item.get("text"))]
    quote = release.get("quote") if isinstance(release.get("quote"), dict) else None
    if quote and not quote.get("text"):
        quote = None
    return {
        "version": str(release["version"]),
        "date": str(release.get("date") or ""),
        "title": release.get("title") or "",
        "highlights": highlights,
        "quote": quote,
    }


def from_data(data):
    """Valid releases from already-parsed notes data (for example fetched for a newer version), newest first."""
    if not isinstance(data, dict):
        return []
    releases = [r for r in (_clean(item) for item in data.get("releases") or []) if r]
    releases.sort(key=lambda r: parse_version(r["version"]), reverse=True)
    return releases


def load(path=NOTES_PATH):
    """Valid releases, newest first. Re-read when the file changes; [] when it is missing or broken."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return []
    if _cache["path"] == path and _cache["mtime"] == mtime:
        return _cache["releases"]
    try:
        with open(path, encoding="utf-8") as handle:
            releases = from_data(json.load(handle))
    except (OSError, ValueError, AttributeError):
        releases = []
    _cache.update(path=path, mtime=mtime, releases=releases)
    return releases


def notes_for(installed, releases):
    """The newest release at or below the installed version (a patch without notes shows its minor's)."""
    current = parse_version(installed)
    if current is None:
        return None
    for release in releases:
        if parse_version(release["version"]) <= current:
            return release
    return None


def pending(installed, seen, releases):
    """Release notes the user has not seen yet for the installed version, or None."""
    release = notes_for(installed, releases)
    if release is None:
        return None
    seen_version = parse_version(seen)
    if seen_version is not None and seen_version >= parse_version(release["version"]):
        return None
    return release


def localized(release, locale):
    """A copy of a release with every text in the given locale, ready for a template."""
    if release is None:
        return None
    quote = release.get("quote")
    return {
        "version": release["version"],
        "date": release["date"],
        "title": localize(release["title"], locale),
        "highlights": [{"title": localize(item.get("title"), locale), "text": localize(item.get("text"), locale),
                        "icon": item.get("icon") if isinstance(item.get("icon"), str) else None}
                       for item in release["highlights"]],
        "quote": {"text": localize(quote.get("text"), locale), "author": localize(quote.get("author"), locale),
                  "book": localize(quote.get("book"), locale)} if quote else None,
    }


def notes_between(installed, latest, releases):
    """Every release newer than installed and up to latest, newest first: what an update brings."""
    low, high = parse_version(installed), parse_version(latest)
    if high is None:
        return []
    return [r for r in releases if (low is None or parse_version(r["version"]) > low)
            and parse_version(r["version"]) <= high]
