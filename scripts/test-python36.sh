#!/usr/bin/env bash
# Run the installer suite on its oldest supported interpreter, isolated from the host daemon.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
plugin="$(docker info --format '{{range .ClientInfo.Plugins}}{{if eq .Name "compose"}}{{.Path}}{{end}}{{end}}')"
test -x "$plugin"
docker run --rm --network=none --cap-drop=ALL --security-opt=no-new-privileges \
    --read-only --tmpfs /tmp:rw,nosuid,nodev --user "$(id -u):$(id -g)" \
    -v "$root:/work:ro" -v "$plugin:/usr/local/bin/docker-compose:ro" -w /work \
    -e PATH=/work/tests/bin:/usr/local/bin:/usr/bin:/bin -e PYTHONDONTWRITEBYTECODE=1 \
    python:3.6.15-slim-buster@sha256:e10aa83604948c6d8d9f72a9a20193d84bb2dbe550b725eb5208387117fde065 \
    python -m unittest discover -s tests -p test_manage.py -v
