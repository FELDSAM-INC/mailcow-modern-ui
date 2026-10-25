# mailcow compatibility

Use **mailcow 2026-09a or newer**, including **2026-10**.
Older releases have not been fully tested. History confirms that `2026-09` shares the
accepted schema; releases through `2026-07b` use older schemas and currently fail API readiness.

| mailcow release | Compatibility evidence |
| --- | --- |
| `2026-09a` | Supported; the database fixture and nginx integration tests use this baseline. |
| `2026-10` | Supported; installation with Ansible, root URL mode, mobile/desktop login, API readiness, and the classic interface were verified on a running server. |
| `2026-09` | Schema definition is identical to `2026-09a` and `2026-10`; full installation remains untested. |
| `2026-07b` and earlier | Older schemas; currently rejected by the API's readiness check. |

## Database schema

The current API accepts database schema **`18082026_1200`**. Both
[`2026-09a`](https://github.com/mailcow/mailcow-dockerized/blob/2026-09a/data/web/inc/init_db.inc.php)
and [`2026-10`](https://github.com/mailcow/mailcow-dockerized/blob/2026-10/data/web/inc/init_db.inc.php)
declare that schema. Compatibility is checked by schema, not by an exact mailcow release name.

The complete `init_db.inc.php` file is byte-identical in `2026-09`, `2026-09a`, and
`2026-10`. This establishes schema compatibility, rather than full acceptance of every
feature on an older release.

The same readiness check applies to older releases. A newer release that changes the schema
may require an updated API image; see the API's
[supported schemas](https://github.com/FELDSAM-INC/mailcow-rest-v2#supported-mailcow-releases).

## Schema history

The upstream 2025/2026 release tags were checked on 25 October 2026. These values come
from each release's `data/web/inc/init_db.inc.php`:

| Release tags | Database schema |
| --- | --- |
| `2026-09`, `2026-09a`, `2026-10` | `18082026_1200` |
| `2026-03` through `2026-07b`, including the intervening patch releases | `19022026_1220` |
| `2026-01` | `28012026_1000` |
| `2025-12`, `2025-12a` | `10312025_0525` |
| `2025-09c`, `2025-10`, `2025-10a` | `07102025_1015` |
| `2025-09`, `2025-09a`, `2025-09b` | `19082025_1436` |
| `2025-03` through `2025-07`, including the intervening patch releases | `27012025_1555` |
| `2025-01`, `2025-01a`, `2025-02` | `20112024_1105` |

The current schema was introduced by
[`8bd9e12a` on 18 August 2026](https://github.com/mailcow/mailcow-dockerized/commit/8bd9e12a73ec68945db9e12f8af406b863d9e2d8).
It added `da_acl.alias_external_goto` for controlling aliases with external destinations.
That column is absent in `2026-07b`; the API uses it in domain-administrator permission
queries and writes. Supporting that older schema therefore requires compatibility handling
and tests, rather than just accepting its version number.

Earlier changes include `admin.attributes` and forced password/2FA settings in
[`ad5b94af`](https://github.com/mailcow/mailcow-dockerized/commit/ad5b94af5e48297631629c2a118e7f163a044a07),
`alias.sender_allowed` in
[`c06112b2`](https://github.com/mailcow/mailcow-dockerized/commit/c06112b26e6f41c7f9d5c2ea2549b266e66a44e3),
and mailbox EAS/DAV access attributes in
[`56ea4302`](https://github.com/mailcow/mailcow-dockerized/commit/56ea4302ed13ac9aa344dc840689c4dd6ac76b68).

## Community Preview 1 documentation

The `2026-09a` value in the frozen preview manifest records the original fixture baseline.
The preview's existing UI/API images also support `2026-10`; no replacement image is needed.
Installation guides archived under the `v0.1.0-preview.1` tag retain their original wording.
This page and the published release notes provide the updated compatibility guidance.
