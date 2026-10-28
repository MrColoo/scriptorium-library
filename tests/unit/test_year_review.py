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
