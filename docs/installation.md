# Manual installation

Run these commands on an **existing mailcow server**, as root or with `sudo`.
Use one block at a time and stop if it fails.

Use mailcow **2026-09a or newer**, including **2026-10**. Older releases remain untested:
`2026-09` shares the accepted schema, while releases through `2026-07b` currently fail
the API's schema check. See [compatibility and schema history](compatibility.md).

You also need a working HTTPS certificate,
Git, Python **3.9+** for the published preview's helper, and Docker Compose **2.20.3+**.
Docker, mailcow, and its database must already be running. Keep your usual mailcow
backup before installing an addon.

The helper on `main` also supports Python **3.6+** and the existing-installation update
mode below. Those installer fixes are not included in older preview tags.

## 1. Download

```bash
git clone --branch v0.1.0-preview.5 --depth 1 https://github.com/FELDSAM-INC/mailcow-modern-ui.git /opt/mailcow-modern-ui
```

## 2. Set your mailcow directory

Change this path if mailcow is elsewhere, for example `/root/mailcow-dockerized`.
Keep the same shell for the remaining commands.

```bash
MAILCOW_DIR=/opt/mailcow-dockerized
```

## 3. Prepare configuration

```bash
python3 /opt/mailcow-modern-ui/scripts/manage.py configure --mailcow-dir "$MAILCOW_DIR"
```

