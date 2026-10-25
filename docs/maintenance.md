# Updates, rollback, and removal

These commands are for an installation created with this repository's helper.
Set `MAILCOW_DIR` to the existing mailcow directory and run as root.

```bash
MAILCOW_DIR=/opt/mailcow-dockerized
```

```bash
cd "$MAILCOW_DIR"
```

## Backups

Keep your normal mailcow database/data backups and a secure copy of
`modern-ui/secrets.env`. The API's `restv2_` tables are in the mailcow database.
The application key must survive upgrades and reinstalls; changing it invalidates
encrypted application state. Do not put that file in a public repository or issue.

Before an upgrade, record the currently running image digests:

```bash
docker inspect --format '{{.Name}} {{.Image}}' "$(docker compose ps -q restv2-mailcow)" "$(docker compose ps -q ng-mailcow)"
```

The output identifies local image IDs. Get their registry digests (keep both lines):

```bash
docker image inspect --format '{{json .RepoDigests}}' "$(docker inspect --format '{{.Image}}' "$(docker compose ps -q restv2-mailcow)")" "$(docker inspect --format '{{.Image}}' "$(docker compose ps -q ng-mailcow)")"
```

## Update

For an Ansible installation, update this repository on the controller and rerun the
playbook with the same inventory. For a manual installation:

```bash
git -C /opt/mailcow-modern-ui pull --ff-only
```

```bash
python3 /opt/mailcow-modern-ui/scripts/manage.py configure --mailcow-dir "$MAILCOW_DIR"
```

That command selects `latest`. If you pinned images, pass the intended `--api-image`
and `--ui-image` values again. The existing application key is preserved.

```bash
docker compose pull restv2-mailcow ng-mailcow
```

```bash
docker compose up -d --no-deps --wait --wait-timeout 180 restv2-mailcow ng-mailcow
```

```bash
python3 /opt/mailcow-modern-ui/scripts/manage.py activate --mailcow-dir "$MAILCOW_DIR"
```

```bash
docker compose restart ofelia-mailcow
```

Check both public URLs as in the [installation guide](installation.md#9-verify-and-sign-in).
Use `/` for the UI check if you selected root mode. Manual activation preserves the saved
URL selection; Ansible applies `modern_ui_path` from your inventory on every run.
After updating **mailcow itself**, verify that its schema is supported by the API before
updating these containers. The API readiness check enforces its supported schema list.

## Roll back images

Use the previously recorded API and UI registry digests with `configure`:

```bash
python3 /opt/mailcow-modern-ui/scripts/manage.py configure --mailcow-dir "$MAILCOW_DIR" --api-image ghcr.io/feldsam-inc/mailcow-rest-v2@sha256:PREVIOUS_API_DIGEST --ui-image ghcr.io/feldsam-inc/mailcowui-ng@sha256:PREVIOUS_UI_DIGEST
```

Replace the placeholders, then repeat the pull, start, activate, and Ofelia commands
above. Check compatibility notes before downgrading: changing images does not reverse
database migrations. If a release needs a database rollback, restore its matching backup.
Before reverting to a UI image without root-routing support, switch back to `/ng/` using
`activate --ui-path /ng/ --mailcow-dir "$MAILCOW_DIR"`.

## Uninstall the addon

Remove the routes first, while the containers still exist:

```bash
python3 /opt/mailcow-modern-ui/scripts/manage.py deactivate --mailcow-dir "$MAILCOW_DIR"
```

```bash
docker compose stop restv2-mailcow ng-mailcow
```

```bash
docker compose rm -f restv2-mailcow ng-mailcow
```

```bash
python3 /opt/mailcow-modern-ui/scripts/manage.py detach --mailcow-dir "$MAILCOW_DIR"
```

```bash
docker compose restart ofelia-mailcow
```

The managed Compose include is removed; other overrides remain. The classic interface
continues to work. The application key, local configuration backups, and API database
tables remain for a later reinstall. Mail, mailboxes, and mailcow volumes are retained.
Deactivation removes all managed nginx routes, including the optional root snippets.
The saved URL preference remains for a later reinstall.
Do not use `docker compose down -v` to remove this addon: it targets the entire mailcow project.

## Troubleshooting

Check service status and recent logs:

```bash
docker compose ps restv2-mailcow ng-mailcow
```

```bash
docker compose logs --tail 100 restv2-mailcow ng-mailcow
```

```bash
docker compose logs --tail 100 nginx-mailcow
```

- **Unsupported schema:** use a mailcow release supported by the API. Do not bypass readiness.
- **Images denied:** these images are public. Check the image spelling, registry reachability,
  and any stale local Docker credentials.
- **Compose validation fails:** run `docker compose config --quiet` on the server. Avoid sharing
  full `docker compose config` output: it includes resolved database passwords and the API key.
- **nginx activation fails:** the helper restores the previous file. Run
  `docker compose exec -T nginx-mailcow nginx -t` to inspect the error, resolve it, and retry activation.
- **New UI returns 502:** verify both addon services are healthy and the nginx snippet is active.
- **Ansible HTTPS checks fail:** verify the server can reach its public hostname and trusts the
  certificate chain. TLS verification is enabled.
- **Key missing:** restore `modern-ui/secrets.env` from backup. The helper refuses to silently
  generate a replacement key for an existing managed installation.
