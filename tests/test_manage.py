import argparse
import base64
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "manage", Path(__file__).parents[1] / "scripts/manage.py"
)
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


class InstallationTests(unittest.TestCase):
    """Compile real Compose configurations without starting containers or using a server."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="modern-ui-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env_patch = patch.dict(os.environ, {"COMPOSE_FILE": ""})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        (self.root / "docker-compose.yml").write_text("""services:
  mysql-mailcow:
    image: example.invalid/mysql:test
    networks: [mailcow-network]
  redis-mailcow:
    image: example.invalid/redis:test
    networks: [mailcow-network]
  nginx-mailcow:
    image: example.invalid/nginx:test
  ofelia-mailcow:
    image: example.invalid/ofelia:test
networks:
  mailcow-network: {}
volumes:
  rspamd-vol-1: {}
""")
        (self.root / "mailcow.conf").write_text("""MAILCOW_HOSTNAME=mail.example.org
TZ=Etc/UTC
DBNAME=mailcow
DBUSER=mailcow
DBPASS=test-password-not-a-real-credential
REDISPASS=test-redis-not-a-real-credential
COMPOSE_PROJECT_NAME=modern-ui-test
""")
        (self.root / ".env").symlink_to("mailcow.conf")
        for name in [
            "data/conf/nginx",
            "data/web/inc",
            "data/web/lang",
            "data/conf/rspamd/custom",
            "data/assets/templates",
            "data/conf/dovecot",
        ]:
            (self.root / name).mkdir(parents=True, exist_ok=True)
        for name in ["global_sieve_before", "global_sieve_after"]:
            (self.root / "data/conf/dovecot" / name).touch()

    def configure(self):
        return manage.configure(
            self.root,
            "ghcr.io/feldsam-inc/mailcow-rest-v2:latest",
            "ghcr.io/feldsam-inc/mailcowui-ng:latest",
        )

    def test_cli_defaults_install_the_fixed_preview_pair(self):
        release = json.loads((manage.SOURCE / "deploy/release.json").read_text())
        with patch("sys.argv", ["manage.py", "configure", "--mailcow-dir", str(self.root)]):
            with patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(manage.main(), 0)
        model = json.loads(manage.compose(self.root, "config", "--format", "json"))
        for component, service in [("api", "restv2-mailcow"), ("ui", "ng-mailcow")]:
            expected = release["images"][component]["image"]
            self.assertRegex(expected, r"@sha256:[0-9a-f]{64}$")
            self.assertEqual(model["services"][service]["image"], expected)

    def test_cli_image_overrides_take_precedence_over_release_defaults(self):
        args = [
            "manage.py", "configure", "--mailcow-dir", str(self.root),
            "--api-image", "ghcr.io/feldsam-inc/mailcow-rest-v2:custom",
            "--ui-image", "ghcr.io/feldsam-inc/mailcowui-ng:custom",
        ]
        with patch("sys.argv", args), patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(manage.main(), 0)
        model = json.loads(manage.compose(self.root, "config", "--format", "json"))
        self.assertEqual(model["services"]["restv2-mailcow"]["image"], args[-3])
        self.assertEqual(model["services"]["ng-mailcow"]["image"], args[-1])

    def test_invalid_release_defaults_fail_before_configuration_changes(self):
        source = self.root / "invalid-release"
        (source / "deploy").mkdir(parents=True)
        (source / "deploy/release.json").write_text('{"images": {}}')
        with patch.object(manage, "SOURCE", source):
            with patch("sys.argv", ["manage.py", "configure", "--mailcow-dir", str(self.root)]):
                with patch("sys.stderr", new_callable=io.StringIO) as error:
                    self.assertEqual(manage.main(), 1)
        self.assertIn("release manifest", error.getvalue())
        self.assertFalse((self.root / "modern-ui").exists())
        self.assertFalse((self.root / "docker-compose.override.yml").exists())

    def test_compose_paths_secrets_and_service_isolation(self):
        self.assertTrue(self.configure())
        model = json.loads(manage.compose(self.root, "config", "--format", "json"))
        api = model["services"]["restv2-mailcow"]
        self.assertEqual(api["environment"]["MAILCOW_HOSTNAME"], "mail.example.org")
        self.assertEqual(api["environment"]["RESTV2_DEFAULT_DKIM_SELECTOR"], "dkim")
        self.assertEqual(len(base64.b64decode(api["environment"]["APP_KEY"][7:])), 32)
        self.assertEqual(api["environment"]["DBPASS"], "test-password-not-a-real-credential")
        mounts = {volume["target"]: volume["source"] for volume in api["volumes"]}
        self.assertEqual(mounts["/mailcow/web/inc"], str(self.root / "data/web/inc"))
        self.assertEqual(
            mounts["/mailcow/global_sieve/before"],
            str(self.root / "data/conf/dovecot/global_sieve_before"),
        )
        for name in manage.SERVICES:
            self.assertTrue(model["services"][name]["read_only"])
            self.assertNotIn("ports", model["services"][name])
        self.assertEqual((self.root / "modern-ui").stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.root / "modern-ui/secrets.env").stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.root / "modern-ui/.gitignore").read_text(), "*\n")

    def test_rerun_preserves_key_and_makes_no_changes(self):
        self.configure()
        key = (self.root / "modern-ui/secrets.env").read_bytes()
        self.assertFalse(self.configure())
        self.assertEqual((self.root / "modern-ui/secrets.env").read_bytes(), key)

    def test_existing_override_and_configuration_remain_intact(self):
        override = (
            "# My custom configuration\nservices:\n  nginx-mailcow:\n    restart: unless-stopped\n"
        )
        (self.root / "docker-compose.override.yml").write_text(override)
        original_conf = (self.root / "mailcow.conf").read_bytes()
        self.configure()
        self.assertTrue(
            (self.root / "docker-compose.override.yml").read_text().startswith(override)
        )
        self.assertEqual((self.root / "modern-ui/override.before-install").read_text(), override)
        self.assertEqual((self.root / "mailcow.conf").read_bytes(), original_conf)

    def test_existing_key_is_adopted(self):
        value = "base64:" + base64.b64encode(b"k" * 32).decode()
        with (self.root / "mailcow.conf").open("a") as stream:
            stream.write('RESTV2_APP_KEY="' + value + '"\n')
        self.configure()
        self.assertEqual(
            (self.root / "modern-ui/secrets.env").read_text(), "APP_KEY=" + value + "\n"
        )

    def test_invalid_or_missing_key_is_never_rotated(self):
        self.configure()
        key = self.root / "modern-ui/secrets.env"
        key.write_text("APP_KEY=invalid\n")
        with self.assertRaisesRegex(manage.InstallError, "Invalid application key"):
            self.configure()
        self.assertEqual(key.read_text(), "APP_KEY=invalid\n")
        key.unlink()
        with self.assertRaisesRegex(manage.InstallError, "key is missing"):
            self.configure()

    def test_invalid_compose_rolls_back_override_and_secret(self):
        original = manage.compose

        def fail_config(root, *args):
            if args == ("config", "--quiet"):
                raise manage.InstallError("invalid test configuration")
            return original(root, *args)

        with patch.object(manage, "compose", side_effect=fail_config):
            with self.assertRaises(manage.InstallError):
                self.configure()
        self.assertFalse((self.root / "docker-compose.override.yml").exists())
        self.assertFalse((self.root / "modern-ui/secrets.env").exists())
        self.assertFalse(manage.owned(self.root))

    def test_existing_include_and_conflicting_services_are_rejected(self):
        override = self.root / "docker-compose.override.yml"
        for content in [
            "include: [other.yml]\n",
            "services:\n  ng-mailcow:\n    image: example.invalid/ui:test\n",
        ]:
            with self.subTest(content=content):
                override.write_text(content)
                with self.assertRaises(manage.InstallError):
                    self.configure()
                self.assertEqual(override.read_text(), content)
                self.assertFalse((self.root / "modern-ui/secrets.env").exists())

    def test_symlink_override_is_not_followed(self):
        target = self.root / "unrelated.yml"
        target.write_text("private content")
        (self.root / "docker-compose.override.yml").symlink_to(target)
        with self.assertRaisesRegex(manage.InstallError, "symlink"):
            self.configure()
        self.assertEqual(target.read_text(), "private content")

    def test_symlink_secret_is_not_followed(self):
        self.configure()
        target = self.root / "unrelated-secret"
        target.write_text("private content")
        secret = self.root / "modern-ui/secrets.env"
        secret.unlink()
        secret.symlink_to(target)
        with self.assertRaisesRegex(manage.InstallError, "symlink"):
            self.configure()
        self.assertEqual(target.read_text(), "private content")

    def test_existing_nginx_routes_are_not_overwritten(self):
        route = self.root / "data/conf/nginx/site.restv2.custom"
        route.write_text("existing installation")
        with self.assertRaisesRegex(manage.InstallError, "Existing site"):
            self.configure()
        self.assertEqual(route.read_text(), "existing installation")

    def test_failed_nginx_test_restores_previous_file(self):
        self.configure()
        route = self.root / "data/conf/nginx/site.restv2.custom"
        route.write_text("previous routes")
        with patch.object(
            manage, "compose", side_effect=[manage.InstallError("test failure"), "", ""]
        ):
            with self.assertRaisesRegex(manage.InstallError, "previous file was restored"):
                manage.routes(self.root)
        self.assertEqual(route.read_text(), "previous routes")

    def test_failed_first_nginx_activation_removes_new_file(self):
        self.configure()
        with patch.object(
            manage,
            "compose",
            side_effect=["", manage.InstallError("reload failure"), "", ""],
        ):
            with self.assertRaises(manage.InstallError):
                manage.routes(self.root)
        self.assertFalse((self.root / "data/conf/nginx/site.restv2.custom").exists())

    def test_nginx_activation_is_idempotent(self):
        self.configure()
        with patch.object(manage, "compose", return_value="") as execute:
            self.assertTrue(manage.routes(self.root))
            self.assertFalse(manage.routes(self.root))
            self.assertEqual(execute.call_count, 2)

    def root_manifest(self):
        return json.dumps(
            {
                "rootRoutingVersion": 1,
                "supportedUiPaths": ["/ng/", "/"],
                "routeRoots": ["domains", "sign-in", "sso", "reset-password"],
            }
        )

    def test_root_activation_preserves_the_selection_on_updates_and_can_switch_back(self):
        self.configure()
        with patch.object(manage, "compose", return_value=self.root_manifest()):
            self.assertTrue(manage.routes(self.root, ui_path="/"))
            self.assertFalse(manage.routes(self.root))
            snippet = self.root / "data/conf/nginx/site.modern-ui-root.custom"
            self.assertIn("domains|reset-password|sign-in|sso", snippet.read_text())
            self.assertEqual((self.root / "modern-ui/ui-path").read_text(), "/\n")
            self.assertTrue(manage.routes(self.root, ui_path="/ng/"))
            self.assertFalse(snippet.exists())
            self.assertFalse((self.root / "data/conf/nginx/modern-ui-root-proxy.custom").exists())
            self.assertEqual((self.root / "modern-ui/ui-path").read_text(), "/ng/\n")

    def test_root_activation_rejects_old_images_and_internal_route_collisions(self):
        self.configure()
        invalid = [
            "<html>old app</html>",
            "{}",
            json.dumps({"rootRoutingVersion": 1, "supportedUiPaths": ["/"], "routeRoots": ["api"]}),
            json.dumps(
                {
                    "rootRoutingVersion": 1,
                    "supportedUiPaths": ["/"],
                    "routeRoots": ["x); return 200;"],
                }
            ),
        ]
        for manifest in invalid:
            with (
                self.subTest(manifest=manifest),
                patch.object(manage, "compose", return_value=manifest),
            ):
                with self.assertRaises(manage.InstallError):
                    manage.routes(self.root, ui_path="/")
                self.assertFalse(
                    (self.root / "data/conf/nginx/site.modern-ui-root.custom").exists()
                )
                self.assertFalse((self.root / "modern-ui/ui-path").exists())

    def test_failed_root_activation_restores_all_files_and_previous_mode(self):
        self.configure()
        with patch.object(manage, "compose", return_value=""):
            manage.routes(self.root)
        old = (self.root / "data/conf/nginx/site.restv2.custom").read_bytes()
        with patch.object(
            manage,
            "compose",
            side_effect=[self.root_manifest(), manage.InstallError("bad nginx"), "", ""],
        ):
            with self.assertRaises(manage.InstallError):
                manage.routes(self.root, ui_path="/")
        self.assertEqual((self.root / "data/conf/nginx/site.restv2.custom").read_bytes(), old)
        self.assertEqual((self.root / "modern-ui/ui-path").read_text(), "/ng/\n")
        self.assertFalse((self.root / "data/conf/nginx/site.modern-ui-root.custom").exists())
        self.assertFalse((self.root / "data/conf/nginx/modern-ui-root-proxy.custom").exists())

    def test_deactivation_removes_both_modes_without_rotating_key(self):
        self.configure()
        key = (self.root / "modern-ui/secrets.env").read_bytes()
        with patch.object(manage, "compose", return_value=self.root_manifest()):
            manage.routes(self.root, ui_path="/")
            self.assertTrue(manage.routes(self.root, remove=True))
            self.assertFalse(manage.routes(self.root, remove=True))
        self.assertFalse(list((self.root / "data/conf/nginx").glob("*.custom")))
        self.assertEqual((self.root / "modern-ui/secrets.env").read_bytes(), key)

    def test_detach_retains_key_and_other_overrides(self):
        (self.root / "docker-compose.override.yml").write_text(
            "services:\n  nginx-mailcow:\n    restart: always\n"
        )
        self.configure()
        original = manage.compose

        def stopped(root, *args):
            if args[0] == "ps":
                return ""
            return original(root, *args)

        with patch.object(manage, "compose", side_effect=stopped):
            self.assertTrue(manage.detach(self.root))
        self.assertNotIn(manage.BLOCK, (self.root / "docker-compose.override.yml").read_text())
        self.assertIn("restart: always", (self.root / "docker-compose.override.yml").read_text())
        self.assertTrue((self.root / "modern-ui/secrets.env").exists())
        self.assertTrue(self.configure())

    def test_detach_refuses_to_orphan_containers(self):
        self.configure()
        with patch.object(manage, "compose", return_value="container-id\n"):
            with self.assertRaisesRegex(manage.InstallError, "Stop and remove"):
                manage.detach(self.root)
        self.assertIn(manage.BLOCK, (self.root / "docker-compose.override.yml").read_text())

    def test_rejects_image_injection(self):
        for value in ['image"\nprivileged: true', "image $(id)", ""]:
            with (
                self.subTest(value=value),
                self.assertRaises(argparse.ArgumentTypeError),
            ):
                manage.image_reference(value)


if __name__ == "__main__":
    unittest.main()
