"""
tests/test_workspace_creation.py
----------------------------------
E2E test: Create a workspace and verify it reaches Running state.

Auth: uses session-scoped `authenticated_context` (OTP login happens once
      in conftest.py before this test runs — user enters the OTP at session start).

Workspace name: session-scoped fixture from tests/conftest.py, shared with
                test_workspace_crud.py so both operate on the same workspace.
"""
import logging

import pytest
from playwright.sync_api import Page

from pages.workspaces_page import WorkspacesPage

logger = logging.getLogger(__name__)

WORKSPACE_TIMEOUT_MS = 600_000  # max wait for Running/Error (10 minutes)


@pytest.mark.e2e
class TestWorkspaceCreation:

    def test_workspace_creation_e2e(self, auth_page: Page, workspace_name: str):
        """
        Create a serverless workspace and assert it reaches Running state.
        """
        workspaces = WorkspacesPage(auth_page)

        # ── Navigate to workspaces ────────────────────────────────────────
        workspaces.navigate()

        # ── Create workspace ──────────────────────────────────────────────
        workspaces.create_serverless_workspace(workspace_name)
        logger.info("Submitted workspace creation: %s", workspace_name)

        # ── Verify Creating state ─────────────────────────────────────────
        workspaces.wait_for_creating_state(workspace_name, timeout=30_000)
        logger.info("Workspace '%s' is in Creating state ✓", workspace_name)

        # ── Poll until Running or Error ───────────────────────────────────
        print(f"\nWaiting for workspace '{workspace_name}' to reach Running or Error…")
        final_status = workspaces.wait_for_running_or_error(
            workspace_name, timeout=WORKSPACE_TIMEOUT_MS
        )

        # ── Assert ────────────────────────────────────────────────────────
        assert final_status == "Running", (
            f"Workspace creation of '{workspace_name}' got failed — "
            f"final status was '{final_status}'"
        )
        logger.info("Workspace '%s' is Running ✓", workspace_name)
