# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Ranking for "More like this" on the book page."""

import pytest

from cps import similar

pytestmark = pytest.mark.unit


def _rank(links, authors=frozenset({1}), tags=frozenset({10, 11}), series=frozenset(), tag_counts=None, size=100):
    return similar.rank(book_id=1, authors=set(authors), tags=set(tags), publishers={5}, languages={7},
                        series=set(series), links=links, tag_counts=tag_counts or {10: 3, 11: 60},
                        library_size=size)


def test_same_author_ranks_first():
    links = {2: {"tags": {10}}, 3: {"authors": {1}}}
    assert _rank(links) == [3, 2]


def test_rare_tag_beats_common_tag():
    links = {2: {"tags": {11}}, 3: {"tags": {10}}}
    assert _rank(links) == [3, 2]


def test_publisher_and_language_only_break_ties():
    links = {2: {"tags": {10}}, 3: {"tags": {10}, "publishers": {5}, "languages": {7}},
             4: {"publishers": {5}, "languages": {7}}}
    assert _rank(links) == [3, 2]


def test_same_series_and_the_book_itself_are_left_out():
    links = {1: {"authors": {1}}, 2: {"authors": {1}, "series": {9}}, 3: {"tags": {11}}}
    assert _rank(links, series={9}) == [3]


@pytest.mark.parametrize("count, weight", [(0, 0.0), (3, 3.0), (15, 2.0), (40, 1.0), (90, 0.5)])
def test_tag_weight(count, weight):
    assert similar.tag_weight(count, 100) == weight
