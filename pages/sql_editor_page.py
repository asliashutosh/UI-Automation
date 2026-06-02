"""
SQLEditorPage
-------------
Represents the /sql-editor page.

Key actions:
  - Select a catalog
  - Type / paste a SQL query
  - Run the query
  - Read result rows / columns
  - Read error messages
"""
import logging
from typing import List, Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class SQLEditorPage(BasePage):
    # ------------------------------------------------------------------
    # Editor area selectors
    # ------------------------------------------------------------------
    EDITOR_CONTAINER = (
        "[data-testid='sql-editor'], "
        ".sql-editor, "
        ".CodeMirror, "
        ".monaco-editor, "
        "[role='textbox'][aria-label*='editor' i]"
    )
    # Monaco editor uses a contenteditable div; CodeMirror uses .CodeMirror-code
    EDITOR_TEXTAREA = (
        ".monaco-editor textarea, "
        ".CodeMirror textarea, "
        "[data-testid='sql-textarea'], "
        "textarea[name='query']"
    )

    # ------------------------------------------------------------------
    # Catalog / schema selectors
    # ------------------------------------------------------------------
    CATALOG_SELECT = (
        "[data-testid='catalog-select'], "
        "select[name='catalog'], "
        ".catalog-selector"
    )
    CATALOG_DROPDOWN_TRIGGER = (
        "[data-testid='catalog-dropdown'], "
        "button:near(:text('Catalog')), "
        ".catalog-select__control, "
        "div[role='combobox']:near(:text('Catalog'))"
    )

    DATABASE_SELECT = (
        "[data-testid='database-select'], "
        "select[name='database'], "
        ".database-selector"
    )

    # ------------------------------------------------------------------
    # Run / execute buttons
    # ------------------------------------------------------------------
    RUN_BUTTON = (
        "button:has-text('Run'), "
        "button:has-text('Execute'), "
        "button[aria-label='Run query'], "
        "[data-testid='run-query-btn']"
    )
    STOP_BUTTON = (
        "button:has-text('Stop'), "
        "button[aria-label='Stop query'], "
        "[data-testid='stop-query-btn']"
    )

    # ------------------------------------------------------------------
    # Results area
    # ------------------------------------------------------------------
    RESULTS_TABLE = (
        "[data-testid='query-results'], "
        ".query-results table, "
        ".results-table table, "
        "table"
    )
    RESULTS_LOADING_INDICATOR = (
        ".query-loading, "
        "[data-testid='query-loading'], "
        ".loading-spinner:visible"
    )
    ERROR_MESSAGE = (
        "[data-testid='query-error'], "
        ".query-error, "
        ".error-message, "
        "[role='alert']"
    )
    ROW_COUNT_DISPLAY = (
        "[data-testid='row-count'], "
        ".row-count, "
        "span:has-text('rows')"
    )

    def __init__(self, page: Page):
        super().__init__(page)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to_sql_editor(self, base_url: str) -> None:
        self.navigate(f"{base_url}/sql-editor")
        self._wait_for_editor_ready()

    def _wait_for_editor_ready(self) -> None:
        self.wait_for_network_idle()
        editor_selectors = [s.strip() for s in self.EDITOR_CONTAINER.split(",")]
        for sel in editor_selectors:
            if self.is_visible(sel, timeout=15_000):
                logger.info("SQL editor is ready")
                return
        logger.warning("SQL editor container not detected by known selectors")

    # ------------------------------------------------------------------
    # Catalog selection
    # ------------------------------------------------------------------

    def select_catalog(self, catalog_name: str) -> None:
        """Select a catalog from the catalog dropdown."""
        # Try native <select> first
        select_selectors = [s.strip() for s in self.CATALOG_SELECT.split(",")]
        for sel in select_selectors:
            if self.is_visible(sel, timeout=3000):
                loc = self.page.locator(sel).first
                try:
                    loc.select_option(label=catalog_name)
                    logger.info("Selected catalog '%s' via <select>", catalog_name)
                    return
                except Exception:
                    pass

        # Custom dropdown
        trigger_selectors = [s.strip() for s in self.CATALOG_DROPDOWN_TRIGGER.split(",")]
        for sel in trigger_selectors:
            if self.is_visible(sel, timeout=3000):
                self.click(sel)
                option_selectors = [
                    f"[role='option']:has-text('{catalog_name}')",
                    f"li:has-text('{catalog_name}')",
                    f".select__option:has-text('{catalog_name}')",
                    f"[data-testid='catalog-option']:has-text('{catalog_name}')",
                ]
                for opt_sel in option_selectors:
                    if self.is_visible(opt_sel, timeout=5000):
                        self.click(opt_sel)
                        logger.info("Selected catalog '%s'", catalog_name)
                        return

        raise RuntimeError(f"Could not select catalog '{catalog_name}'")

    # ------------------------------------------------------------------
    # Query input
    # ------------------------------------------------------------------

    def set_query(self, sql: str) -> None:
        """
        Clear the editor and type the given SQL.
        Handles both Monaco and CodeMirror editors.
        """
        # Monaco editor: click to focus, then Ctrl+A and type
        monaco_selectors = [
            ".monaco-editor .view-line",
            ".monaco-editor",
        ]
        for sel in monaco_selectors:
            if self.is_visible(sel, timeout=3000):
                self.page.locator(sel).first.click()
                self.page.keyboard.press("Control+a")
                self.page.keyboard.type(sql)
                logger.info("Set query in Monaco editor")
                return

        # CodeMirror editor
        cm_selectors = [".CodeMirror-code", ".CodeMirror"]
        for sel in cm_selectors:
            if self.is_visible(sel, timeout=3000):
                self.page.locator(sel).first.click()
                self.page.keyboard.press("Control+a")
                self.page.keyboard.type(sql)
                logger.info("Set query in CodeMirror editor")
                return

        # Plain textarea fallback
        textarea_selectors = [s.strip() for s in self.EDITOR_TEXTAREA.split(",")]
        for sel in textarea_selectors:
            if self.is_visible(sel, timeout=3000):
                loc = self.page.locator(sel).first
                loc.click()
                loc.press("Control+a")
                loc.type(sql)
                logger.info("Set query in textarea")
                return

        raise RuntimeError("Could not find SQL editor input element")

    def clear_query(self) -> None:
        """Clear the SQL editor."""
        self.set_query("")

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run_query(self) -> None:
        """Click the Run / Execute button."""
        run_selectors = [s.strip() for s in self.RUN_BUTTON.split(",")]
        for sel in run_selectors:
            if self.is_visible(sel, timeout=5000):
                self.click(sel)
                logger.info("Query execution started")
                return
        # Keyboard shortcut fallback (Ctrl+Enter is common)
        self.page.keyboard.press("Control+Enter")
        logger.info("Query executed via Ctrl+Enter")

    def wait_for_results(self, timeout_ms: int = 120_000) -> None:
        """Wait until the query finishes (loading indicator disappears)."""
        # First wait for loading indicator to appear (query started)
        loading_appeared = False
        loading_selectors = [s.strip() for s in self.RESULTS_LOADING_INDICATOR.split(",")]
        for sel in loading_selectors:
            if self.is_visible(sel, timeout=5000):
                loading_appeared = True
                break

        if loading_appeared:
            # Now wait for it to disappear
            for sel in loading_selectors:
                try:
                    self.page.locator(sel).wait_for(state="hidden", timeout=timeout_ms)
                    break
                except PlaywrightTimeoutError:
                    continue

        # Wait for results table or error
        result_selectors = [s.strip() for s in self.RESULTS_TABLE.split(",")]
        error_selectors = [s.strip() for s in self.ERROR_MESSAGE.split(",")]
        combined = result_selectors + error_selectors

        deadline = timeout_ms / 1000
        import time
        start = time.time()
        while time.time() - start < deadline:
            for sel in combined:
                if self.is_visible(sel, timeout=2000):
                    logger.info("Query results/error appeared")
                    return
            time.sleep(1)

    def run_and_wait(self, timeout_ms: int = 120_000) -> None:
        """Run the query and wait for results."""
        self.run_query()
        self.wait_for_results(timeout_ms)

    # ------------------------------------------------------------------
    # Results reading
    # ------------------------------------------------------------------

    def get_result_row_count(self) -> int:
        """Return the number of data rows in the results table."""
        table_selectors = [s.strip() for s in self.RESULTS_TABLE.split(",")]
        for sel in table_selectors:
            rows = self.page.locator(f"{sel} tbody tr")
            count = rows.count()
            if count > 0:
                return count
        return 0

    def get_result_column_names(self) -> List[str]:
        """Return column names from the results table header."""
        table_selectors = [s.strip() for s in self.RESULTS_TABLE.split(",")]
        for sel in table_selectors:
            headers = self.page.locator(f"{sel} thead th")
            count = headers.count()
            if count > 0:
                return [(headers.nth(i).inner_text() or "").strip() for i in range(count)]
        return []

    def get_result_cell(self, row: int, col: int) -> str:
        """Return the text content of a result cell (0-based indices)."""
        table_selectors = [s.strip() for s in self.RESULTS_TABLE.split(",")]
        for sel in table_selectors:
            rows = self.page.locator(f"{sel} tbody tr")
            if rows.count() > row:
                cells = rows.nth(row).locator("td")
                if cells.count() > col:
                    return (cells.nth(col).inner_text() or "").strip()
        return ""

    def get_row_count_from_display(self) -> Optional[int]:
        """Parse the row count from the 'X rows' display element."""
        import re
        selectors = [s.strip() for s in self.ROW_COUNT_DISPLAY.split(",")]
        for sel in selectors:
            if self.is_visible(sel, timeout=3000):
                text = self.get_text(sel)
                match = re.search(r"(\d+)", text)
                if match:
                    return int(match.group(1))
        return None

    def has_results(self) -> bool:
        return self.get_result_row_count() > 0

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    def get_error_message(self) -> str:
        """Return any visible error message, empty string if none."""
        selectors = [s.strip() for s in self.ERROR_MESSAGE.split(",")]
        for sel in selectors:
            if self.is_visible(sel, timeout=3000):
                return self.get_text(sel)
        return ""

    def has_error(self) -> bool:
        return bool(self.get_error_message())

    # ------------------------------------------------------------------
    # Convenience: run query end-to-end
    # ------------------------------------------------------------------

    def execute_query(self, sql: str, catalog: Optional[str] = None) -> None:
        """
        Optionally select a catalog, set the query text, and run it.
        Waits for results.
        """
        if catalog:
            self.select_catalog(catalog)
        self.set_query(sql)
        self.run_and_wait()
