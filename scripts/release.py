#!/usr/bin/env python3
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Release helper. The release notes in cps/release_notes.json are the single source of truth:
the app shows them in What's new and in the update dialog, and the GitHub release is written from them.

    python3 scripts/release.py new v1.2.0        add a template entry to fill in
    python3 scripts/release.py check v1.2.0      validate the entry (used by CI)
    python3 scripts/release.py notes v1.2.0      print the GitHub release text (used by CI)
    python3 scripts/release.py prepare v1.2.0    date the entry, commit "Release v1.2.0" and tag it

`prepare` never pushes. It prints the two commands that publish the release; pushing the tag starts
the Release workflow (.github/workflows/release.yml), which tests, builds the image and writes the
GitHub release.
"""

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTES_PATH = os.path.join(ROOT, "cps", "release_notes.json")
IMAGE = "ghcr.io/mrcoloo/scriptorium-library"
TAG_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-[0-9A-Za-z.-]+)?$")
LOCALES = ("en", "it")


def _releases_module():
    # cps/releases.py is pure; load it by path so the Flask app is not imported.
    spec = importlib.util.spec_from_file_location("scriptorium_releases", os.path.join(ROOT, "cps", "releases.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


releases = _releases_module()


class ReleaseError(Exception):
    pass


def load_notes(path=None):
    with open(path or NOTES_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def save_notes(data, path=None):
    with open(path or NOTES_PATH, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def find(data, version):
    for entry in data.get("releases") or []:
        if isinstance(entry, dict) and entry.get("version") == version:
            return entry
    return None


def check_tag(version):
    if not TAG_RE.match(version or ""):
        raise ReleaseError("{!r} is not a release tag: use vMAJOR.MINOR.PATCH, e.g. v1.2.0 (or v1.2.0-rc.1)".format(version))


def is_prerelease(version):
    return "-" in version


def problems(data, version, need_date=True):
    """Everything wrong with a release entry, as readable sentences (empty when it is ready)."""
    issues = []
    entry = find(data, version)
    if entry is None:
        return ["cps/release_notes.json has no entry for {}. Run: python3 scripts/release.py new {}".format(version, version)]

    def missing(value, where):
        for locale in LOCALES:
            text = value.get(locale) if isinstance(value, dict) else (value if locale == "en" else None)
            if not isinstance(text, str) or not text.strip() or text.strip().startswith("TODO"):
                issues.append("{}: missing {!r} text".format(where, locale))

    if need_date and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(entry.get("date") or "")):
        issues.append("date must be YYYY-MM-DD (prepare sets it)")
    missing(entry.get("title"), "title")
    highlights = entry.get("highlights") or []
    if not 1 <= len(highlights) <= 6:
        issues.append("give 1 to 6 highlights (there are {})".format(len(highlights)))
    for index, item in enumerate(highlights, 1):
        if not isinstance(item, dict):
            issues.append("highlight {} is not an object".format(index))
            continue
        missing(item.get("title"), "highlight {} title".format(index))
        missing(item.get("text"), "highlight {} text".format(index))
        if not isinstance(item.get("icon"), str):
            issues.append("highlight {}: add an icon name from cps/static/img/icons.svg".format(index))
    quote = entry.get("quote")
    if not isinstance(quote, dict):
        issues.append("add a quote: a short line from a book that fits the release")
    else:
        missing(quote.get("text"), "quote")
        if not quote.get("author"):
            issues.append("quote: missing author")
    icons = os.path.join(ROOT, "cps", "static", "img", "icons.svg")
    if os.path.isfile(icons):
        sprite = open(icons, encoding="utf-8").read()
        for index, item in enumerate(highlights, 1):
            if isinstance(item, dict) and isinstance(item.get("icon"), str) \
                    and 'id="{}"'.format(item["icon"]) not in sprite:
                issues.append("highlight {}: icon {!r} is not in the sprite".format(index, item["icon"]))
    return issues


def template(version):
    todo = {"en": "TODO", "it": "TODO"}
    return {"version": version, "date": "",
            "title": dict(todo),
            "highlights": [{"icon": "sparkles", "title": dict(todo), "text": dict(todo)} for _ in range(3)],
            "quote": {"text": dict(todo), "author": "", "book": dict(todo)}}


def render(data, version, repository="MrColoo/scriptorium-library"):
    """The GitHub release text, from the release notes (English, then Italian in a fold)."""
    entry = find(data, version)
    if entry is None:
        raise ReleaseError("no release notes for {}".format(version))
    release = releases.from_data({"releases": [entry]})[0]

    def section(locale):
        local = releases.localized(release, locale)
        lines = []
        for item in local["highlights"]:
            lines.append("- **{}**{}".format(item["title"], " — " + item["text"] if item["text"] else ""))
        quote = local.get("quote")
        if quote and quote["text"]:
            lines += ["", "> {}".format(quote["text"])]
            source = quote["author"] + (", *{}*".format(quote["book"]) if quote["book"] else "")
            lines.append("> — {}".format(source))
        return local["title"], lines

    title, lines = section("en")
    it_title, it_lines = section("it")
    out = ["## {}".format(title), ""] + lines
    out += ["", "### Update", "",
            "Back up your `config` folder, then run next to your `docker-compose.yml`:", "",
            "```bash", "docker compose pull && docker compose up -d", "```", "",
            "Image: `{}:{}`{}".format(IMAGE, version, "" if is_prerelease(version) else " (also `latest`)")]
    if it_title and it_title != title:
        out += ["", "<details>", "<summary>🇮🇹 In italiano</summary>", "", "## {}".format(it_title), ""] + it_lines
        out += ["", "</details>"]
    return "\n".join(out) + "\n"


# ---------- git ----------

def git(*args, capture=True):
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=capture)
    if result.returncode != 0:
        raise ReleaseError("git {} failed: {}".format(" ".join(args), (result.stderr or "").strip()))
    return (result.stdout or "").strip()


def latest_tag():
    tags = [t for t in git("tag", "--list", "v*").splitlines() if TAG_RE.match(t) and not is_prerelease(t)]
    tags.sort(key=lambda t: releases.parse_version(t))
    return tags[-1] if tags else None


def prepare(version, dry_run=False, today=None):
    check_tag(version)
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        raise ReleaseError("release from the main branch")
    if git("status", "--porcelain"):
        raise ReleaseError("commit or stash your changes first")
    if git("tag", "--list", version):
        raise ReleaseError("tag {} already exists".format(version))
    previous = latest_tag()
    if previous and not is_prerelease(version) and not releases.is_newer(version, previous):
        raise ReleaseError("{} is not newer than the latest release {}".format(version, previous))
    data = load_notes()
    issues = problems(data, version, need_date=False)
    if issues:
        raise ReleaseError("release notes are not ready:\n  - " + "\n  - ".join(issues))
    find(data, version)["date"] = (today or date.today()).isoformat()
    if dry_run:
        print(render(data, version))
        print("Dry run: nothing written, committed or tagged.")
        return
    save_notes(data)
    git("add", NOTES_PATH)
    git("commit", "-m", "Release {}".format(version))
    git("tag", "-a", version, "-m", "Scriptorium {}".format(version))
    print("Committed \"Release {}\" and tagged {}. To publish:\n".format(version, version))
    print("  git push origin main")
    print("  git push origin {}\n".format(version))
    print("Pushing the tag starts the Release workflow: tests, image, GitHub release.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("new", "check", "notes", "prepare"):
        p = sub.add_parser(name)
        p.add_argument("version")
        if name in ("check", "notes"):
            p.add_argument("--notes-file", default=None, help="read the notes from another file")
        if name == "prepare":
            p.add_argument("--dry-run", action="store_true", help="show the release text, change nothing")
    args = parser.parse_args(argv)
    try:
        check_tag(args.version)
        if args.command == "new":
            data = load_notes()
            if find(data, args.version):
                raise ReleaseError("{} already has an entry".format(args.version))
            data["releases"].insert(0, template(args.version))
            save_notes(data)
            print("Added a template for {} to cps/release_notes.json: replace every TODO.".format(args.version))
        elif args.command == "check":
            issues = problems(load_notes(args.notes_file), args.version)
            if issues:
                raise ReleaseError("release notes for {} are not ready:\n  - ".format(args.version) + "\n  - ".join(issues))
            print("Release notes for {} are ready.".format(args.version))
        elif args.command == "notes":
            sys.stdout.write(render(load_notes(args.notes_file), args.version))
        else:
            prepare(args.version, dry_run=args.dry_run)
    except ReleaseError as error:
        print("error: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
