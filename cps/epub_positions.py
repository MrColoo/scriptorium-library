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


# ---------- Highlights: finding the words in the book ----------
#
# A highlight made on a device carries its words and roughly where they start. The built-in reader needs
# an exact CFI range instead, so the words are looked up in the chapter's text. Whitespace is left out
# on both sides: devices turn line breaks and runs of spaces into one space or a new line, and paragraphs
# may sit side by side in the markup with nothing between them.

_SKIP_CHARS = {"­", "​", "‌", "‍", "﻿"}
_MIN_WORDS = 2
_found = {}


def _squeeze(text):
    return "".join(char for char in text if not char.isspace() and char not in _SKIP_CHARS)


def _utf16(text):
    """Offsets in the reader are counted in UTF-16 units, as in JavaScript."""
    return len(text.encode("utf-16-le")) // 2


class _Chapter:
    """The text of one spine item without whitespace, and where each piece comes from.

    epub.js numbers the text nodes of an element on their own (step 1 is the first text node, 3 the
    second and so on), whatever elements stand between them, so that is how they are counted here.
    """

    def __init__(self, body):
        self.body = body
        self.parts = []  # (start in self.text, element, index of the text node in it, raw text)
        chunks, length = [], 0
        counters = {}

        def add(owner, raw):
            nonlocal length
            index = counters.get(owner, 0)
            counters[owner] = index + 1
            squeezed = _squeeze(raw)
            if squeezed:
                self.parts.append((length, owner, index, raw))
                chunks.append(squeezed)
                length += len(squeezed)

        def walk(node):
            if node.text:
                add(node, node.text)
            for child in node:
                if isinstance(child.tag, str):
                    walk(child)
                if child.tail:
                    add(node, child.tail)

        walk(body)
        self.text = "".join(chunks)
        self.starts = [part[0] for part in self.parts]

    def start_of(self, element):
        """Where an element's text begins, or None."""
        for start, owner, _index, _raw in self.parts:
            if owner is element or element in owner.iterancestors():
                return start
        return None

    def point(self, position, end=False):
        """(element, text node index, UTF-16 offset) of a character of self.text, or of the end of one."""
        import bisect
        target = position - 1 if end else position
        part = self.parts[bisect.bisect_right(self.starts, target) - 1]
        start, owner, index, raw = part
        seen = start
        for offset, char in enumerate(raw):
            if char.isspace() or char in _SKIP_CHARS:
                continue
            if seen == target:
                return owner, index, _utf16(raw[:offset + 1] if end else raw[:offset])
            seen += 1
        return owner, index, _utf16(raw)


def _element_steps(element, html):
    steps = []
    node = element
    while node is not None and node is not html:
        parent = node.getparent()
        steps.append(2 * (_elements(parent).index(node) + 1))
        node = parent
    return list(reversed(steps))


def _range_cfi(book, index, chapter, first, last):
    start, end = chapter.point(first), chapter.point(last, end=True)
    html = chapter.body.getparent()
    start_steps = _element_steps(start[0], html)
    end_steps = _element_steps(end[0], html)
    common = 0
    while common < min(len(start_steps), len(end_steps)) and start_steps[common] == end_steps[common]:
        common += 1

    def relative(steps, point):
        return "".join("/{}".format(step) for step in steps[common:]) + "/{}:{}".format(2 * point[1] + 1, point[2])

    return "epubcfi(/{}/{}!/{},{},{})".format(book.spine_step, 2 * index, "/".join(str(s) for s in start_steps[:common]),
                                              relative(start_steps, start), relative(end_steps, end))


def _hint(book, xpointer):
    """(spine index, element) a KOReader position points at, as far as it goes."""
    match = _XPOINTER.match(xpointer or "")
    if not match:
        return None, None
    index = int(match.group(1))
    body = book.body(index)
    if body is None:
        return None, None
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
    return index, node


def highlight_ranges(path, highlights):
    """The built-in reader's CFI range for each highlight made elsewhere, or None where the words are not found.

    highlights: [(text, xpointer or None)]. With KOReader's start position the chapter it names is searched
    first and the match nearest to it wins; without one (a Kobo highlight) the whole book is searched.
    """
    results = [None] * len(highlights)
    try:
        key = (path, os.path.getmtime(path))
        book = _book(path)
    except Exception as e:
        log.debug("Cannot look for highlights in %s: %s", path, e)
        return results
    chapters = {}

    def chapter(index):
        if index not in chapters:
            body = book.body(index)
            chapters[index] = _Chapter(body) if body is not None else None
        return chapters[index]

    for number, (text, xpointer) in enumerate(highlights):
        wanted = _squeeze(text or "")
        if len((text or "").split()) < _MIN_WORDS and len(wanted) < 12:
            continue  # a word or two could be anywhere
        cache_key = (key, wanted, xpointer)
        if cache_key in _found:
            results[number] = _found[cache_key]
            continue
        try:
            hinted, element = _hint(book, xpointer)
            order = list(range(1, len(book.items) + 1))
            if hinted:
                order.remove(hinted)
                order.insert(0, hinted)
            cfi = None
            for index in order:
                current = chapter(index)
                if current is None:
                    continue
                matches = []
                position = current.text.find(wanted)
                while position != -1 and len(matches) < 50:
                    matches.append(position)
                    position = current.text.find(wanted, position + 1)
                if not matches:
                    continue
                best = matches[0]
                if index == hinted and element is not None:
                    near = current.start_of(element)
                    if near is not None:
                        best = min(matches, key=lambda found: abs(found - near))
                cfi = _range_cfi(book, index, current, best, best + len(wanted))
                break
        except Exception as e:
            log.debug("Could not place a highlight in %s: %s", path, e)
            cfi = None
        if len(_found) > 2000:
            _found.clear()
        _found[cache_key] = results[number] = cfi
    return results


def range_xpointers(path, cfi_range):
    """KOReader's positions for the start and the end of a CFI range of the built-in reader: (pos0, pos1).

    Either is None when it cannot be worked out; they are exact to the character only in plain text.
    """
    match = re.match(r"^epubcfi\(([^,]*),([^,]*),([^,]*)\)$", cfi_range or "")
    if not match:
        return cfi_to_xpointer(path, cfi_range), None
    base, start, end = match.groups()
    return (cfi_to_xpointer(path, "epubcfi({}{})".format(base, start)),
            cfi_to_xpointer(path, "epubcfi({}{})".format(base, end)))
