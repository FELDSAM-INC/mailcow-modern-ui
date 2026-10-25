# mailcow compatibility

Use **mailcow 2026-09a or newer**, including **2026-10**.
Older releases are expected to work, but have not been tested yet.

| mailcow release | Compatibility evidence |
| --- | --- |
| `2026-09a` | Supported; the database fixture and nginx integration tests use this baseline. |
| `2026-10` | Supported; installation with Ansible, root URL mode, mobile/desktop login, API readiness, and the classic interface were verified on a running server. |
| Older releases | Expected to work with a compatible database schema; untested. |

## Database schema

The current API accepts database schema **`18082026_1200`**. Both
[`2026-09a`](https://github.com/mailcow/mailcow-dockerized/blob/2026-09a/data/web/inc/init_db.inc.php)
and [`2026-10`](https://github.com/mailcow/mailcow-dockerized/blob/2026-10/data/web/inc/init_db.inc.php)
declare that schema. Compatibility is checked by schema, not by an exact mailcow release name.

The same readiness check applies to older releases. A newer release that changes the schema
may require an updated API image; see the API's
[supported schemas](https://github.com/FELDSAM-INC/mailcow-rest-v2#supported-mailcow-releases).

## Community Preview 1 documentation

The `2026-09a` value in the frozen preview manifest records the original fixture baseline.
The preview's existing UI/API images also support `2026-10`; no replacement image is needed.
Installation guides archived under the `v0.1.0-preview.1` tag retain their original wording.
This page and the published release notes provide the updated compatibility guidance.
