# -*- coding: utf-8 -*-
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Translate a reading position between the built-in reader and KOReader, through the EPUB file.

Both point at the same place in the same book, in two notations:

- the built-in reader (epub.js) uses an EPUB CFI: ``epubcfi(/6/26!/4/52/1:0)`` is the 13th item of the
  spine, then element child 26 of the body (even steps count elements), then a text offset;
- KOReader (crengine) uses an XPointer: ``/body/DocFragment[13]/body/p[26]/text().0`` is the 13th spine
  item, then elements by tag name and position among siblings of the same name.

Translating needs the chapter's own markup, which the server has. The position is kept to the element
(a paragraph, usually) and to the character only when the text node is unambiguous; when the two
files differ (a KEPUB on the device, an EPUB in the browser) the XPointer may not exist on the device,
and the plugin then falls back to the percentage that travels with it.
"""

import os
import posixpath
import re
import zipfile
from urllib.parse import unquote

from lxml import etree

from . import logger

log = logger.create()

_PARSER = etree.XMLParser(recover=True, resolve_entities=False, no_network=True, load_dtd=False)
_HTML_PARSER = etree.HTMLParser(recover=True, no_network=True)
_CFI = re.compile(r"^epubcfi\((/\d+(?:\[[^\]]*\])?/\d+(?:\[[^\]]*\])?)!((?:/\d+(?:\[[^\]]*\])?)*)(?::(\d+))?(?:\[[^\]]*\])?")
_XPOINTER = re.compile(r"^/body/DocFragment\[(\d+)\](?:/body((?:/[\w.:-]+(?:\[\d+\])?)*?))?(?:/text\(\)(?:\[(\d+)\])?(?:\.(\d+))?)?(?:\.\d+)?$")
_cache = {}


def _elements(node):
    return [child for child in node if isinstance(child.tag, str)]


def _name(node):
    return etree.QName(node).localname.lower()


class _Book:
    """The spine of an EPUB file and the markup of its items."""

    def __init__(self, path):
        self.path = path
        with zipfile.ZipFile(path) as archive:
            container = etree.fromstring(archive.read("META-INF/container.xml"), _PARSER)
            rootfile = next(node for node in container.iter() if isinstance(node.tag, str) and _name(node) == "rootfile")
            opf_path = rootfile.get("full-path")
            package = etree.fromstring(archive.read(opf_path), _PARSER)
        base = posixpath.dirname(opf_path)
        manifest = {}
        spine = None
        for node in package.iter():
            if not isinstance(node.tag, str):
                continue
            if _name(node) == "item" and node.get("id"):
                manifest[node.get("id")] = posixpath.normpath(posixpath.join(base, unquote(node.get("href") or "")))
            elif _name(node) == "spine":
                spine = node
        if spine is None:
            raise ValueError("no spine")
        children = _elements(package)
        self.spine_step = 2 * (children.index(spine) + 1) if spine in children else 6
        self.items = [manifest.get(ref.get("idref")) for ref in _elements(spine) if _name(ref) == "itemref"]

    def body(self, index):
        """The <body> of the spine item at a 1-based index, or None."""
        if not 1 <= index <= len(self.items) or not self.items[index - 1]:
            return None
        with zipfile.ZipFile(self.path) as archive:
            data = archive.read(self.items[index - 1])
        root = etree.fromstring(data, _PARSER)
        if root is None:
            root = etree.fromstring(data, _HTML_PARSER)
        if root is None:
            return None
        for node in root.iter():
            if isinstance(node.tag, str) and _name(node) == "body":
                return node
        return None


def _book(path):
    """Parsed spine of the EPUB at path, cached while the file does not change."""
    key = (path, os.path.getmtime(path))
    book = _cache.get(key)
    if book is None:
        if len(_cache) > 32:
            _cache.clear()
        book = _cache[key] = _Book(path)
    return book


def _steps(text):
    return [int(step.split("[")[0]) for step in text.split("/") if step]


def _plain_text(text):
    """A text node both engines count the same way: no line breaks or runs of spaces to collapse."""
    return bool(text) and "\n" not in text and "  " not in text and text == text.lstrip()


def cfi_to_xpointer(path, cfi):
    """KOReader's XPointer for a position of the built-in reader, or None."""
    try:
        match = _CFI.match(cfi or "")
        if not match:
            return None
        spine_steps, inner, offset = _steps(match.group(1)), _steps(match.group(2)), match.group(3)
        index = spine_steps[-1] // 2
        body = _book(path).body(index)
        if body is None or not inner:
            return None
        # The first inner step leads from <html> to <body>; the rest walk down from the body.
        node, chain, text_slot = body, [], None
        for step in inner[1:]:
            if step % 2:  # a text position, between elements
                text_slot = step
                break
            children = _elements(node)
            if step // 2 > len(children):
                break
            node = children[step // 2 - 1]
            chain.append(node)
        parts = []
        for element in chain:
            parent = element.getparent()
            same = [child for child in _elements(parent) if _name(child) == _name(element)]
            parts.append("{}[{}]".format(_name(element), same.index(element) + 1))
        xpointer = "/body/DocFragment[{}]/body".format(index) + "".join("/" + part for part in parts)
        if text_slot == 1 and offset is not None and _plain_text(node.text) and int(offset) <= len(node.text):
            xpointer += "/text().{}".format(int(offset))
        return xpointer
    except Exception as e:  # a damaged or unusual file: no exact position, the percentage still works
        log.debug("Could not translate %s in %s: %s", cfi, path, e)
        return None


def xpointer_to_cfi(path, xpointer):
    """The built-in reader's CFI for a KOReader position, or None."""
    try:
        match = _XPOINTER.match(xpointer or "")
        if not match:
            return None
        index = int(match.group(1))
        book = _book(path)
        body = book.body(index)
        if body is None:
            return None
        html = body.getparent()
        steps = [2 * (_elements(html).index(body) + 1)]
        node = body
        for part in (match.group(2) or "").split("/"):
            if not part:
                continue
            name, _, position = part.partition("[")
            position = int(position.rstrip("]") or 1) if position else 1
            same = [child for child in _elements(node) if _name(child) == name.lower()]
            if len(same) < position:
                break
            node = same[position - 1]
            steps.append(2 * (_elements(node.getparent()).index(node) + 1))
        cfi = "epubcfi(/{}/{}!/{}".format(book.spine_step, 2 * index, "/".join(str(step) for step in steps))
        text_index, offset = match.group(3), match.group(4)
        if offset is not None and (text_index or "1") == "1" and _plain_text(node.text) and int(offset) <= len(node.text):
            cfi += "/1:{}".format(int(offset))
        return cfi + ")"
    except Exception as e:
        log.debug("Could not translate %s in %s: %s", xpointer, path, e)
        return None
