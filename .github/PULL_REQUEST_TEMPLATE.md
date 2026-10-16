## What does this change?

<!-- A short description, and the issue it fixes if any: "Fixes #123". -->

## How did you test it?

<!-- Steps you followed, pages you checked, devices (Kobo, KOReader…) if relevant. -->

## Checklist

- [ ] One focused change; commits have clear messages
- [ ] Unit tests pass: `.venv/bin/python -m pytest tests/unit -q`
- [ ] Pages I touched work in light and dark mode and at phone width
- [ ] No inline JavaScript or `on*=` attributes; new text goes through `_()`
- [ ] Internal identifiers (env vars, container paths, `cwa.db`, routes) unchanged, or the change is discussed in the issue
- [ ] Docs updated if behaviour or settings changed
- [ ] No secrets, personal data or local paths in the diff
