# -*- coding: utf-8 -*-
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""What's new after an update, and the notice that a newer release is out.

- Every user sees the release notes of the installed version once, in a dialog.
- Administrators get an update button in the top bar while a newer release exists. It opens a dialog
  with that release's highlights and quote, read from the release_notes.json of the new version's tag,
  and the command that updates the container.
- The newest release is looked up on GitHub in the background, at most every 12 hours and only while
  update notifications are on; until then the version found at container start is used.

What each user has seen is stored in ``user.view_settings["whats_new"]``, so nothing is added to the
database.
"""

import threading
import time

import requests
from flask import Blueprint, abort, jsonify, request
from flask_babel import get_locale, gettext as _
from sqlalchemy.orm.attributes import flag_modified

from . import constants, logger, releases, ub
from .cw_login import current_user
from .render_template import render_title_template
from .usermanagement import user_login_required

log = logger.create()

whats_new = Blueprint('whats_new', __name__)

SETTINGS_KEY = "whats_new"
REPOSITORY = "MrColoo/scriptorium-library"
RELEASES_URL = "https://github.com/{}/releases".format(REPOSITORY)
LATEST_API_URL = "https://api.github.com/repos/{}/releases/latest".format(REPOSITORY)
NOTES_URL = "https://raw.githubusercontent.com/{}/{{tag}}/cps/release_notes.json".format(REPOSITORY)
CHECK_INTERVAL = 12 * 60 * 60

_latest = {"version": None, "checked": 0.0, "running": False, "notes": [], "notes_for": None}
_latest_lock = threading.Lock()


def _locale():
    try:
        return str(get_locale() or "en")
    except Exception:
        return "en"


def _state(user):
    state = (getattr(user, "view_settings", None) or {}).get(SETTINGS_KEY)
    return state if isinstance(state, dict) else {}


def _remember(user, key, value):
    settings = dict(user.view_settings or {})
    state = dict(_state(user))
    state[key] = value
    settings[SETTINGS_KEY] = state
    user.view_settings = settings
    flag_modified(user, "view_settings")
    ub.session_commit("What's new: {}={} for user {}".format(key, value, user.name))


def release_url(version):
    return "{}/tag/{}".format(RELEASES_URL, version) if version else RELEASES_URL


# ---------- Newest release ----------

def _fetch_latest():
    try:
        response = requests.get(LATEST_API_URL, timeout=5,
                                headers={"Accept": "application/vnd.github+json",
                                         "User-Agent": "Scriptorium/{}".format(constants.INSTALLED_VERSION)})
        if response.status_code == 200:
            tag = (response.json() or {}).get("tag_name")
            if releases.parse_version(tag) is not None:
                with _latest_lock:
                    _latest["version"] = tag
                _fetch_notes(tag)
    except Exception as e:  # offline, rate limited, GitHub down: keep what we know
        log.debug("Could not check for a new release: %s", e)
    finally:
        with _latest_lock:
            _latest["running"] = False


def _fetch_notes(tag):
    """Release notes as published with the new version, so the dialog can show what it brings."""
    if _latest.get("notes_for") == tag:
        return
    try:
        response = requests.get(NOTES_URL.format(tag=tag), timeout=5,
                                headers={"User-Agent": "Scriptorium/{}".format(constants.INSTALLED_VERSION)})
        if response.status_code == 200:
            notes = releases.from_data(response.json())
            with _latest_lock:
                _latest["notes"], _latest["notes_for"] = notes, tag
    except Exception as e:
        log.debug("Could not fetch the release notes of %s: %s", tag, e)


def latest_version(check=True):
    """The newest known release. With check=True, refresh it in the background when it is stale."""
    with _latest_lock:
        if _latest["version"] is None and releases.parse_version(constants.STABLE_VERSION):
            _latest["version"] = constants.STABLE_VERSION
        start = check and not _latest["running"] and time.time() - _latest["checked"] >= CHECK_INTERVAL
        if start:
            _latest["running"] = True
            _latest["checked"] = time.time()
        version = _latest["version"]
    if start:
        threading.Thread(target=_fetch_latest, name="scriptorium-release-check", daemon=True).start()
    return version


def update_notice(user, check=True):
    """For administrators: {version, installed, url, dismissed} while a newer release exists, else None."""
    if user is None or getattr(user, "is_anonymous", True) or not user.role_admin():
        return None
    latest = latest_version(check=check)
    if not releases.is_newer(latest, constants.INSTALLED_VERSION):
        return None
    with _latest_lock:
        notes = list(_latest["notes"]) if _latest.get("notes_for") == latest else []
    if not notes:  # a release can also be described in the notes this version already ships
        notes = releases.load()
    coming = [releases.localized(release, _locale())
              for release in releases.notes_between(constants.INSTALLED_VERSION, latest, notes)]
    highlights = [item for release in coming for item in release["highlights"]][:6]
    quote = next((release["quote"] for release in coming if release.get("quote")), None)
    return {
        "version": latest,
        "installed": constants.INSTALLED_VERSION,
        "url": release_url(latest),
        "dismissed": _state(user).get("update_dismissed") == latest,
        "title": coming[0]["title"] if coming else "",
        "date": coming[0]["date"] if coming else "",
        "highlights": highlights,
        "quote": quote,
    }


# ---------- Release notes ----------

def popup_for(user):
    """The release notes to show this user once, already translated, or None."""
    if user is None or getattr(user, "is_anonymous", True):
        return None
    release = releases.pending(constants.INSTALLED_VERSION, _state(user).get("seen"), releases.load())
    return releases.localized(release, _locale())


@whats_new.route("/whats-new")
@user_login_required
def page():
    notes = [releases.localized(release, _locale()) for release in releases.load()]
    installed = releases.notes_for(constants.INSTALLED_VERSION, releases.load())
    if installed and releases.pending(constants.INSTALLED_VERSION, _state(current_user).get("seen"), [installed]):
        _remember(current_user, "seen", installed["version"])
    return render_title_template("whats_new.html", title=_("What's new"), notes=notes,
                                 installed=constants.INSTALLED_VERSION, releases_url=RELEASES_URL,
                                 page="whats_new")


@whats_new.route("/whats-new/seen", methods=["POST"])
@user_login_required
def mark_seen():
    release = releases.notes_for(constants.INSTALLED_VERSION, releases.load())
    if release:
        _remember(current_user, "seen", release["version"])
    return jsonify({"success": True})


@whats_new.route("/whats-new/dismiss-update", methods=["POST"])
@user_login_required
def dismiss_update():
    if not current_user.role_admin():
        abort(403)
    latest = latest_version(check=False)
    if latest:
        _remember(current_user, "update_dismissed", latest)
    return jsonify({"success": True})


@whats_new.route("/update/auto-check", methods=["POST"])
@user_login_required
def auto_check():
    """Turn the background release check (and the update button) on or off."""
    if not current_user.role_admin():
        abort(403)
    enabled = bool((request.get_json(silent=True) or {}).get("enabled"))
    from cwa_db import CWA_DB
    CWA_DB().update_cwa_settings({"cwa_update_notifications": 1 if enabled else 0})
    return jsonify({"ok": True, "enabled": enabled})
