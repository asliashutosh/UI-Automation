"""
pages/workspaces_page.py
-------------------------
Page object for the Workspaces page (/workspaces).
Covers full CRUD: create, disable, enable, delete, and status polling.
"""
import logging
import time

from pages.base_page import BasePage

logger = logging.getLogger(__name__)

# States that end a transition (no more polling needed)
TERMINAL_STATES = {"Running", "Error", "Failed", "Disabled"}


class WorkspacesPage(BasePage):

    def navigate(self):
        self.page.goto("/workspaces")
        self.page.wait_for_load_state("networkidle")
        logger.info("Navigated to /workspaces")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reload_and_wait(self):
        """Reload the page and wait for it to settle — used by pollers."""
        self.page.reload()
        self.page.wait_for_load_state("networkidle")

    # ------------------------------------------------------------------
    # Row helpers
    # ------------------------------------------------------------------

    def get_workspace_row(self, name: str):
        return self.page.locator("tr", has_text=name)

    def get_workspace_status(self, name: str) -> str:
        """Return the current status text for a workspace row."""
        row = self.get_workspace_row(name)
        status_cell = row.locator("td").nth(1)
        return status_cell.inner_text().strip()

    def open_workspace(self, name: str):
        """
        Click the Open button on the workspace row.
        Returns the new popup Page (workspace app tab).
        """
        row = self.get_workspace_row(name)
        with self.page.expect_popup() as popup_info:
            row.get_by_role("button", name="Open", exact=True).click()
        workspace_page = popup_info.value
        # Use "load" not "networkidle" — workspace app has continuous background
        # polling/WebSocket traffic so networkidle never fires
        workspace_page.wait_for_load_state("load")
        workspace_page.wait_for_timeout(2_000)  # brief settle time
        logger.info("Opened workspace '%s' → %s", name, workspace_page.url)
        return workspace_page

    def workspace_exists(self, name: str) -> bool:
        return self.page.locator("tr", has_text=name).count() > 0

    def get_all_workspace_names(self) -> list[str]:
        cells = self.page.locator("table tbody tr td:first-child")
        return [cells.nth(i).inner_text().strip() for i in range(cells.count())]

    # ------------------------------------------------------------------
    # Status polling (generic)
    # ------------------------------------------------------------------

    def wait_for_status(
        self,
        name: str,
        expected: str,
        timeout: int = 300_000,
        poll_interval: int = 30_000,
    ) -> str:
        """
        Wait poll_interval ms, then reload and check status.
        Repeats until `expected` is reached or timeout expires.

        poll_interval defaults to 30s — long enough to not spam reloads
        but short enough to catch transitions promptly.
        """
        deadline = time.time() + timeout / 1000
        logger.info(
            "Waiting for workspace '%s' → '%s' (timeout=%ds, checking every %ds)…",
            name, expected, timeout // 1000, poll_interval // 1000,
        )
        while time.time() < deadline:
            # Wait first, then reload — avoids reloading before the
            # server has had a chance to process the state change
            self.page.wait_for_timeout(poll_interval)
            self._reload_and_wait()
            status = self.get_workspace_status(name)
            logger.info("Workspace '%s' status: %s", name, status)
            if status == expected:
                return status

        current = self.get_workspace_status(name)
        raise TimeoutError(
            f"Workspace '{name}' did not reach '{expected}' within {timeout // 1000}s. "
            f"Current status: '{current}'"
        )

    def wait_for_running_or_error(
        self,
        name: str,
        timeout: int = 600_000,
        poll_interval: int = 30_000,
    ) -> str:
        """
        Poll until Running or Error. Returns whichever is reached first.
        Waits poll_interval before each reload — workspace creation takes
        several minutes so checking every 30s is plenty.
        """
        deadline = time.time() + timeout / 1000
        logger.info(
            "Waiting for workspace '%s' to reach Running or Error "
            "(timeout=%ds, checking every %ds)…",
            name, timeout // 1000, poll_interval // 1000,
        )
        while time.time() < deadline:
            self.page.wait_for_timeout(poll_interval)
            self._reload_and_wait()
            status = self.get_workspace_status(name)
            logger.info("Workspace '%s' status: %s", name, status)
            if status in ("Running", "Error", "Failed"):
                return status

        raise TimeoutError(
            f"Workspace '{name}' did not reach Running or Error within {timeout // 1000}s."
        )

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def open_create_dialog(self):
        self.page.get_by_role("button", name="Create").click()
        self.page.get_by_role("button", name="Serverless Best for teams").click()
        logger.info("Opened create workspace dialog (Serverless)")

    def fill_workspace_name(self, name: str):
        self.page.get_by_role("textbox", name="Workspace Name").click()
        self.page.get_by_role("textbox", name="Workspace Name").fill(name)
        logger.info("Filled workspace name: %s", name)

    def submit_create(self):
        self.page.get_by_role("button", name="Create Workspace").click()
        logger.info("Clicked Create Workspace")

    def create_serverless_workspace(self, name: str):
        self.open_create_dialog()
        self.fill_workspace_name(name)
        self.submit_create()

    def wait_for_creating_state(self, name: str, timeout: int = 60_000):
        """
        Wait for the workspace row to appear with 'Creating' status.
        After submission we wait 3s for the server to process, then do
        a single reload so the new row is visible in the table.
        """
        self.page.wait_for_timeout(3_000)   # brief pause — let server process
        self._reload_and_wait()
        row = self.get_workspace_row(name)
        row.locator("text=Creating").wait_for(timeout=timeout)
        logger.info("Workspace '%s' is in Creating state", name)

    # ------------------------------------------------------------------
    # Disable
    # ------------------------------------------------------------------

    def disable_workspace(self, name: str):
        """Click the Disable action button for the workspace and confirm."""
        self.page.get_by_role("button", name=f"Disable {name}").click()
        self.page.get_by_role("button", name="Disable").click()
        logger.info("Clicked Disable for workspace '%s'", name)

    def wait_for_disabling_state(self, name: str, timeout: int = 15_000):
        """Status badge updates in-place — no reload needed."""
        row = self.get_workspace_row(name)
        row.locator("text=Disabling").wait_for(timeout=timeout)
        logger.info("Workspace '%s' is Disabling", name)

    # ------------------------------------------------------------------
    # Enable
    # ------------------------------------------------------------------

    def enable_workspace(self, name: str):
        """Click the Enable action button for the workspace and confirm."""
        self.page.get_by_role("button", name=f"Enable {name}").click()
        self.page.get_by_role("button", name="Enable").click()
        logger.info("Clicked Enable for workspace '%s'", name)

    def wait_for_enabling_state(self, name: str, timeout: int = 15_000):
        """Status badge updates in-place — no reload needed."""
        row = self.get_workspace_row(name)
        row.locator("text=Enabling").wait_for(timeout=timeout)
        logger.info("Workspace '%s' is Enabling", name)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_workspace(self, name: str):
        """Open the options menu for the workspace row and click Delete."""
        row = self.get_workspace_row(name)
        row.get_by_role("button").last.click()
        self.page.get_by_role("menuitem", name="Delete").click()
        self.page.get_by_role("button", name="Delete").click()
        logger.info("Clicked Delete for workspace '%s'", name)

    def wait_for_deleting_state(self, name: str, timeout: int = 15_000):
        """Status badge updates in-place — no reload needed."""
        row = self.get_workspace_row(name)
        row.locator("text=Deleting").wait_for(timeout=timeout)
        logger.info("Workspace '%s' is Deleting", name)

    def wait_for_workspace_deleted(
        self, name: str, timeout: int = 180_000, poll_interval: int = 30_000
    ):
        """Poll until the workspace row disappears from the table."""
        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            self.page.wait_for_timeout(poll_interval)
            self._reload_and_wait()
            if not self.workspace_exists(name):
                logger.info("Workspace '%s' has been deleted ✓", name)
                return
        raise TimeoutError(
            f"Workspace '{name}' was not removed from the list within {timeout // 1000}s."
        )
