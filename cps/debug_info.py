# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2018-2025 Calibre-Web contributors
# Copyright (C) 2024-2025 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

import shutil
import glob
import zipfile
import json
from io import BytesIO
from flask_babel.speaklater import LazyString

import os
import re

from flask import send_file
import importlib

from . import logger, config
from .about import collect_stats

log = logger.create()

# A Kobo sync address and a magic link work like passwords, and they are logged with each request
SECRET_IN_LOG = re.compile(rb"(/kobo/|/verify/|with token: )[^/\s\"'?]+")


class lazyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, LazyString):
            return str(obj)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


def assemble_logfiles(file_name):
    log_list = sorted(glob.glob(file_name + '*'), reverse=True)
    wfd = BytesIO()
    for f in log_list:
        with open(f, 'rb') as fd:
            shutil.copyfileobj(fd, wfd)
    wfd.seek(0)
    version = importlib.metadata.version("flask")
    if int(version.split('.')[0]) < 2:
        return send_file(wfd,
                         as_attachment=True,
                         attachment_filename=os.path.basename(file_name))
    else:
        return send_file(wfd,
                         as_attachment=True,
                         download_name=os.path.basename(file_name))


def redact_log(data):
    return SECRET_IN_LOG.sub(rb"\1<redacted>", data)


def send_debug():
    file_list = glob.glob(logger.get_logfile(config.config_logfile) + '*')
    file_list.extend(glob.glob(logger.get_accesslogfile(config.config_access_logfile) + '*'))
    for element in [logger.LOG_TO_STDOUT, logger.LOG_TO_STDERR]:
        if element in file_list:
            file_list.remove(element)
    memory_zip = BytesIO()
    with zipfile.ZipFile(memory_zip, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('settings.txt', json.dumps(config.to_dict(), sort_keys=True, indent=2))
        zf.writestr('libs.txt', json.dumps(collect_stats(), sort_keys=True, indent=2, cls=lazyEncoder))
        for fp in file_list:
            with open(fp, 'rb') as log_file:
                zf.writestr(os.path.basename(fp), redact_log(log_file.read()))
    memory_zip.seek(0)
    version = importlib.metadata.version("flask")
    if int(version.split('.')[0]) < 2:
        return send_file(memory_zip,
                         as_attachment=True,
                         attachment_filename="Calibre-Web-Automated-debug-pack.zip")
    else:
        return send_file(memory_zip,
                         as_attachment=True,
                         download_name="Calibre-Web-Automated-debug-pack.zip")
