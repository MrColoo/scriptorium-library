# Calibre-Web Automated – fork of Calibre-Web
# Copyright (C) 2024-2026 Calibre-Web Automated contributors
# SPDX-License-Identifier: GPL-3.0-or-later
# See CONTRIBUTORS for full list of authors.

"""Static guards for security fixes, so they do not quietly regress.

They read the source instead of running the app: cheap, and independent of the database
setup the rest of the suite needs.
"""

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TEMPLATES = REPO / "cps" / "templates"


def _function(path, name):
    tree = ast.parse((REPO / path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {path}")


def _whitelists_order(func):
    """True if the function compares `order` against ("asc", "desc") with `not in`."""
    for node in ast.walk(func):
        if (isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "order"
                and any(isinstance(op, ast.NotIn) for op in node.ops)):
            values = {elt.value for comp in node.comparators if isinstance(comp, (ast.Tuple, ast.List, ast.Set))
                      for elt in comp.elts if isinstance(elt, ast.Constant)}
            if values == {"asc", "desc"}:
                return True
    return False


@pytest.mark.unit
@pytest.mark.parametrize("path,name", [("cps/web.py", "list_books"), ("cps/admin.py", "list_users")])
def test_sort_direction_is_whitelisted_before_raw_sql(path, name):
    # The direction comes from the query string; anything but asc/desc must be dropped.
    assert _whitelists_order(_function(path, name))


@pytest.mark.unit
@pytest.mark.parametrize("path", ["cps/web.py", "cps/admin.py"])
def test_order_by_is_not_built_from_request_strings(path):
    source = (REPO / path).read_text(encoding="utf-8")
    assert not re.search(r"text\(\s*sort(_param)?\s*\+", source)


@pytest.mark.unit
def test_cover_enforcer_does_not_use_a_shell():
    source = (REPO / "scripts" / "cover_enforcer.py").read_text(encoding="utf-8")
    assert "os.system(" not in source


CSRF_EXEMPT_ALLOWED = {
    # Called by e-readers or other CWA processes, which cannot send a CSRF token.
    "cps/kobo.py", "cps/readingservices.py", "cps/gdrive.py", "cps/progress_syncing/protocols/kosync.py",
}


@pytest.mark.unit
def test_csrf_exemptions_only_on_machine_endpoints():
    offenders = []
    for path in (REPO / "cps").rglob("*.py"):
        rel = path.relative_to(REPO).as_posix()
        if rel in CSRF_EXEMPT_ALLOWED:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if line.strip() != "@csrf.exempt":
                continue
            # Allowed when the same decorator stack also restricts the route to CWA's own processes.
            stack = []
            j = i
            while j < len(lines) and (lines[j].strip().startswith("@") or not lines[j].strip()):
                stack.append(lines[j].strip())
                j += 1
            k = i - 1
            while k >= 0 and lines[k].strip().startswith("@"):
                stack.append(lines[k].strip())
                k -= 1
            if "@internal_only" not in stack:
                offenders.append(f"{rel}:{i + 1}")
    assert not offenders, "CSRF-exempt routes reachable by browsers: " + ", ".join(offenders)


SAFE_FILTER = re.compile(r"\|\s*safe\b")


@pytest.mark.unit
def test_templates_do_not_mark_data_as_safe():
    """`|safe` is only acceptable on translated static strings; library data must be escaped or sanitised."""
    offenders = []
    for path in TEMPLATES.glob("*.html"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if SAFE_FILTER.search(line) and "_(" not in line:
                offenders.append(f"{path.name}:{number}")
    assert not offenders, "Use |sanitize_html or plain output instead of |safe: " + ", ".join(offenders)


@pytest.mark.unit
def test_page_title_is_escaped():
    layout = (TEMPLATES / "layout.html").read_text(encoding="utf-8")
    assert re.search(r"<title>.*\{\{\s*title\s*\}\}", layout)
    assert "title|safe" not in layout.replace(" ", "")
