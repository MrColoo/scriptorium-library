# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Goodreads and StoryGraph exports are parsed, matched to the library and planned safely."""

import pytest

from cps import reading_import, ub

pytestmark = pytest.mark.unit

GOODREADS = '''﻿Book Id,Title,Author,Author l-f,Additional Authors,ISBN,ISBN13,My Rating,Average Rating,Publisher,Binding,Number of Pages,Year Published,Original Publication Year,Date Read,Date Added,Bookshelves,Bookshelves with positions,Exclusive Shelf,My Review,Spoiler,Private Notes,Read Count,Owned Copies
1,"Dune (Dune, #1)",Frank Herbert,"Herbert, Frank",,"=""0441172717""","=""9780441172719""",5,4.27,Ace,Paperback,604,1990,1965,2026/03/03,2025/12/01,,,read,,,,1,0
2,The Left Hand of Darkness,Ursula K. Le Guin,"Le Guin, Ursula K.",,"=""""","=""""",4,4.1,Ace,Paperback,304,2000,1969,,2026/01/01,,,currently-reading,,,,0,0
3,Solaris,Stanisław Lem,"Lem, Stanisław","Joanna Kilmartin, Steve Cox","=""""","=""""",0,3.9,,,204,2002,1961,,2026/01/02,,,to-read,,,,0,0
4,Not In The Library,Someone Else,"Else, Someone",,"=""""","=""""",0,3,,,100,2001,2001,2026/02/02,2026/01/02,,,read,,,,1,0
5,A Book I Gave Up,Someone,"Someone",,"=""""","=""""",0,3,,,100,2001,2001,,2026/01/02,,,did-not-finish,,,,0,0
'''

STORYGRAPH = '''Title,Authors,Contributors,ISBN/UID,Format,Read Status,Date Added,Last Date Read,Dates Read,Read Count,Moods,Pace,Character- or Plot-Driven?,Strong Character Development?,Loveable Characters?,Diverse Characters?,Flawed Characters?,Star Rating,Review,Content Warnings,Content Warning Description,Tags,Owned?
Il Gattopardo,Giuseppe Tomasi di Lampedusa,,9788807900358,paperback,read,2026/01/01,2026/10/20,2026/09/01-2026/10/20,1,,,,,,,,4.5,,,,,No
Neuromancer,William Gibson,,,digital,currently-reading,2026/01/01,,,0,,,,,,,,,,,,,No
'''

LIBRARY = [
    {"id": 14, "title": "Dune", "authors": ["Frank Herbert"], "isbns": ["9780441172719"]},
    {"id": 16, "title": "The Left Hand of Darkness", "authors": ["Ursula K. Le Guin"], "isbns": []},
    {"id": 19, "title": "Solaris", "authors": ["Stanisław Lem"], "isbns": []},
    {"id": 11, "title": "Il Gattopardo", "authors": ["Giuseppe Tomasi di Lampedusa"], "isbns": ["8807900351"]},
    {"id": 18, "title": "Neuromancer", "authors": ["William Gibson"], "isbns": []},
    {"id": 30, "title": "Solaris", "authors": ["Someone Unrelated"], "isbns": []},
]


def test_goodreads_parsing():
    source, rows = reading_import.parse_csv(GOODREADS)
    assert source == "goodreads"
    assert [row["status"] for row in rows] == ["read", "reading", "to-read", "read"]  # did-not-finish skipped
    dune = rows[0]
    assert dune["isbns"] == ["9780441172719", "0441172717"]
    assert dune["date"] == "2026-03-03" and dune["rating"] == 5
    assert rows[2]["authors"] == ["Stanisław Lem", "Joanna Kilmartin", "Steve Cox"]


def test_storygraph_parsing():
    source, rows = reading_import.parse_csv(STORYGRAPH)
    assert source == "storygraph"
    assert rows[0] == {"title": "Il Gattopardo", "authors": ["Giuseppe Tomasi di Lampedusa"],
                       "isbns": ["9788807900358"], "status": "read", "date": "2026-10-20", "rating": 4.5}
    assert rows[1]["status"] == "reading"


def test_unknown_format_is_rejected():
    with pytest.raises(ValueError):
        reading_import.parse_csv("a,b,c\n1,2,3\n")


@pytest.mark.parametrize("title, expected", [
    ("Dune (Dune, #1)", "dune"), ("The Left Hand of Darkness", "left hand of darkness"),
    ("Il Gattopardo", "gattopardo"), ("Sapiens: A Brief History of Humankind", "sapiens"), ("Città invisibili", "citta invisibili"),
])
def test_normalize_title(title, expected):
    assert reading_import.normalize_title(title) == expected


def test_isbn10_to_13():
    assert reading_import.isbn10_to_13("0441172717") == "9780441172719"
    assert reading_import.isbn10_to_13("8807900351") == "9788807900358"


def test_matching_by_isbn_then_title_and_author():
    index = reading_import.build_index(LIBRARY)
    _, rows = reading_import.parse_csv(GOODREADS)
    matched, unmatched = reading_import.match(rows, index)
    assert [(row["book_id"], row["how"]) for row in matched] == [(14, "isbn"), (16, "title"), (19, "title")]
    assert [row["title"] for row in unmatched] == ["Not In The Library"]
    _, rows = reading_import.parse_csv(STORYGRAPH)
    matched, _ = reading_import.match(rows, index)
    assert [(row["book_id"], row["how"]) for row in matched] == [(11, "isbn"), (18, "title")]


def test_same_title_by_another_author_does_not_match():
    index = reading_import.build_index([LIBRARY[-1]])
    matched, unmatched = reading_import.match([{"title": "Solaris", "authors": ["Stanisław Lem"], "isbns": [],
                                                "status": "read", "date": None, "rating": None}], index)
    assert not matched and unmatched


def test_plan_never_moves_backwards():
    rows = [{"book_id": 1, "status": "read", "date": "2026-01-01"},
            {"book_id": 2, "status": "read", "date": None},
            {"book_id": 3, "status": "reading", "date": None},
            {"book_id": 4, "status": "to-read", "date": None},
            {"book_id": 5, "status": "to-read", "date": None},
            {"book_id": 1, "status": "reading", "date": None}]
    current = {2: ub.ReadBook.STATUS_FINISHED, 3: ub.ReadBook.STATUS_FINISHED, 5: ub.ReadBook.STATUS_IN_PROGRESS}
    actions = reading_import.plan(rows, current)
    assert [(a["book_id"], a["action"]) for a in actions] == [(1, "finish"), (4, "shelve")]
    current[2] = ub.ReadBook.STATUS_FINISHED
    rows[1]["date"] = "2025-05-05"
    assert ("date" in [a["action"] for a in reading_import.plan(rows, current)])
