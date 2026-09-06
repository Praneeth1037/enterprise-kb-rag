#!/usr/bin/env python3
"""Render captured terminal transcripts as PNG screenshots.

Runs the real commands, captures their real stdout, and renders each capture in a
terminal-styled page with Playwright. Regenerate with:

    python3 docs/make_screenshots.py
"""

from __future__ import annotations

import html
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 18px; background: #1b1f27; display: inline-block;
         width: max-content; min-width: 100%;
         font-family: "DejaVu Sans Mono", "Menlo", monospace; }}
  .win {{ background: #0d1117; border-radius: 9px; overflow: hidden;
          box-shadow: 0 14px 40px rgba(0,0,0,.55); border: 1px solid #2b3240; }}
  .bar {{ background: #21262d; padding: 9px 14px; display: flex; align-items: center;
          gap: 8px; border-bottom: 1px solid #2b3240; }}
  .dot {{ width: 11px; height: 11px; border-radius: 50%; }}
  .r {{ background:#ff5f56 }} .y {{ background:#ffbd2e }} .g {{ background:#27c93f }}
  .ttl {{ color:#8b949e; font-size:12.5px; margin-left:10px; letter-spacing:.2px }}
  pre {{ margin:0; padding:16px 20px; color:#c9d1d9; font-size:{size}px;
         line-height:1.42; white-space:{wrap}; max-width:{maxw}; }}
  .cmd {{ color:#7ee787; font-weight:600 }}
  .p   {{ color:#58a6ff }}
</style></head><body>
<div class="win">
  <div class="bar"><span class="dot r"></span><span class="dot y"></span>
    <span class="dot g"></span><span class="ttl">{title}</span></div>
  <pre>{body}</pre>
</div></body></html>"""


def run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return (proc.stdout + proc.stderr).rstrip("\n")


def render(name: str, title: str, command: str, output: str, size: float = 12.5,
           wrap: bool = True, max_width: str = "1050px") -> None:
    from playwright.sync_api import sync_playwright

    body = (f'<span class="p">pardha@macbook enterprise-kb-rag %</span> '
            f'<span class="cmd">{html.escape(command)}</span>\n'
            f"{html.escape(output)}\n"
            f'<span class="p">pardha@macbook enterprise-kb-rag %</span> ')
    page_html = PAGE.format(
        title=title, body=body, size=size,
        wrap="pre-wrap" if wrap else "pre",
        maxw=max_width if wrap else "none")
    tmp = DOCS / f"_{name}.html"
    tmp.write_text(page_html, encoding="utf-8")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        page = browser.new_page(viewport={"width": 400, "height": 300},
                                device_scale_factor=2)
        page.goto(tmp.as_uri())
        page.wait_for_timeout(250)
        page.screenshot(path=str(DOCS / f"{name}.png"), full_page=True)
        browser.close()
    tmp.unlink(missing_ok=True)
    print(f"wrote docs/{name}.png")


def main() -> int:
    render(
        "screenshot_test_case",
        "Test case 1 - single-hop lookup (works)",
        "python3 run_baseline.py --input examples/test1.txt",
        run([sys.executable, "run_baseline.py", "--input", "examples/test1.txt"]),
    )
    render(
        "screenshot_acl_leak",
        "Test case 3 - access-control failure (contractor asks for salary bands)",
        "python3 run_baseline.py --input examples/test3.txt --role contractor",
        run([sys.executable, "run_baseline.py", "--input", "examples/test3.txt",
             "--role", "contractor"]),
    )
    render(
        "screenshot_eval",
        "Full evaluation - 32 gold questions",
        "python3 run_eval.py",
        run([sys.executable, "run_eval.py"]),
        size=11.0,
        wrap=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
