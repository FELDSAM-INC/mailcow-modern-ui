# Maintaining the showcase

`index.html`, `showcase.css`, and `showcase.js` are the browser gallery. All screenshots
are local files in `screenshots/`, with capture dates, routes, and source revision in
`screenshots/capture-manifest.json`. The current images use sample data from UI revision
`3c0ea10d`, captured on 25 October 2026; they are not freshly captured on every release.

Open `index.html` locally, or serve this directory using any static web server.
The gallery has no analytics, external fonts, or third-party JavaScript.

## Offline download

Regenerate the single-file version after changing the page, styles, script, or images:

```bash
python3 scripts/package-showcase.py
```

Commit `docs/mailcow-modern-ui-showcase.html` alongside those changes. It embeds all
screenshots, CSS, and JavaScript, so the visual tour also works without internet access.
Installation and source links still need a connection.

## GitHub Pages (optional)

In this repository's **Settings → Pages**, select **Deploy from a branch**, branch
**main**, directory **/docs**. After GitHub finishes publishing, the URL will be:

`https://feldsam-inc.github.io/mailcow-modern-ui/`

The repository README and offline download work without enabling Pages. This repository
does not provision a Pages site or claim that the URL is already live.

## Refresh screenshots

Capture against the UI project's mock-data setup using its
[`scripts/showcase/capture.mjs`](https://github.com/FELDSAM-INC/mailcowui-ng/blob/main/scripts/showcase/capture.mjs).
Copy the resulting images and manifest into this repository, review them for real personal
data or credentials, update the visible capture date/revision in the README and gallery,
and regenerate the offline download. Preserve sample data labels.
