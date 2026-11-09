# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Positions translate between the built-in reader (EPUB CFI) and KOReader (XPointer) through the book."""

import zipfile

import pytest

from cps import epub_positions

pytestmark = pytest.mark.unit

CHAPTER_2 = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Two</title></head>
<body>
  <h1>Chapter Two</h1>
  <div class="scene"><p>First in the scene.</p><p>Second in the scene.</p></div>
  <p>Call me Ishmael.</p>
  <p>Some years ago, never mind how long precisely.</p>
  <!-- a comment is not an element -->
  <div><div><p>Deep inside.</p></div></div>
</body></html>"""


@pytest.fixture
def epub(tmp_path):
    path = tmp_path / "book.epub"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr("OEBPS/content.opf",
                   '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="2.0">'
                   '<metadata/><manifest><item id="a" href="Text/one.xhtml" media-type="application/xhtml+xml"/>'
                   '<item id="b" href="Text/two%20words.xhtml" media-type="application/xhtml+xml"/></manifest>'
                   '<spine><itemref idref="a"/><itemref idref="b"/></spine></package>')
        z.writestr("OEBPS/Text/one.xhtml", '<html xmlns="http://www.w3.org/1999/xhtml"><body><p>One.</p></body></html>')  # no head
        z.writestr("OEBPS/Text/two words.xhtml", CHAPTER_2)
    return str(path)


@pytest.mark.parametrize("cfi, xpointer", [
    # h1 is element 1 (step 2), the scene div 2 (4), "Call me Ishmael." 3 (6), "Some years ago" 4 (8)
    ("epubcfi(/6/4!/4/6/1:5)", "/body/DocFragment[2]/body/p[1]/text().5"),
    ("epubcfi(/6/4!/4/8)", "/body/DocFragment[2]/body/p[2]"),
    ("epubcfi(/6/4!/4/4/4/1:0)", "/body/DocFragment[2]/body/div[1]/p[2]/text().0"),
    ("epubcfi(/6/4!/4/10/2/2)", "/body/DocFragment[2]/body/div[2]/div[1]/p[1]"),
    ("epubcfi(/6/2!/2/2/1:2)", "/body/DocFragment[1]/body/p[1]/text().2"),  # no <head>: body is element 1
])
def test_both_directions(epub, cfi, xpointer):
    assert epub_positions.cfi_to_xpointer(epub, cfi) == xpointer
    assert epub_positions.xpointer_to_cfi(epub, xpointer) == cfi


def test_koreader_notation_without_indexes(epub):
    assert epub_positions.xpointer_to_cfi(epub, "/body/DocFragment[2]/body/div/p") == "epubcfi(/6/4!/4/4/2)"
    assert epub_positions.xpointer_to_cfi(epub, "/body/DocFragment[2]") == "epubcfi(/6/4!/4)"


def test_positions_that_do_not_exist_stop_at_the_nearest_element(epub):
    assert epub_positions.xpointer_to_cfi(epub, "/body/DocFragment[2]/body/p[2]/span[4]") == "epubcfi(/6/4!/4/8)"
    assert epub_positions.cfi_to_xpointer(epub, "epubcfi(/6/4!/4/40)") == "/body/DocFragment[2]/body"


@pytest.mark.parametrize("value", [None, "", "nonsense", "epubcfi(/6/40!/4/2)", "/body/DocFragment[9]/body/p[1]"])
def test_unknown_positions_give_nothing(epub, value):
    assert epub_positions.cfi_to_xpointer(epub, value) is None or value.startswith("/body")
    assert epub_positions.xpointer_to_cfi(epub, value) is None or (value or "").startswith("epubcfi")


def test_a_damaged_file_gives_nothing(tmp_path):
    broken = tmp_path / "broken.epub"
    broken.write_bytes(b"not a zip")
    assert epub_positions.cfi_to_xpointer(str(broken), "epubcfi(/6/4!/4/6)") is None
    assert epub_positions.xpointer_to_cfi(str(broken), "/body/DocFragment[2]/body/p[1]") is None
