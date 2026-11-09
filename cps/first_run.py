# -*- coding: utf-8 -*-
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""First run: the administrator account is created in the browser, then a short welcome tour.

- A new installation starts without the shipped admin / admin123 account. Until an account exists,
  every page leads to /setup, where the first person to open Scriptorium chooses the administrator's
  name and password. Installations that already have accounts never see it.
- SCRIPTORIUM_DEFAULT_ADMIN=true brings the old behaviour back (admin / admin123, with a new password
  asked at the first sign-in), for automated installs and tests.
- New accounts (the first one, and those added later by an administrator or by registration) open
  the home page with a welcome tour of the main features. Whether it is still to be shown is kept in
  ``user.view_settings["welcome_tour"]``, so nothing is added to the database.
"""

from flask import Blueprint, abort, jsonify, redirect, request, url_for
from flask_babel import get_locale, gettext as _
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.security import generate_password_hash

from . import constants, logger, ub
from .cw_login import current_user, login_user
from .usermanagement import user_login_required

log = logger.create()

first_run = Blueprint('first_run', __name__)

DEFAULT_ADMIN_ENV = constants.DEFAULT_ADMIN_ENV
default_admin_requested = constants.default_admin_requested
WELCOME_KEY = "welcome_tour"
# Machine clients get an answer they understand instead of the setup page.
_API_PREFIXES = ("/kosync", "/opds", "/kobo", "/api", "/ajax", "/readingservices")
_needs_setup = None


def needs_setup():
    """True while no account other than Guest exists. Checked once, then remembered."""
    global _needs_setup
    if _needs_setup is False:
        return False
    try:
        count = ub.session.query(ub.User).filter(
            ub.User.role.op('&')(constants.ROLE_ANONYMOUS) != constants.ROLE_ANONYMOUS).count()
    except Exception as e:
        log.debug("Could not count accounts: %s", e)
        return False
    _needs_setup = count == 0
    return _needs_setup


def _reset():
    global _needs_setup
    _needs_setup = None


@first_run.before_app_request
def lead_to_setup():
    if request.endpoint in ("first_run.setup", "first_run.create", "static") or not needs_setup():
        return None
    if request.path.startswith(_API_PREFIXES):
        return jsonify({"error": "Scriptorium is not set up yet. Open it in a browser to create the first account."}), 503
    return redirect(url_for("first_run.setup"))


def _form_errors(name, password):
    from .helper import check_username, valid_password
    errors = {}
    try:
        check_username(name)
    except Exception as e:
        errors["name"] = str(e)
    if not password:
        errors["password"] = _("Choose a password.")
    else:
        try:
            valid_password(password)
        except Exception as e:
            errors["password"] = str(e)
    return errors


def _page(name="", errors=None, status=200):
    from . import config
    from .render_template import render_title_template
    return render_title_template("setup.html", name=name, errors=errors or {}, config=config,
                                 title=_("First start")), status


@first_run.route("/setup", methods=["GET"])
def setup():
    if not needs_setup():
        return redirect(url_for("web.index"))
    return _page()


@first_run.route("/setup", methods=["POST"])
def create():
    if not needs_setup():
        abort(404)
    name = (request.form.get("name") or "").strip()
    password = request.form.get("password") or ""
    errors = _form_errors(name, password)
    if errors:
        return _page(name, errors, 400)
    user = ub.User()
    user.name = name
    user.email = None
    user.role = constants.ADMIN_USER_ROLES
    user.sidebar_view = constants.ADMIN_USER_SIDEBAR
    user.password = generate_password_hash(password)
    user.locale = _locale_for_user()
    user.view_settings = {WELCOME_KEY: "pending"}
    ub.session.add(user)
    try:
        ub.session.commit()
    except Exception as e:
        ub.session.rollback()
        log.error("Could not create the first account: %s", e)
        return _page(name, {"name": _("The account could not be created. Please try again.")}, 500)
    _reset()
    ub.create_system_magic_shelves_for_user(user.id)
    log.info("First account created: %s", user.name)
    from . import config
    config.config_is_initial = False
    login_user(user, remember=True)
    return redirect(url_for("web.index"))


def _locale_for_user():
    """The language the browser asked for, when Scriptorium speaks it."""
    try:
        locale = str(get_locale() or "en")
    except Exception:
        locale = "en"
    return locale if locale else "en"


# ---------- Welcome tour ----------

def shows_welcome(user):
    if user is None or getattr(user, "is_anonymous", True):
        return False
    return (getattr(user, "view_settings", None) or {}).get(WELCOME_KEY) == "pending"


def mark_for_welcome(user):
    """Show the welcome tour at this user's first visit. The caller commits."""
    settings = dict(user.view_settings or {})
    settings[WELCOME_KEY] = "pending"
    user.view_settings = settings
    try:
        flag_modified(user, "view_settings")
    except Exception:  # a user not attached to a session yet
        pass


@first_run.route("/welcome/done", methods=["POST"])
@user_login_required
def welcome_done():
    settings = dict(current_user.view_settings or {})
    settings[WELCOME_KEY] = "done"
    # A new account has nothing to catch up on: the release notes of this version count as read.
    whats_new_state = dict(settings.get("whats_new") or {})
    whats_new_state.setdefault("seen", constants.INSTALLED_VERSION)
    settings["whats_new"] = whats_new_state
    current_user.view_settings = settings
    flag_modified(current_user, "view_settings")
    ub.session_commit("Welcome tour seen by {}".format(current_user.name))
    return jsonify({"success": True})


@first_run.route("/welcome/again", methods=["POST"])
@user_login_required
def welcome_again():
    """Show the tour again at the next visit of the home page (from the profile)."""
    mark_for_welcome(current_user)
    ub.session_commit()
    return jsonify({"success": True})
