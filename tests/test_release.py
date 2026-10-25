import hashlib
import importlib.util
import json
import unittest
import urllib.request
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_release", Path(__file__).parents[1] / "scripts/check-release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseImagesTests(unittest.TestCase):
    revision = "a" * 40
    repository = "mailcowui-ng"

    def registry(self, architectures=("amd64", "arm64"), revision=None):
        base = "https://ghcr.io/v2/feldsam-inc/mailcowui-ng"
        resources = {}

        def store(kind, data):
            raw = json.dumps(data).encode()
            digest = "sha256:" + hashlib.sha256(raw).hexdigest()
            resources[f"{base}/{kind}/{digest}"] = raw
            return digest

        manifests = []
        for arch in architectures:
            config = store("blobs", {
                "os": "linux", "architecture": arch,
                "config": {"Labels": {
                    "org.opencontainers.image.revision": revision or self.revision,
                }},
            })
            manifest = store("manifests", {"config": {"digest": config}})
            manifests.append({
                "digest": manifest, "platform": {"os": "linux", "architecture": arch},
            })
        digest = store("manifests", {"manifests": manifests})

        def fetch(url, headers=None):
            if url.startswith("https://ghcr.io/token?"):
                return b'{"token":"anonymous-fixture-token"}'
            self.assertEqual(headers["Authorization"], "Bearer anonymous-fixture-token")
            return resources[url]

        return f"ghcr.io/feldsam-inc/mailcowui-ng@{digest}", fetch

    def test_accepts_public_images_for_both_architectures_at_the_recorded_revision(self):
        reference, fetch = self.registry()
        release.verify_image(self.repository, reference, self.revision, fetch)

    def test_rejects_a_missing_architecture(self):
        reference, fetch = self.registry(architectures=("amd64",))
        with self.assertRaisesRegex(ValueError, "both Linux AMD64 and ARM64"):
            release.verify_image(self.repository, reference, self.revision, fetch)

    def test_rejects_an_image_from_a_different_commit(self):
        reference, fetch = self.registry(revision="b" * 40)
        with self.assertRaisesRegex(ValueError, "source revision differs"):
            release.verify_image(self.repository, reference, self.revision, fetch)

    def test_rejects_registry_content_that_does_not_match_its_digest(self):
        reference, fetch = self.registry()

        def corrupt(url, headers=None):
            raw = fetch(url, headers)
            return raw if "/token?" in url else raw + b" "

        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            release.verify_image(self.repository, reference, self.revision, corrupt)

    def test_rejects_moving_image_tags_before_contacting_the_registry(self):
        with self.assertRaisesRegex(ValueError, "fixed GHCR SHA-256 digest"):
            release.verify_image(
                self.repository, "ghcr.io/feldsam-inc/mailcowui-ng:latest", self.revision
            )

    def test_signed_storage_redirects_do_not_receive_the_registry_token(self):
        request = urllib.request.Request(
            "https://ghcr.io/v2/example/blobs/value", headers={"Authorization": "Bearer fixture"}
        )
        redirected = release.RegistryRedirect().redirect_request(
            request, None, 302, "Found", {}, "https://storage.example/blob?signature=fixture"
        )
        self.assertFalse(redirected.has_header("Authorization"))
