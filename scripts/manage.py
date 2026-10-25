#!/usr/bin/env python3
"""Prepare the shared Compose files and safely activate mailcow's nginx routes.

Python standard library only. Never source mailcow.conf or print resolved Compose
configuration: both can contain secrets. Container startup remains an explicit step.
"""

import argparse
import base64
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
SERVICES = ("restv2-mailcow", "ng-mailcow")
BLOCK = """# BEGIN mailcow-modern-ui
include:
  - path: ./modern-ui/compose.yml
    project_directory: .
    env_file: ./mailcow.conf
# END mailcow-modern-ui
"""
OWNER = "mailcow-modern-ui\n"


class InstallError(Exception):
    pass


def run(args, cwd):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode:
        # Docker errors can echo interpolated passwords. Keep them out of CI logs.
        raise InstallError("Command failed: " + " ".join(args) + ". Inspect it on the server.")
    return result.stdout


def compose(root, *args):
    command = [
        "docker",
        "compose",
        "--env-file",
        "mailcow.conf",
        "-f",
        "docker-compose.yml",
    ]
    if (root / "docker-compose.override.yml").exists():
        command += ["-f", "docker-compose.override.yml"]
    return run(command + list(args), root)


def snapshot(path):
    if path.is_symlink():
        raise InstallError("Refusing to replace a symlink: " + str(path))
    if path.exists():
        if not path.is_file():
            raise InstallError("Expected a regular file: " + str(path))
        return path.read_bytes(), path.stat().st_mode & 0o777
    return None


