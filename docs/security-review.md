# Independent security review brief

Status: **pending independent review**. Automated checks and an author review are not an independent
audit. Complete this review before presenting a preview as a release candidate.

## Scope and evidence

Review both application source revisions, exact multiarchitecture image digests, the installer commit,
manual and Ansible installation, root and `/ng/` routing, and the tested upstream mailcow version.
Record the reviewer, dates, tools, coverage gaps and findings privately. Use synthetic data in a
disposable installation. Do not send a production database or real mail to scanning services.

Start with each repository's `SECURITY.md`, `docs/security-checks.md`, OpenAPI contract, authentication
middleware and authorization tests. Use the OWASP ASVS authentication, session, access control,
validation, cryptography and configuration requirements as a review checklist, recording the version used.

## Required investigation

- Administrator/domain administrator/mailbox separation, including nested resources, bulk operations,
  renamed/deleted/recreated accounts, revoked domain assignments and concurrent requests.
- API-key scope, network restrictions, expiration, revocation, owner lifecycle and interaction with cookies.
- Password reset enumeration/replay, recovery-address changes, session invalidation, MFA enrollment/removal,
  TOTP replay, WebAuthn origin/RP/challenge binding, SSO state/nonce and impersonation termination.
- SQL/command/template injection; paths and uploaded assets; unsafe HTML; request body/content-type
  handling; CSRF and cookie/CSP behavior in both supported URL layouts.
- Sync, routing, DNS and identity-provider connections: allowed destinations, TLS verification,
  redirects, internal-service exposure, timeouts and role permissions. Private mail infrastructure
  can be intentional; document the trust boundary rather than blanket-blocking private addresses.
- Passwords, API keys, DKIM private keys, reset/SSO tokens and message contents in responses, exports,
  application/proxy logs, audit records, caches and CI artifacts.
- Shared database/Redis assumptions, upstream schema compatibility, legacy endpoints, container API
  access, installation secrets, rollback and backup restoration.
- CI credentials, untrusted PR execution, branch/tag protections, candidate image scanning and
  provenance, published artifact contents and dependency/update policy.

## Acceptance

Reproduce and fix confirmed issues with focused regression tests. Resolve critical/high findings
before RC; record explicit, time-limited acceptance for any remaining risk with an owner. Repeat
checks against the final source/image pair and retain sanitized evidence. A report must state any
untested functionality; an empty or interrupted scan is not approval.

No external reviewer has been commissioned by this implementation.
