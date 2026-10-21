# Deploying Quarry

Quarry deploys the same way as Gauntlet:

* One Docker container on the droplet, listening on `127.0.0.1:8091`.
* The image comes from `ghcr.io/daevil1/quarry`. GitHub Actions builds it on every push to `master`, so the
  droplet never builds anything.
* The host's nginx serves HTTPS and proxies to the container.
* The database is the DigitalOcean managed PostgreSQL.

The address below is `quarry.daevil1.com`. Choose it before the first passkey is made: passkeys are bound to
the host name, so moving Quarry to another domain later means registering new passkeys.

## 1. Database (DigitalOcean)

1. **Databases ›** your cluster **› Users & Databases**: add the user `quarry` and the database `quarry`.
2. **Settings › Trusted sources**: the droplet should already be there (Gauntlet uses it).
3. **Overview › Connection details**: database `quarry`, user `quarry`. Copy host, port and password, or the
   connection string (keep `?sslmode=require`).
4. Connected as `doadmin` to the database `quarry`, run `GRANT USAGE, CREATE ON SCHEMA public TO quarry;`
   (PostgreSQL 15+ no longer lets every user create tables in `public`).

Quarry creates its tables at startup and keeps at most 5 connections.

## 2. The image

`.github/workflows/ci.yml` pushes `ghcr.io/daevil1/quarry:latest` after the tests pass on `master`.

The package inherits the repository's visibility, so it is public and the droplet pulls it without logging in.
(If it were ever private: log in once on the droplet with a classic token that has only `read:packages`,
`docker login ghcr.io -u DaEvil1`.)

## 3. The app (on the droplet)

The repository is public, so the droplet fetches the three files itself. On the droplet (`ssh root@usjibush.com`):

```bash
mkdir -p /srv/quarry && cd /srv/quarry
curl -fsSLO https://raw.githubusercontent.com/DaEvil1/quarry/master/deploy/compose.yaml
curl -fsSL https://raw.githubusercontent.com/DaEvil1/quarry/master/deploy/quarry.env.example -o quarry.env
curl -fsSLO https://raw.githubusercontent.com/DaEvil1/quarry/master/deploy/nginx-quarry.conf
echo "QUARRY_IMAGE=ghcr.io/daevil1/quarry:latest" > .env && chmod 600 quarry.env
```

Fill in `quarry.env`:

| Setting | Value |
|---|---|
| `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGSSLMODE=require` | from step 1 (or one `QUARRY_DATABASE_URL`) |
| `QUARRY_BASE_URL` | `https://quarry.daevil1.com` |
| `QUARRY_SETUP_TOKEN` | output of `openssl rand -hex 24` (keep it in your password manager until setup is done) |

```bash
docker compose up -d
docker compose logs -f app          # "Application startup complete", then Ctrl+C (the container keeps running)
curl -s http://127.0.0.1:8091/healthz     # ok
```

## 4. DNS and HTTPS

1. Domeneshop › **Mine domener › daevil1.com › DNS-pekere**: write `quarry` on the left of `.daevil1.com`, the
   droplet's IP (`167.99.83.56`) on the right, and press **+**. There is no wildcard record and no `AAAA` (the
   droplet isn't serving IPv6), so only this `A` record is needed. It answers within minutes:
   `nslookup quarry.daevil1.com`.
2. On the droplet:

```bash
sudo cp /srv/quarry/nginx-quarry.conf /etc/nginx/sites-available/quarry
sudo ln -s /etc/nginx/sites-available/quarry /etc/nginx/sites-enabled/quarry
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d quarry.daevil1.com
```

The proxy must pass `Host` through (the provided config does): the app refuses writes whose `Origin` doesn't
match.

## 5. First run

1. Open https://quarry.daevil1.com on your desktop. It goes to **Set up Quarry**.
2. Enter the setup token, your name and a name for this device, and create the passkey (Windows Hello, Touch ID
   or a security key).
3. Save the ten recovery codes somewhere that is not this computer.
4. Create the first world.
5. On the Android phone, open the same address in Chrome and give the phone a passkey of its own:
   * A passkey in Windows Hello can't be used from the phone. The QR code in a passkey prompt only works the
     other way round: a computer shows it, and a phone scans it to act as the computer's passkey.
   * A passkey in 1Password should sync to the phone, but Chrome on Android didn't offer it (Pixel 8,
     Android 17, Chrome set to "Autofill using another service": it still went straight to Google Password
     Manager). Webauthn.io behaved the same, so it is not something Quarry can fix.
   * What works: **Lost your passkey?** → a recovery code → **Settings › Add passkey**. Chrome saves it in
     Google Password Manager. Then **Make new codes** if you want the full ten again.
   * Chrome's menu › **Add to home screen** installs Quarry. It opens on Capture, and appears in Android's share
     sheet.

Once set up, `QUARRY_SETUP_TOKEN` is ignored; you may remove it from `quarry.env`.

## Updating

```bash
cd /srv/quarry && docker compose pull && docker compose up -d
```

Migrations run at startup. The managed cluster's daily backups cover the database.

## Locked out

If every passkey is gone and the recovery codes are lost, reset from the droplet:

```bash
cd /srv/quarry && docker compose exec app quarry users
docker compose exec app quarry passkey reset "<your name or user id>"
```

It removes that user's passkeys and sessions and prints ten new recovery codes.

## If something is off

| Symptom | Likely cause |
|---|---|
| "Passkeys only work on the address Quarry is set up for" | `QUARRY_BASE_URL` doesn't match the address in the browser |
| The passkey prompt never appears | the page isn't on HTTPS (only `localhost` may use plain HTTP) |
| "Cross-site request refused." | nginx isn't passing `Host`, or `QUARRY_BASE_URL` has the wrong host |
| Database timeout in `docker compose logs app` | the droplet isn't under *Trusted sources* |
