# Install with Ansible

Run Ansible on your workstation or automation host. It connects over SSH to an
**existing, running mailcow server**. The server needs Python 3.9+, Docker Compose
2.20.3+, mailcow **2026-09a or newer** (including **2026-10**), and a working HTTPS URL.
Older mailcow releases remain untested. `2026-09` shares the accepted schema; releases
through `2026-07b` currently fail the API's schema check.
See [compatibility and the database schema check](compatibility.md).

The playbook uses only `ansible-core` built-in modules; no Galaxy collections or
application build tools are required. Use a supported Ansible release on the controller.
The target Python version must also be supported by that Ansible release.

## 1. Download

```bash
git clone --branch v0.1.0-preview.2 --depth 1 https://github.com/FELDSAM-INC/mailcow-modern-ui.git
```

```bash
cd mailcow-modern-ui
```

## 2. Copy the inventory

```bash
cp ansible/inventory.example.yml ansible/inventory.yml
```

## 3. Edit your server settings

```bash
nano ansible/inventory.yml
```

Set the SSH hostname, `ansible_user`, `mailcow_dir`, and `mailcow_url`.
Use the server's real HTTPS hostname, without a trailing slash.
SSH keys are recommended; leave host key checking enabled.
The inventory is ignored by Git.

To serve the interface at `https://mail.example.org/`, set `modern_ui_path: /`.
The default is `/ng/`. Keep this setting in your inventory for later runs; changing it
back to `/ng/` restores the classic root page. See the
[root URL behaviour](installation.md#optional-use--instead-of-ng) for endpoint compatibility.

## 4. Install

```bash
ansible-playbook -i ansible/inventory.yml ansible/install.yml
```

If your SSH user needs a sudo password, add `--ask-become-pass`.

The playbook copies only deployment files, preserves the API key, validates Compose,
pulls both public images, waits for the two services to become healthy, safely reloads
nginx, refreshes Ofelia when needed, and checks both URLs over HTTPS from the server.
It uses the same configuration helper and template as manual installation.

## Updates and pinned versions

Check out the desired release tag on the controller and run the same playbook again.
The default images are the fixed pair in [deploy/release.json](../deploy/release.json).
From the controller's `mailcow-modern-ui` directory, fetch the release tags:

```bash
git fetch --tags origin
```

Select the desired release (replace this tag when a newer release is available):

```bash
git checkout v0.1.0-preview.2
```

Then rerun the install command with the same inventory. The application key is retained.
Unchanged container/configuration state does not trigger an nginx reload or
Ofelia restart. Pulling checks for a newer image; a new image can recreate its service.

| Inventory variable | Default | Purpose |
| --- | --- | --- |
| `mailcow_dir` | Required | Existing mailcow directory |
| `mailcow_url` | Required | Public HTTPS origin |
| `modern_ui_path` | `/ng/` | Browser URL path: `/ng/` or `/` |
| `modern_ui_api_image` | Release manifest API digest | Override the API image tag or digest |
| `modern_ui_web_image` | Release manifest UI digest | Override the UI image tag or digest |
| `modern_ui_tools_dir` | `/opt/mailcow-modern-ui` | Remote deployment helper directory |
| `modern_ui_pull` | `true` | Pull images before starting; set false for already loaded images |

Release defaults already use fixed digests. Explicit inventory image settings override
them; remove those settings to follow the selected release's image pair. The `:latest`
tags select the moving development channel.

This playbook follows the same
[existing-installation restrictions](installation.md#existing-installations-and-custom-compose-layouts)
as the manual helper. It does not install or upgrade mailcow itself.

The playbook applies changes and does not implement Ansible `--check` mode. Validate
its syntax without connecting to a server:

```bash
ansible-playbook -i ansible/inventory.yml ansible/install.yml --syntax-check
```

See [maintenance](maintenance.md) for backups, rollback, and removal.
