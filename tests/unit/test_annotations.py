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
        assert [(row.source_id, row.note) for row in rows] == [("device:unknown/d2|p2", "Added a note")]

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

    def test_two_devices_keep_their_own_highlights(self, session):
        annotations.replace_koreader(1, 7, [{"id": "k1", "text": "From the Kobo"}], device="kobo-id")
        session.commit()
        annotations.replace_koreader(1, 7, [{"id": "p1", "text": "From the phone"}], device="phone-id")
        session.commit()
        assert sorted(row.text for row in _rows(session)) == ["From the Kobo", "From the phone"]
        annotations.replace_koreader(1, 7, [], device="phone-id")
        session.commit()
        assert [row.text for row in _rows(session)] == ["From the Kobo"]

    def test_highlights_from_before_the_update_are_taken_over(self, session):
        session.add(annotations.ub.ReaderAnnotation(user_id=1, book_id=7, source="koreader", source_id="k1", text="Old"))
        session.add(annotations.ub.ReaderAnnotation(user_id=1, book_id=7, source="koreader", source_id="k2", text="Gone"))
        session.commit()
        annotations.replace_koreader(1, 7, [{"id": "p1", "text": "Phone"}], device="phone-id")
        session.commit()
        assert len(_rows(session)) == 3  # another device's old highlights are left alone
        annotations.replace_koreader(1, 7, [{"id": "k1", "text": "Old"}], device="kobo-id")
        session.commit()
        annotations.replace_koreader(1, 7, [{"id": "k1", "text": "Old", "note": "Now with a note"}], device="kobo-id")
        session.commit()
        kobo = [row for row in _rows(session) if row.source_id.startswith("device:kobo-id/")]
        assert [(row.source_id, row.note) for row in kobo] == [("device:kobo-id/k1", "Now with a note")]

    def test_the_same_highlight_from_two_devices_is_shown_once(self, session, monkeypatch):
        same = {"id": "x", "text": "Shared", "pos": "/body/p[2]"}
        annotations.replace_koreader(1, 7, [same], device="kobo-id")
        annotations.replace_koreader(1, 7, [same, {"id": "y", "text": "Other", "pos": "/body/p[9]"}], device="phone-id")
        session.commit()
        book = SimpleNamespace(id=7)

        class Query:
            def filter(self, *args):
                return self

            def all(self):
                return [book]

        monkeypatch.setattr(annotations.calibre_db, "session", SimpleNamespace(query=lambda *a: Query()), raising=False)
        monkeypatch.setattr(annotations.calibre_db, "common_filters", lambda *a, **k: True, raising=False)
        groups = annotations.grouped(1)
        assert sorted(row.text for row in groups[0]["highlights"]) == ["Other", "Shared"]

    def test_id_falls_back_to_position_and_date(self):
        fields = annotations.normalize_koreader({"text": "T", "pos": "/body/p[3]", "datetime": "2026-10-01 10:00:00"})
        assert fields["source_id"] == "/body/p[3]|2026-10-01 10:00:00"
        assert annotations.normalize_koreader({"text": "no id or position"}) is None


