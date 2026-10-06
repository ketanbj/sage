from __future__ import annotations

import html
from pathlib import Path


def markdown_to_self_contained_html(markdown: str) -> str:
    # Purposefully tiny renderer: preserve the full Markdown as safely escaped preformatted text.
    # The file has no scripts, fonts, remote assets, or network dependencies.
    escaped = html.escape(markdown)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>SAGE report</title><style>
body{{max-width:980px;margin:2rem auto;padding:0 1rem;font:16px/1.5 system-ui;color:#17202a}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f8fa;padding:1.25rem;border-radius:8px}}
</style></head><body><pre>{escaped}</pre></body></html>\n"""


def write_html(path: Path, markdown: str) -> None:
    path.write_text(markdown_to_self_contained_html(markdown), encoding="utf-8")
