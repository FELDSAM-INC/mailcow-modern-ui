# Maintaining the showcase

`index.html`, `showcase.css`, and `showcase.js` are the browser gallery. All screenshots
are local files in `screenshots/`, with capture dates, routes, and source revision in
`screenshots/capture-manifest.json`. The current images use sample data from UI revision
`3c0ea10d`, captured on 25 October 2026; they are not freshly captured on every release.

Share the [GitHub Pages gallery](https://feldsam-inc.github.io/mailcow-modern-ui/).
You can also open `index.html` locally or serve this directory using any static web server.
The gallery has no analytics, external fonts, or third-party JavaScript.

## Offline download

Regenerate the single-file version after changing the page, styles, script, or images:

```bash
python3 scripts/package-showcase.py
```

Commit `docs/mailcow-modern-ui-showcase.html` alongside those changes. It embeds all
screenshots, CSS, and JavaScript, so the visual tour also works without internet access.
Installation and source links still need a connection.

## GitHub Pages

Enable publishing once in this repository's
[Settings → Pages](https://github.com/FELDSAM-INC/mailcow-modern-ui/settings/pages):

1. Under **Build and deployment**, select **Deploy from a branch**.
2. Select branch **main** and directory **/docs**.
3. Click **Save** and wait for GitHub's Pages deployment to finish.

The public gallery URL is:

`https://feldsam-inc.github.io/mailcow-modern-ui/`

Future pushes to `main` publish this directory automatically. The `.nojekyll` file
keeps the gallery as plain static HTML; no application build, deployment secret, or
custom Actions workflow is needed. The URL returns 404 until Pages is enabled and its
first deployment completes.

Use the Pages URL when sharing the tour. GitHub's repository file viewer and raw-file
URLs are for source/downloads and can show the HTML as text. The hosted gallery renders
in the browser and its download buttons save the offline file as
`mailcow-modern-ui-showcase.html` from the same site.

## Refresh screenshots

Capture against the UI project's mock-data setup using its
[`scripts/showcase/capture.mjs`](https://github.com/FELDSAM-INC/mailcowui-ng/blob/main/scripts/showcase/capture.mjs).
Copy the resulting images and manifest into this repository, review them for real personal
data or credentials, update the visible capture date/revision in the README and gallery,
and regenerate the offline download. Preserve sample data labels.
