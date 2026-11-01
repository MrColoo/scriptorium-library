# Remote access

At home, `http://192.168.1.50:8083` is all you need. This guide is for reaching your library from
anywhere, and for getting HTTPS, which the [installable app](using-scriptorium.md#install-it-as-an-app)
requires.

> [!CAUTION]
> Do not simply forward port 8083 on your router. That puts an unencrypted login page on the public
> internet: your password would travel in clear text, and anyone could probe your server.

## Which option is right for you?

| | Tailscale | Cloudflare Tunnel | Reverse proxy |
| --- | --- | --- | --- |
| **Difficulty** | Easy | Medium | Medium to hard |
| **You need** | A free account and an app on each device | A domain and a free account | A domain and two open ports on your router |
| **Who can reach it** | Only your own devices | The internet | The internet |
| **Phone and browser** | ✅ | ✅ | ✅ |
| **Kobo away from home** | ❌ It cannot join a VPN | ✅ | ✅ |
| **KOReader away from home** | Only where Tailscale runs, such as Android | ✅ | ✅ |
| **Installable app** | ✅ With `tailscale serve` | ✅ | ✅ |
| **Good to know** | The safest choice: nothing is public | Works when your provider blocks incoming ports. Cloudflare can see your traffic, and limits upload size | Everything stays under your control |

**Not sure? Start with Tailscale.** You can change later, and nothing about your library depends on
it. If you only need your Kobo to sync when it is at home, Tailscale is all you will ever need.

## Tailscale

[Tailscale](https://tailscale.com) connects your devices in a private network. Nothing is exposed to
the internet, and you do not touch your router.

1. Create a free account, and install Tailscale on your server and your phone.
2. On the server, turn on HTTPS for your library:

   ```bash
   sudo tailscale serve --bg 8083
   ```

3. It prints an address such as `https://server.your-tailnet.ts.net`. Open that on your phone.

The first time, the command may ask you to enable HTTPS and MagicDNS in the Tailscale admin console,
and shows a link to do so. See [Tailscale's guide](https://tailscale.com/kb/1242/tailscale-serve).

## Reverse proxy with Caddy

[Caddy](https://caddyserver.com) is the simplest proxy to start with: it gets and renews HTTPS
certificates on its own.

**You need:**

- a domain, or a subdomain such as `books.example.com`, pointing to your home's public IP. If that
  IP changes, use a dynamic DNS service;
- ports 80 and 443 on your router forwarded to the server.

Add Caddy to your `docker-compose.yml`, under `services:`, next to `scriptorium`:

```yaml
  caddy:
    image: caddy:2
    container_name: caddy
    restart: unless-stopped
    ports:
      - 80:80
      - 443:443
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - ./caddy-data:/data
```

Create a file named `Caddyfile` next to it:

```caddy
books.example.com {
    reverse_proxy scriptorium:8083
}
```

Start it with `docker compose up -d`, wait a minute, and open `https://books.example.com`. Then do
the [final steps](#final-steps).

## Reverse proxy with nginx

```nginx
server {
    listen 443 ssl;
    http2 on;
    server_name books.example.com;

    ssl_certificate     /etc/letsencrypt/live/books.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/books.example.com/privkey.pem;

    # Book uploads, and the large headers and responses of Kobo sync
    client_max_body_size 0;
    proxy_buffer_size 128k;
    proxy_buffers 4 256k;
    proxy_busy_buffers_size 256k;

    location / {
        proxy_pass http://127.0.0.1:8083;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
    }
}
```

The `http2 on;` line needs nginx 1.25.1 or newer. On older versions, use `listen 443 ssl http2;`.

## Reverse proxy with Traefik

Add these labels to the `scriptorium` service, adjusting the entry point and certificate resolver to
your own Traefik setup:

```yaml
    labels:
      - traefik.enable=true
      - traefik.http.routers.scriptorium.rule=Host(`books.example.com`)
      - traefik.http.routers.scriptorium.entrypoints=websecure
      - traefik.http.routers.scriptorium.tls.certresolver=letsencrypt
      - traefik.http.services.scriptorium.loadbalancer.server.port=8083
```

## Cloudflare Tunnel

A tunnel connects your server outwards to Cloudflare, so no ports are opened on your router.

1. Add your domain to Cloudflare, and in **Zero Trust → Networks → Tunnels** create a tunnel.
   Copy its token.
2. Add the connector to your `docker-compose.yml`:

   ```yaml
     cloudflared:
       image: cloudflare/cloudflared:latest
       container_name: cloudflared
       restart: unless-stopped
       command: tunnel run
       environment:
         - TUNNEL_TOKEN=your-tunnel-token
   ```

3. In the tunnel settings, add a public hostname `books.example.com` with the service
   `http://scriptorium:8083`.

Limits to keep in mind:

- Cloudflare's free plan limits uploads to 100 MB per request. Larger books will fail through the
  tunnel, but can still go through the ingest folder.
- Cloudflare's terms restrict some uses of its network for serving large files. Read them, and
  consider a reverse proxy for heavy use.
- Cloudflare decrypts traffic on its servers. If that matters to you, choose another option.

## Final steps

Once your HTTPS address works:

1. Open Scriptorium **from the HTTPS address** and turn on *Settings → Server & features → Security →
   Use via HTTPS*. Session cookies are then marked `Secure`.

   > [!WARNING]
   > After this, you can no longer sign in over plain HTTP, such as `http://192.168.1.50:8083`. Only
   > turn it on when HTTPS works, and use the HTTPS address from then on.

2. Check that **Limit failed login attempts** is still on in the same section. It is on by default.
3. If your Kobo should sync from anywhere, open *Profile → Devices* from the public address and
   create the sync address again from there. Paste the new line into the Kobo.
4. Consider closing the direct route: remove the `ports:` section from `scriptorium` once Caddy
   reaches it over the Docker network.
5. Read [Security](security.md).

## More than one proxy

Scriptorium trusts one proxy by default, which covers everything above.

If there is more than one hop in front of it, for example Cloudflare Tunnel → nginx → Scriptorium,
set `TRUSTED_PROXY_COUNT` to the number of proxies. If it is too low, Scriptorium sees a different
client address on each request, and session protection logs users out.

Scriptorium reads `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Host` and
`X-Forwarded-Prefix` from the proxy.

## Serving from a sub-path

A subdomain such as `books.example.com` is simpler and is what these guides assume. To serve from
`example.com/books` instead, send the prefix in the `X-Script-Name` header:

```nginx
location /books {
    proxy_pass http://127.0.0.1:8083;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Scheme $scheme;
    proxy_set_header X-Script-Name /books;
}
```

The Kobo and the installed app have not been tested on a sub-path.

## Kobo through a proxy

The proxy must pass requests to `/kobo/` unchanged and allow large responses, such as cover images
and book downloads. The nginx example above already includes the limits Kobo needs. Self-signed
certificates are rejected by the Kobo, so use a public certificate such as Let's Encrypt.
