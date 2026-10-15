# -*- coding: utf-8 -*-
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Per-user appearance: colours, header art and shapes layered over the stock design.

The choice is stored in ``user.view_settings["appearance"]``. An empty choice means the
stock look, untouched. Values are validated every time they are read, because
view_settings can also be written through the generic /ajax/view endpoint.
"""

from flask import Blueprint, flash, redirect, request, url_for
from flask_babel import gettext as _, lazy_gettext as N_
from sqlalchemy.orm.attributes import flag_modified

from . import calibre_db, db, logger, ub
from .appearance_styles import HUE_KEYS, OPTIONS, PRESETS, SETTINGS_KEY, html_attrs, sanitize
from .cw_login import current_user
from .render_template import render_title_template
from .usermanagement import user_login_required

log = logger.create()

appearance = Blueprint('appearance', __name__)

PRESET_LABELS = {
    "stock": N_("Classic"),
    "aurora": N_("Aurora"),
    "sunset": N_("Sunset"),
    "ocean": N_("Ocean"),
    "forest": N_("Forest"),
    "paper": N_("Paper"),
    "neon": N_("Neon"),
    "lavender": N_("Lavender"),
    "coral": N_("Coral"),
    "midnight": N_("Midnight"),
    "citrus": N_("Citrus"),
}


def for_user(user):
    if not user or getattr(user, "is_anonymous", True):
        return {}
    settings = getattr(user, "view_settings", None) or {}
    return sanitize(settings.get(SETTINGS_KEY))


def _save(user, ap):
    settings = dict(user.view_settings or {})
    if ap:
        settings[SETTINGS_KEY] = ap
    else:
        settings.pop(SETTINGS_KEY, None)
    user.view_settings = settings
    flag_modified(user, "view_settings")
    ub.session_commit("Appearance updated for user {}".format(user.name))


@appearance.route("/me/appearance", methods=["GET", "POST"])
@user_login_required
def customize():
    if current_user.is_anonymous:
        return redirect(url_for('web.index'))
    if request.method == "POST":
        preset = request.form.get("preset")
        if preset == "stock" or request.form.get("action") == "reset":
            _save(current_user, {})
            flash(_("Back to the classic look."), category="success")
        elif preset in PRESETS:  # a style card clicked without JavaScript
            _save(current_user, sanitize(PRESETS[preset]))
            flash(_("Your style is saved."), category="success")
        else:
            _save(current_user, sanitize({key: request.form.get(key) for key in list(OPTIONS) + list(HUE_KEYS)}))
            flash(_("Your style is saved."), category="success")
        return redirect(url_for('appearance.customize'))

    current = for_user(current_user)
    sample_books = []
    try:
        sample_books = (calibre_db.session.query(db.Books)
                        .filter(calibre_db.common_filters())
                        .filter(db.Books.has_cover == 1)
                        .order_by(db.Books.timestamp.desc())
                        .limit(6).all())
    except Exception as ex:  # preview covers are decoration only
        log.debug("Could not load preview covers: %s", ex)
    presets = [{"key": key, "label": PRESET_LABELS[key], "values": values, "attrs": html_attrs(sanitize(values))}
               for key, values in PRESETS.items()]
    return render_title_template("appearance.html", title=_("Customize"), page="appearance",
                                 current=current or sanitize(PRESETS["aurora"]), is_stock=not current,
                                 presets=presets, options=OPTIONS, sample_books=sample_books)
