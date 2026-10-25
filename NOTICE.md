# Third-party notices

The deployment template and nginx snippet derive from
[mailcow-rest-v2](https://github.com/FELDSAM-INC/mailcow-rest-v2) and
[mailcowui-ng](https://github.com/FELDSAM-INC/mailcowui-ng), both GPL-3.0.
The gallery, its styling and behaviour, and screenshots were copied from mailcowui-ng.
The exact deployment source commits are recorded in `deploy/sources.json`.

Screenshots show the mailcowui-ng interface using TailAdmin Vue Free (MIT), Lucide icons
(ISC), and mailcow branding. Their component notices and license texts are maintained in
[mailcowui-ng's third-party notices](https://github.com/FELDSAM-INC/mailcowui-ng/blob/main/THIRD_PARTY_NOTICES.md).
This repository includes screenshots of those components, not the application's component code.

mailcow is the upstream project's name. This community addon is maintained independently;
the name and screenshots do not imply endorsement by mailcow or TailAdmin.

`tests/nginx/upstream/2026-09a/` contains unmodified nginx templates from
[mailcow/mailcow-dockerized tag 2026-09a](https://github.com/mailcow/mailcow-dockerized/tree/2026-09a/data/assets/templates),
copyright the mailcow contributors, distributed under GPL-3.0. `SHA256SUMS` records
their original bytes. These templates are test fixtures; installation does not replace
mailcow's own templates.
