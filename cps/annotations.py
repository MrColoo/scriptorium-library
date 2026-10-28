# -*- coding: utf-8 -*-
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Highlights and notes from reading devices, and the Highlights page.

- Kobo: the device sends its annotations to the reading-services API when it syncs; they are stored
  as they arrive (updated and deleted ones included), whether or not Hardcover is configured.
- KOReader: the Scriptorium plugin sends every highlight of the open book with its progress; the list
  replaces what was stored for that book, so deletions on the device carry over.

Everything lives in the reader_annotation table, one row per highlight.
"""

from datetime import datetime, timezone

from flask import Blueprint, Response, request
from flask_babel import gettext as _
from sqlalchemy import func

from . import calibre_db, db, logger, ub
from .cw_login import current_user
from .render_template import render_title_template
from .usermanagement import user_login_required

log = logger.create()

annotations = Blueprint('annotations', __name__)

SOURCES = ("kobo", "koreader")
MAX_TEXT = 20000
MAX_SHORT = 500
MAX_ITEMS = 10000


def _clip(value, limit):
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def _parse_time(value):
    """UTC datetime from ISO strings ("2026-10-28T20:15:03Z") or KOReader's "2026-10-28 21:15:03"."""
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    for candidate in (text, text.replace(" ", "T", 1)):
        try:
            moment = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)
    return None


# ---------- Device payloads ----------

def normalize_kobo(annotation):
    """Fields we keep from one Kobo annotation, or None for bookmarks without text."""
    if not isinstance(annotation, dict):
        return None
    source_id = _clip(annotation.get("id"), MAX_SHORT)
    text = _clip(annotation.get("highlightedText"), MAX_TEXT)
    note = _clip(annotation.get("noteText"), MAX_TEXT)
    if not source_id or not (text or note):
        return None
    span = ((annotation.get("location") or {}).get("span") or {}) if isinstance(annotation.get("location"), dict) else {}
    return {
        "source_id": source_id,
        "text": text,
        "note": note,
        "color": _clip(annotation.get("highlightColor"), 32),
        "chapter": _clip(span.get("chapterTitle"), MAX_SHORT),
        "position": _clip(span.get("startPath") or span.get("chapterFilename"), MAX_SHORT),
        "created": _parse_time(annotation.get("clientCreatedUtc") or annotation.get("clientLastModifiedUtc")),
    }


def normalize_koreader(item):
    """Fields we keep from one highlight sent by the KOReader plugin, or None."""
    if not isinstance(item, dict):
        return None
    text = _clip(item.get("text"), MAX_TEXT)
    note = _clip(item.get("note"), MAX_TEXT)
    position = _clip(item.get("pos"), MAX_SHORT)
    source_id = _clip(item.get("id"), MAX_SHORT) or (position and "{}|{}".format(position, item.get("datetime") or ""))
    if not source_id or not (text or note):
        return None
    return {
        "source_id": source_id,
        "text": text,
        "note": note,
        "color": _clip(item.get("color"), 32),
        "chapter": _clip(item.get("chapter"), MAX_SHORT),
        "position": position,
        "created": _parse_time(item.get("datetime")),
    }


def _upsert(user_id, book_id, source, fields):
    row = ub.session.query(ub.ReaderAnnotation).filter(
        ub.ReaderAnnotation.user_id == int(user_id),
        ub.ReaderAnnotation.source == source,
        ub.ReaderAnnotation.source_id == fields["source_id"]).first()
    if row is None:
        row = ub.ReaderAnnotation(user_id=int(user_id), book_id=int(book_id), source=source,
                                  source_id=fields["source_id"])
        ub.session.add(row)
    row.book_id = int(book_id)
    for key in ("text", "note", "color", "chapter", "position"):
        setattr(row, key, fields[key])
    if fields.get("created"):
        row.created = fields["created"]
    return row


def apply_kobo_patch(user_id, book_id, data):
    """Store a Kobo PATCH /annotations body. Returns (stored, deleted). The caller commits."""
    if not isinstance(data, dict):
        return 0, 0
    stored = deleted = 0
    for annotation in (data.get("updatedAnnotations") or [])[:MAX_ITEMS]:
        fields = normalize_kobo(annotation)
        if fields:
            _upsert(user_id, book_id, "kobo", fields)
            stored += 1
    deleted_ids = [str(i) for i in (data.get("deletedAnnotationIds") or [])[:MAX_ITEMS] if i]
    if deleted_ids:
        deleted = ub.session.query(ub.ReaderAnnotation).filter(
            ub.ReaderAnnotation.user_id == int(user_id),
            ub.ReaderAnnotation.source == "kobo",
            ub.ReaderAnnotation.source_id.in_(deleted_ids)).delete(synchronize_session=False)
    return stored, deleted


