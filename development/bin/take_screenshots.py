"""Capture documentation screenshots from a running Nautobot development instance.

This script drives a real browser with Playwright. It is not part of the test suite and it is not
installed with the app. Run it by hand after you change the UI, then commit the refreshed images.

Prerequisites:

    pip install playwright
    python -m playwright install chromium

Usage:

    invoke start
    python development/bin/take_screenshots.py --url http://localhost:8080

The instance must already hold demonstration data. See docs/dev/dev_environment.md.
"""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).parent.parent.parent
IMAGE_DIR = REPO_ROOT / "docs" / "images"
MEDIA_DIR = REPO_ROOT / "docs" / "media"

# The development instance shows a "Local" banner that production users never see.
HIDE_CHROME_CSS = """
header#header .banner-alert-area { display: none !important; }
"""

# The Django Debug Toolbar renders inside a shadow root, so CSS cannot reach it. Remove the host.
REMOVE_DEBUG_TOOLBAR_JS = "() => { document.getElementById('djDebugRoot')?.remove(); }"

VIEWPORT = {"width": 1600, "height": 760}


def log(message):
    """Print a progress line."""
    print(f"  {message}", flush=True)


def set_theme(context, base_url, theme):
    """Force the Nautobot colour theme. Nautobot reads it from two cookies."""
    context.add_cookies(
        [
            {"name": "theme_choice", "value": theme, "url": base_url},
            {"name": "theme", "value": theme, "url": base_url},
        ]
    )


def login(page, base_url, username, password):
    """Sign in to Nautobot."""
    page.goto(f"{base_url}/login/")
    page.fill("input[name=username]", username)
    page.fill("input[name=password]", password)
    page.click("button[type=submit], input[type=submit]")
    page.wait_for_load_state("networkidle")


def settle(page):
    """Wait for the page to finish loading and hide the development-only chrome."""
    page.wait_for_load_state("networkidle")
    page.evaluate(REMOVE_DEBUG_TOOLBAR_JS)
    page.add_style_tag(content=HIDE_CHROME_CSS)
    page.wait_for_timeout(400)


def shot(page, path, full_page=True):
    """Write one screenshot and report it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=full_page)
    log(f"wrote {path.relative_to(REPO_ROOT)}")


def capture_provider_list(page, base_url, target):
    """The AI Providers list view."""
    page.goto(f"{base_url}/plugins/ai-models/providers/")
    settle(page)
    shot(page, target)


def capture_model_list(page, base_url, target):
    """The AI Models list view."""
    page.goto(f"{base_url}/plugins/ai-models/ai-models/")
    settle(page)
    shot(page, target)


def capture_provider_detail(page, base_url, target, provider_name):
    """The detail view of one named provider, which shows its AI Models panel."""
    page.goto(f"{base_url}/plugins/ai-models/providers/?q={provider_name.replace(' ', '+')}")
    settle(page)
    page.locator("table tbody tr a").first.click()
    settle(page)
    shot(page, target)


def capture_add_form(page, base_url, target):
    """The add form, which shows the embedded-create button beside External Integration."""
    page.goto(f"{base_url}/plugins/ai-models/providers/add/")
    settle(page)
    shot(page, target)


def capture_embedded_modal(page, base_url, target):
    """The embedded-create modal that builds an External Integration without leaving the form."""
    page.goto(f"{base_url}/plugins/ai-models/providers/add/")
    settle(page)
    page.locator('button[hx-get*="external-integrations/add"]').first.click()
    page.wait_for_selector("#embedded_action_modal .modal-content form", timeout=15000)
    page.wait_for_timeout(1200)
    shot(page, target, full_page=False)


def capture_job_result(page, base_url, target):
    """The most recent Discover AI Models job result, including its log."""
    page.goto(f"{base_url}/extras/job-results/?q=Discover+AI+Models")
    settle(page)
    page.locator("table tbody tr a").first.click()
    settle(page)
    page.wait_for_timeout(1500)
    shot(page, target)


def capture_navigation(page, base_url, target):
    """The AI Tools section of the side navigation, with its flyout open."""
    page.goto(f"{base_url}/plugins/ai-models/providers/")
    settle(page)

    button = page.locator('#sidenav li[data-section-name="AI Tools"] > button').first
    button.click()
    flyout_id = button.get_attribute("aria-controls")
    flyout = page.locator(f"#{flyout_id}")
    flyout.wait_for(state="visible", timeout=10000)
    page.wait_for_timeout(600)

    sidenav_box = page.locator("#sidenav").bounding_box()
    flyout_box = flyout.bounding_box()
    right = max(sidenav_box["width"], flyout_box["x"] + flyout_box["width"])

    target.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(
        path=str(target),
        clip={"x": 0, "y": 0, "width": right, "height": VIEWPORT["height"]},
    )
    log(f"wrote {target.relative_to(REPO_ROOT)}")


def main():
    """Capture every documentation screenshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8080", help="Base URL of the running instance.")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin")
    parser.add_argument(
        "--detail-provider",
        default="Ollama Lab",
        help="Name of the provider to feature in the detail screenshot.",
    )
    args = parser.parse_args()
    base_url = args.url.rstrip("/")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()

        for theme in ("light", "dark"):
            print(f"[{theme}]")
            context = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
            set_theme(context, base_url, theme)
            page = context.new_page()
            login(page, base_url, args.username, args.password)

            # The overview page in the app documentation shows one image for each theme.
            capture_provider_list(page, base_url, MEDIA_DIR / f"ss_main_page_{theme}.png")

            if theme == "light":
                capture_model_list(page, base_url, IMAGE_DIR / "ai-models-list.png")
                capture_provider_detail(page, base_url, IMAGE_DIR / "provider-detail.png", args.detail_provider)
                capture_add_form(page, base_url, IMAGE_DIR / "provider-add-form.png")
                capture_embedded_modal(page, base_url, IMAGE_DIR / "external-integration-modal.png")
                capture_job_result(page, base_url, IMAGE_DIR / "discovery-job-result.png")
                capture_navigation(page, base_url, IMAGE_DIR / "ai-tools-navigation.png")
                capture_provider_list(page, base_url, IMAGE_DIR / "ai-providers-list.png")

            context.close()

        browser.close()
    print("done")


if __name__ == "__main__":
    main()
