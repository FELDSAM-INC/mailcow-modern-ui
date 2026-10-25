#!/usr/bin/env python3
"""Run the real playbook in temporary fixtures; simulate Docker mutations only.

Requires root for the playbook's file ownership, Docker Compose, and ansible-playbook
beside this Python interpreter (or on PATH). No mail server or application is started.
"""

import importlib.util
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *_args):
        pass


def main():
    if os.geteuid() != 0:
        raise SystemExit(
            "Run as root: the playbook creates root-owned files in a temporary directory."
        )
    playbook = Path(sys.executable).parent / "ansible-playbook"
    if not playbook.is_file():
        playbook = shutil.which("ansible-playbook")
    if not playbook:
        raise SystemExit("Install ansible-core into the Python environment first.")
    spec = importlib.util.spec_from_file_location("fixtures", REPO / "tests/test_manage.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    test = fixture.InstallationTests()
    test.setUp()
    root = test.root
    server = None
    try:
        cert, key = root / "test.crt", root / "test.key"
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=DNS:localhost",
                "-keyout",
                str(key),
                "-out",
                str(cert),
            ],
            check=True,
            capture_output=True,
        )
        server = HTTPServer(("127.0.0.1", 0), Handler)
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(cert, key)
        server.socket = tls.wrap_socket(server.socket, server_side=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        bindir = root / "bin"
        bindir.mkdir()
        wrapper = """#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys
args = sys.argv[1:]
root = pathlib.Path(os.environ['MODERN_UI_TEST_ROOT'])
assert pathlib.Path.cwd() == root, 'Docker must only operate in the fixture'
with (root / 'commands.jsonl').open('a') as log:
    log.write(json.dumps(args) + '\\n')
if 'config' in args or 'version' in args:
    sys.exit(subprocess.run([REAL_DOCKER] + args).returncode)
if 'wget' in args:
    print(MANIFEST)
elif 'up' in args:
    state = root / 'started'
    replacement = root / 'replace-image'
    if replacement.exists():
        stream = sys.stdout if replacement.read_text() == 'stdout' else sys.stderr
        print('Container fixture Recreated', file=stream)
        replacement.unlink()
    else:
        print('Container fixture Running' if state.exists() else 'Container fixture Created', file=sys.stderr)
    state.touch()
elif not any(word in args for word in ['pull', 'exec', 'restart']):
    raise SystemExit('Unexpected Docker operation')
"""
        wrapper = wrapper.replace("REAL_DOCKER", repr(shutil.which("docker")))
        wrapper = wrapper.replace(
            "MANIFEST", repr((REPO / "tests/nginx/deployment.json").read_text())
        )
        (bindir / "docker").write_text(wrapper)
        (bindir / "docker").chmod(0o755)
        options = {
            "ansible_connection": "local",
            "ansible_become": False,
            "ansible_python_interpreter": sys.executable,
            "mailcow_dir": str(root),
            "mailcow_url": f"https://localhost:{server.server_port}",
            "modern_ui_tools_dir": str(root / "tools"),
            "modern_ui_pull": False,
            "modern_ui_api_image": "ghcr.io/feldsam-inc/mailcow-rest-v2:inventory-test",
            "modern_ui_web_image": "ghcr.io/feldsam-inc/mailcowui-ng:inventory-test",
        }
        env = {
            **os.environ,
            "PATH": str(bindir) + ":" + os.environ["PATH"],
            "SSL_CERT_FILE": str(cert),
            "MODERN_UI_TEST_ROOT": str(root),
            "ANSIBLE_NOCOLOR": "1",
        }
        expected_restarts = 0
        for attempt, path in enumerate(["/", "/", "/ng/", "/ng/", "/ng/", "/ng/"], 1):
            if attempt in (4, 5):
                # A newer image under the same tag changes no installer files.
                (root / "replace-image").write_text("stderr" if attempt == 4 else "stdout")
            options["modern_ui_path"] = path
            inventory = root / "inventory.json"
            inventory.write_text(
                json.dumps({"all": {"children": {"mailcow": {"hosts": {"fixture": options}}}}})
            )
            result = subprocess.run(
                [str(playbook), "-i", str(inventory), str(REPO / "ansible/install.yml")],
                env=env,
                text=True,
                capture_output=True,
                timeout=120,
            )
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            recap = next(line for line in result.stdout.splitlines() if "unreachable=" in line)
            if attempt in (2, 6):
                assert re.search(r"changed=0\b", recap), recap
            else:
                expected_restarts += 1
            commands = [
                json.loads(line) for line in (root / "commands.jsonl").read_text().splitlines()
            ]
            assert sum("restart" in command for command in commands) == expected_restarts, (
                f"Pass {attempt}: Ofelia must rediscover replacement containers, and remain unchanged on reruns"
            )
            assert (root / "modern-ui/ui-path").read_text().strip() == path
            assert (root / "data/conf/nginx/site.modern-ui-root.custom").exists() == (path == "/")
            print(f"Pass {attempt} ({path}): {recap.strip()}")
        assert (root / "tools/scripts/manage.py").is_file()
        model = json.loads(fixture.manage.compose(root, "config", "--format", "json"))
        assert model["services"]["restv2-mailcow"]["image"] == options["modern_ui_api_image"]
        assert model["services"]["ng-mailcow"]["image"] == options["modern_ui_web_image"]
        commands = [json.loads(line) for line in (root / "commands.jsonl").read_text().splitlines()]
        assert not any("pull" in command for command in commands), (
            "Inventory pull=false was ignored"
        )
        print(
            "Passed: inventory overrides, real Compose, HTTPS, idempotence, root-mode switchback and scheduler refresh after image updates. Docker mutations were simulated."
        )
    finally:
        if server:
            server.shutdown()
            server.server_close()
        test.doCleanups()


if __name__ == "__main__":
    main()
