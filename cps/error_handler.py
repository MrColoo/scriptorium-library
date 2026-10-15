# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2018-2025 Calibre-Web contributors
# Copyright (C) 2024-2025 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

import traceback

from flask import render_template
from werkzeug.exceptions import default_exceptions
try:
    from werkzeug.exceptions import FailedDependency
except ImportError:
    from werkzeug.exceptions import UnprocessableEntity as FailedDependency

from . import config, app, logger, services


log = logger.create()

# custom error page

def error_http(error):
    headers = {'WWW-Authenticate': f'Basic realm="{config.config_calibre_web_title or "calibre-web-automated"}"'} if error.code == 401 else {}
    return render_template('http_error.html',
                           error_code="Error {0}".format(error.code),
                           error_name=error.name,
                           issue=False,
                           unconfigured=not config.db_configured,
                           instance=config.config_calibre_web_title
                           ), error.code, headers


def internal_error(error):
    stack = traceback.format_exc()
    log.error("Unhandled error: %s", stack)
    # Tracebacks reveal paths and code; only administrators get to see them.
    show_stack = False
    try:
        from .cw_login import current_user
        show_stack = bool(current_user and current_user.is_authenticated and current_user.role_admin())
    except Exception:
        show_stack = False
    return render_template('http_error.html',
                           error_code="500 Internal Server Error",
                           error_name='The server encountered an internal error and was unable to complete your '
                                      'request. There is an error in the application.',
                           issue=True,
                           unconfigured=False,
                           error_stack=stack.split("\n") if show_stack else [],
                           instance=config.config_calibre_web_title
                           ), 500


def init_errorhandler():
    # http error handling
    for ex in default_exceptions:
        if ex < 500:
            app.register_error_handler(ex, error_http)
        elif ex == 500:
            app.register_error_handler(ex, internal_error)

    if services.ldap:
        # Only way of catching the LDAPException upon logging in with LDAP server down
        @app.errorhandler(services.ldap.LDAPException)
        # pylint: disable=unused-variable
        def handle_exception(e):
            log.debug('LDAP server not accessible while trying to login to opds feed')
            return error_http(FailedDependency())

