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
- The built-in reader (source "web"): its highlights also go to KOReader. Plugin 1.3 fetches them and
  adds them to the book on the device, marked with their id here ("web:<id>"). When it sends them back,
  a changed note or colour updates the highlight here, and one deleted on the device is deleted here.

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
WEB_ID_PREFIX = "web:"
READER_COLORS = ("yellow", "green", "blue", "pink")
# KOReader's colour names, shown with the nearest of the built-in reader's own
_NEAREST_COLOR = {"red": "pink", "purple": "pink", "orange": "yellow", "olive": "green", "cyan": "blue",
                  "gray": "yellow", "grey": "yellow"}
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


def reader_color(value):
    """The built-in reader's colour closest to a device's colour name."""
    value = (value or "").strip().lower() if isinstance(value, str) else ""
    return value if value in READER_COLORS else _NEAREST_COLOR.get(value, "yellow")


def _web_id(value):
    """The row id in "web:<id>", or None."""
    if isinstance(value, str) and value.startswith(WEB_ID_PREFIX) and value[len(WEB_ID_PREFIX):].isdigit():
        return int(value[len(WEB_ID_PREFIX):])
    return None


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


DEVICE_PREFIX = "device:"


def _device_scope(device):
    """Prefix of the source ids of one KOReader device, e.g. 'device:3f2a…/'."""
    return "{}{}/".format(DEVICE_PREFIX, _clip(device, 64) or "unknown")


def _web_rows(user_id, book_id, ids):
    if not ids:
        return []
    return ub.session.query(ub.ReaderAnnotation).filter(
        ub.ReaderAnnotation.user_id == int(user_id), ub.ReaderAnnotation.book_id == int(book_id),
        ub.ReaderAnnotation.source == "web", ub.ReaderAnnotation.id.in_(list(ids))).all()


def _apply_web_changes(user_id, book_id, changed, removed_ids):
    """Notes and colours changed in KOReader on highlights of the built-in reader, and the ones deleted there."""
    removed = 0
    for row in _web_rows(user_id, book_id, removed_ids):
        ub.session.delete(row)
        removed += 1
    for row in _web_rows(user_id, book_id, changed):
        item = changed[row.id]
        note = _clip(item.get("note"), MAX_TEXT)
        if note != row.note:
            row.note = note
        color = item.get("color")
        if isinstance(color, str) and color in READER_COLORS and color != row.color:
            row.color = color  # KOReader's other colours have no match here: the reader's stays
    return removed


def replace_koreader(user_id, book_id, items, device=None, removed_web=None):
    """Make the highlights one KOReader device holds for a book match the list it sent. The caller commits.

    Each device only replaces its own, so with KOReader on a Kobo and on a phone, a sync from one never
    removes the other's highlights. Highlights stored before devices were told apart carry no device:
    the device that sends one of them again takes it over, and the others leave them alone.
    Highlights the device got from the built-in reader come back with their id here: they stay the
    reader's, with the device's note and colour; removed_web lists those deleted on the device.
    """
    scope = _device_scope(device)
    wanted = {}
    web_changes = {}
    for item in (items or [])[:MAX_ITEMS]:
        web_id = _web_id(item.get("scriptorium_id")) if isinstance(item, dict) else None
        if web_id is not None:
            web_changes[web_id] = item
            continue
        fields = normalize_koreader(item)
        if fields:
            wanted[fields["source_id"]] = fields
    removed_ids = {web_id for web_id in map(_web_id, (removed_web or [])[:MAX_ITEMS]) if web_id is not None}
    removed = _apply_web_changes(user_id, book_id, web_changes, removed_ids - set(web_changes))
    existing = ub.session.query(ub.ReaderAnnotation).filter(
        ub.ReaderAnnotation.user_id == int(user_id),
        ub.ReaderAnnotation.book_id == int(book_id),
        ub.ReaderAnnotation.source == "koreader").all()
    for row in existing:
        if row.source_id.startswith(scope):
            if row.source_id[len(scope):] not in wanted:
                ub.session.delete(row)
                removed += 1
        elif not row.source_id.startswith(DEVICE_PREFIX) and row.source_id in wanted:
            row.source_id = scope + row.source_id
    ub.session.flush()
    for source_id, fields in wanted.items():
        _upsert(user_id, book_id, "koreader", dict(fields, source_id=scope + source_id))
    return len(wanted), removed


def web_for_koreader(user_id, book_id, path=None):
    """The built-in reader's highlights of a book, for the KOReader plugin to add to the book on the device.

    pos0 and pos1 are where it starts and ends in KOReader's notation, translated through the library's
    file (see epub_positions); the plugin checks the words there and looks for them in the book otherwise.
    """
    from . import epub_positions
    rows = ub.session.query(ub.ReaderAnnotation).filter(
        ub.ReaderAnnotation.user_id == int(user_id), ub.ReaderAnnotation.book_id == int(book_id),
        ub.ReaderAnnotation.source == "web").order_by(ub.ReaderAnnotation.created).limit(MAX_ITEMS).all()
    result = []
    for row in rows:
        if not row.text:
            continue
        item = {"id": "{}{}".format(WEB_ID_PREFIX, row.id), "text": row.text, "note": row.note or "",
                "color": row.color or "yellow", "chapter": row.chapter or "",
                "datetime": (row.created or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S")}
        pos0, pos1 = epub_positions.range_xpointers(path, row.source_id) if path else (None, None)
        if pos0:
            item["pos0"] = pos0
        if pos0 and pos1:
            item["pos1"] = pos1
        result.append(item)
    return result


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


def _without_copies(rows):
    """The same highlight sent by two devices (same place, same words) is shown once."""
    seen = set()
    unique = []
    for row in rows:
        key = (row.position, (row.text or "").strip(), (row.note or "").strip())
        if row.position and key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


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
        items = _without_copies(items)
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
