# Security

Scriptorium holds your library, your users' passwords and tokens that can download every book. This page
explains how the application protects them and what you should do when you deploy it.

## Deploying safely

- **Change the default password.** The first login as `admin` / `admin123` forces a new password
  before anything else can be done.
- **Never forward port 8083 to the internet.** Use a VPN, or a reverse proxy with a real certificate.
  [Remote access](remote-access.md) compares the options. With HTTPS working, enable
  *Settings → Server & features → Security → Use via HTTPS* so session cookies are marked `Secure`.
- **Do not expose the container port directly** when you use reverse-proxy authentication: anyone
  who reaches Scriptorium without the proxy could send the `Remote-User` header and log in as anyone.
- **Keep the Kobo sync address private.** It works like a password for your books. Regenerate it
  from your profile if it leaks, and revoke it when a device is lost.
- **Give people only the permissions they need**, and keep *Anonymous Browsing* and *Public
  Registration* off on a public address. See [Administration](administration.md#users).
- **Back up `/config`.** It contains `app.db` (users, settings, reading progress) and `cwa.db`. Keep
  backups private: they hold your users' password hashes. See [Backups](updating-and-backups.md#backups).
- **Keep the image updated.** Administrators see a notice in the interface when a new release is
  out.

### Blocking repeated sign-in attempts

*Limit failed login attempts* is on by default and slows down password guessing. If your library is
public, a tool such as [fail2ban](https://github.com/fail2ban/fail2ban) can also ban addresses at the
firewall. Failed sign-ins are written to `/config/calibre-web.log`:

```text
Login failed for user "someone" IP-address: 203.0.113.7
```

## How the application is hardened

**Browser**
- A strict Content-Security-Policy: scripts load only from the server itself, with no inline code
  anywhere in the interface. The in-browser readers are the only pages allowed `eval` and `blob:`
  documents, because epub.js, pdf.js, the comic and DjVu viewers need them. Scripts embedded in
  EPUB files are blocked.
- `X-Frame-Options` / `frame-ancestors`, `X-Content-Type-Options`, `Referrer-Policy` and
  `Permissions-Policy` headers on every response.
- All user-provided text (titles, authors, tags, shelf names, log lines) is escaped; book
  descriptions and comment columns are sanitised to a small set of HTML tags before display,
  including books imported in bulk that never passed through the editor.
- CSRF tokens on every form and on every state-changing request, including the automation
  services, duplicate tools, library refresh and log actions. State-changing endpoints accept POST
  only.

**Server**
- Sort columns and directions in table endpoints are whitelisted; queries are built with SQLAlchemy
  expressions or bound parameters, never string formatting.
- No shell commands are built from book paths or names.
- Redirects after login and shelf actions only go to paths on the same site.
- Changing your password requires the current one.
- Kobo endpoints, including the store proxy, require a valid per-user token.
- Profile pictures accept only PNG, JPEG and WebP up to 500 KB and are served as images, never as
  HTML or SVG.
- Static files are served with versioned URLs, so browsers always get the current scripts after an
  upgrade.
- Python dependencies have minimum versions above known vulnerable releases.

The repository contains regression tests for these fixes in
`tests/unit/test_security_regressions.py`.

## Reporting a vulnerability

See [SECURITY.md](../SECURITY.md). Please report privately, not in a public issue.
