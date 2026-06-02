"""
tests/test_workspace_crud.py
-----------------------------
Workspace operation tests — disable and enable.

The workspace is created and deleted automatically by the session fixture
in tests/conftest.py. These tests focus purely on the operations.
"""
import logging

import pytest
from playwright.sync_api import Page

from pages.workspaces_page import WorkspacesPage

logger = logging.getLogger(__name__)

DISABLE_TIMEOUT_MS = 300_000   # 5 min
ENABLE_TIMEOUT_MS  = 300_000   # 5 min


@pytest.mark.e2e
class TestWorkspaceCRUD:

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
