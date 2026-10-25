#!/usr/bin/env python3
"""Exercise root mode against the exact supported mailcow nginx templates in Docker.

Only disposable containers and temporary synthetic files are used. Requires Jinja2.
Optionally run a browser script against a real UI build with --ui-source/--ui-dist.
"""

import argparse
import importlib.util
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from jinja2 import Environment, StrictUndefined

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("manage", REPO / "scripts/manage.py")
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


def run(args, cwd=None, **kwargs):
    return subprocess.run(
        args, cwd=cwd, check=True, text=True, capture_output=True, **kwargs
    ).stdout


def request(origin, path, method="GET", host="mail.example.org", data=None):
    req = urllib.request.Request(
        origin + path,
        data=data,
        method=method,
        headers={"Host": host, "Content-Type": "application/x-www-form-urlencoded"},
    )

    # Preserve Location and status instead of following SOGo/DAV redirects.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None

    try:
        result = urllib.request.build_opener(NoRedirect).open(req, timeout=15)
    except urllib.error.HTTPError as error:
        result = error
    body = result.read().decode()
    try:
        body = json.loads(body)
    except ValueError:
        pass
    return result.status, result.headers.get("Location"), body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui-source", type=Path)
    parser.add_argument("--ui-dist", type=Path)
    parser.add_argument("--browser-script", type=Path)
    args = parser.parse_args()
    if args.ui_dist and not args.ui_source:
        parser.error("--ui-dist requires --ui-source")
    if args.ui_dist and not (args.ui_dist / "deployment.json").is_file():
        parser.error("Build the UI before starting the browser fixture: deployment.json is missing")
    with tempfile.TemporaryDirectory(prefix="modern-ui-nginx-") as temporary:
        root = Path(temporary)
        for name in [
            "data/conf/nginx",
            "data/web/inc",
            "data/web/lang",
            "data/conf/rspamd/custom",
            "data/assets/templates",
            "data/conf/dovecot",
            "includes",
            "cert",
            "internal",
        ]:
            (root / name).mkdir(parents=True, exist_ok=True)
        for name in ["global_sieve_before", "global_sieve_after"]:
            (root / "data/conf/dovecot" / name).touch()
        (root / "mailcow.conf").write_text("COMPOSE_PROJECT_NAME=" + root.name + "\n")
        (root / ".env").symlink_to("mailcow.conf")
        manage.private_directory(root)
        manage.write(root / "modern-ui/.managed-by", manage.OWNER)
        php_files = [
            "index.php",
            "reset-password.php",
            "quarantine.php",
            "sogo-auth.php",
            "mobileconfig.php",
            "qhandler.php",
            "autodiscover.php",
            "autodiscover-json.php",
            "autoconfig.php",
            "mta-sts.php",
            "json_api.php",
            "resource.php",
            "f2b-banlist.php",
            "oauth/authorize.php",
            "oauth/token.php",
            "admin/dashboard.php",
            "user.php",
        ]
        for name in php_files:
            target = root / "data/web" / name
            target.parent.mkdir(exist_ok=True, parents=True)
            target.touch()
        for name in ["index.php", "pipe.php", "mailcowauth.php"]:
            (root / "internal" / name).touch()
        for name in ["lang/lang.en-gb.json", ".well-known/acme-challenge/test", "operator.txt"]:
            target = root / "data/web" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("fixture content\n")
        values = dict(
            MAILCOW_HOSTNAME="mail.example.org",
            HTTP_PORT=8080,
            HTTPS_PORT=8443,
            HTTP_REDIRECT=False,
            ENABLE_IPV6=False,
            NGINX_USE_PROXY_PROTOCOL=False,
            ADDITIONAL_SERVER_NAMES=[],
            TRUSTED_PROXIES=[],
            valid_cert_dirs=[],
            PHPFPMHOST="backend",
            RSPAMDHOST="backend",
            SOGOHOST="backend",
            SKIP_RSPAMD=False,
            SKIP_SOGO=False,
        )
        engine = Environment(undefined=StrictUndefined)
        upstream = REPO / "tests/nginx/upstream/2026-09a"
        for name, target in [
            ("nginx.conf.j2", root / "nginx.conf"),
            ("sites-default.conf.j2", root / "includes/sites-default.conf"),
        ]:
            target.write_text(engine.from_string((upstream / name).read_text()).render(**values))
        run(
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
                "/CN=mail.example.org",
                "-keyout",
                str(root / "cert/key.pem"),
                "-out",
                str(root / "cert/cert.pem"),
            ]
        )
        (root / "wget").write_text(
            "#!/usr/local/bin/python\nimport sys,urllib.request\nsys.stdout.buffer.write(urllib.request.urlopen(sys.argv[-1]).read())\n"
        )
        (root / "wget").chmod(0o755)
        services = {
            "backend": {
                "image": "python:3.12-slim-bookworm",
                "command": ["python", "/fixtures/stub.py", "backend"],
                "volumes": [str(REPO / "tests/nginx") + ":/fixtures:ro"],
                "networks": {"default": {"aliases": ["phpfpm", "restv2-mailcow"]}},
            },
            "ng-mailcow": {
                "image": "python:3.12-slim-bookworm",
                "command": ["python", "/fixtures/stub.py", "ui"],
                "volumes": [
                    str(REPO / "tests/nginx") + ":/fixtures:ro",
                    str(root / "wget") + ":/usr/local/bin/wget:ro",
                ],
            },
            "nginx-mailcow": {
                "image": "ghcr.io/mailcow/nginx:1.30.4-1",
                "entrypoint": ["nginx", "-g", "daemon off;"],
                "depends_on": ["backend", "ng-mailcow"],
                "ports": [
                    "127.0.0.1::8080",
                    "127.0.0.1::8081",
                    "127.0.0.1::9081",
                    "127.0.0.1::9082",
                ],
                "volumes": [
                    str(root / "nginx.conf") + ":/etc/nginx/nginx.conf:ro",
                    str(root / "includes") + ":/etc/nginx/includes:ro",
                    str(root / "data/conf/nginx") + ":/etc/nginx/conf.d:ro",
                    str(root / "cert") + ":/etc/ssl/mail:ro",
                    str(root / "data/web") + ":/web:ro",
                ]
                + [
                    str(root / "internal") + ":/" + name + ":ro"
                    for name in ["dynmaps", "meta_exporter", "mailcowauth"]
                ],
            },
        }
        if args.ui_dist:
            services["ng-mailcow"] = {
                "image": "nginx:1.28-alpine",
                "entrypoint": ["nginx", "-g", "daemon off;"],
                "volumes": [
                    str(args.ui_dist.resolve()) + ":/usr/share/nginx/html/ng:ro",
                    str(args.ui_source.resolve() / "docker/nginx/default.conf")
                    + ":/etc/nginx/conf.d/default.conf:ro",
                    str(args.ui_source.resolve() / "docker/nginx/security-headers.conf")
                    + ":/etc/nginx/security-headers.conf:ro",
                ],
            }
        (root / "docker-compose.yml").write_text(json.dumps({"services": services}))
        try:
            manage.compose(root, "up", "-d")
            origin = "http://" + manage.compose(root, "port", "nginx-mailcow", "8080").strip()
            for _ in range(50):
                try:
                    if request(origin, "/")[0] == 200:
                        break
                except OSError:
                    pass
                time.sleep(0.1)
            manage.routes(root)
            time.sleep(0.3)
            cases = [
                ("/?oauth", "GET", "mail.example.org", None),
                ("/?iam_sso=1", "GET", "mail.example.org", None),
                ("/?code=test&state=state", "GET", "mail.example.org", None),
                ("/", "POST", "mail.example.org", b"login_user=test&pass=synthetic"),
                ("/", "GET", "autodiscover.example.org", None),
                ("/", "GET", "autoconfig.example.org", None),
                ("/index.php?mobileconfig&app_password", "GET", "mail.example.org", None),
                ("/reset-password", "POST", "mail.example.org", b"token=test&password=synthetic"),
            ]
            cases += [
                (path, "GET", "mail.example.org", None)
                for path in [
                    "/api/v1/get/status/containers",
                    "/api/v2/health/ready",
                    "/SOGo/so/",
                    "/sogo-auth",
                    "/mobileconfig.php?only_email",
                    "/oauth/authorize?client_id=test",
                    "/oauth/token",
                    "/qhandler/release/test",
                    "/.well-known/acme-challenge/test",
                    "/.well-known/mta-sts.txt",
                    "/.well-known/caldav",
                    "/.well-known/carddav",
                    "/Autodiscover/Autodiscover.xml",
                    "/Autodiscover/Autodiscover.json",
                    "/mail/config-v1.1.xml",
                    "/lang/lang.en-gb.json",
                    "/rspamd/",
                    "/f2b-banlist.php",
                    "/reset-password.php?token=test",
                    "/quarantine.php",
                    "/admin/dashboard",
                    "/operator.txt",
                    "/unknown-page",
                ]
            ]
            cases += [
                ("/SOGo/dav/", "PROPFIND", "mail.example.org", b"<propfind/>"),
                ("/Microsoft-Server-ActiveSync", "OPTIONS", "mail.example.org", None),
            ]
            baseline = [
                request(origin, path, method, host, data) for path, method, host, data in cases
            ]
            internal_origins = [
                "http://" + manage.compose(root, "port", "nginx-mailcow", str(port)).strip()
                for port in [8081, 9081, 9082]
            ]
            internal_before = [request(url, "/") for url in internal_origins]
            private_before = manage.compose(
                root, "exec", "-T", "nginx-mailcow", "wget", "-qO-", "http://127.0.0.1:65510/"
            )
            manage.routes(root, ui_path="/")
            time.sleep(0.4)
            for case, expected in zip(cases, baseline):
                path, method, host, data = case
                actual = request(origin, path, method, host, data)
                if actual != expected:
                    raise AssertionError(
                        f"Legacy routing changed for {method} {host}{path}: {expected!r} -> {actual!r}"
                    )
            assert [request(url, "/") for url in internal_origins] == internal_before
            assert (
                manage.compose(
                    root, "exec", "-T", "nginx-mailcow", "wget", "-qO-", "http://127.0.0.1:65510/"
                )
                == private_before
            )
            assert "__MAILCOW_UI_BASE_PATH__ = '/'" in request(origin, "/ng/app-config.js")[2]
            if not args.ui_dist:
                for path in [
                    "/",
                    "/sign-in",
                    "/domains",
                    "/mailboxes/alice%40example.org",
                    "/sso/return?code=test",
                ]:
                    status, _, payload = request(origin, path)
                    assert status == 200 and payload["handler"] == "ui", (path, payload)
            if args.browser_script:
                result = run(
                    ["node", str(args.browser_script.resolve())],
                    env={**os.environ, "ROOT_UI_ORIGIN": origin},
                    timeout=180,
                )
                print(result.strip())
            manage.compose(root, "stop", "ng-mailcow")
            credential = "private-routing-test-credential"
            for path in [
                "/sso/return?code=" + credential,
                "/ng/reset-password?token=" + credential,
            ]:
                assert request(origin, path)[0] == 502
            logs = manage.compose(root, "logs", "nginx-mailcow")
            assert credential not in logs, (
                "An unavailable UI leaked a credential into outer nginx logs"
            )
            assert request(origin, "/api/v1/get/status/containers")[2]["handler"] == "php"
            manage.routes(root, ui_path="/ng/")
            time.sleep(0.4)
            assert request(origin, "/")[2]["handler"] == "php"
            print(
                f"Passed: {len(cases)} legacy requests, four internal listeners, root activation, outage log redaction and rollback."
            )
        except Exception as error:
            if isinstance(error, subprocess.CalledProcessError):
                print(error.stderr)
            print(manage.compose(root, "logs", "--tail", "35", "nginx-mailcow"))
            raise
        finally:
            manage.compose(root, "down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