def replace_koreader(user_id, book_id, items):
    """Make the stored KOReader highlights of a book match the list the device sent. The caller commits."""
    wanted = {}
    for item in (items or [])[:MAX_ITEMS]:
        fields = normalize_koreader(item)
        if fields:
            wanted[fields["source_id"]] = fields
    existing = ub.session.query(ub.ReaderAnnotation).filter(
        ub.ReaderAnnotation.user_id == int(user_id),
        ub.ReaderAnnotation.book_id == int(book_id),
        ub.ReaderAnnotation.source == "koreader").all()
    removed = 0
    for row in existing:
        if row.source_id not in wanted:
            ub.session.delete(row)
            removed += 1
    for fields in wanted.values():
        _upsert(user_id, book_id, "koreader", fields)
    return len(wanted), removed


def store_kobo_request(user, entitlement_id, data):
    """Store the annotations of a Kobo PATCH for the signed-in user; never raises."""
    try:
        if user is None or not getattr(user, "is_authenticated", False) or getattr(user, "is_anonymous", True):
            return
        book = calibre_db.get_book_by_uuid(entitlement_id)
        if book is None:
            return
        stored, deleted = apply_kobo_patch(user.id, book.id, data)
        if stored or deleted:
            ub.session_commit("Kobo highlights for book {}: {} stored, {} deleted".format(book.id, stored, deleted))
    except Exception as e:
        log.warning("Could not store Kobo highlights: %s", e)
        ub.session.rollback()


# ---------- Reading them back ----------

def count_for_book(user_id, book_id):
    try:
        return ub.session.query(func.count(ub.ReaderAnnotation.id)).filter(
            ub.ReaderAnnotation.user_id == int(user_id), ub.ReaderAnnotation.book_id == int(book_id)).scalar() or 0
    except Exception as e:
        log.debug("Could not count highlights: %s", e)
        return 0


def grouped(user_id, book_id=None, query=None):
    """[{book, highlights: [rows], latest}] newest first, only books the user may see."""
    rows = ub.session.query(ub.ReaderAnnotation).filter(ub.ReaderAnnotation.user_id == int(user_id))
    if book_id is not None:
        rows = rows.filter(ub.ReaderAnnotation.book_id == int(book_id))
    if query:
        like = "%{}%".format(query.replace("%", r"\%").replace("_", r"\_"))
        rows = rows.filter((ub.ReaderAnnotation.text.ilike(like, escape="\\"))
                           | (ub.ReaderAnnotation.note.ilike(like, escape="\\"))
                           | (ub.ReaderAnnotation.chapter.ilike(like, escape="\\")))
    by_book = {}
    for row in rows.all():
        by_book.setdefault(row.book_id, []).append(row)
    if not by_book:
        return []
    books = {b.id: b for b in calibre_db.session.query(db.Books)
             .filter(db.Books.id.in_(list(by_book))).filter(calibre_db.common_filters()).all()}
    oldest = datetime.min

    def when(row):
        moment = row.created or row.updated
        return moment.replace(tzinfo=None) if moment else oldest

    groups = []
    for book_id_, items in by_book.items():
        if book_id_ not in books:
            continue
        items.sort(key=lambda row: (row.chapter is None, when(row)))
        groups.append({"book": books[book_id_], "highlights": items, "latest": max(when(row) for row in items)})
    groups.sort(key=lambda group: group["latest"], reverse=True)
    return groups


def to_markdown(groups):
    """Highlights as Markdown, one section per book: easy to paste into Obsidian, Notion or Readwise."""
    lines = []
    for group in groups:
        book = group["book"]
        authors = ", ".join(author.name for author in book.authors)
        lines.append("# {}{}".format(book.title, " — " + authors if authors else ""))
        lines.append("")
        chapter = None
        for row in group["highlights"]:
            if row.chapter and row.chapter != chapter:
                chapter = row.chapter
                lines.append("## {}".format(chapter))
                lines.append("")
            if row.text:
                lines.extend("> " + line if line else ">" for line in row.text.splitlines())
                lines.append("")
            if row.note:
                lines.append("**{}:** {}".format(_("Note"), row.note))
                lines.append("")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


@annotations.route("/highlights")
@user_login_required
def highlights_page():
    query = (request.args.get("q") or "").strip()[:200]
    book_id = request.args.get("book", type=int)
    groups = grouped(current_user.id, book_id=book_id, query=query or None)
    total = sum(len(group["highlights"]) for group in groups)
    return render_title_template("highlights.html", title=_("Highlights"), groups=groups, total=total,
                                 query=query, book_id=book_id, page="highlights")


@annotations.route("/highlights/export.md")
@user_login_required
def export_markdown():
    book_id = request.args.get("book", type=int)
    groups = grouped(current_user.id, book_id=book_id)
    name = "highlights"
    if book_id is not None and groups:
        name = "highlights-{}".format(groups[0]["book"].id)
    return Response(to_markdown(groups), mimetype="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="{}.md"'.format(name)})
