"""
tests/test_workspace_crud.py
-----------------------------
CRUD tests for the workspace created by test_workspace_creation.py.

Auth: uses pre-injected session cookie (no OTP needed here).
Workspace: identified by the session-scoped `workspace_name` fixture from conftest.py.

Run order (within the same pytest session):
  1. test_workspace_creation.py  ← creates the workspace
  2. test_workspace_crud.py      ← disable / enable / delete it

Flow:
  - Check current state (Running or Disabled)
  - If Running  → Disable → verify Disabled → Enable  → verify Running
  - If Disabled → Enable  → verify Running  → Disable → verify Disabled
  - Delete workspace → verify it disappears from the list
"""
import logging

import pytest
from playwright.sync_api import Page

from pages.workspaces_page import WorkspacesPage

logger = logging.getLogger(__name__)

DISABLE_TIMEOUT_MS = 300_000   # 5 min — disable can take a while
ENABLE_TIMEOUT_MS  = 300_000   # 5 min
DELETE_TIMEOUT_MS  = 180_000   # 3 min


@pytest.mark.e2e
class TestWorkspaceCRUD:

    def test_disable_and_enable(self, auth_page: Page, workspace_name: str):
        """
        Check current workspace state and run both disable and enable transitions.

        Starting state  │ Test sequence
        ────────────────┼─────────────────────────────────────────
        Running         │ Disable → Disabled → Enable → Running
        Disabled        │ Enable  → Running  → Disable → Disabled
        """
        ws = WorkspacesPage(auth_page)
        ws.navigate()

        current = ws.get_workspace_status(workspace_name)
        logger.info("Workspace '%s' current status: %s", workspace_name, current)

        if current == "Running":
            # ── Disable ──────────────────────────────────────────────────
            ws.disable_workspace(workspace_name)
            ws.wait_for_disabling_state(workspace_name)

            result = ws.wait_for_status(
                workspace_name, "Disabled", timeout=DISABLE_TIMEOUT_MS
            )
            assert result == "Disabled", (
                f"Workspace '{workspace_name}' did not reach Disabled — got '{result}'"
            )
            logger.info("Disable: PASSED ✓")

            # ── Enable ───────────────────────────────────────────────────
            ws.enable_workspace(workspace_name)
            ws.wait_for_enabling_state(workspace_name)

            result = ws.wait_for_status(
                workspace_name, "Running", timeout=ENABLE_TIMEOUT_MS
            )
            assert result == "Running", (
                f"Workspace '{workspace_name}' did not reach Running after Enable — got '{result}'"
            )
            logger.info("Enable: PASSED ✓")

        elif current == "Disabled":
            # ── Enable ───────────────────────────────────────────────────
            ws.enable_workspace(workspace_name)
            ws.wait_for_enabling_state(workspace_name)

            result = ws.wait_for_status(
                workspace_name, "Running", timeout=ENABLE_TIMEOUT_MS
            )
            assert result == "Running", (
                f"Workspace '{workspace_name}' did not reach Running — got '{result}'"
            )
            logger.info("Enable: PASSED ✓")

            # ── Disable ──────────────────────────────────────────────────
            ws.disable_workspace(workspace_name)
            ws.wait_for_disabling_state(workspace_name)

            result = ws.wait_for_status(
                workspace_name, "Disabled", timeout=DISABLE_TIMEOUT_MS
            )
            assert result == "Disabled", (
                f"Workspace '{workspace_name}' did not reach Disabled — got '{result}'"
            )
            logger.info("Disable: PASSED ✓")

        else:
            pytest.fail(
                f"Workspace '{workspace_name}' is in an unexpected state: '{current}'. "
                f"Expected 'Running' or 'Disabled'."
            )

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
