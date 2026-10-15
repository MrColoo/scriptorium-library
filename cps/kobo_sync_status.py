# -*- coding: utf-8 -*-
# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2018-2025 Calibre-Web contributors
# Copyright (C) 2024-2025 Calibre-Web Automated contributors
# Copyright (C) 2026 Mrcoloo (Scriptorium changes)
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

from .cw_login import current_user
from . import ub
from datetime import datetime, timezone
from sqlalchemy.sql.expression import or_, and_, true
# from sqlalchemy import exc


# Add the current book id to kobo_synced_books table for current user, if entry is already present,
# do nothing (safety precaution)
def add_synced_books(book_id):
    is_present = ub.session.query(ub.KoboSyncedBooks).filter(ub.KoboSyncedBooks.book_id == book_id)\
        .filter(ub.KoboSyncedBooks.user_id == current_user.id).count()
    if not is_present:
        synced_book = ub.KoboSyncedBooks()
        synced_book.user_id = current_user.id
        synced_book.book_id = book_id
        ub.session.add(synced_book)
        ub.session_commit()


# Select all entries of current book in kobo_synced_books table, which are from current user and delete them
def remove_synced_book(book_id, all=False, session=None):
    if not all:
        user = ub.KoboSyncedBooks.user_id == current_user.id
    else:
        user = true()
    if not session:
        ub.session.query(ub.KoboSyncedBooks).filter(ub.KoboSyncedBooks.book_id == book_id).filter(user).delete()
        ub.session_commit()
    else:
        session.query(ub.KoboSyncedBooks).filter(ub.KoboSyncedBooks.book_id == book_id).filter(user).delete()
        ub.session_commit(_session=session)


def change_archived_books(book_id, state=None, message=None):
    archived_book = ub.session.query(ub.ArchivedBook).filter(and_(ub.ArchivedBook.user_id == int(current_user.id),
                                                                  ub.ArchivedBook.book_id == book_id)).first()
    if not archived_book:
        archived_book = ub.ArchivedBook(user_id=current_user.id, book_id=book_id)

    archived_book.is_archived = state if state else not archived_book.is_archived
    archived_book.last_modified = datetime.now(timezone.utc)        # toDo. Check utc timestamp

    ub.session.merge(archived_book)
    ub.session_commit(message)
    return archived_book.is_archived


# select all books which are synced by the current user and do not belong to a synced shelf and set them to archive
# select all shelves from current user which are synced and do not belong to the "only sync" shelves
def update_on_sync_shelfs(user_id):
    # Books that are no longer on a synced shelf are removed from the device by the next
    # library sync (see HandleSyncRequest), which needs their KoboSyncedBooks rows to know
    # what is on the device. They used to be archived here instead, which also hid the
    # user's whole library in the web UI and kept the books on the Kobo.

    # Search all shelf which are currently not synced
    shelves_to_archive = ub.session.query(ub.Shelf).filter(ub.Shelf.user_id == user_id).filter(
        ub.Shelf.kobo_sync == 0).all()
    for a in shelves_to_archive:
        ub.session.add(ub.ShelfArchive(uuid=a.uuid, user_id=user_id))
        ub.session_commit()
