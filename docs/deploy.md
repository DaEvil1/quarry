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

* The repository is public, so the package can be public too: on GitHub, **your profile › Packages › quarry ›
  Package settings › Change visibility › Public**. Then the droplet pulls without logging in.
* If you keep the package private, log in on the droplet once with a classic token that has only
  `read:packages`: `docker login ghcr.io -u DaEvil1`.

## 3. The app (on the droplet)

From the repo checkout on your PC:

```bash
ssh droplet "sudo mkdir -p /srv/quarry && sudo chown \$USER /srv/quarry"
scp deploy/compose.yaml droplet:/srv/quarry/compose.yaml
scp deploy/quarry.env.example droplet:/srv/quarry/quarry.env
scp deploy/nginx-quarry.conf droplet:/srv/quarry/nginx-quarry.conf
```

On the droplet:

```bash
cd /srv/quarry
echo "QUARRY_IMAGE=ghcr.io/daevil1/quarry:latest" > .env
chmod 600 quarry.env
```

Fill in `quarry.env`:

| Setting | Value |
|---|---|
| `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGSSLMODE=require` | from step 1 (or one `QUARRY_DATABASE_URL`) |
| `QUARRY_BASE_URL` | `https://quarry.daevil1.com` |
| `QUARRY_SETUP_TOKEN` | output of `python3 -c "import secrets; print(secrets.token_urlsafe(24))"` |

```bash
docker compose up -d
docker compose logs -f app          # "Application startup complete", then Ctrl+C
curl -s http://127.0.0.1:8091/healthz     # ok
```

## 4. DNS and HTTPS

1. Domeneshop › daevil1.com › DNS: an `A` record `quarry` pointing at the droplet (skip if a wildcard exists).
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
5. On the Android phone: open the same address in Chrome and sign in. Chrome offers your phone, or a passkey
   saved in Google Password Manager. If the desktop's passkey isn't available on the phone, sign in with a
   recovery code there, then **Settings › Add passkey** on the phone. Afterwards, Chrome's menu ›
   **Add to home screen** installs Quarry as an app.

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