def write(path, content, mode=0o600):
    data = content.encode() if isinstance(content, str) else content
    previous = snapshot(path)
    if previous == (data, mode):
        return False
    # Atomic replacement also prevents a partly written secret/config on failure.
    fd, name = tempfile.mkstemp(prefix=".modern-ui-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            os.fchmod(stream.fileno(), mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return True


def restore(path, previous):
    if previous is None:
        path.unlink(missing_ok=True)
    else:
        write(path, *previous)


def private_directory(root):
    directory = root / "modern-ui"
    if directory.is_symlink():
        raise InstallError("modern-ui must be a real directory, not a symlink.")
    directory.mkdir(mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    write(directory / ".gitignore", "*\n")
    return directory


def preflight(root):
    for name in [
        "docker-compose.yml",
        "mailcow.conf",
        "data/conf/dovecot/global_sieve_before",
        "data/conf/dovecot/global_sieve_after",
    ]:
        if not (root / name).is_file():
            raise InstallError("Missing mailcow file: " + str(root / name))
    for name in [
        "data/conf/nginx",
        "data/web/inc",
        "data/web/lang",
        "data/conf/rspamd/custom",
        "data/assets/templates",
    ]:
        if not (root / name).is_dir():
            raise InstallError("Missing mailcow directory: " + str(root / name))
    if not (root / ".env").exists() or not (root / ".env").samefile(root / "mailcow.conf"):
        raise InstallError("Expected mailcow's standard .env symlink to mailcow.conf.")
    for name in [
        "compose.yml",
        "compose.yaml",
        "compose.override.yml",
        "compose.override.yaml",
        "docker-compose.override.yaml",
    ]:
        if (root / name).exists():
            raise InstallError(
                "Ambiguous Compose file: " + name + ". Use the documented manual integration."
            )
    if os.environ.get("COMPOSE_FILE") or re.search(
        r"^\s*(?:export\s+)?COMPOSE_FILE\s*=", (root / "mailcow.conf").read_text(), re.M
    ):
        raise InstallError(
            "Custom COMPOSE_FILE requires manual integration; no configuration was changed."
        )
    version = run(["docker", "compose", "version", "--short"], root).strip().lstrip("v")
    match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    if not match or tuple(map(int, match.groups())) < (2, 20, 3):
        raise InstallError("Docker Compose 2.20.3 or newer is required.")


def owned(root):
    if (root / "modern-ui").is_symlink():
        raise InstallError("modern-ui must be a real directory, not a symlink.")
    marker = root / "modern-ui/.managed-by"
    snapshot(marker)
    return marker.exists() and marker.read_text() == OWNER


def key_value(root, directory):
    path = directory / "secrets.env"
    snapshot(path)
    if path.exists():
        text = path.read_text()
        match = re.fullmatch(r"APP_KEY=(base64:[A-Za-z0-9+/]+={0,2})\n?", text)
    elif owned(root):
        raise InstallError(
            "The existing application key is missing. Restore modern-ui/secrets.env from backup."
        )
    else:
        # Retain a key an operator already placed in mailcow.conf.
        matches = re.findall(r"^RESTV2_APP_KEY=(.*)$", (root / "mailcow.conf").read_text(), re.M)
        if len(matches) > 1:
            raise InstallError("Duplicate RESTV2_APP_KEY entries in mailcow.conf.")
        value = (
            matches[0].strip().strip("\"'")
            if matches
            else "base64:" + base64.b64encode(secrets.token_bytes(32)).decode()
        )
        match = re.fullmatch(r"(base64:[A-Za-z0-9+/]+={0,2})", value)
    try:
        if not match or len(base64.b64decode(match[1][7:], validate=True)) != 32:
            raise ValueError()
    except ValueError:
        raise InstallError(
            "Invalid application key. Restore a valid 32-byte base64 key; it will not be regenerated."
        ) from None
    return "APP_KEY=" + match[1] + "\n"


def image_reference(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:@+-]*", value):
        raise argparse.ArgumentTypeError("Use a container image tag or digest, without whitespace.")
    return value


def configure(root, api_image, ui_image):
    preflight(root)
    override = root / "docker-compose.override.yml"
    previous_override = snapshot(override)
    text = previous_override[0].decode() if previous_override else ""
    managed = owned(root)
    if ("# BEGIN mailcow-modern-ui" in text or "# END mailcow-modern-ui" in text) and text.count(
        BLOCK
    ) != 1:
        raise InstallError("The managed include was edited. Restore its block before continuing.")
    if BLOCK in text and not managed:
        raise InstallError(
            "An existing include has no ownership marker. Restore its modern-ui directory."
        )
    if BLOCK not in text:
        # Appending to a YAML mapping with an existing include would duplicate a key.
        # Compose validates all other syntax before anything is changed.
        if re.search(
            r"^(?:include|'include'|\"include\")\s*:", text, re.M
        ) or text.lstrip().startswith("{"):
            raise InstallError(
                "The override already has an include or uses flow YAML. See manual integration in docs/installation.md."
            )
        existing = set(compose(root, "config", "--services").split())
        if existing.intersection(SERVICES):
            raise InstallError(
                "The API or UI is already configured. See migration instructions; no services were replaced."
            )
        text = text.rstrip() + ("\n\n" if text.strip() else "") + BLOCK
    nginx = root / "data/conf/nginx/site.restv2.custom"
    if nginx.exists() and not managed:
        raise InstallError(
            "Existing site.restv2.custom found. Migrate the existing installation first."
        )
    directory = private_directory(root)
    key = key_value(root, directory)
    template = (SOURCE / "deploy/compose.yml").read_text()
    template = template.replace("@API_IMAGE@", image_reference(api_image)).replace(
        "@UI_IMAGE@", image_reference(ui_image)
    )
    targets = {
        directory / "secrets.env": (key, 0o600),
        directory / "compose.yml": (template, 0o600),
        override: (text, previous_override[1] if previous_override else 0o644),
        directory / ".managed-by": (OWNER, 0o600),
    }
    before = {path: snapshot(path) for path in targets}
    backup = directory / "override.before-install"
    if previous_override and not managed and not backup.exists():
        write(backup, previous_override[0])
    changed = False
    try:
        for path, (content, mode) in targets.items():
            changed = write(path, content, mode) or changed
        compose(root, "config", "--quiet")
    except (InstallError, OSError):
        for path, previous in before.items():
            restore(path, previous)
        raise
    return changed


def routes(root, remove=False):
    preflight(root)
    if not owned(root):
        raise InstallError("Run configure before managing nginx routes.")
    path = root / "data/conf/nginx/site.restv2.custom"
    previous = snapshot(path)
    if remove and previous is None:
        return False
    if not remove:
        desired = (SOURCE / "deploy/nginx/site.restv2.custom").read_bytes()
        if previous == (desired, 0o644):
            return False
    if previous:
        write(root / "modern-ui/nginx.before-last-change", previous[0])
    try:
        if remove:
            path.unlink()
        else:
            write(path, desired, 0o644)
        compose(root, "exec", "-T", "nginx-mailcow", "nginx", "-t")
        compose(root, "exec", "-T", "nginx-mailcow", "nginx", "-s", "reload")
    except (InstallError, OSError):
        restore(path, previous)
        # A failed reload must also put the previous working routes back in memory.
        try:
            compose(root, "exec", "-T", "nginx-mailcow", "nginx", "-t")
            compose(root, "exec", "-T", "nginx-mailcow", "nginx", "-s", "reload")
        except InstallError:
            pass
        raise InstallError(
            "nginx activation failed. The previous file was restored; inspect nginx on the server."
        ) from None
    return True


def detach(root):
    preflight(root)
    if not owned(root):
        raise InstallError("This installation is not managed by mailcow-modern-ui.")
    if (root / "data/conf/nginx/site.restv2.custom").exists():
        raise InstallError("Run deactivate before detaching the Compose include.")
    override = root / "docker-compose.override.yml"
    previous = snapshot(override)
    if not previous or BLOCK not in previous[0].decode():
        return False
    if compose(root, "ps", "--all", "--quiet", *SERVICES).strip():
        raise InstallError(
            "Stop and remove the two addon containers before detaching. See docs/maintenance.md."
        )
    remaining = previous[0].decode().replace(BLOCK, "")
    try:
        if remaining.strip():
            write(override, remaining, previous[1])
        else:
            override.unlink()
        compose(root, "config", "--quiet")
    except (InstallError, OSError):
        restore(override, previous)
        raise
    # Retain the key and API-owned database data for a reversible reinstall.
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["configure", "activate", "deactivate", "detach"])
    parser.add_argument("--mailcow-dir", type=Path, required=True)
    parser.add_argument(
        "--api-image",
        type=image_reference,
        default="ghcr.io/feldsam-inc/mailcow-rest-v2:latest",
    )
    parser.add_argument(
        "--ui-image",
        type=image_reference,
        default="ghcr.io/feldsam-inc/mailcowui-ng:latest",
    )
    args = parser.parse_args()
    root = args.mailcow_dir.resolve()
    try:
        if args.action == "configure":
            changed = configure(root, args.api_image, args.ui_image)
        elif args.action == "detach":
            changed = detach(root)
        else:
            changed = routes(root, remove=args.action == "deactivate")
        print(json.dumps({"changed": changed, "action": args.action}))
    except (InstallError, OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
