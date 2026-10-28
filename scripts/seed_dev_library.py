#!/usr/bin/env python3
# Scriptorium – based on Calibre-Web Automated, a fork of Calibre-Web
# Copyright (C) 2026 Mrcoloo
# SPDX-License-Identifier: GPL-3.0-or-later
# See NOTICE and CONTRIBUTORS for the upstream projects and their authors.

"""Build a throwaway Calibre library with sample books for local UI development.

Usage: python scripts/seed_dev_library.py <target-dir>
       python scripts/seed_dev_library.py --dev-admin <path-to-app.db>

Creates <target-dir>/library (metadata.db, covers, minimal EPUB files) and
<target-dir>/config (empty, for app.db and cwa.db). Needs Pillow. Does not need Calibre.
"""

import os
import shutil
import sqlite3
import sys
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BOOKS = [
    # title, author, series, index, tags, publisher, year, rating(0-10), lang, description
    ("The Name of the Rose", "Umberto Eco", None, 0, ["Historical mystery", "Middle Ages"], "Harcourt", 1983, 8, "eng",
     "<p>In 1327 a Franciscan friar and his young novice investigate a string of deaths in a wealthy Benedictine "
     "abbey, where the library is a labyrinth and some books are not meant to be read.</p>"),
    ("Foucault's Pendulum", "Umberto Eco", None, 0, ["Literary fiction"], "Harcourt", 1989, 6, "eng", ""),
    ("Invisible Cities", "Italo Calvino", None, 0, ["Literary fiction"], "Harcourt", 1974, 10, "eng",
     "<p>Marco Polo describes to Kublai Khan the cities of his empire, each one stranger than the last.</p>"),
    ("The Baron in the Trees", "Italo Calvino", "Our Ancestors", 2, ["Literary fiction"], "Harcourt", 1959, 8, "eng", ""),
    ("The Cloven Viscount", "Italo Calvino", "Our Ancestors", 1, ["Literary fiction"], "Harcourt", 1962, 8, "eng", ""),
    ("The Nonexistent Knight", "Italo Calvino", "Our Ancestors", 3, ["Literary fiction"], "Harcourt", 1962, 6, "eng", ""),
    ("Family Lexicon", "Natalia Ginzburg", None, 0, ["Memoir"], "NYRB Classics", 2017, 8, "eng", ""),
    ("Zeno's Conscience", "Italo Svevo", None, 0, ["Classics"], "Vintage", 2003, 6, "eng", ""),
    ("The Periodic Table", "Primo Levi", None, 0, ["Short stories"], "Schocken", 1984, 10, "eng", ""),
    ("The Leopard", "Giuseppe Tomasi di Lampedusa", None, 0, ["Classics"], "Pantheon", 1960, 8, "eng",
     "<p>Sicily, 1860. As Garibaldi's troops land, an ageing prince watches his world end with irony and grace.</p>"),
    ("My Brilliant Friend", "Elena Ferrante", "Neapolitan Novels", 1, ["Literary fiction"], "Europa Editions", 2012, 8, "eng", ""),
    ("The Story of a New Name", "Elena Ferrante", "Neapolitan Novels", 2, ["Literary fiction"], "Europa Editions", 2013, 8, "eng", ""),
    ("Dune", "Frank Herbert", "Dune", 1, ["Science fiction", "Classics"], "Chilton", 1965, 10, "eng",
     "<p>On the desert planet Arrakis, the only source of the most valuable substance in the universe, young "
     "Paul Atreides is caught between noble houses, an empire and the people of the deep desert.</p>"),
    ("Dune Messiah", "Frank Herbert", "Dune", 2, ["Science fiction"], "Putnam", 1969, 6, "eng", ""),
    ("The Left Hand of Darkness", "Ursula K. Le Guin", "Hainish Cycle", 4, ["Science fiction"], "Ace", 1969, 10, "eng", ""),
    ("The Dispossessed", "Ursula K. Le Guin", "Hainish Cycle", 5, ["Science fiction"], "Harper & Row", 1974, 8, "eng", ""),
    ("Neuromancer", "William Gibson", "Sprawl", 1, ["Science fiction", "Cyberpunk"], "Ace", 1984, 8, "eng", ""),
    ("Solaris", "Stanisław Lem", None, 0, ["Science fiction"], "Walker", 1970, 8, "eng", ""),
    ("Project Hail Mary", "Andy Weir", None, 0, ["Science fiction"], "Ballantine", 2021, 8, "eng",
     "<p>A schoolteacher wakes up alone on a spaceship with no memory of how he got there, and the fate of "
     "Earth depending on him.</p>"),
    ("Klara and the Sun", "Kazuo Ishiguro", None, 0, ["Literary fiction"], "Faber", 2021, 6, "eng", ""),
    ("The Remains of the Day", "Kazuo Ishiguro", None, 0, ["Literary fiction"], "Faber", 1989, 8, "eng", ""),
    ("Sapiens", "Yuval Noah Harari", None, 0, ["Non-fiction", "History"], "Harper", 2011, 6, "eng", ""),
    ("Thinking, Fast and Slow", "Daniel Kahneman", None, 0, ["Non-fiction", "Psychology"], "FSG", 2011, 8, "eng", ""),
    # Escaping test: every field carries markup that must be shown as text, never run.
    ("<img src=x onerror=alert(1)>", "Test <b>Author</b>", None, 0, ["<script>x</script>"], "Evil & Co", 2020, 2, "eng",
     "<p onclick=\"alert(1)\">Escaping test book.</p><script>alert('xss')</script>"),
]

