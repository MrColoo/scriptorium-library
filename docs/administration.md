# Administration

For the person who runs the server: users, sign-in, email, maintenance and monitoring. All of it is
under **Settings** in the sidebar.

## Users

*Settings → Users → Add New User* creates an account. *Edit Users* opens a table for changing many
accounts at once: click a value to change it, and permission switches save immediately.

Each user has their own shelves, reading progress, highlights, devices, style and archived books.
Books and metadata are shared.

### Permissions

| Permission | Allows |
| --- | --- |
| **Admin User** | Everything, including Settings. |
| **Allow Downloads** | Downloading books. Also needed for Kobo sync. |
| **Allow eBook Viewer** | Reading in the browser. |
| **Allow Uploads** | Adding books. Shown once *Enable Uploads* is on. |
| **Allow Edit** | Changing metadata, covers and formats. |
| **Allow Delete Books** | Deleting books from the library. |
| **Allow Changing Password** | Changing their own password. |
| **Allow Editing Public Shelves** | Changing shelves shared with everyone. |

Defaults for new accounts are in *Settings → Interface → Default Settings for New Users*.

> [!TIP]
> Give family members *Downloads*, *eBook Viewer* and *Changing Password*. Keep *Edit* and *Delete*
> to the people who look after the library.

### Hiding books from a user

Open a user and add **allowed and denied values**. Allowed values limit the library to books that
have them, and denied values hide every book that has them. This works on tags and on custom Calibre
columns, and it is how you set up a children's account: for example, allow only the tag `kids`.

Restrictions apply to the web interface, OPDS and Kobo sync. Set defaults for new users in *Settings →
Interface*. *Language of Books* on a user's Preferences limits which languages they see.

### Guests and registration

These are in *Settings → Server & features → Features*:

- **Anonymous Browsing** lets anyone in without an account. They get the permissions of the `Guest`
  user, which you edit like any other.
- **Public Registration** adds a sign-up page. It needs a working mail server, because the password
  is sent by email. *Settings → Email server → Registration domains* limits who may register.
- **Magic Link Remote Login** signs in a new device by approving a link from a device where you are
  already signed in, handy for typing on an e-reader's browser.

Keep the first two off if your library is reachable from the internet.

## Sign-in options

Choose the login type in *Settings → Server & features → Login*.

> [!WARNING]
> Before switching login type, make sure at least one administrator will be able to sign in
> afterwards. If you get locked out, see [Resetting a password](updating-and-backups.md#resetting-a-password).

### Standard

Usernames and passwords stored in Scriptorium. The password policy is under *Security*: by default at
least 8 characters, with a number, a lowercase and an uppercase letter, and a special character.

### LDAP

For Active Directory, OpenLDAP, LLDAP and similar. Fill in the server, administrator account,
Distinguished Name and user filter. **Auto-create users from LDAP** creates an account at first
sign-in. Otherwise, press *Import LDAP Users* on the Settings page. To limit access to a group, use
the group filter and group name.

### OAuth and OpenID Connect

GitHub, Google and any generic OIDC provider, such as Authelia, Authentik, Keycloak or PocketID.

1. Scriptorium must be on HTTPS.
2. In your provider, create an application with this redirect URL:

   ```text
   https://books.example.com/login/<provider>/authorized
   ```

   `<provider>` is `github`, `google` or `generic`.
3. Enter the client ID and secret in *Login*. For a generic provider, enter the **OAuth Metadata URL**
   (usually ending in `/.well-known/openid-configuration`) and let it discover the endpoints, or tick
   the option to enter them by hand.
4. If you get "invalid redirect URI" errors, set **OAuth Redirect Host** to `https://books.example.com`.

With **Enable OAuth Group-Based Admin Role Management** under *Security*, group membership at the provider can decide
who is an administrator.

Users created through OAuth have no password, so they cannot sign in to KOReader or OPDS until you
set one. Set a password for each of them before going back to standard login.

**Disable Standard Login** removes the username and password form. Test your provider first.

### Reverse proxy authentication

Use this when a proxy such as Authelia or Authentik has already signed the user in. Turn on **Allow
Reverse Proxy Authentication** and set the header name, usually `Remote-User`.

> [!CAUTION]
> Scriptorium trusts that header completely. Anyone who can reach Scriptorium without passing through
> the proxy can sign in as any user. Do not publish port 8083: use a private Docker network.

Exclude these paths from your proxy's login, because devices cannot complete a browser sign-in:
`/kobo/`, `/kosync` and `/opds`.

## Email

See [Set up the mail server](ereaders.md#1-set-up-the-mail-server-administrator).

## Scheduled tasks

*Settings → Scheduled tasks* sets a daily maintenance window, while the library is quiet.

| Setting | Default | What it does |
| --- | --- | --- |
| **Start Time** | 4:00 | When maintenance starts. |
| **Maximum Duration** | 10 hours | When it must stop. |
| **Scheduled Thumbnail Refresh** | On | Refreshes all thumbnails. They are also made on demand. |
| **Reconnect Calibre Database** | Off | Picks up changes made outside Scriptorium. |
| **Generate Metadata Backup Files** | Off | Writes a `metadata.opf` next to each book, so the catalogue can be rebuilt in Calibre if `metadata.db` is lost. |

Time zones come from `TZ`. Running and finished jobs are listed under *Tasks* in the sidebar.

## Monitoring

| Where | What it tells you |
| --- | --- |
| **Check Service Status** | Whether each background service is running. Start here when automation seems stuck. |
| **Statistics** | Usage over time: active users, downloads, books read, searches and system information, with a CSV export. |
| **Logs & history** (*Library tools*) | The logs of every import, conversion and fix. |
| **About** (account menu) | Installed version and library totals. |
| **Tasks** | Conversions, emails and maintenance in progress. |

The main log is the container's output: run `docker compose logs -f`. More detail is available under *Settings → Server & features → Server → Log Level*.

## System actions

Under *System* on the Settings page:

- **Download Debug Package**: settings, library versions and the access log in a zip, for bug reports.
  Passwords, API keys, tokens and Kobo sync addresses are left out, but your folder paths, server names
  and the addresses in the access log are not, so look through it before posting it in public.
- **Reconnect Calibre Database**: reloads `metadata.db`.
- **Restart** and **Shutdown**: restart or stop the app.

## Hardcover

[Hardcover](https://hardcover.app) is a free reading tracker, and Scriptorium connects to it in three
ways:

| Use | Set up with |
| --- | --- |
| **Metadata provider** | A user's *Hardcover API Token* (*Profile → Preferences*), or the key in Settings, or `HARDCOVER_TOKEN`. |
| **Automatic matching** of the library | *Automation → Hardcover*. See [Metadata](automation.md#metadata). |
| **Reading progress and highlights** from the Kobo | *Enable Hardcover Sync*, and *Sync Kobo annotations to Hardcover*. Each user needs their own token. |
