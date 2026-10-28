# Development

## Run from source

You need Python 3.10 or newer and a few system libraries: `libmagic`, and the LDAP/SASL headers
for `python-ldap` (macOS: `brew install libmagic openldap`; Debian/Ubuntu:
`apt install libmagic1 libldap2-dev libsasl2-dev`). Calibre itself is only needed for conversion.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r optional-requirements.txt -r requirements-dev.txt
```

Create a throwaway library with sample books, covers and EPUB files:

```bash
.venv/bin/python scripts/seed_dev_library.py /tmp/cwa-dev
```

Start the server against it:

```bash
cd /path/to/scriptorium-library
CWA_DB_PATH=/tmp/cwa-dev/config CALIBRE_DBPATH=/tmp/cwa-dev/config DEVELOP_ON=true \
PYTHONPATH=scripts:. CWA_PORT_OVERRIDE=8089 \
.venv/bin/python cps.py -p /tmp/cwa-dev/config/app.db
```

Open `http://localhost:8089`, sign in as `admin` / `admin123`, choose a new password, and point
*Settings → Calibre library* at `/tmp/cwa-dev/library`. `DEVELOP_ON=true` reloads templates
without a restart; Python changes need one. Static files are versioned by content hash, so edited
CSS and JS are picked up on the next page load.

Paths such as `/config/*.log` and `/app/calibre-web-automated` exist only in the container; the
services that use them (convert library, EPUB fixer, ingest) report an error when run from source.
To work on those, use the Docker setup: build with `build.sh` and start
`docker compose -f docker-compose.yml.dev up -d` (see the comments in that file for live-edit
mounts).

## Tests

```bash
.venv/bin/python -m pytest tests/unit -q
```

Unit tests run without Docker. `tests/integration` and `tests/smoke` start containers; see
`tests/README.md`. `tests/unit/test_security_regressions.py` guards the security fixes (no
`|safe` on user data, no inline scripts, whitelisted sorting, strict CSP) — keep it passing.

## Front end

The interface is server-rendered Jinja with a small amount of vanilla JavaScript. There is no
build step and no framework.

- **Design system**: `cps/static/css/app.css`. Colours, spacing and typography are CSS custom
  properties on `:root`, redefined for dark mode under `[data-theme="dark"]`. Components (`.btn`,
  `.card`, `.field`, `.switch`, `.segmented`, `.chip`, `.badge`, `.modal`, `.menu`…) are plain
  classes; reuse them before adding new ones.
- **Fonts and icons** are self-hosted: Geist and Newsreader in `static/fonts`, an SVG sprite in
  `static/img/icons.svg` used through the `ui.icon()` macro.
- **Macros** in `templates/_macros.html` (imported as `ui` by `layout.html`): `icon`, `cover_img`,
  `book_card`, `field`, `switch`, `csrf_field`, `empty_state`, `pagination_nav`, `sort_menu`…
- **Behaviour** is attached with data attributes handled by `static/js/app.js`:
  `data-dialog-open`, `data-confirm` on forms, `data-post` buttons, `data-copy`,
  `data-show-if`, `data-autosubmit`, `data-multiselect`, `data-suggest` and more (documented at
  the top of the file). Page-specific scripts live next to it (`details.js`, `profile.js`,
  `datatable.js`…) and read their configuration from
  `<script type="application/json">` blocks.
- **No inline JavaScript.** The Content-Security-Policy only allows scripts from the server, so
  `<script>` blocks with code and `onclick=` attributes will not run (and a unit test fails).
  Pass data as JSON, put code in a static file.
- **Personal styles** (*Customize*) live in `static/css/themes.css` and `cps/appearance_styles.py`.
  A style is a set of `data-ap-*` attributes plus the `--ap-h`/`--ap-h2` hues on a scope element
  (`<html>`, or a preview card). Option rules only set custom properties on that element; the
  component rules at the bottom of `themes.css` read them with the stock value as fallback, so an
  element without a style looks exactly like the default design. To add an option value, add it to
  `OPTIONS` in `appearance_styles.py` and a rule in `themes.css` (a unit test checks they match).
- **`window.CWA`** exposes helpers for page scripts: `request()` (fetch with CSRF header),
  `toast()`, `confirm()`, `openDialog()`, `t()` for translated strings.

Readers (`read*.html`, `listenmp3.html`) are standalone pages; the EPUB, comic, PDF and DjVu ones
wrap third-party engines in `static/js/libs` and get a looser CSP.

## Translations

Strings are marked with `_()` in Python and templates. After changing them:

```bash
.venv/bin/pybabel extract -F babel.cfg -o messages.pot .
for po in cps/translations/*/LC_MESSAGES/messages.po; do msgmerge --update --backup=none "$po" messages.pot; done
```

(`scripts/update_translations.sh` does the same and compiles the catalogs.) Translate the new
entries in your language's `messages.po`, keeping `%(name)s` placeholders intact, and check it with
`msgfmt --check`. `.mo` files are compiled at build time and not committed.

Placeholders that JavaScript fills in are passed through gettext as values, e.g.
`_('%(count)s selected', count='%n')`, so translators see a normal message.

## Release notes

Every release adds an entry to `cps/release_notes.json`: a version, a date, a title and three to
five highlights, each text in English (`en`) and in any other language you can write (`it`, …).
After an update every user sees the entry for the installed version once, in a dialog; all
entries are listed under *What's new* in the account menu and on the About page. A patch release
without its own entry shows its minor's notes, so it does not pop up again. A unit test checks
that the file is valid and that every highlight has an English and an Italian title.

Administrators get a notice while a newer release exists on GitHub (looked up at most every 12
hours, only while *Enable Update Notifications* is on), which they can hide until the next one.

## Pull requests

Keep the backend close to upstream Calibre-Web-Automated where possible, so fixes can flow both ways. Run
the unit tests, check pages in light and dark mode and at phone width, and describe what you
tested.
