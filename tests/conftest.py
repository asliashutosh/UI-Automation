"""
tests/conftest.py
-----------------
Test-scoped fixtures:
  - Unique credential name per test run (to avoid name collisions)
  - AWS helper instance
  - e6data API client instance
  - Automatic credential cleanup after each test
  - Page object factories
"""
import logging
import time
import uuid
from typing import Generator, List, Optional, Iterator

import pytest
from playwright.sync_api import Page

from config.settings import config
from helpers.aws_helper import AWSHelper
from helpers.e6data_api import E6DataAPIClient
from pages.aws_setup_wizard import AWSSetupWizard
from pages.catalogs_page import CatalogsPage
from pages.create_credential_dialog import CreateCredentialDialog
from pages.settings_page import SettingsPage
from pages.sql_editor_page import SQLEditorPage
from pages.workspaces_page import WorkspacesPage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers / clients
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def workspace_name() -> str:
    """
    Session-scoped unique workspace name.
    Shared across test_workspace_creation.py and test_workspace_crud.py
    so both operate on the same workspace within one pytest session.
    """
    name = f"auto-{str(uuid.uuid4())[:8]}"
    logger.info("Session workspace name: %s", name)
    return name


@pytest.fixture(scope="session")
def aws_helper() -> AWSHelper:
    """Session-scoped AWS helper (boto3)."""
    return AWSHelper(
        aws_access_key_id=config.aws_access_key_id,
        aws_secret_access_key=config.aws_secret_access_key,
        aws_session_token=config.aws_session_token,
        region=config.aws_region,
    )


@pytest.fixture(scope="session")
def api_client() -> E6DataAPIClient:
    """Session-scoped e6data API client."""
    return E6DataAPIClient(
        base_url=config.base_url,
        session_cookie=config.session_cookie,
    )


@pytest.fixture(scope="session")
def k8s_helper():
    """
    Session-scoped Kubernetes helper.
    Skips tests automatically when K8s is not configured or reachable.
    """
    from helpers.k8s_helper import K8sHelper
    try:
        helper = K8sHelper(
            kubeconfig_path=config.k8s_kubeconfig_path or None,
            context=config.k8s_context or None,
            namespace=config.k8s_namespace,
        )
        return helper
    except Exception as exc:
        pytest.skip(f"K8s not available: {exc}")


@pytest.fixture(scope="session")
def azure_helper():
    """
    Session-scoped Azure helper.
    Skips tests automatically when Azure subscription ID is not configured.
    """
    if not config.azure_subscription_id:
        pytest.skip("Azure not configured: set AZURE_SUBSCRIPTION_ID in .env")
    from helpers.azure_helper import AzureHelper
    try:
        helper = AzureHelper(
            subscription_id=config.azure_subscription_id,
            tenant_id=config.azure_tenant_id or None,
            client_id=config.azure_client_id or None,
            client_secret=config.azure_client_secret or None,
        )
        return helper
    except Exception as exc:
        pytest.skip(f"Azure auth failed: {exc}")


# ---------------------------------------------------------------------------
# Credential lifecycle
# ---------------------------------------------------------------------------

@pytest.fixture
def unique_cred_name() -> str:
    """
    Generate a unique credential name for this test run.
    Format: playwright-<8-char-uuid>
    """
    short_id = str(uuid.uuid4()).split("-")[0]
    name = f"playwright-{short_id}"
    logger.info("Generated unique credential name: %s", name)
    return name


@pytest.fixture
def credential_cleanup(api_client: E6DataAPIClient):
    """
    Fixture that records credential names created during a test and
    deletes them in teardown regardless of test outcome.

    Usage:
        def test_foo(page, unique_cred_name, credential_cleanup):
            credential_cleanup.register(unique_cred_name)
            ...
    """
    cleanup_helper = _CredentialCleanupHelper(api_client)
    yield cleanup_helper
    cleanup_helper.cleanup()


