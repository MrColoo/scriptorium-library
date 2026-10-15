# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2018-2025 Calibre-Web contributors
# Copyright (C) 2024-2025 Calibre-Web Automated contributors
# Copyright (C) 2026 Mrcoloo (Scriptorium changes)
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Storage for admin-assigned profile pictures.

Pictures live in ``user_profiles.json`` next to the CWA database as a map of
username -> ``data:image/...;base64,...`` URI, the format earlier releases wrote.
"""

import base64
import binascii
import hashlib
import json
import os
import tempfile
from threading import Lock

MAX_IMAGE_BYTES = 512000
_ALLOWED_PREFIXES = {
    "data:image/png;base64,": "image/png",
    "data:image/jpeg;base64,": "image/jpeg",
    "data:image/jpg;base64,": "image/jpeg",
    "data:image/webp;base64,": "image/webp",
}

_lock = Lock()
_cache = {"mtime": None, "data": {}}


class ProfilePictureError(ValueError):
    pass


def storage_path():
    return os.path.join(os.environ.get("CWA_DB_PATH", "/config"), "user_profiles.json")


def load_all():
    """Return the username -> data URI map, re-reading the file only when it changed."""
    path = storage_path()
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    with _lock:
        if _cache["mtime"] != mtime:
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                _cache["data"] = data if isinstance(data, dict) else {}
            except (OSError, ValueError):
                _cache["data"] = {}
            _cache["mtime"] = mtime
        return dict(_cache["data"])


def decode(data_uri):
    """Validate a data URI and return (mimetype, bytes)."""
    if not isinstance(data_uri, str):
        raise ProfilePictureError("invalid")
    for prefix, mimetype in _ALLOWED_PREFIXES.items():
        if data_uri.startswith(prefix):
            try:
                raw = base64.b64decode(data_uri[len(prefix):], validate=True)
            except (binascii.Error, ValueError):
                raise ProfilePictureError("invalid")
            if not raw:
                raise ProfilePictureError("invalid")
            if len(raw) > MAX_IMAGE_BYTES:
                raise ProfilePictureError("too_large")
            return mimetype, raw
    raise ProfilePictureError("unsupported")


def get(username):
    """Return (mimetype, bytes) for a user's picture, or None."""
    uri = load_all().get(username)
    if not uri:
        return None
    try:
        return decode(uri)
    except ProfilePictureError:
        return None


def version(username):
    """Short token that changes whenever the picture changes (for cache busting)."""
    uri = load_all().get(username)
    if not uri:
        return None
    return hashlib.sha1(uri.encode("utf-8")).hexdigest()[:10]


def _write(data):
    path = storage_path()
    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".user_profiles.", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def set_picture(username, data_uri):
    decode(data_uri)
    with _lock:
        data = _read_for_update()
        data[username] = data_uri
        _write(data)
        _cache["mtime"] = None


def remove_picture(username):
    with _lock:
        data = _read_for_update()
        if data.pop(username, None) is None:
            return False
        _write(data)
        _cache["mtime"] = None
        return True


def _read_for_update():
    try:
        with open(storage_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except ValueError:
        # A corrupt file would otherwise block every update; start over.
        return {}
