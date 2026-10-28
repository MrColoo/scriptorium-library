# -*- coding: utf-8 -*-
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Books like this one, ranked from the library itself, with no outside service.

A candidate scores for each author it shares with the book, for each tag it shares (rare tags count
more than ones half the library has), for the same publisher and the same language. Books of the
same series are left out: the book page already links to the series.
"""

from sqlalchemy import func

from . import calibre_db, db, logger

log = logger.create()

AUTHOR_WEIGHT = 4.0
PUBLISHER_WEIGHT = 1.0
LANGUAGE_WEIGHT = 0.5


def tag_weight(books_with_tag, library_size):
    """Rare tags say more about a book than ones half the library has."""
    if library_size <= 0 or books_with_tag <= 0:
        return 0.0
    share = books_with_tag / library_size
    if share <= 0.05:
        return 3.0
    if share <= 0.2:
        return 2.0
    if share <= 0.5:
        return 1.0
    return 0.5


def rank(book_id, authors, tags, publishers, languages, series, links, tag_counts, library_size):
    """Pure scoring. links maps candidate id -> {"authors", "tags", "publishers", "languages", "series"} sets."""
    scores = {}
    for candidate, info in links.items():
        if candidate == book_id or (series and info.get("series", set()) & series):
            continue
        score = AUTHOR_WEIGHT * len(info.get("authors", set()) & authors)
        score += sum(tag_weight(tag_counts.get(tag, 0), library_size) for tag in info.get("tags", set()) & tags)
        if not score:
            continue  # a shared publisher or language alone is not a reason
        score += PUBLISHER_WEIGHT * bool(info.get("publishers", set()) & publishers)
        score += LANGUAGE_WEIGHT * bool(info.get("languages", set()) & languages)
        scores[candidate] = score
    return sorted(scores, key=lambda candidate: (-scores[candidate], -candidate))


def for_book(book, limit=6):
    """Up to `limit` books similar to `book` that the current user may see."""
    try:
        session = calibre_db.session
        authors = {a.id for a in book.authors}
        tags = {t.id for t in book.tags}
        if not authors and not tags:
            return []
        publishers = {p.id for p in book.publishers}
        languages = {lang.id for lang in book.languages}
        series = {s.id for s in book.series}

        links = {}

        def add(table, column, key, values):
            if not values:
                return
            for candidate, value in session.query(table.c.book, getattr(table.c, column)) \
                    .filter(getattr(table.c, column).in_(values)):
                links.setdefault(candidate, {}).setdefault(key, set()).add(value)

        add(db.books_authors_link, "author", "authors", authors)
        add(db.books_tags_link, "tag", "tags", tags)
        candidates = [candidate for candidate in links if candidate != book.id]
        if not candidates:
            return []
        for table, column, key, values in ((db.books_publishers_link, "publisher", "publishers", publishers),
                                           (db.books_languages_link, "lang_code", "languages", languages),
                                           (db.books_series_link, "series", "series", series)):
            if values:
                for candidate, value in session.query(table.c.book, getattr(table.c, column)) \
                        .filter(table.c.book.in_(candidates), getattr(table.c, column).in_(values)):
                    links.setdefault(candidate, {}).setdefault(key, set()).add(value)

        tag_counts = dict(session.query(db.books_tags_link.c.tag, func.count(db.books_tags_link.c.book))
                          .filter(db.books_tags_link.c.tag.in_(tags)).group_by(db.books_tags_link.c.tag)) if tags else {}
        library_size = session.query(func.count(db.Books.id)).scalar() or 0

        ranked = rank(book.id, authors, tags, publishers, languages, series, links, tag_counts, library_size)
        if not ranked:
            return []
        shortlist = ranked[:limit * 3]
        visible = {b.id: b for b in session.query(db.Books)
                   .filter(db.Books.id.in_(shortlist))
                   .filter(calibre_db.common_filters()).all()}
        return [visible[candidate] for candidate in shortlist if candidate in visible][:limit]
    except Exception as e:
        log.debug("Could not find similar books for %s: %s", getattr(book, "id", "?"), e)
        return []
