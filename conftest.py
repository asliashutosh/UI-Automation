"""
Root conftest.py
----------------
Sets up browser context with cookie-based authentication.
All tests share the `browser_context` fixture which injects the
e6_session JWT cookie so every page load is pre-authenticated.

Also installs the pytest_runtest_makereport hook to capture
screenshots on test failure.
"""
import logging
import time
from pathlib import Path
from typing import Generator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from config.settings import config

logger = logging.getLogger(__name__)

SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# pytest hooks
# ---------------------------------------------------------------------------

def pytest_configure(config):
    """Ensure the reports directory exists."""
    reports_dir = Path(__file__).parent / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    After each test phase, if the test FAILED and a `page` fixture was used,
    take a full-page screenshot and attach it to the test report.
    """
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        page: Page = item.funcargs.get("auth_page") or item.funcargs.get("page")
        if page is not None:
            test_name = item.nodeid.replace("/", "_").replace("::", "__").replace(" ", "_")
            screenshot_path = SCREENSHOTS_DIR / f"FAIL_{test_name}_{int(time.time())}.png"
            try:
                page.screenshot(path=str(screenshot_path), full_page=True)
                logger.info("Failure screenshot saved: %s", screenshot_path)
                # Attach to pytest-html report if available
                if hasattr(report, "extras"):
                    try:
                        from pytest_html import extras as html_extras
                        report.extras.append(html_extras.image(str(screenshot_path)))
                    except ImportError:
                        pass
            except Exception as exc:
                logger.warning("Could not capture failure screenshot: %s", exc)


# ---------------------------------------------------------------------------
# Browser fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def playwright_instance():
    """Session-scoped Playwright instance."""
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright_instance) -> Generator[Browser, None, None]:
    """
    Session-scoped browser.
    Chromium is used by default (headless).
    Set PLAYWRIGHT_HEADLESS=false in environment to run headed.
    """
    import os
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() not in ("false", "0", "no")
    # slow_mo adds a delay (ms) between every action — makes interactions
    # feel human-paced. Default 800ms; override with PLAYWRIGHT_SLOW_MO env var.
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", "800"))
    browser = playwright_instance.chromium.launch(
        headless=headless,
        slow_mo=slow_mo,
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )
    yield browser
    browser.close()


@pytest.fixture(scope="function")
def browser_context(browser: Browser) -> Generator[BrowserContext, None, None]:
    """
    Function-scoped browser context.

    Each test gets a fresh browser context (isolated cookies, storage, etc.)
    with the e6_session JWT cookie pre-injected so pages load as an
    authenticated user.
    """
    from urllib.parse import urlparse
    parsed = urlparse(config.base_url)
    domain = parsed.hostname  # e.g. e6f12eab8a-ue1a.e6compute.xyz

    context = browser.new_context(
        base_url=config.base_url,
        viewport={"width": 1440, "height": 900},
        ignore_https_errors=True,
        record_video_dir=None,
    )

    # Inject authentication cookie
    context.add_cookies([
        {
            "name": "e6_session",
            "value": config.session_cookie,
            "domain": domain,
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "sameSite": "Lax",
        }
    ])

    logger.info("Browser context created with e6_session cookie for domain: %s", domain)

    yield context

    context.close()


@pytest.fixture(scope="function")
def page(browser_context: BrowserContext) -> Generator[Page, None, None]:
    """
    Function-scoped page fixture.
    Opens a new tab within the authenticated browser context.
    """
    page = browser_context.new_page()

    # Set default navigation timeout
    page.set_default_navigation_timeout(60_000)
    page.set_default_timeout(30_000)

    yield page

    page.close()


@pytest.fixture(scope="function")
def fresh_page(browser: Browser) -> Generator[Page, None, None]:
    """
    Function-scoped page with NO cookie injection.
    Use this for one-off tests that manage their own login.
    """
    context = browser.new_context(
        base_url=config.base_url,
        viewport={"width": 1440, "height": 900},
        ignore_https_errors=True,
    )
    page = context.new_page()
    page.set_default_navigation_timeout(120_000)
    page.set_default_timeout(30_000)

    yield page

    context.close()


@pytest.fixture(scope="session")
def authenticated_context(browser: Browser) -> Generator[BrowserContext, None, None]:
    """
    Session-scoped browser context authenticated via OTP login.

    Login happens ONCE per pytest session — user enters the OTP when prompted.
    The same context (and its cookies + org selection) is reused by every
    test that requests auth_page, so all tests run in the same browser session.
    """
    import time as _time
    from pages.login_page import LoginPage
    from helpers.gmail_helper import GmailOTPHelper

    context = browser.new_context(
        base_url=config.base_url,
        viewport={"width": 1440, "height": 900},
        ignore_https_errors=True,
    )
    setup_page = context.new_page()
    setup_page.set_default_navigation_timeout(120_000)
    setup_page.set_default_timeout(30_000)

    login = LoginPage(setup_page)
    login.navigate()
    login.enter_email(config.user_email)

    # Record timestamp BEFORE triggering OTP so we ignore stale emails
    otp_requested_at = _time.time()
    login.click_continue()
    login.wait_for_otp_input()

    # ── Auto-fetch OTP from Gmail ─────────────────────────────────────
    logger.info("Fetching OTP from Gmail (sender: no-reply@e6.run)...")
    gmail = GmailOTPHelper()
    otp = gmail.get_otp_with_retry(
        sender="no-reply@e6.run",
        max_retries=12,
        interval=5,
        received_after=otp_requested_at,
    )

    login.fill_otp(otp)
    login.click_verify()
    # ─────────────────────────────────────────────────────────────────

    login.wait_for_login_complete(timeout=30_000)
    login.switch_organization(config.org_name)
    logger.info("Session login complete — org switched to '%s'", config.org_name)

    setup_page.close()

    yield context

    context.close()


@pytest.fixture(scope="session")
def auth_page(authenticated_context: BrowserContext) -> Generator[Page, None, None]:
    """
    Session-scoped page from the authenticated context.
    One tab is reused across all tests — each test navigates to its own URL
    at the start so there is no state bleed between tests.
    """
    p = authenticated_context.new_page()
    p.set_default_navigation_timeout(60_000)
    p.set_default_timeout(30_000)

    yield p

    p.close()
