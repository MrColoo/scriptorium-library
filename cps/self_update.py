# -*- coding: utf-8 -*-
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""One-click updates, done safely.

A container cannot replace its own image, and giving Scriptorium the Docker socket would hand it
root on the host. Instead the administrator points Scriptorium at a service that already updates
containers, through two environment variables:

    SCRIPTORIUM_UPDATE_WEBHOOK  URL that pulls the new image and recreates the container
                                (for example Watchtower's HTTP API: http://watchtower:8080/v1/update)
    SCRIPTORIUM_UPDATE_TOKEN    bearer token sent with the request (optional)

When an administrator presses Update:
1. a newer release must exist and no other update may be running;
2. app.db, cwa.db and the library's metadata.db are copied with SQLite's online backup into
   /config/backups/pre-update-<version>-<time>/ (the five most recent are kept);
3. the webhook is called in the background, so the response reaches the browser before the
   container restarts; the page then polls /update/status until the new version answers.

The webhook URL and token come only from the environment and never reach the browser.
"""

import os
import shutil
import sqlite3
import threading
import time
from datetime import datetime

import requests
from flask import Blueprint, abort, jsonify, request
from flask_babel import gettext as _

from . import config, constants, logger, releases, ub
from .cw_login import current_user
from .usermanagement import user_login_required

log = logger.create()

self_update = Blueprint('self_update', __name__)

WEBHOOK_ENV = "SCRIPTORIUM_UPDATE_WEBHOOK"
TOKEN_ENV = "SCRIPTORIUM_UPDATE_TOKEN"
KEEP_BACKUPS = 5
STALE_AFTER = 15 * 60

_state = {"state": "idle", "error": None, "started": 0.0, "target": None, "backup": None}
_lock = threading.Lock()


def configured():
    return bool(os.environ.get(WEBHOOK_ENV, "").strip())


def _require_admin():
    if not current_user.role_admin():
        abort(403)


# ---------- Backup ----------

def _databases():
    paths = [ub.app_DB_path,
             os.path.join(os.environ.get("CWA_DB_PATH", "/config"), "cwa.db")]
    library = getattr(config, "config_calibre_dir", None)
    if library:
        paths.append(os.path.join(library, "metadata.db"))
    return [path for path in paths if path and os.path.isfile(path)]


def backup_databases(root, version, sources=None, keep=KEEP_BACKUPS):
    """Copy each database with SQLite's online backup (safe while it is in use). Returns the folder."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = os.path.join(root, "pre-update-{}-{}".format(str(version).lstrip("vV") or "unknown", stamp))
    os.makedirs(target, exist_ok=True)
    for source in sources if sources is not None else _databases():
        destination = os.path.join(target, os.path.basename(source))
        with sqlite3.connect(source, timeout=30) as src, sqlite3.connect(destination) as dst:
            src.backup(dst)
        # A copy that does not pass SQLite's own check is no backup at all.
        with sqlite3.connect(destination) as check:
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("backup of {} failed its integrity check".format(os.path.basename(source)))
    old = sorted((name for name in os.listdir(root) if name.startswith("pre-update-")), reverse=True)
    for name in old[keep:]:
        shutil.rmtree(os.path.join(root, name), ignore_errors=True)
    return target


def _backup_root():
    base = os.path.dirname(ub.app_DB_path) if ub.app_DB_path else os.environ.get("CWA_DB_PATH", "/config")
    return os.path.join(base, "backups")


# ---------- Webhook ----------

def call_webhook(url, token=None, post=requests.post):
    """Ask the update service to update. A dropped connection counts as started: it restarts us."""
    headers = {"User-Agent": "Scriptorium/{}".format(constants.INSTALLED_VERSION)}
    if token:
        headers["Authorization"] = "Bearer {}".format(token)
    try:
        response = post(url, headers=headers, timeout=(5, 20))
    except (requests.exceptions.ReadTimeout, requests.exceptions.ChunkedEncodingError):
        return None  # the service is busy updating, possibly stopping this container
    except requests.exceptions.ConnectionError as e:
        return "Could not reach the update service: {}".format(e.__class__.__name__)
    if response.status_code in (401, 403):
        return "The update service refused the token (HTTP {}).".format(response.status_code)
    if response.status_code >= 400:
        return "The update service answered HTTP {}.".format(response.status_code)
    return None


def _run(url, token):
    time.sleep(1)  # let the response reach the browser first
    error = call_webhook(url, token)
    with _lock:
        if error:
            _state.update(state="failed", error=error)
            log.error("Update failed: %s", error)
        else:
            _state.update(state="restarting")
            log.info("Update service accepted the request; waiting for the restart")


def _busy():
    return _state["state"] in ("backing-up", "updating", "restarting") and time.time() - _state["started"] < STALE_AFTER


@self_update.route("/update/start", methods=["POST"])
@user_login_required
def start():
    _require_admin()
    from . import whats_new
    latest = whats_new.latest_version(check=False)
    if not releases.is_newer(latest, constants.INSTALLED_VERSION):
        return jsonify({"ok": False, "error": "no-update", "message": _("You already have the latest version.")}), 409
    if not configured():
        return jsonify({"ok": False, "error": "not-configured",
                        "message": _("One-click updates are not set up on this server.")}), 409
    with _lock:
        if _busy():
            return jsonify({"ok": False, "error": "running", "message": _("An update is already running.")}), 409
        _state.update(state="backing-up", error=None, started=time.time(), target=latest, backup=None)
    try:
        folder = backup_databases(_backup_root(), constants.INSTALLED_VERSION)
    except Exception as e:
        with _lock:
            _state.update(state="failed", error=_("The backup failed, so nothing was changed: %(error)s", error=e))
        log.error("Pre-update backup failed: %s", e)
        return jsonify({"ok": False, "error": "backup", "message": _state["error"]}), 500
    with _lock:
        _state.update(state="updating", backup=folder)
    log.info("Pre-update backup written to %s; asking the update service for %s", folder, latest)
    threading.Thread(target=_run, args=(os.environ[WEBHOOK_ENV].strip(), os.environ.get(TOKEN_ENV, "").strip()),
                     name="scriptorium-update", daemon=True).start()
    return jsonify({"ok": True, "from": constants.INSTALLED_VERSION, "to": latest, "backup": folder})


@self_update.route("/update/status")
@user_login_required
def status():
    _require_admin()
    with _lock:
        state = dict(_state)
    return jsonify({"version": constants.INSTALLED_VERSION, "state": state["state"], "error": state["error"],
                    "target": state["target"]})


@self_update.route("/update/auto-check", methods=["POST"])
@user_login_required
def auto_check():
    _require_admin()
    enabled = bool((request.get_json(silent=True) or {}).get("enabled"))
    from cwa_db import CWA_DB
    CWA_DB().update_cwa_settings({"cwa_update_notifications": 1 if enabled else 0})
    return jsonify({"ok": True, "enabled": enabled})
