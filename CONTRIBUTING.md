# Contributing to Scriptorium

Thanks for helping. Bug reports, ideas, translations and code are all welcome.

## Before you start

- **Bugs and ideas:** open an issue with the matching template. Search first; someone may have
  reported it already.
- **Security problems:** do not open an issue — see [SECURITY.md](SECURITY.md).
- **Larger changes:** open an issue to discuss the approach before writing a lot of code.

## Making a change

1. Fork the repository and create a branch from `main`.
2. Set up the app from source: [docs/development.md](docs/development.md) (a sample library is
   one command away).
3. Keep the change focused: one fix or feature per pull request, small commits with clear messages.
4. Run the unit tests: `.venv/bin/python -m pytest tests/unit -q`.
5. Check the pages you touched in light and dark mode and at phone width.
6. Open a pull request and fill in the checklist.

If your change is something users will notice, add it to the next version's entry in
`cps/release_notes.json` (`python3 scripts/release.py new vX.Y.Z` creates one). Maintainers release
as described in [docs/releasing.md](docs/releasing.md).

### Front-end rules

- No inline JavaScript or `on*=` attributes: the Content-Security-Policy blocks them. Put code in
  `cps/static/js/` and pass data with `<script type="application/json">`.
- Reuse the design tokens and components in `cps/static/css/app.css` before adding new styles.
- New user-facing text goes through `_()` so it can be translated.

### Backend changes

Scriptorium keeps its backend close to [Calibre-Web-Automated](https://github.com/crocodilestick/Calibre-Web-Automated).
Fixes that apply to both projects are best proposed upstream too. Don't rename internal
identifiers (environment variables, container paths, `cwa.db`, routes): existing installs rely on
them.

## Translations

Strings live in `cps/translations/<language>/LC_MESSAGES/messages.po`. To update the template and
the catalogs after changing text, follow [docs/development.md → Translations](docs/development.md#translations).
To translate, edit the `messages.po` of your language (keep `%(name)s` placeholders unchanged) and
open a pull request. Check your file with `msgfmt --check`.

## License

By contributing you agree that your contribution is licensed under the
[GNU GPL v3.0 or later](LICENSE), like the rest of the project. Keep existing copyright notices
in the files you edit.
