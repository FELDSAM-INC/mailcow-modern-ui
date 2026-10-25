#!/usr/bin/env python3
"""Reproducible security checks without hosted scanners or model API credentials."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
LOCK = json.loads((ROOT / 'security/tools.json').read_text())
CACHE = Path(os.environ.get('SECURITY_TOOLS_CACHE', Path.home() / '.cache/mailcow-security'))
REPORTS = ROOT / 'security-reports'


def download(url, digest):
    with urllib.request.urlopen(url, timeout=120) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != digest:
        raise RuntimeError('Checksum mismatch: ' + url)
    return data


def binary(name):
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'AMD64'):
        raise RuntimeError('The pinned CLI binaries require Linux x86_64 (including CI).')
    spec = LOCK[name]
    target = CACHE / (name + '-' + spec['version']) / name
    # Validate the downloaded archive on every installation; never execute a remote script.
    if not target.exists():
        data = download(spec['url'], spec['sha256'])
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            member = archive.extractfile(name)
            if member is None:
                raise RuntimeError('Binary missing from archive')
            payload = member.read()
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
            temporary.write(payload)
            temporary_path = Path(temporary.name)
        temporary_path.chmod(0o755)
        temporary_path.replace(target)
    return str(target)


def run(*args, **kwargs):
    subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def secrets():
    run(binary('gitleaks'), 'git', '--log-opts=--all', '--redact=100', '--no-banner',
        '--report-format=json', '--report-path=' + str(REPORTS / 'secrets.json'))


def source():
    spec = LOCK['semgrep']
    selection = hashlib.sha256(json.dumps(spec['rules'], sort_keys=True).encode()).hexdigest()[:16]
    rules = CACHE / ('rules-' + spec['revision'] + '-' + selection)
    rules.mkdir(parents=True, exist_ok=True)
    for path, digest in spec['rules'].items():
        target = rules / path.replace('/', '--')
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            target.write_bytes(download('https://raw.githubusercontent.com/semgrep/semgrep-rules/'
                                        + spec['revision'] + '/' + path, digest))
    run('docker', 'run', '--rm', '--network=none', '--cap-drop=ALL',
        '--security-opt=no-new-privileges', '--user', f'{os.getuid()}:{os.getgid()}',
        '-e', 'SEMGREP_USER_DATA_FOLDER=/tmp/semgrep',
        '-v', str(ROOT) + ':/src:ro', '-v', str(rules) + ':/rules:ro',
        '-v', str(REPORTS) + ':/reports', '-w', '/src', spec['image'],
        'semgrep', 'scan', '--config=/rules', '--metrics=off', '--disable-version-check',
        '--strict', '--error', '--jobs=2', '--max-memory=1800', '--timeout=30',
        '--sarif-output=/reports/source.sarif', '--json-output=/reports/source.json',
        *LOCK['source_paths'])


def config():
    if not LOCK['config_paths'] and not LOCK.get('config_tests'):
        raise RuntimeError('No configuration checks configured')
    if LOCK.get('config_tests'):
        run(*LOCK['config_tests'])
    (REPORTS / 'config-coverage.json').write_text(json.dumps({
        'trivyTargets': LOCK['config_paths'],
        'installerChecks': LOCK.get('config_tests', []),
        'note': 'Trivy does not inspect Docker Compose or Ansible; installer integration tests cover those.'
    }, indent=2) + '\n')
    failed = False
    for target in LOCK['config_paths']:
        try:
            run(binary('trivy'), 'config', '--exit-code=1', '--severity=HIGH,CRITICAL',
                '--format=json', '--output=' + str(REPORTS / ('config-' + target.replace('/', '-') + '.json')),
                '--ignorefile=security/trivy-ignore.yaml', target)
        except subprocess.CalledProcessError:
            failed = True
    if failed:
        raise SystemExit(1)


def image(reference, architecture):
    # Always retain all severities and unfixed issues. The release gate blocks fixed HIGH/CRITICAL
    # vulnerabilities; unresolved upstream vulnerabilities remain visible in the complete report.
    trivy = binary('trivy')
    common = ('--scanners=vuln', '--platform=' + architecture,
              '--ignorefile=security/trivy-ignore.yaml', '--timeout=15m')
    suffix = architecture.replace('/', '-')
    report = REPORTS / ('image-' + suffix + '.json')
    run(trivy, 'image', *common, '--format=json', '--output=' + str(report), reference)
    run(trivy, 'convert', '--format=cyclonedx', '--output=' + str(REPORTS / ('sbom-' + suffix + '.cdx.json')), str(report))
    run(trivy, 'image', *common, '--severity=HIGH,CRITICAL', '--ignore-unfixed', '--exit-code=1', reference)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('check', choices=['secrets', 'source', 'config', 'image'])
    parser.add_argument('--image')
    parser.add_argument('--platform', default='linux/amd64', choices=['linux/amd64', 'linux/arm64'])
    args = parser.parse_args()
    REPORTS.mkdir(exist_ok=True)
    if args.check == 'image':
        if not args.image:
            parser.error('--image is required for image scans')
        image(args.image, args.platform)
    else:
        globals()[args.check]()


if __name__ == '__main__':
    main()
