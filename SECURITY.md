# Security

## Reporting vulnerabilities

Please use [GitHub private vulnerability reporting](https://github.com/FELDSAM-INC/mailcow-modern-ui/security/advisories/new).
If it is unavailable, open an issue requesting a private reporting channel **without exploit details**.
Do not include passwords, tokens, private keys, database dumps, or personal mail in public issues.

Include the affected image digest/source revision, a minimal reproduction using synthetic data,
the required role and the potential impact. Test only installations you own or are authorized to assess.

## Supported versions

This is a community preview. Security fixes are delivered on `main` and in subsequent preview releases;
older previews do not have a separate maintenance branch. A pinned installation does not update itself.
Review release notes and update both components to a compatible pair.

## Review policy

Prioritize cross-domain/mailbox authorization, account takeover, API key scope and revocation,
MFA/reset/SSO/passkey lifecycle, injection, external request boundaries, credential leakage,
and installer/CI privilege boundaries. Every confirmed issue needs a regression test where practical.
Do not treat an incomplete, failed or skipped scan as evidence of safety.

See [automated checks](docs/security-checks.md) and the
[independent review brief](https://github.com/FELDSAM-INC/mailcow-modern-ui/blob/main/docs/security-review.md).