PALETTE = [("#2B3A55", "#F3EEE2"), ("#B4552F", "#FFF6EC"), ("#3E7A57", "#F4F1E6"), ("#C9A227", "#2A220C"),
           ("#6B5BA8", "#F5F2FF"), ("#8E3B46", "#FBEFEF"), ("#2F5D73", "#EAF4F7"), ("#1F1F24", "#F2C14E"),
           ("#E7E2D6", "#2B2B2B"), ("#4A3B2F", "#F1E3C8"), ("#14323A", "#7FE0C9"), ("#5C7A3A", "#F3F6EA")]


def sort_key(text):
    for article in ("The ", "A ", "An "):
        if text.startswith(article):
            return text[len(article):] + ", " + article.strip()
    return text


def author_sort(name):
    parts = name.split()
    return name if len(parts) < 2 else parts[-1] + ", " + " ".join(parts[:-1])


def safe_path(text):
    return "".join(c if c.isalnum() or c in " -_.,'" else "_" for c in text).strip()[:60] or "book"


def make_cover(path, title, author, colors):
    bg, fg = colors
    img = Image.new("RGB", (600, 900), bg)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Georgia.ttf", 54)
        small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Georgia.ttf", 28)
    except OSError:
        font = small = ImageFont.load_default()
    words, lines, line = title.split(), [], ""
    for word in words:
        candidate = (line + " " + word).strip()
        if draw.textlength(candidate, font=font) > 500 and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    lines.append(line)
    y = 80
    for text in lines:
        draw.text((50, y), text, font=font, fill=fg)
        y += 66
    draw.text((50, 800), author.upper(), font=small, fill=fg)
    draw.rectangle([0, 0, 14, 900], fill=tuple(max(0, int(bg[i:i + 2], 16) - 30) for i in (1, 3, 5)))
    img.save(path, "JPEG", quality=85)


def make_epub(path, title, author, book_uuid):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr("content.opf",
                   '<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">'
                   '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{t}</dc:title><dc:creator>{a}</dc:creator>'
                   '<dc:identifier id="id">urn:uuid:{u}</dc:identifier><dc:language>en</dc:language></metadata>'
                   '<manifest><item id="c1" href="c1.xhtml" media-type="application/xhtml+xml"/>'
                   '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/></manifest>'
                   '<spine toc="ncx"><itemref idref="c1"/></spine></package>'.format(
                       t=escape_xml(title), a=escape_xml(author), u=book_uuid))
        z.writestr("toc.ncx",
                   '<?xml version="1.0"?><ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head/>'
                   '<docTitle><text>{t}</text></docTitle><navMap><navPoint id="n1" playOrder="1"><navLabel><text>1</text>'
                   '</navLabel><content src="c1.xhtml"/></navPoint></navMap></ncx>'.format(t=escape_xml(title)))
        paragraphs = "".join("<p>Paragraph {} of the sample text for {}.</p>".format(i, escape_xml(title)) for i in range(1, 60))
        z.writestr("c1.xhtml",
                   '<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>1</title></head>'
                   '<body><h1>{t}</h1>{p}</body></html>'.format(t=escape_xml(title), p=paragraphs))


