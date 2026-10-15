# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2018-2025 Calibre-Web contributors
# Copyright (C) 2024-2025 Calibre-Web Automated contributors
# Copyright (C) 2026 Mrcoloo (Scriptorium changes)
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

# Inspired by https://github.com/ChrisTM/Flask-CacheBust
# Uses query strings so CSS font files are found without having to resort to absolute URLs

import os
import hashlib

from . import logger


log = logger.create()


def init_cache_busting(app):
    """
    Configure `app` to so that `url_for` adds a unique query string to URLs generated
    for the `'static'` endpoint.

    This allows setting long cache expiration values on static resources
    because whenever the resource changes, so does its URL.
    """

    static_folder = os.path.join(app.static_folder, '')  # path to the static file folder, with trailing slash

    hash_table = {}  # web path -> (mtime, short hash)

    def file_version(rooted_filename):
        with open(rooted_filename, 'rb') as f:
            return hashlib.md5(f.read(), usedforsecurity=False).hexdigest()[:7]

    log.debug('Computing cache-busting values...')
    for dirpath, __, filenames in os.walk(static_folder):
        for filename in filenames:
            rooted_filename = os.path.join(dirpath, filename)
            file_path = rooted_filename.replace(static_folder, "").replace("\\", "/")
            try:
                hash_table[file_path] = (os.path.getmtime(rooted_filename), file_version(rooted_filename))
            except PermissionError:
                log.error("No permission to access {} file.".format(rooted_filename))
    log.debug('Finished computing cache-busting values')

    def bust_filename(file_name):
        entry = hash_table.get(file_name)
        if not entry:
            return ""
        # Re-hash files changed since startup (development, hot fixes) so their URL changes too.
        rooted_filename = os.path.join(static_folder, file_name)
        try:
            mtime = os.path.getmtime(rooted_filename)
            if mtime != entry[0]:
                entry = (mtime, file_version(rooted_filename))
                hash_table[file_name] = entry
        except OSError:
            pass
        return entry[1]

    def unbust_filename(file_name):
        return file_name.split("?", 1)[0]

    @app.url_defaults
    # pylint: disable=unused-variable
    def reverse_to_cache_busted_url(endpoint, values):
        """
        Make `url_for` produce busted filenames when using the 'static' endpoint.
        """
        if endpoint == "static":
            file_hash = bust_filename(values["filename"])
            if file_hash:
                values["q"] = file_hash

    def debusting_static_view(filename):
        """
        Serve a request for a static file having a busted name.
        """
        return original_static_view(filename=unbust_filename(filename))

    # Replace the default static file view with our debusting view.
    original_static_view = app.view_functions["static"]
    app.view_functions["static"] = debusting_static_view
