# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Your year in books: the numbers behind the slides."""

from collections import Counter
from datetime import date, datetime, timezone

import pytest

from cps import year_review

pytestmark = pytest.mark.unit


def _book(book_id, when, authors=("A",), tags=(), series=()):
    return {"id": book_id, "title": "Book {}".format(book_id), "authors": list(authors), "tags": list(tags),
            "series": list(series), "when": datetime(2026, *when, tzinfo=timezone.utc)}


def test_longest_streak():
    days = [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3), date(2026, 1, 10), date(2026, 1, 11), date(2026, 1, 2)]
    assert year_review.longest_streak(days) == 3
    assert year_review.longest_streak([]) == 0


@pytest.mark.parametrize("hours, expected", [
    ({7: 3, 22: 1}, "morning"), ({14: 2}, "afternoon"), ({20: 5, 8: 1}, "evening"), ({1: 2, 23: 2, 15: 1}, "night"), ({}, None),
])
def test_time_of_day(hours, expected):
    assert year_review.time_of_day(Counter(hours)) == expected


def test_reading_styles():
    many = [_book(i, (1, 1)) for i in range(24)]
    assert year_review.reading_style(many) == "voracious"
    saga = [_book(1, (1, 1), series=["Dune"]), _book(2, (2, 1), series=["Dune"]), _book(3, (3, 1), authors=["B"])]
    assert year_review.reading_style(saga) == "saga"
    devotee = [_book(1, (1, 1)), _book(2, (2, 1)), _book(3, (3, 1), authors=["B"])]
    assert year_review.reading_style(devotee) == "devotee"
    explorer = [_book(i, (1, 1), authors=[str(i)], tags=[t]) for i, t in enumerate("abcde")]
    assert year_review.reading_style(explorer) == "explorer"
    assert year_review.reading_style([_book(1, (1, 1))]) == "savourer"
    assert year_review.reading_style([]) is None


def test_pick_quote_prefers_a_noted_card_sized_highlight():
    highlights = [{"text": "short"}, {"text": "x" * 500}, {"text": "A sentence long enough to sit nicely on a card."},
                  {"text": "Another sentence that is long enough for the card, with a note.", "note": "Yes"}]
    assert year_review.pick_quote(highlights)["note"] == "Yes"
    assert year_review.pick_quote([{"text": "tiny"}])["text"] == "tiny"
    assert year_review.pick_quote([{"text": None}]) is None


def test_summarize():
    finished = [_book(2, (3, 5, 21)), _book(1, (1, 10, 22), tags=["Sci-fi"], series=["Dune"]),
                _book(3, (3, 6, 21), authors=["B"], tags=["Sci-fi", "Classic"])]
    activity = [datetime(2026, 3, 7, 21, tzinfo=timezone.utc), datetime(2025, 12, 31, 12, tzinfo=timezone.utc)]
    summary = year_review.summarize(2026, finished, finished + [_book(4, (4, 1))], 600, activity,
                                    [{"text": "A highlight of a decent length, fit for the card."}], 12)
    assert summary["finished"] == 3 and summary["started"] == 4
    assert summary["first"]["id"] == 1 and summary["last"]["id"] == 3
    assert summary["authors"][0] == {"name": "A", "count": 2}
    assert summary["genres"][0] == {"name": "Sci-fi", "count": 2}
    assert summary["series"] == 1
    assert summary["busiest_month"] == 3
    assert summary["streak"] >= 2
    assert all(day.startswith("2026-") for day in summary["days"])
    assert summary["added"] == 12 and summary["minutes"] == 600
    assert year_review.has_story(summary)


def test_empty_year_has_no_story():
    summary = year_review.summarize(2026, [], [], 0, [], [], 0)
    assert summary["first"] is None and summary["style"] is None
    assert not year_review.has_story(summary)


def _pages(day, hour, minutes, book="Dune", key=1, book_id=None, first_page=1):
    """KOReader statistics rows: one page a minute from `hour` on `day` (local time)."""
    card = {"key": key, "id": book_id, "title": book, "authors": ["Frank Herbert"]}
    start = datetime(2026, *day, hour)
    return [{"when": start.replace(minute=m % 60, hour=hour + m // 60), "seconds": 60, "book": card,
             "page": first_page + m} for m in range(minutes)]


def test_koreader_statistics_feed_the_year():
    pages = _pages((3, 2), 22, 120) + _pages((3, 3), 22, 30, first_page=200) \
        + _pages((5, 1), 8, 50, book="Emma", key=2, book_id=9) \
        + [dict(_pages((1, 1), 9, 1)[0], when=datetime(2025, 12, 31, 23))]  # last year: left out
    summary = year_review.summarize(2026, [], [], 10, [], [], 0, pages)
    assert summary["minutes"] == 10 + 200
    assert summary["pages_read"] == 200
    assert summary["started"] == 2  # Dune and Emma, read in KOReader
    assert summary["active_days"] == 3
    assert summary["streak"] == 2
    assert summary["clock"][22] == 90 and summary["clock"][23] == 60 and summary["clock"][8] == 50
    assert summary["peak_hour"] == 22
    assert summary["time_of_day"] == "evening"
    assert summary["top_book"] == {"id": None, "title": "Dune", "authors": ["Frank Herbert"], "minutes": 150, "pages": 150}
    assert summary["biggest_day"] == {"date": "2026-03-02", "minutes": 120}
    assert year_review.has_story(summary)


def test_clock_rays_point_midnight_up():
    rays = year_review.clock_rays([0] * 6 + [30] + [0] * 17)
    assert rays[0]["x1"] == rays[0]["x2"] == 130 and rays[0]["y2"] < rays[0]["y1"]
    assert rays[6]["peak"] and rays[6]["x2"] > rays[0]["x2"]
    assert not year_review.clock_rays([0] * 24)[6]["peak"]
