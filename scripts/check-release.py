#!/usr/bin/env python3
"""Verify a preview's fixed public images before publishing its GitHub release."""

import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
PREVIEW_VERSION = r"0\.\d+\.\d+-preview\.[1-9]\d*"
MEDIA_TYPES = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.docker.distribution.manifest.v2+json",
])


class RegistryRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, *args):
        redirected = super().redirect_request(request, *args)
        if redirected and (
            urllib.parse.urlsplit(request.full_url).netloc
            != urllib.parse.urlsplit(redirected.full_url).netloc
        ):
            redirected.remove_header("Authorization")
        return redirected


def read(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.build_opener(RegistryRedirect()).open(request, timeout=30) as response:
        return response.read()


def verify_image(repository, reference, revision, fetch=read, *, version=None):
    prefix = f"ghcr.io/feldsam-inc/{repository}@sha256:"
    if not reference.startswith(prefix) or not re.fullmatch(
        r"[0-9a-f]{64}", reference[len(prefix):]
    ):
        raise ValueError(f"{repository}: expected a fixed GHCR SHA-256 digest")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError(f"{repository}: expected a full source revision")
    if version is not None and not re.fullmatch(PREVIEW_VERSION, version):
        raise ValueError(f"{repository}: expected a community preview version")
    token_url = f"https://ghcr.io/token?scope=repository:feldsam-inc/{repository}:pull"
    token = json.loads(fetch(token_url))["token"]
    headers = {"Authorization": "Bearer " + token, "Accept": MEDIA_TYPES}
    registry = f"https://ghcr.io/v2/feldsam-inc/{repository}"

    def content(path, digest):
        raw = fetch(f"{registry}/{path}/{digest}", headers)
        if "sha256:" + hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f"{repository}: registry content digest mismatch")
        return json.loads(raw)

    index = content("manifests", reference.split("@", 1)[1])
    if version is not None:
        tagged = fetch(f"{registry}/manifests/{version}", headers)
        if "sha256:" + hashlib.sha256(tagged).hexdigest() != reference.split("@", 1)[1]:
            raise ValueError(f"{repository}: release tag points to a different image")
    platforms = set()
    for descriptor in index["manifests"]:
        platform = descriptor.get("platform", {})
        arch = platform.get("architecture")
        if platform.get("os") != "linux" or arch not in ("amd64", "arm64"):
            continue  # The index may also contain provenance attestations.
        if arch in platforms:
            raise ValueError(f"{repository}: duplicate {arch} image")
        manifest = content("manifests", descriptor["digest"])
        config = content("blobs", manifest["config"]["digest"])
        if config["config"]["Labels"].get("org.opencontainers.image.revision") != revision:
            raise ValueError(f"{repository}: {arch} source revision differs from the release")
        if config["os"] != "linux" or config["architecture"] != arch:
            raise ValueError(f"{repository}: platform metadata mismatch")
        platforms.add(arch)
    if platforms != {"amd64", "arm64"}:
        raise ValueError(f"{repository}: both Linux AMD64 and ARM64 images are required")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag")
    args = parser.parse_args()
    release = json.loads((SOURCE / "deploy/release.json").read_text())
    version = release["version"]
    if (
        not re.fullmatch(PREVIEW_VERSION, version)
        or release["prerelease"] is not True
    ):
        raise ValueError("Expected an explicitly marked community preview version")
    if args.tag and args.tag != "v" + version:
        raise ValueError("The Git tag differs from the release manifest")
    if not (SOURCE / "docs/releases" / (version + ".md")).is_file():
        raise ValueError("Release notes are missing")
    for component, repository in [("api", "mailcow-rest-v2"), ("ui", "mailcowui-ng")]:
        image = release["images"][component]
        verify_image(repository, image["image"], image["revision"], version=version)
        print(f"{component}: release tag, public AMD64 and ARM64 digests and source revision verified")


if __name__ == "__main__":
    main()
