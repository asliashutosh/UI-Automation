"""
tests/test_storage_credentials.py
-----------------------------------
Storage Credential CRUD tests — runs against an existing Running workspace.

Full flow:
  1. Open the workspace (new browser tab)
  2. Use the federation API to get Engine Role ARN, External ID, VPCE
  3. Settings → Storage Credentials → New Credential
  4. Fill name, click Launch Setup (new popup tab)
  5. Fill wizard: S3 bucket, Glue, stack name, ARN, External ID, VPCE
  6. Continue → AWS CLI → Download setup script
  7. Run script locally → extract created Role ARN
  8. Back in credential dialog → fill Role ARN → Create
  9. Verify credential appears in the list
 10. Cleanup — delete the credential

Run order (must follow workspace creation):
  pytest tests/test_workspace_crud.py::TestWorkspaceCRUD::test_create_workspace
         tests/test_storage_credentials.py
         tests/test_workspace_crud.py::TestWorkspaceCRUD::test_disable_and_enable
         tests/test_workspace_crud.py::TestWorkspaceCRUD::test_delete_workspace
"""
import logging
import uuid
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Page

from config.settings import config
from helpers.e6data_api import E6DataAPIClient
from helpers.shell_helper import run_setup_script
from pages.credential_setup_wizard_page import CredentialSetupWizardPage
from pages.workspace_settings_page import WorkspaceSettingsPage
from pages.workspaces_page import WorkspacesPage

logger = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def credential_name() -> str:
    """Unique credential name for this test run."""
    name = f"auto-cred-{uuid.uuid4().hex[:8]}"
    logger.info("Credential under test: %s", name)
    return name


@pytest.fixture(scope="module")
def stack_name() -> str:
    """Unique CloudFormation stack name for the setup wizard."""
    return f"auto-stack-{uuid.uuid4().hex[:8]}"


@pytest.mark.e2e
class TestStorageCredentials:

    def test_create_storage_credential(
        self,
        auth_page: Page,
        workspace_name: str,
        credential_name: str,
        stack_name: str,
    ):
        """
        Full E2E: open workspace → new credential → setup wizard →
        run script → paste Role ARN → create credential.
        """

        # ── Step 1: Open workspace in a new tab ──────────────────────────
        ws = WorkspacesPage(auth_page)
        ws.navigate()
        workspace_page = ws.open_workspace(workspace_name)

        # ── Step 2: Fetch federation details via API ──────────────────────
        parsed = urlparse(workspace_page.url)
        workspace_base_url = f"{parsed.scheme}://{parsed.netloc}"
        logger.info("Workspace URL: %s", workspace_base_url)

        workspace_api = E6DataAPIClient(
            base_url=workspace_base_url,
            session_cookie=config.session_cookie,
        )
        # Federation API uses camelCase field names
        federation = workspace_api.get_federation_details()
        engine_role_arn = federation.get("engineRoleArn") or config.test_engine_role_arn
        vpce            = federation.get("s3GatewayEndpointId") or config.test_vpce
        logger.info("Engine Role ARN : %s", engine_role_arn)
        logger.info("VPCE            : %s", vpce)

        # ── Step 3: Settings → Storage Credentials → New Credential ──────
        settings = WorkspaceSettingsPage(workspace_page)
        settings.navigate_to_storage_credentials()
        settings.click_new_credential()
        settings.fill_credential_name(credential_name)

        # ── Step 4: Read External ID from the credential dialog UI ────────
        # External ID is generated server-side and shown in the dialog —
        # it is NOT in the federation API response.
        external_id = settings.get_external_id()
        logger.info("External ID     : %s", external_id)

        # ── Step 5: Launch Setup → wizard popup ───────────────────────────
        wizard_page = settings.launch_setup()
        wizard = CredentialSetupWizardPage(wizard_page)

        # ── Step 6: Fill the setup wizard ─────────────────────────────────
        wizard.fill_s3_bucket(config.test_bucket)
        wizard.click_add_bucket()
        wizard.enable_glue_catalog()
        wizard.fill_stack_name(stack_name)
        wizard.fill_engine_role_arn(engine_role_arn)
        wizard.fill_external_id(external_id)
        wizard.fill_vpce(vpce)
        wizard.click_continue_to_setup()

        # ── Step 6: AWS CLI → Download script ────────────────────────────
        wizard.select_aws_cli()
        script_path = wizard.download_setup_script()
        logger.info("Script downloaded: %s", script_path)

        # ── Step 7: Run script → extract Role ARN ─────────────────────────
        role_arn = run_setup_script(script_path)
        logger.info("Created Role ARN: %s", role_arn)

        # ── Step 8: Back in credential dialog → fill ARN → Create ─────────
        settings.fill_role_arn(role_arn)
        settings.click_create_credential()

        # ── Step 9: Verify credential appears in the list ─────────────────
        assert settings.credential_exists(credential_name), (
            f"Credential '{credential_name}' was not found in the list after creation"
        )
        logger.info("Storage credential '%s' created ✓", credential_name)

    def test_delete_storage_credential(
        self,
        auth_page: Page,
        workspace_name: str,
        credential_name: str,
    ):
        """
        Delete the storage credential created in the previous test
        and verify it no longer appears in the list.
        """
        ws = WorkspacesPage(auth_page)
        ws.navigate()
        workspace_page = ws.open_workspace(workspace_name)

        settings = WorkspaceSettingsPage(workspace_page)
        settings.navigate_to_storage_credentials()

        assert settings.credential_exists(credential_name), (
            f"Cannot delete: credential '{credential_name}' not found"
        )

        settings.delete_credential(credential_name)

        assert not settings.credential_exists(credential_name), (
            f"Credential '{credential_name}' still appears after deletion"
        )
        logger.info("Storage credential '%s' deleted ✓", credential_name)
