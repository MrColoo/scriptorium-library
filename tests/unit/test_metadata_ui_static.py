# Calibre-Web Automated – modified for Scriptorium
# Copyright (C) 2026 Mrcoloo (Scriptorium changes)
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_metadata_description_apply_writes_the_submitted_field():
    """Applying a fetched description must land in the textarea the edit form submits."""
    js = (REPO_ROOT / "cps/static/js/book-edit.js").read_text(encoding="utf-8")
    template = (REPO_ROOT / "cps/templates/book_edit.html").read_text(encoding="utf-8")

    assert 'if (chosen.description) setValue("comments", book.description || "");' in js
    assert 'name="comments" id="comments"' in template


def test_metadata_result_button_is_apply_not_save():
    """The per-result button applies values; it must not submit (save) the edit form."""
    js = (REPO_ROOT / "cps/static/js/book-edit.js").read_text(encoding="utf-8")
    template = (REPO_ROOT / "cps/templates/book_edit.html").read_text(encoding="utf-8")

    assert 'var apply = el("button", "btn btn-sm btn-primary", S.apply || "Apply");' in js
    assert 'apply.type = "button";' in js
    assert "'apply': _('Apply selected')" in template
