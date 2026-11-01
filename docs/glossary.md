# Glossary

Plain explanations of the words you will meet in these guides.

## Self-hosting

**Bind mount.** A folder on your computer that is shown to a container. The lines under `volumes:`
in `docker-compose.yml` are bind mounts: `./library:/calibre-library` means "my `library` folder
appears inside the container as `/calibre-library`".

**Container.** A sealed box that holds an app and everything it needs. Removing a container does
not remove your books or settings, because those live in folders outside it.

**Docker.** The tool that downloads and runs containers.

**Docker Compose.** The part of Docker that reads `docker-compose.yml`, so you can start everything
with one command instead of a very long one.

**Domain.** A name such as `books.example.com` that points to a server, so you do not have to
remember an IP address.

**Environment variable.** A setting passed to a container, written as `NAME=value`. They go under
`environment:` in `docker-compose.yml`.

**Host.** The computer that runs Docker, as opposed to the inside of the container.

**HTTPS.** The encrypted version of HTTP: the padlock in your browser. You need it as soon as your
library is reachable from the internet.

**Image.** The packaged app that Docker downloads. A container is a running copy of an image.

**IP address.** A machine's number on a network, such as `192.168.1.50`. Addresses starting with
`192.168.`, `10.` or `172.16`–`172.31` only work inside your home network.

**LAN.** Your local network: the devices connected to your home router.

**Localhost.** "This same computer". `http://localhost:8083` only works in a browser on the machine
that runs Scriptorium. From your phone, `localhost` would mean the phone itself.

**NAS.** A small always-on computer built to store files.

**Port.** A numbered door on a computer. Scriptorium listens on door 8083, which is why the address
ends in `:8083`.

**PUID and PGID.** The numbers of the Linux user and group that own the files Scriptorium writes.

**Reverse proxy.** A program that receives web traffic and passes it to the right app. It is also
where HTTPS usually lives. See [Remote access](remote-access.md).

**Tag.** A label for one version of an image: `latest`, `v1.1.0`. See
[Choosing a version](updating-and-backups.md#choosing-a-version).

**Volume.** Docker's word for storage that outlives a container. In these guides it means the
bind mounts described above.

**VPN.** A private, encrypted link between your devices. Tailscale is a popular and easy one.

## Ebooks

**ACSM.** Not a book, but a small Adobe file used to download a DRM-protected book. Scriptorium
cannot open DRM-protected books.

**Calibre.** The well-known desktop app for managing ebooks. Scriptorium uses a standard Calibre
library and Calibre's conversion tools, but you do not need Calibre installed.

**Calibre library.** A folder holding `metadata.db` and one folder per author, with the book files
inside. You can open it in Calibre desktop at any time.

**DRM.** Copy protection applied to some bought ebooks. Protected files cannot be converted or
read outside the shop's own apps.

**E-reader.** A device with an e-ink screen, such as a Kobo or Kindle.

**EPUB.** The most common open ebook format.

**KEPUB.** An EPUB with small additions for Kobo devices: better page numbers, reading statistics
and faster page turns.

**KOReader.** Free reading software you can install on many e-readers and on Android.

**Metadata.** Information about a book: title, author, series, description, cover and so on.

**OPDS.** A standard way for reading apps to browse a library over the network, like an app store
for your own books.

## Scriptorium

**Ingest.** Importing a book. The *ingest folder* is the inbox that Scriptorium watches.

**Provider.** An online source of metadata, such as Google Books or Hardcover.

**Shelf.** A list of books you make by hand.

**Smart shelf.** A shelf that fills itself from rules you set, such as "unread science fiction".

**Sync address.** The personal link that connects a Kobo to your library.

**Target format.** The format every imported book is converted to, usually EPUB or KEPUB.