class TestBuiltInReaderOnKOReader:
    """Highlights made in the browser go to KOReader, and what happens to them there comes back."""

    def _web(self, session, cfi="epubcfi(/6/4!/4,/6/1:0,/8/1:10)", text="Call me Ishmael. Some years", note=None):
        row = annotations.ub.ReaderAnnotation(user_id=1, book_id=7, source="web", source_id=cfi, text=text,
                                              note=note, color="yellow", position=cfi)
        session.add(row)
        session.commit()
        return row

    def test_they_are_listed_for_the_plugin(self, session, monkeypatch):
        from cps import epub_positions
        monkeypatch.setattr(epub_positions, "range_xpointers",
                            lambda path, cfi: ("/body/DocFragment[2]/body/p[1]/text().0", "/body/DocFragment[2]/body/p[2]/text().10"))
        row = self._web(session, note="A good start")
        self._web(session, cfi="epubcfi(/6/2!/4/2,/1:0,/1:3)", text=None)  # nothing to find in the book
        items = annotations.web_for_koreader(1, 7, "book.epub")
        assert len(items) == 1
        assert items[0]["id"] == "web:{}".format(row.id)
        assert (items[0]["text"], items[0]["note"], items[0]["pos0"], items[0]["pos1"]) == \
            ("Call me Ishmael. Some years", "A good start", "/body/DocFragment[2]/body/p[1]/text().0",
             "/body/DocFragment[2]/body/p[2]/text().10")
        assert "pos0" not in annotations.web_for_koreader(1, 7, None)[0]

    def test_coming_back_they_stay_the_readers(self, session):
        row = self._web(session)
        sent = [{"scriptorium_id": "web:{}".format(row.id), "id": "x", "text": row.text, "note": "Noted on the Kobo",
                 "color": "green", "pos": "/body/DocFragment[2]/body/p[1]/text().0"},
                {"id": "own", "text": "Made on the device", "pos": "/body/p[9]"}]
        assert annotations.replace_koreader(1, 7, sent, device="libra") == (1, 0)
        session.commit()
        assert [(r.source, r.note, r.color) for r in _rows(session)] == \
            [("koreader", None, None), ("web", "Noted on the Kobo", "green")]

    def test_colours_the_reader_does_not_have_are_not_taken(self, session):
        row = self._web(session)
        annotations.replace_koreader(1, 7, [{"scriptorium_id": "web:{}".format(row.id), "color": "red"}], device="libra")
        assert row.color == "yellow"
        assert annotations.reader_color("red") == "pink" and annotations.reader_color(None) == "yellow"

    def test_deleted_on_the_device_is_deleted_here(self, session):
        kept, gone = self._web(session), self._web(session, cfi="epubcfi(/6/2!/4/2,/1:0,/1:9)")
        other_book = annotations.ub.ReaderAnnotation(user_id=1, book_id=8, source="web", source_id="c", text="t")
        session.add(other_book)
        session.commit()
        sent = [{"scriptorium_id": "web:{}".format(kept.id), "note": ""}]
        assert annotations.replace_koreader(1, 7, sent, device="libra",
                                            removed_web=["web:{}".format(gone.id), "web:{}".format(other_book.id), "nonsense"]) == (0, 1)
        session.commit()
        assert sorted(r.id for r in _rows(session, "web")) == sorted([kept.id, other_book.id])


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


class TestPassageOfTheDay:
    @pytest.fixture
    def library(self, monkeypatch):
        books = {7: SimpleNamespace(id=7, title="Moby-Dick"), 8: SimpleNamespace(id=8, title="Emma")}
        query = SimpleNamespace(filter=lambda *a: query, all=lambda: [books[7], books[8]])
        monkeypatch.setattr(annotations.calibre_db, "session", SimpleNamespace(query=lambda *a: query), raising=False)
        monkeypatch.setattr(annotations.calibre_db, "common_filters", lambda: True, raising=False)
        return books

    def _add(self, session, book_id, source_id, text):
        session.add(annotations.ub.ReaderAnnotation(user_id=1, book_id=book_id, source="kobo", source_id=source_id, text=text))
        session.commit()

    def test_the_same_all_day_and_from_the_users_highlights(self, session, library):
        from datetime import date
        self._add(session, 7, "a", "Call me Ishmael. Some years ago, never mind how long precisely.")
        self._add(session, 8, "b", "Emma Woodhouse, handsome, clever, and rich, with a comfortable home.")
        self._add(session, 8, "c", "Too short.")
        days = [date(2026, 11, day) for day in range(1, 21)]
        picks = [annotations.passage_of_the_day(1, today=day)["highlight"].source_id for day in days]
        assert set(picks) == {"a", "b"}
        assert annotations.passage_of_the_day(1, today=days[0])["highlight"].source_id == picks[0]
        assert annotations.passage_of_the_day(2) is None

    def test_none_without_highlights(self, session, library):
        assert annotations.passage_of_the_day(1) is None


def test_the_passage_of_the_day_can_be_turned_off(monkeypatch):
    monkeypatch.setattr("sqlalchemy.orm.attributes.flag_modified", lambda *a: None)
    user = SimpleNamespace(view_settings={"theme": "dark"})
    assert annotations.shows_passage(user) and annotations.shows_passage(SimpleNamespace(view_settings=None))
    annotations.set_passage(user, False)
    assert not annotations.shows_passage(user) and user.view_settings["theme"] == "dark"
    annotations.set_passage(user, True)
    assert annotations.shows_passage(user) and annotations.PASSAGE_KEY not in user.view_settings