The default image pair is pinned in [this preview's release manifest](../deploy/release.json).
Re-running these commands installs the same UI and API builds.
The same builds are publicly available as `ghcr.io/feldsam-inc/mailcow-rest-v2:0.1.0-preview.5`
and `ghcr.io/feldsam-inc/mailcowui-ng:0.1.0-preview.5`; the installer uses their fixed digests.

This adds a managed `include` to `docker-compose.override.yml`, preserves other
services and comments, generates the application key once, and validates Compose.
The key is stored in `modern-ui/secrets.env` (mode `0600`) inside a private directory.
An existing `RESTV2_APP_KEY` in `mailcow.conf` is retained. The helper does not edit
`mailcow.conf`. An existing override is backed up in `modern-ui/override.before-install`.

The `modern-ui/.gitignore` excludes that entire directory from mailcow's Git repository,
including during an upstream update. Back up `modern-ui/secrets.env` securely.

## 4. Open the mailcow directory

```bash
cd "$MAILCOW_DIR"
```

## 5. Pull the published images

```bash
docker compose pull restv2-mailcow ng-mailcow
```

## 6. Start the API and UI

```bash
docker compose up -d --no-deps --wait --wait-timeout 180 restv2-mailcow ng-mailcow
```

This starts only the two new services and waits for health checks. API startup creates
its own database tables. Stop here if readiness fails; see [troubleshooting](maintenance.md#troubleshooting).

## 7. Activate the web routes

```bash
python3 /opt/mailcow-modern-ui/scripts/manage.py activate --mailcow-dir "$MAILCOW_DIR"
```

This installs `data/conf/nginx/site.restv2.custom`, runs `nginx -t`, and reloads nginx.
If validation or reload fails, it restores the previous routing files and URL selection.

## 8. Register scheduled jobs

```bash
docker compose restart ofelia-mailcow
```

Ofelia discovers the API's job labels at startup. This enables audit retention,
mass mail processing, and expired webmail handoff cleanup.

## 9. Verify and sign in

```bash
docker compose ps restv2-mailcow ng-mailcow
```

Both services should be healthy. Replace `mail.example.org` with your hostname:

```bash
curl -fsS https://mail.example.org/api/v2/health/ready
```

```bash
curl -fsSI https://mail.example.org/ng/
```

Open **https://mail.example.org/ng/** and use your existing mailcow account.

## Optional: use `/` instead of `/ng/`

After starting the current UI image, choose the root URL:

```bash
python3 /opt/mailcow-modern-ui/scripts/manage.py activate --mailcow-dir "$MAILCOW_DIR" --ui-path /
```

Open **https://mail.example.org/**. The classic interface remains available at
**https://mail.example.org/index.php**. Old `/ng/` bookmarks, password-reset links,
and SSO return URLs continue to work; existing identity-provider callback registrations
can stay unchanged. Static assets still use `/ng/`.

The helper verifies that the running UI image supports this mode before changing nginx.
An older image must be updated first. Only the UI's declared routes are forwarded:
mailcow's APIs, SOGo, DAV, ActiveSync, autodiscovery, ACME, PHP handlers, and internal
listeners retain their existing routing. Query-bearing requests to `/` and non-GET/HEAD
requests continue to use the classic handlers. Custom nginx routes sharing a UI namespace
need an operator review; this is not a catch-all replacement of mailcow's web server.

The selection is saved. Later `activate` commands without `--ui-path` preserve it.
To switch back:

```bash
python3 /opt/mailcow-modern-ui/scripts/manage.py activate --mailcow-dir "$MAILCOW_DIR" --ui-path /ng/
```

Both switches test and reload nginx, with automatic restoration if activation fails.

## Image overrides and the development channel

The preview already uses fixed image digests. To select another compatible pair,
use `--api-image` and `--ui-image` in step 3:

```bash
python3 /opt/mailcow-modern-ui/scripts/manage.py configure --mailcow-dir "$MAILCOW_DIR" --api-image ghcr.io/feldsam-inc/mailcow-rest-v2@sha256:API_DIGEST --ui-image ghcr.io/feldsam-inc/mailcowui-ng@sha256:UI_DIGEST
```

Replace the digest placeholders with real published values from the
[API package](https://github.com/orgs/FELDSAM-INC/packages/container/package/mailcow-rest-v2)
and [UI package](https://github.com/orgs/FELDSAM-INC/packages/container/package/mailcowui-ng).
Record both values and use them again when reconfiguring. Image settings are stored in
`modern-ui/compose.yml`; rerunning `configure` without image arguments selects the pair
from the checked-out release manifest.

To explicitly follow successful development builds, pass
`--api-image ghcr.io/feldsam-inc/mailcow-rest-v2:latest` and
`--ui-image ghcr.io/feldsam-inc/mailcowui-ng:latest` to `configure` instead.

## Existing installations and custom Compose layouts

Ordinary service overrides are preserved. The helper deliberately stops before replacing
existing `restv2-mailcow` / `ng-mailcow` services, an existing unmanaged nginx snippet,
an existing top-level `include`, flow-style YAML, or a custom `COMPOSE_FILE` setup.
It expects mailcow's usual `.env` symlink to `mailcow.conf`.

**Already using the API/UI:** `update-images` updates an existing custom deployment
whose two services have ordinary block-style definitions and literal image references
in `docker-compose.override.yml`. Use the installer from `main` until these changes are
included in a new preview:

```bash
python3 /opt/mailcow-modern-ui/scripts/manage.py update-images --mailcow-dir "$MAILCOW_DIR" --api-image ghcr.io/feldsam-inc/mailcow-rest-v2:latest --ui-image ghcr.io/feldsam-inc/mailcowui-ng:latest
```

Use published version tags or digests instead of `latest` to pin a fixed pair. This
command changes only the two image references. It preserves the existing application
key, environment files, branding, mounts, nginx routes, and other services. It saves a
private backup in `modern-ui/override.before-image-update`, verifies that all other
effective Compose settings are identical, and restores the override on failure. It
does not create a managed installation or start containers.

For an automated pull, restart and health check, use Ansible's
[`modern_ui_existing_installation` mode](ansible.md#existing-custom-installations).
Other layouts still require manual integration. Keep the existing nginx routing when
using this update mode; `activate` and `deactivate` are for managed installations.

**Existing top-level `include`:** you can integrate manually. Copy the two service
definitions from [the template](../deploy/compose.yml) into your Compose configuration,
replace `@API_IMAGE@` and `@UI_IMAGE@` with published image references, and provide
`APP_KEY` in the referenced private environment file. Resolve bind mounts from the
mailcow directory. Validate with `docker compose config --quiet`, then use steps 5–6.
Copy the [nginx snippet](../deploy/nginx/site.restv2.custom) to
`data/conf/nginx/site.restv2.custom`, test and reload nginx, and finish with steps 8–9.
Use your own configuration management for this layout; the helper's activation and
uninstall commands require its ownership marker.

The include mechanism is documented in
[Docker's Compose guide](https://docs.docker.com/compose/how-tos/multiple-compose-files/include/).
