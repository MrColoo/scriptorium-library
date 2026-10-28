# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Highlights from Kobo and KOReader are stored, updated, deleted and exported correctly."""

from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from cps import annotations, ub

pytestmark = pytest.mark.unit


@pytest.fixture
def session(monkeypatch):
    engine = create_engine("sqlite://")
    for module in (ub, annotations.ub):
        module.Base.metadata.create_all(engine)
    test_session = scoped_session(sessionmaker(bind=engine))
    for module in (ub, annotations.ub):
        monkeypatch.setattr(module, "session", test_session)
    yield test_session
    test_session.remove()


def _rows(session, source=None):
    query = session.query(annotations.ub.ReaderAnnotation)
    if source:
        query = query.filter_by(source=source)
    return sorted(query.all(), key=lambda row: row.source_id)


def _kobo(annotation_id, text="A passage", note=None, color="yellow"):
    return {"id": annotation_id, "highlightedText": text, "noteText": note, "highlightColor": color,
            "clientLastModifiedUtc": "2026-10-20T08:30:00Z",
            "location": {"span": {"chapterTitle": "Chapter 1", "startPath": "span#kobo.1.1"}}}


class TestKobo:
    def test_bookmarks_without_text_are_ignored(self):
        assert annotations.normalize_kobo({"id": "x", "highlightedText": "", "noteText": None}) is None
        assert annotations.normalize_kobo({"highlightedText": "no id"}) is None
        assert annotations.normalize_kobo("garbage") is None

    def test_normalize(self):
        fields = annotations.normalize_kobo(_kobo("a1", note="Remember this"))
        assert fields["chapter"] == "Chapter 1"
        assert fields["position"] == "span#kobo.1.1"
        assert fields["created"].year == 2026

    def test_patch_stores_updates_and_deletes(self, session):
        annotations.apply_kobo_patch(1, 7, {"updatedAnnotations": [_kobo("a1"), _kobo("a2")]})
        session.commit()
        annotations.apply_kobo_patch(1, 7, {"updatedAnnotations": [_kobo("a1", text="Edited")],
                                            "deletedAnnotationIds": ["a2"]})
        session.commit()
        rows = _rows(session)
        assert [(row.source_id, row.text) for row in rows] == [("a1", "Edited")]

    def test_other_users_are_untouched(self, session):
        annotations.apply_kobo_patch(1, 7, {"updatedAnnotations": [_kobo("a1")]})
        annotations.apply_kobo_patch(2, 7, {"deletedAnnotationIds": ["a1"]})
        session.commit()
        assert len(_rows(session)) == 1

    def test_long_text_is_clipped(self, session):
        annotations.apply_kobo_patch(1, 7, {"updatedAnnotations": [_kobo("a1", text="x" * 50000)]})
        session.commit()
        assert len(_rows(session)[0].text) == annotations.MAX_TEXT


class TestKOReader:
    def test_replace_matches_the_device(self, session):
        first = [{"id": "d1|p1", "text": "One", "chapter": "I"}, {"id": "d2|p2", "text": "Two"}]
        annotations.replace_koreader(1, 7, first)
        session.commit()
        annotations.replace_koreader(1, 7, [{"id": "d2|p2", "text": "Two", "note": "Added a note"}])
        session.commit()
        rows = _rows(session, "koreader")
        assert [(row.source_id, row.note) for row in rows] == [("d2|p2", "Added a note")]

    def test_replace_only_touches_that_book(self, session):
        annotations.replace_koreader(1, 7, [{"id": "a", "text": "Seven"}])
        annotations.replace_koreader(1, 8, [{"id": "b", "text": "Eight"}])
        annotations.replace_koreader(1, 7, [])
        session.commit()
        assert [row.book_id for row in _rows(session)] == [8]

    def test_kobo_highlights_survive_a_koreader_sync(self, session):
        annotations.apply_kobo_patch(1, 7, {"updatedAnnotations": [_kobo("k1")]})
        annotations.replace_koreader(1, 7, [])
        session.commit()
        assert [row.source for row in _rows(session)] == ["kobo"]

    def test_id_falls_back_to_position_and_date(self):
        fields = annotations.normalize_koreader({"text": "T", "pos": "/body/p[3]", "datetime": "2026-10-01 10:00:00"})
        assert fields["source_id"] == "/body/p[3]|2026-10-01 10:00:00"
        assert annotations.normalize_koreader({"text": "no id or position"}) is None


def test_markdown_export():
    book = SimpleNamespace(title="Dune", authors=[SimpleNamespace(name="Frank Herbert")])
    rows = [SimpleNamespace(chapter="Book One", text="Fear is the mind-killer.\nI will face my fear.", note=None),
            SimpleNamespace(chapter="Book One", text=None, note="Reread this"),
            SimpleNamespace(chapter=None, text="The spice must flow.", note="Classic")]
    markdown = annotations.to_markdown([{"book": book, "highlights": rows}])
    assert markdown.startswith("# Dune — Frank Herbert\n")
    assert "## Book One" in markdown
    assert "> Fear is the mind-killer.\n> I will face my fear." in markdown
    assert "**Note:** Reread this" in markdown
    assert markdown.count("## Book One") == 1