def escape_xml(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main(target):
    library = os.path.join(target, "library")
    config = os.path.join(target, "config")
    if os.path.exists(library):
        shutil.rmtree(library)
    os.makedirs(library)
    os.makedirs(config, exist_ok=True)
    db_path = os.path.join(library, "metadata.db")
    shutil.copy(os.path.join(REPO, "empty_library", "metadata.db"), db_path)

    conn = sqlite3.connect(db_path)
    conn.create_function("title_sort", 1, sort_key)
    conn.create_function("uuid4", 0, lambda: str(uuid.uuid4()))
    cur = conn.cursor()

    def get_or_create(table, column, value, extra=None):
        row = cur.execute("SELECT id FROM {} WHERE {}=?".format(table, column), (value,)).fetchone()
        if row:
            return row[0]
        cols, vals = [column], [value]
        for k, v in (extra or {}).items():
            cols.append(k)
            vals.append(v)
        cur.execute("INSERT INTO {} ({}) VALUES ({})".format(table, ",".join(cols), ",".join("?" * len(vals))), vals)
        return cur.lastrowid

    now = datetime.now(timezone.utc)
    for n, (title, author, series, index, tags, publisher, year, rating, lang, desc) in enumerate(BOOKS):
        book_uuid = str(uuid.uuid4())
        author_id = get_or_create("authors", "name", author, {"sort": author_sort(author)})
        rel_path = "{}/{} ({})".format(safe_path(author), safe_path(title), n + 1)
        added = (now - timedelta(days=n * 3)).strftime("%Y-%m-%d %H:%M:%S+00:00")
        cur.execute("INSERT INTO books (title, sort, timestamp, pubdate, series_index, author_sort, path, uuid, has_cover, last_modified)"
                    " VALUES (?,?,?,?,?,?,?,?,1,?)",
                    (title, sort_key(title), added, "{}-06-01 00:00:00+00:00".format(year), float(index or 1),
                     author_sort(author), rel_path, book_uuid, added))
        book_id = cur.lastrowid
        cur.execute("INSERT INTO books_authors_link (book, author) VALUES (?,?)", (book_id, author_id))
        if series:
            series_id = get_or_create("series", "name", series, {"sort": sort_key(series)})
            cur.execute("INSERT INTO books_series_link (book, series) VALUES (?,?)", (book_id, series_id))
        for tag in tags:
            cur.execute("INSERT INTO books_tags_link (book, tag) VALUES (?,?)", (book_id, get_or_create("tags", "name", tag)))
        cur.execute("INSERT INTO books_publishers_link (book, publisher) VALUES (?,?)",
                    (book_id, get_or_create("publishers", "name", publisher, {"sort": publisher})))
        if rating:
            cur.execute("INSERT INTO books_ratings_link (book, rating) VALUES (?,?)",
                        (book_id, get_or_create("ratings", "rating", rating)))
        cur.execute("INSERT INTO books_languages_link (book, lang_code, item_order) VALUES (?,?,0)",
                    (book_id, get_or_create("languages", "lang_code", lang)))
        if desc:
            cur.execute("INSERT INTO comments (book, text) VALUES (?,?)", (book_id, desc))
        cur.execute("INSERT INTO identifiers (book, type, val) VALUES (?,?,?)", (book_id, "isbn", "97800000{:05d}".format(n)))

        folder = os.path.join(library, rel_path)
        os.makedirs(folder)
        file_stem = safe_path(title) + " - " + safe_path(author)
        make_cover(os.path.join(folder, "cover.jpg"), title, author, PALETTE[n % len(PALETTE)])
        epub_path = os.path.join(folder, file_stem + ".epub")
        make_epub(epub_path, title, author, book_uuid)
        cur.execute("INSERT INTO data (book, format, uncompressed_size, name) VALUES (?,?,?,?)",
                    (book_id, "EPUB", os.path.getsize(epub_path), file_stem))
    conn.commit()
    conn.close()
    print("Seeded {} books into {}".format(len(BOOKS), library))




# Development-only admin password for the local test instance (set with --dev-admin).
DEV_ADMIN_PASSWORD = "cwa-dev-Passw0rd"


def set_dev_admin_password(app_db):
    from werkzeug.security import generate_password_hash
    conn = sqlite3.connect(app_db)
    conn.execute("UPDATE user SET password=? WHERE name='admin'", (generate_password_hash(DEV_ADMIN_PASSWORD),))
    conn.commit()
    conn.close()
    print("admin password set to DEV_ADMIN_PASSWORD from this script")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--dev-admin":
        set_dev_admin_password(sys.argv[2])
    elif len(sys.argv) == 2:
        main(os.path.abspath(sys.argv[1]))
    else:
        sys.exit(__doc__)
