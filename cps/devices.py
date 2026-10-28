# -*- coding: utf-8 -*-
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""The reading devices each user uses, and what the library shows for them.

The choice is stored in ``user.view_settings["devices"]`` as ``{"kobo": bool, "koreader": bool}``,
so nothing is added to the database. A device the administrator has not enabled is never shown.
Without a saved choice, Kobo is shown whenever Kobo sync is on (the behaviour before this
setting existed) and KOReader once the user has synced from it.
"""

from flask import Blueprint, abort, flash, g, redirect, request, url_for
from flask_babel import gettext as _
from sqlalchemy.orm.attributes import flag_modified

from . import config, logger, services, ub
from .progress_syncing.models import KOSyncProgress
from .progress_syncing.settings import is_koreader_sync_enabled
from .cw_login import current_user
from .usermanagement import user_login_required

log = logger.create()

devices = Blueprint('devices', __name__)

SETTINGS_KEY = "devices"
DEVICES = ("kobo", "koreader")


def available(device):
    """Whether the administrator has turned the device's sync on (cached for the request)."""
    cache = g.setdefault("_devices_available", {})
    if device not in cache:
        if device == "kobo":
            cache[device] = bool(services.kobo) and bool(config.config_kobo_sync)
        elif device == "koreader":
            cache[device] = is_koreader_sync_enabled()
        else:
            cache[device] = False
    return cache[device]


def has_koreader_history(user_id):
    try:
        return ub.session.query(KOSyncProgress.id).filter(KOSyncProgress.user_id == int(user_id)).first() is not None
    except Exception as e:
        log.debug("Could not read KOReader progress: %s", e)
        return False


def choices(user):
    """{"kobo": bool, "koreader": bool}: what the user said they use, with the defaults filled in."""
    if user is None or getattr(user, "is_anonymous", True):
        return {device: False for device in DEVICES}
    saved = (getattr(user, "view_settings", None) or {}).get(SETTINGS_KEY)
    saved = saved if isinstance(saved, dict) else {}
    result = {}
    for device in DEVICES:
        if isinstance(saved.get(device), bool):
            result[device] = saved[device]
        elif device == "kobo":
            result[device] = True
        else:
            result[device] = has_koreader_history(user.id)
    return result


def shows(user, device):
    """True when the library should show this device to the user: enabled by the admin and chosen."""
    if user is None or getattr(user, "is_anonymous", True) or not available(device):
        return False
    cache = g.setdefault("_devices_shown", {})
    key = (int(user.id), device)
    if key not in cache:
        cache[key] = choices(user)[device]
    return cache[key]


def _save(user, device, used):
    settings = dict(user.view_settings or {})
    chosen = dict(settings.get(SETTINGS_KEY) or {})
    chosen[device] = bool(used)
    settings[SETTINGS_KEY] = chosen
    user.view_settings = settings
    flag_modified(user, "view_settings")


def _user_or_404(user_id):
    # Device settings can disconnect a device, so only the owner or an admin may change them.
    if current_user.id != user_id and not current_user.role_admin():
        abort(403)
    user = ub.session.query(ub.User).filter(ub.User.id == int(user_id)).first()
    if user is None:
        abort(404)
    return user


def _settings_page_for(user_id, anchor="devices"):
    if user_id == current_user.id:
        return url_for("web.profile") + "#" + anchor
    return url_for("admin.edit_user", user_id=user_id) + "#" + anchor


@devices.route("/me/devices/<int:user_id>/<device>", methods=["POST"])
@user_login_required
def set_device(user_id, device):
    if device not in DEVICES:
        abort(404)
    user = _user_or_404(user_id)
    used = request.form.get("use") == "on"
    _save(user, device, used)
    ub.session_commit("Device choice updated for user {}: {}={}".format(user.name, device, used))
    return redirect(_settings_page_for(user_id, device if used else "devices"))


@devices.route("/me/devices/<int:user_id>/kobo/remove", methods=["POST"])
@user_login_required
def remove_kobo(user_id):
    """Disconnect the Kobo: revoke its sync address, forget which books it holds, hide Kobo features.

    Reading progress and read status are kept, so switching to KOReader on the same device loses nothing.
    """
    user = _user_or_404(user_id)
    ub.session.query(ub.RemoteAuthToken).filter(ub.RemoteAuthToken.user_id == user.id,
                                                ub.RemoteAuthToken.token_type == 1).delete()
    ub.session.query(ub.KoboSyncedBooks).filter(ub.KoboSyncedBooks.user_id == user.id).delete()
    _save(user, "kobo", False)
    ub.session_commit("Kobo removed for user {}".format(user.name))
    flash(_("Kobo removed. Your reading progress is kept."), category="success")
    return redirect(_settings_page_for(user_id))
