# -*- coding: utf-8 -*-
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Installable app: the service worker at the site root, the offline page and the share target.

Books shared from another app are posted to /share-target. The service worker keeps them in a cache
and opens /share, where the signed-in page uploads them with its CSRF token. The server-side
/share-target only exists for browsers without the worker: it stores nothing and sends the user on.
"""

import os

from flask import Blueprint, make_response, redirect, render_template, send_from_directory, url_for
from flask_babel import gettext as _

from . import csrf
from .render_template import render_title_template
from .usermanagement import user_login_required

pwa = Blueprint('pwa', __name__)

STATIC_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "js")


@pwa.app_template_global("service_worker_url")
def service_worker_url():
    """URL of the service worker, versioned by the file's modification time so updates install."""
    try:
        version = int(os.path.getmtime(os.path.join(STATIC_JS, "sw.js")))
    except OSError:
        version = 1
    return url_for("pwa.service_worker", v=version)


@pwa.route("/sw.js")
def service_worker():
    response = make_response(send_from_directory(STATIC_JS, "sw.js", mimetype="text/javascript"))
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Service-Worker-Allowed"] = url_for("web.index")
    return response


@pwa.route("/offline")
def offline():
    return render_template("offline.html")


@pwa.route("/share")
@user_login_required
def share():
    return render_title_template("share.html", title=_("Add shared books"), page="share")


@csrf.exempt
@pwa.route("/share-target", methods=["POST"])
def share_target_fallback():
    # Reached only when the service worker is not installed yet. Nothing is read or stored here.
    return redirect(url_for("pwa.share", missed=1), code=303)
