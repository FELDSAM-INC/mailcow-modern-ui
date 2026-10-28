# Release security rule for coding agents

This maintainer requirement applies to Codex and Claude Code in all three mailcow
repositories: `mailcow-rest-v2`, `mailcowui-ng`, and `mailcow-modern-ui`.

## Required before releasing changed code

Before creating or pushing release tags, publishing a preview/RC/stable release,
promoting release image tags, or deploying that release after application,
installer, dependency, build, or security configuration changes:

1. Finish and commit the release changes, and identify the exact API and UI
   source revisions that will ship. Preserve unrelated user changes; use isolated
   checkouts of the release commits when necessary.
2. Run a fresh, real **full-repository Codex Security scan of both application
   repositories**, even if only one component changed. Run them sequentially with
   each repository's subscription runner. With the usual sibling checkout layout,
   run these commands from any of the three repository roots:

   ```bash
   (cd ../mailcow-rest-v2 && node scripts/security/scan-local.mjs)
   (cd ../mailcowui-ng && node scripts/security/scan-local.mjs)
   ```

   Locate the correct release checkouts if their directories differ. Do not
   substitute a PR diff scan, a path-only scan, `--dry-run`, another scanner, or a
   report from a previous release. This is a release prerequisite, not a scan on
   every edit or session startup.
3. For each scan, require a successful exit and `scan.status: "completed"` in
   `scan-manifest.json`. Verify repository scope and the full target revision
   against the intended release commit. Read `report.md`, `findings.json`, and
   `coverage.json`; exit code 0 or zero findings alone is insufficient.
4. Investigate findings and fix confirmed security issues before releasing.
   Record evidence for false-positive decisions. After a fix or any other
   release-code change, commit it and repeat the affected repository's scan;
   both final reports must still match the exact revisions being released.
5. Keep the complete scan artifacts and diagnostics in private directories
   outside Git worktrees (directories 0700, files 0600). Preserve temporary
   reports in durable private storage. Record both revisions, scan IDs,
   completion status, findings disposition, coverage limits, and report locations
   in the release handoff. Do not commit or publicly upload raw scan reports.
6. Publish or deploy the release only after both scans satisfy this rule and the
   existing tests and image verification pass. If a scan fails, is incomplete, cannot
   authenticate, or cannot run safely, keep the release unpublished, finish
   independent preparation, and report the exact blocker. Never silently waive
   this requirement or describe an unsuccessful scan as clean.

## Subscription and sandbox requirements

- Use `scripts/security/scan-local.mjs` in each application repository. It pins
  the scanner, selects a supported Python, explicitly uses
  `--auth chatgpt --provider openai`, and removes `OPENAI_API_KEY` and
  `CODEX_API_KEY` from the scanner environment. Never fall back to paid API scans.
- If login is missing, use
  `npx --yes @openai/codex-security@0.6.0 login` in the intended account/workspace.
  A successful login status or dry run does not establish model access or a
  completed scan.
- Keep the scanner sandbox and protected credential directory enabled. On Linux,
  check `bwrap --version` and `bwrap --help | rg -- --argv0` when diagnosing
  sandbox startup failures. Bubblewrap 0.6.3 previously caused
  `codex-linux-sandbox` permission errors on the maintainer's machine; 0.13.1
  with `--argv0` was verified working. Fix tool compatibility rather than
  disabling isolation or credential protection.
- Preserve redacted diagnostics privately; `CODEX_SECURITY_LOG_LEVEL=debug`
  enables them. A generic model-access error can wrap a local permission failure,
  so inspect the underlying error before concluding that account access is missing.
- Paid PR scans remain advisory. This local, subscription-based requirement is
  an additional maintainer release rule; it does not replace the existing CI
  security checks or independent-review requirements.

See `docs/security-checks.md` for the existing checks and their coverage.
