"""
BasePage
--------
Provides common helpers shared by all page objects:
  - navigation
  - waiting helpers
  - screenshot on demand
  - toast / notification reading
"""
import logging
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page, Locator, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

SCREENSHOTS_DIR = Path(__file__).parent.parent / "screenshots"


class BasePage:
    # Default timeouts (ms)
    DEFAULT_TIMEOUT = 30_000
    SHORT_TIMEOUT = 10_000
    LONG_TIMEOUT = 60_000

    def __init__(self, page: Page):
        self.page = page
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, url: str) -> None:
        logger.info("Navigating to %s", url)
        # Use domcontentloaded — e6data is a SPA with persistent WebSockets that
        # never reach "networkidle". After DOM is ready we wait for a short settle.
        self.page.goto(url, wait_until="domcontentloaded", timeout=self.LONG_TIMEOUT)
        time.sleep(2)

    def reload(self) -> None:
        self.page.reload(wait_until="domcontentloaded", timeout=self.LONG_TIMEOUT)
        time.sleep(2)

    # ------------------------------------------------------------------
    # Waiting helpers
    # ------------------------------------------------------------------

    def wait_for_selector(self, selector: str, timeout: int = DEFAULT_TIMEOUT) -> Locator:
        locator = self.page.locator(selector)
        locator.wait_for(state="visible", timeout=timeout)
        return locator

    def wait_for_text(self, text: str, timeout: int = DEFAULT_TIMEOUT) -> Locator:
        locator = self.page.get_by_text(text, exact=False)
        locator.first.wait_for(state="visible", timeout=timeout)
        return locator

    def wait_for_url_contains(self, fragment: str, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.page.wait_for_url(f"**{fragment}**", timeout=timeout)

    def wait_for_network_idle(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        # e6data SPA never reaches networkidle (persistent WebSocket).
        # Use a short settle sleep instead.
        time.sleep(2)

    def wait_ms(self, ms: int) -> None:
        """Explicit sleep — use sparingly, prefer proper waits."""
        time.sleep(ms / 1000)

    # ------------------------------------------------------------------
    # Element interaction helpers
    # ------------------------------------------------------------------

    def click(self, selector: str, timeout: int = DEFAULT_TIMEOUT) -> None:
        logger.debug("Clicking: %s", selector)
        self.page.locator(selector).wait_for(state="visible", timeout=timeout)
        self.page.locator(selector).click()

    def fill(self, selector: str, value: str, timeout: int = DEFAULT_TIMEOUT) -> None:
        logger.debug("Filling '%s' with '%s'", selector, value)
        locator = self.page.locator(selector)
        locator.wait_for(state="visible", timeout=timeout)
        locator.clear()
        locator.fill(value)

    def select_option(self, selector: str, value: str, timeout: int = DEFAULT_TIMEOUT) -> None:
        logger.debug("Selecting option '%s' in '%s'", value, selector)
        locator = self.page.locator(selector)
        locator.wait_for(state="visible", timeout=timeout)
        locator.select_option(value)

    def get_text(self, selector: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        locator = self.page.locator(selector)
        locator.wait_for(state="visible", timeout=timeout)
        return (locator.inner_text() or "").strip()

    def get_input_value(self, selector: str, timeout: int = DEFAULT_TIMEOUT) -> str:
        locator = self.page.locator(selector)
        locator.wait_for(state="visible", timeout=timeout)
        return (locator.input_value() or "").strip()

    def is_visible(self, selector: str, timeout: int = SHORT_TIMEOUT) -> bool:
        try:
            self.page.locator(selector).wait_for(state="visible", timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            return False

    def is_checked(self, selector: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
        locator = self.page.locator(selector)
        locator.wait_for(state="visible", timeout=timeout)
        return locator.is_checked()

    def check_checkbox(self, selector: str, timeout: int = DEFAULT_TIMEOUT) -> None:
        locator = self.page.locator(selector)
        locator.wait_for(state="visible", timeout=timeout)
        if not locator.is_checked():
            locator.check()

    def uncheck_checkbox(self, selector: str, timeout: int = DEFAULT_TIMEOUT) -> None:
        locator = self.page.locator(selector)
        locator.wait_for(state="visible", timeout=timeout)
        if locator.is_checked():
            locator.uncheck()

    # ------------------------------------------------------------------
    # Toast / notification
    # ------------------------------------------------------------------

    def get_toast_message(self, timeout: int = DEFAULT_TIMEOUT) -> str:
        """
        Read the first visible toast / snackbar notification.
        Covers common React toast libraries used in e6data UI.
        """
        selectors = [
            "[role='alert']",
            ".Toastify__toast-body",
            ".toast-message",
            "[data-testid='toast']",
            ".notification-message",
            ".ant-message-notice-content",
        ]
        for sel in selectors:
            try:
                locator = self.page.locator(sel).first
                locator.wait_for(state="visible", timeout=timeout // len(selectors))
                return (locator.inner_text() or "").strip()
            except PlaywrightTimeoutError:
                continue
        return ""

    def dismiss_toast(self) -> None:
        """Click the close button on a visible toast if present."""
        close_selectors = [
            ".Toastify__close-button",
            "[aria-label='close']",
            "[data-testid='toast-close']",
        ]
        for sel in close_selectors:
            if self.is_visible(sel, timeout=2000):
                self.page.locator(sel).first.click()
                return

    # ------------------------------------------------------------------
    # Screenshot helpers
    # ------------------------------------------------------------------

    def screenshot(self, name: str) -> Path:
        path = SCREENSHOTS_DIR / f"{name}.png"
        self.page.screenshot(path=str(path), full_page=True)
        logger.info("Screenshot saved: %s", path)
        return path

    def screenshot_on_failure(self, test_name: str) -> Path:
        return self.screenshot(f"FAIL_{test_name}_{int(time.time())}")

    # ------------------------------------------------------------------
    # Modal / dialog helpers
    # ------------------------------------------------------------------

    def wait_for_dialog(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        """Wait for any modal/dialog to become visible."""
        selectors = [
            "[role='dialog']",
            ".modal",
            ".ant-modal-content",
            "[data-testid='dialog']",
        ]
        for sel in selectors:
            if self.is_visible(sel, timeout=timeout // len(selectors)):
                return
        raise PlaywrightTimeoutError("No dialog became visible within timeout")

    def close_dialog(self) -> None:
        """Close an open modal dialog."""
        close_selectors = [
            "[aria-label='Close']",
            "[aria-label='close']",
            ".modal-close",
            "[data-testid='dialog-close']",
            "button.close",
        ]
        for sel in close_selectors:
            if self.is_visible(sel, timeout=2000):
                self.page.locator(sel).first.click()
                return

    # ------------------------------------------------------------------
    # Table helpers
    # ------------------------------------------------------------------

    def get_table_row_count(self, table_selector: str = "table") -> int:
        return self.page.locator(f"{table_selector} tbody tr").count()

    def get_cell_text(self, row_index: int, col_index: int, table_selector: str = "table") -> str:
        cell = self.page.locator(f"{table_selector} tbody tr").nth(row_index).locator("td").nth(col_index)
        return (cell.inner_text() or "").strip()

    def find_table_row_by_text(self, text: str, table_selector: str = "table") -> Optional[Locator]:
        rows = self.page.locator(f"{table_selector} tbody tr")
        count = rows.count()
        for i in range(count):
            row = rows.nth(i)
            if text in (row.inner_text() or ""):
                return row
        return None
