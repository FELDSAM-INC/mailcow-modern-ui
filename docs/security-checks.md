# Security checks

These checks complement Codex Security and manual review. They do not certify that the application
is secure. Scanner configuration and tool versions are reviewed code.

## Required local scans before a release

The maintainer requires fresh subscription-based Codex Security repository scans
of **both API and UI** before releasing changed code, including previews. Follow
[the release rule in AGENTS.md](../AGENTS.md): scan the exact component commits,
review findings and coverage, fix confirmed issues, and retain evidence privately.
Codex loads the root rule automatically; Claude Code imports it through
`CLAUDE.md`. Failed, incomplete, dry-run, or stale scans do not satisfy this rule.
This requirement is separate from the advisory paid PR scan described below.

## Routine checks

The normal CI workflow calls `security.yml` on pull requests, main pushes and release tags.
It must pass before images or installer releases are published. A separate weekly run catches
new advisories even when application code has not changed.

| Check | Coverage | Gate |
| --- | --- | --- |
| Gitleaks CLI | All fetched Git history, default detectors and mailcow API keys | Any unreviewed finding or scanner failure |
| Semgrep CE | Selected PHP/Laravel, JS/TS and Python rules; see `security/tools.json` for this repository's targets | Any selected rule finding, invalid rule or scanner failure |
| Dependency audit | Composer lockfile including development packages in the API; existing npm audit policy in the UI | Composer advisories; npm production moderate+ and development critical |
| Trivy | Production Dockerfiles and container OS/application packages | High/critical configuration issues and **fixable** high/critical image vulnerabilities |
| Installer integration | Rendered Compose, secrets handling, rollback, route ownership and privilege restrictions | Any test failure |
| CodeQL | UI JavaScript/TypeScript, installer Python and GitHub Actions | Findings appear in GitHub code scanning; configure rulesets to require this check |

CodeQL does not support PHP. Semgrep CE has limited interprocedural coverage; source scanning is
not a substitute for the API's authorization matrices and targeted lifecycle tests.
Trivy does not scan our Compose or Ansible syntax: the installer integration tests cover deployment
behavior, rather than reporting an empty Trivy scan as successful coverage.

The Python runner downloads Gitleaks and Trivy binaries only after SHA-256 verification.
Semgrep and ZAP images are pinned by digest. Selected upstream Semgrep rules are pinned by commit
and individual checksums and run with metrics disabled and no network access. Rules remain under
[their upstream license](https://semgrep.dev/legal/rules-license); this project references and downloads them,
without copying them into its application source license.

## Local commands

Requirements: Linux x86_64, Python 3.9+, Git, Docker, and Internet access to download scanners and
vulnerability databases. Container image scans can inspect AMD64 or ARM64 images without executing them.

Run from the repository root, after committing changes so the history scan includes them:

```sh
python3 scripts/security/check.py secrets
python3 scripts/security/check.py source
python3 scripts/security/check.py config
```

In either application repository, scan a local or published image:

```sh
python3 scripts/security/check.py image --image IMAGE --platform linux/amd64
python3 scripts/security/check.py image --image IMAGE --platform linux/arm64
```

Reports go in ignored `security-reports/`. Gitleaks values are redacted. Image reports retain **all
severities and unfixed vulnerabilities**, even though the release gate blocks fixable high/critical
findings. CycloneDX SBOMs accompany image reports. Review unfixed findings before release.
The CI artifact retention is 7 days (14 days for release image evidence).

Before moving `latest` or version tags, the publishing job scans both architectures of the candidate
image **by digest**. It then promotes that same manifest, retaining build provenance and SBOM attestations.
The temporary `scan-*` tag is a candidate, not a supported release. A failing scan leaves existing
release tags untouched. Weekly scans recheck the current `latest` image; pinned older previews must
also be scanned before recommending them for continued use.

Before publishing an installation bundle, `scripts/check-release.py` verifies anonymous registry
access, both image architectures and their source revisions, and that each preview version tag
resolves to the exact image digest recorded in `deploy/release.json`.

## Authenticated runtime testing

In an API checkout with the UI checkout next to it:

```sh
python3 scripts/security/runtime.py --ui-dir ../mailcowui-ng
```

From a UI checkout, run `python3 ../mailcow-rest-v2/scripts/security/runtime.py --ui-dir .`.
The `Runtime security` Actions workflow provides the same test weekly and on manual dispatch, without
production credentials. It tests this repository's checkout against the companion repository's main
branch. Source revisions are recorded by GitHub; release review should repeat against the exact pair.

The runner creates a temporary API snapshot, a unique Compose project, random credentials and sample
data. After building and seeding, the scanner and target use an **internal Docker network without
external egress**. It cannot accept a production URL. A `finally` block removes its containers,
volumes, worktree and network; existing development stacks are not reused.

Runtime coverage includes real HTTP sessions for administrator, domain administrator and mailbox user;
foreign mailbox reads/writes, foreign domain/list isolation, read-only and revoked API keys; passive
checks of frontend HTML/assets; and authenticated ZAP active scans of selected OpenAPI GET endpoints.
Authentication is checked before and after each role's scan. High-risk ZAP alerts, failed assertions,
missing endpoints and scanner errors fail the run. Medium/low alerts remain visible for review.

Active scans have five-minute role budgets and one-minute rule budgets. They do not exhaustively test
all endpoints or mutating operations, and the passive spider does not replace browser-based SPA tests.
Existing PHPUnit tests cover mutation authorization, CSRF, reset-token replay, MFA/passkeys, SSO,
impersonation and log redaction. Reports omit cookies, keys, payload evidence and HTTP bodies.

## Exceptions and credentials

`.gitleaksignore` contains exact reviewed historical fingerprints for synthetic test keys, public
certificates, schema placeholders and source hashes. Entire test directories are **not** excluded.
A different secret in the same file still fails. Never silence a real secret: revoke it and review
its exposure before considering history cleanup.

Trivy exceptions, if necessary, belong in `security/trivy-ignore.yaml`, with exact identifiers,
affected paths/packages, a reason and an expiration. No global severity suppression or ignored
scanner error is permitted. Review and fix findings rather than repeatedly refreshing a baseline.
The current npm policy retains high-severity development advisories as visible warnings; optional
Lighthouse tooling has unresolved upstream advisories and must not process untrusted external sites.

## Codex costs and GitHub administration

Paid Codex Security remains advisory and limited to trusted PR changes. These additional checks use
local tools and have no model API charge; CI compute/storage still consume resources. Full Codex scans
continue through local ChatGPT sign-in. No paid repository-wide scan or automatic paid retry is added.

A repository administrator should verify these settings in each public repository:

1. Enable secret scanning, push protection and private vulnerability reporting under Security settings.
2. Require the CI security and CodeQL checks in the main-branch ruleset, restrict bypasses and require review.
3. Protect release tags; keep Actions token permissions read-only by default and use pinned actions.
4. Review Dependabot updates for application dependencies, base images and Actions. Scanner binary/rule
   pins in `security/tools.json` need deliberate checksum-reviewed updates.

Workflow files cannot enable these repository settings. They require authenticated GitHub administrator
access. Independent human review remains a separate release requirement; see the review brief.
