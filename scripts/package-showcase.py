#!/usr/bin/env python3
"""Build an offline copy from the maintained gallery; standard library only."""

import base64
import re
from pathlib import Path


def build():
    root = Path(__file__).resolve().parents[1] / "docs"
    html = (root / "index.html").read_text()
    html = html.replace('<html lang="en"', '<html data-standalone="true" lang="en"', 1)
    html = html.replace(
        '<link rel="stylesheet" href="showcase.css" />',
        "<style>\n" + (root / "showcase.css").read_text() + "\n</style>",
    )
    html = html.replace('<script src="showcase.js" defer></script>', "")
    html = html.replace(
        "</body>",
        "<script>\n" + (root / "showcase.js").read_text() + "\n</script>\n</body>",
    )

    def embed(match):
        path = root / match[2]
        kind = "image/svg+xml" if path.suffix == ".svg" else "image/jpeg"
        data = base64.b64encode(path.read_bytes()).decode()
        return match[1] + '="data:' + kind + ";base64," + data + '"'

    html = re.sub(r'(src|href)="(screenshots/[^"/]+\.jpg|icon\.svg)"', embed, html)
    html = re.sub(r"^[ \t]+$", "", html, flags=re.MULTILINE)
    (root / "mailcow-modern-ui-showcase.html").write_text(html)


if __name__ == "__main__":
    build()
