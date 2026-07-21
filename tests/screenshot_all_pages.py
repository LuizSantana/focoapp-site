#!/usr/bin/env python3
"""Walk every page of the Foco+ site and capture light/dark x desktop/mobile
screenshots. Serves the repo root over a local HTTP server (not file://, so
relative paths and JS behave exactly like production) and drives it with
Playwright/Chromium.

Usage:
    tests/.venv/bin/python tests/screenshot_all_pages.py
"""
import http.server
import socketserver
import threading
import time
import pathlib
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "tests" / "screenshots"
PORT = 8935

PAGES = [
    ("home-pt-br", "/"),
    ("home-pt-pt", "/pt-pt/"),
    ("home-en", "/en/"),
    ("sobre-pt-br", "/sobre/"),
    ("sobre-pt-pt", "/sobre/pt-pt/"),
    ("sobre-en", "/sobre/en/"),
    ("suporte-pt-br", "/suporte/"),
    ("suporte-pt-pt", "/suporte/pt-pt/"),
    ("suporte-en", "/suporte/en/"),
    ("novidades-pt-br", "/novidades/"),
    ("novidades-pt-pt", "/novidades/pt-pt/"),
    ("novidades-en", "/novidades/en/"),
    ("termos-pt-br", "/termos/"),
    ("termos-pt-pt", "/termos/pt-pt/"),
    ("termos-en", "/termos/en/"),
    ("privacidade-pt-br", "/privacidade/"),
    ("privacidade-pt-pt", "/privacidade/pt-pt/"),
    ("privacidade-en", "/privacidade/en/"),
    ("clip", "/clip/"),
]

VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900},
    "mobile": {"width": 375, "height": 812},
}
COLOR_SCHEMES = ["light", "dark"]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


def start_server():
    handler = lambda *a, **kw: QuietHandler(*a, directory=str(ROOT), **kw)
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    httpd = start_server()
    time.sleep(0.3)

    failures = []
    total = 0

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for viewport_name, viewport in VIEWPORTS.items():
            for scheme in COLOR_SCHEMES:
                context = browser.new_context(
                    viewport=viewport,
                    color_scheme=scheme,
                    device_scale_factor=2,
                )
                page = context.new_page()
                console_errors = []
                page.on(
                    "console",
                    lambda msg: console_errors.append(msg.text)
                    if msg.type == "error"
                    else None,
                )

                for name, path in PAGES:
                    total += 1
                    url = f"http://127.0.0.1:{PORT}{path}"
                    console_errors.clear()
                    try:
                        response = page.goto(url, wait_until="networkidle", timeout=15000)
                        status = response.status if response else None
                        if status != 200:
                            failures.append(f"{name} [{viewport_name}/{scheme}]: HTTP {status}")
                            continue

                        # let scroll-reveal / IntersectionObserver animations settle
                        page.evaluate(
                            "document.querySelectorAll('.reveal').forEach(el => el.classList.add('is-visible'))"
                        )
                        page.wait_for_timeout(150)

                        overflow = page.evaluate(
                            "document.documentElement.scrollWidth > window.innerWidth"
                        )
                        if overflow:
                            failures.append(f"{name} [{viewport_name}/{scheme}]: horizontal overflow")

                        out_path = OUT_DIR / f"{name}__{viewport_name}__{scheme}.png"
                        page.screenshot(path=str(out_path), full_page=True)

                        if console_errors:
                            failures.append(
                                f"{name} [{viewport_name}/{scheme}]: console errors: {console_errors}"
                            )
                    except Exception as exc:
                        failures.append(f"{name} [{viewport_name}/{scheme}]: {exc}")

                context.close()
        browser.close()

    httpd.shutdown()

    print(f"\n{total} page/viewport/scheme combinations captured into {OUT_DIR}")
    if failures:
        print(f"\n{len(failures)} problem(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("0 problems.")


if __name__ == "__main__":
    main()
