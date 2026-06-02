"""
tests/test_workspace_crud.py
-----------------------------
Full CRUD lifecycle tests for a Serverless workspace.

Tests run in order within the session:
  1. test_create_workspace   → Create  and verify Running
  2. test_disable_and_enable → Disable and Enable transitions
  3. test_delete_workspace   → Delete  and verify gone
"""
import logging

import pytest
from playwright.sync_api import Page

from pages.workspaces_page import WorkspacesPage

logger = logging.getLogger(__name__)

CREATE_TIMEOUT_MS  = 600_000   # 10 min — workspace creation can be slow
DISABLE_TIMEOUT_MS = 300_000   # 5 min
ENABLE_TIMEOUT_MS  = 300_000   # 5 min
DELETE_TIMEOUT_MS  = 180_000   # 3 min


@pytest.mark.e2e
class TestWorkspaceCRUD:

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------

    def test_create_workspace(self, auth_page: Page, workspace_name: str):
        """
        Create a new Serverless workspace and verify it reaches Running state.
        Fails with a clear message if it ends up in Error state.
        """
        ws = WorkspacesPage(auth_page)
        ws.navigate()

        ws.create_serverless_workspace(workspace_name)
        logger.info("Submitted workspace creation: %s", workspace_name)

        ws.wait_for_creating_state(workspace_name, timeout=60_000)
        logger.info("Workspace '%s' is in Creating state ✓", workspace_name)

        final_status = ws.wait_for_running_or_error(
            workspace_name, timeout=CREATE_TIMEOUT_MS
        )

        assert final_status == "Running", (
            f"Workspace creation of '{workspace_name}' failed — "
            f"final status was '{final_status}'"
        )
        logger.info("Workspace '%s' is Running ✓", workspace_name)

    # ------------------------------------------------------------------
    # DISABLE / ENABLE
    # ------------------------------------------------------------------

    def test_disable_and_enable(self, auth_page: Page, workspace_name: str):
        """
        Check current workspace state then run both transitions.

        Starting state  │ Sequence
        ────────────────┼──────────────────────────────────────────
        Running         │ Disable → Disabled → Enable → Running
        Disabled        │ Enable  → Running  → Disable → Disabled
        """
        ws = WorkspacesPage(auth_page)
        ws.navigate()

        current = ws.get_workspace_status(workspace_name)
        logger.info("Workspace '%s' current status: %s", workspace_name, current)

        if current == "Running":
            # Disable
            ws.disable_workspace(workspace_name)
            ws.wait_for_disabling_state(workspace_name)
            result = ws.wait_for_status(workspace_name, "Disabled", timeout=DISABLE_TIMEOUT_MS)
            assert result == "Disabled", (
                f"Workspace '{workspace_name}' did not reach Disabled — got '{result}'"
            )
            logger.info("Disable: PASSED ✓")

            # Enable
            ws.enable_workspace(workspace_name)
            ws.wait_for_enabling_state(workspace_name)
            result = ws.wait_for_status(workspace_name, "Running", timeout=ENABLE_TIMEOUT_MS)
            assert result == "Running", (
                f"Workspace '{workspace_name}' did not reach Running — got '{result}'"
            )
            logger.info("Enable: PASSED ✓")

        elif current == "Disabled":
            # Enable
            ws.enable_workspace(workspace_name)
            ws.wait_for_enabling_state(workspace_name)
            result = ws.wait_for_status(workspace_name, "Running", timeout=ENABLE_TIMEOUT_MS)
            assert result == "Running", (
                f"Workspace '{workspace_name}' did not reach Running — got '{result}'"
            )
            logger.info("Enable: PASSED ✓")

            # Disable
            ws.disable_workspace(workspace_name)
            ws.wait_for_disabling_state(workspace_name)
            result = ws.wait_for_status(workspace_name, "Disabled", timeout=DISABLE_TIMEOUT_MS)
            assert result == "Disabled", (
                f"Workspace '{workspace_name}' did not reach Disabled — got '{result}'"
            )
            logger.info("Disable: PASSED ✓")

        else:
            pytest.fail(
                f"Workspace '{workspace_name}' is in unexpected state: '{current}'. "
                f"Expected 'Running' or 'Disabled'."
            )

    # ------------------------------------------------------------------
    # DELETE
    # ------------------------------------------------------------------

    def test_delete_workspace(self, auth_page: Page, workspace_name: str):
        """
        Delete the workspace and verify it no longer appears in the list.
        """
        ws = WorkspacesPage(auth_page)
        ws.navigate()

        assert ws.workspace_exists(workspace_name), (
            f"Cannot delete: workspace '{workspace_name}' not found in the list"
        )

        ws.delete_workspace(workspace_name)
        ws.wait_for_deleting_state(workspace_name)
        ws.wait_for_workspace_deleted(workspace_name, timeout=DELETE_TIMEOUT_MS)

        assert not ws.workspace_exists(workspace_name), (
            f"Workspace '{workspace_name}' still appears in the list after deletion"
        )
        logger.info("Workspace '%s' deleted successfully ✓", workspace_name)
