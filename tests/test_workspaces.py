"""
tests/test_workspaces.py
-------------------------
Tests for the Workspaces page — converted from Playwright codegen recording.

Auth: uses pre-injected session cookie (no OTP login needed).
The raw codegen recording is preserved in tests/recorded_raw.py for reference.
"""
import uuid
import logging

import pytest
from playwright.sync_api import Page

from pages.workspaces_page import WorkspacesPage

logger = logging.getLogger(__name__)


@pytest.fixture
def workspaces_page(page: Page) -> WorkspacesPage:
    return WorkspacesPage(page)


@pytest.fixture
def unique_workspace_name() -> str:
    return f"test-ws-{str(uuid.uuid4())[:8]}"


@pytest.mark.smoke
class TestWorkspacesPage:

    def test_workspaces_page_loads(self, workspaces_page: WorkspacesPage):
        """Workspaces page must load without errors."""
        workspaces_page.navigate()
        workspaces_page.page.wait_for_selector("text=Workspaces")

    def test_workspaces_list_is_visible(self, workspaces_page: WorkspacesPage):
        """Workspace table must be visible with at least one entry."""
        workspaces_page.navigate()
        names = workspaces_page.get_all_workspace_names()
        assert len(names) > 0, "Expected at least one workspace in the list"
        logger.info("Found workspaces: %s", names)

    def test_create_button_opens_dialog(self, workspaces_page: WorkspacesPage):
        """Clicking Create should open the workspace type selection dialog."""
        workspaces_page.navigate()
        workspaces_page.page.get_by_role("button", name="Create").click()
        workspaces_page.page.get_by_role("button", name="Serverless Best for teams").wait_for()


@pytest.mark.regression
class TestCreateWorkspace:

    def test_create_serverless_workspace(
        self,
        workspaces_page: WorkspacesPage,
        unique_workspace_name: str,
    ):
        """
        Creating a serverless workspace should show 'Creating' status.
        Converted from codegen recording — original flow ended at Error state
        which is an environment issue (crud workspace had pre-existing errors).
        """
        workspaces_page.navigate()
        workspaces_page.create_serverless_workspace(unique_workspace_name)

        # Workspace should appear with Creating status first
        workspaces_page.page.get_by_text("Creating").wait_for(timeout=15_000)
        logger.info("Workspace '%s' is in Creating state", unique_workspace_name)

    def test_workspace_name_is_required(self, workspaces_page: WorkspacesPage):
        """Submitting with an empty workspace name should not proceed."""
        workspaces_page.navigate()
        workspaces_page.open_create_dialog()
        # Do not fill name — submit directly
        workspaces_page.page.get_by_role("button", name="Create Workspace").click()
        # Dialog should still be open (not dismissed)
        assert workspaces_page.page.get_by_role("button", name="Create Workspace").is_visible()