class _CredentialCleanupHelper:
    def __init__(self, api_client: E6DataAPIClient):
        self._api = api_client
        self._names: List[str] = []
        self._ids: List[str] = []

    def register(self, name: str) -> None:
        """Register a credential name for cleanup."""
        self._names.append(name)

    def register_id(self, credential_id: str) -> None:
        """Register a credential ID for cleanup."""
        self._ids.append(credential_id)

    def cleanup(self) -> None:
        """Delete all registered credentials."""
        for name in self._names:
            try:
                self._api.delete_credential_by_name(name)
                logger.info("Cleanup: deleted credential '%s'", name)
            except Exception as exc:
                logger.warning("Cleanup: could not delete credential '%s': %s", name, exc)
        for cred_id in self._ids:
            try:
                self._api.delete_storage_credential(cred_id)
                logger.info("Cleanup: deleted credential id=%s", cred_id)
            except Exception as exc:
                logger.warning("Cleanup: could not delete credential id=%s: %s", cred_id, exc)


# ---------------------------------------------------------------------------
# Catalog lifecycle
# ---------------------------------------------------------------------------

@pytest.fixture
def unique_catalog_name() -> str:
    """Generate a unique catalog name for this test run."""
    short_id = str(uuid.uuid4()).split("-")[0]
    return f"playwright-catalog-{short_id}"


@pytest.fixture
def catalog_cleanup(api_client: E6DataAPIClient):
    """Fixture that cleans up catalogs created during a test."""
    helper = _CatalogCleanupHelper(api_client)
    yield helper
    helper.cleanup()


class _CatalogCleanupHelper:
    def __init__(self, api_client: E6DataAPIClient):
        self._api = api_client
        self._names: List[str] = []

    def register(self, name: str) -> None:
        self._names.append(name)

    def cleanup(self) -> None:
        for name in self._names:
            try:
                self._api.delete_catalog_by_name(name)
                logger.info("Cleanup: deleted catalog '%s'", name)
            except Exception as exc:
                logger.warning("Cleanup: could not delete catalog '%s': %s", name, exc)


# ---------------------------------------------------------------------------
# CloudFormation lifecycle
# ---------------------------------------------------------------------------

@pytest.fixture
def cf_stack_cleanup(aws_helper: AWSHelper):
    """Fixture that deletes CF stacks registered during a test."""
    helper = _CFStackCleanupHelper(aws_helper)
    yield helper
    helper.cleanup()


class _CFStackCleanupHelper:
    def __init__(self, aws_helper: AWSHelper):
        self._aws = aws_helper
        self._stack_names: List[str] = []

    def register(self, stack_name: str) -> None:
        self._stack_names.append(stack_name)

    def cleanup(self) -> None:
        for stack_name in self._stack_names:
            try:
                self._aws.delete_cf_stack(stack_name, wait=False)
                logger.info("Cleanup: initiated deletion of CF stack '%s'", stack_name)
            except Exception as exc:
                logger.warning("Cleanup: could not delete CF stack '%s': %s", stack_name, exc)


# ---------------------------------------------------------------------------
# Page object factories
# ---------------------------------------------------------------------------

@pytest.fixture
def settings_page(page: Page) -> SettingsPage:
    return SettingsPage(page)


@pytest.fixture
def create_credential_dialog(page: Page) -> CreateCredentialDialog:
    return CreateCredentialDialog(page)


@pytest.fixture
def aws_setup_wizard_page(page: Page) -> AWSSetupWizard:
    return AWSSetupWizard(page)


@pytest.fixture
def catalogs_page(page: Page) -> CatalogsPage:
    return CatalogsPage(page)


@pytest.fixture
def sql_editor_page(page: Page) -> SQLEditorPage:
    return SQLEditorPage(page)


@pytest.fixture
def workspaces_page(page: Page) -> WorkspacesPage:
    return WorkspacesPage(page)
