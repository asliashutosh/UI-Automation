"""
tests/api/test_credentials_api.py
----------------------------------
API-level tests for storage credentials — no browser required.
These run against the e6data REST API directly.
"""
import pytest

from helpers.e6data_api import E6DataAPIClient


@pytest.mark.api
class TestStorageCredentialsAPI:
    """Health and CRUD checks for the storage credentials API."""

    def test_platform_health(self, api_client: E6DataAPIClient):
        """Platform should return a healthy response."""
        healthy = api_client.health_check()
        assert healthy, "Platform health check failed"

    def test_list_credentials_returns_list(self, api_client: E6DataAPIClient):
        """List endpoint must return a list (possibly empty)."""
        credentials = api_client.list_storage_credentials()
        assert isinstance(credentials, list)

    def test_credential_create_and_delete(
        self,
        api_client: E6DataAPIClient,
        unique_cred_name: str,
        credential_cleanup,
    ):
        """Creating a credential via API should succeed and it should be retrievable."""
        credential_cleanup.register(unique_cred_name)

        cred = api_client.create_storage_credential(
            name=unique_cred_name,
            cloud="aws",
            auth_mode="iam_role",
        )
        assert cred is not None
        assert cred.get("name") == unique_cred_name

        # Verify it appears in the list
        names = [c.get("name") for c in api_client.list_storage_credentials()]
        assert unique_cred_name in names

    def test_list_catalogs_returns_list(self, api_client: E6DataAPIClient):
        """Catalogs list endpoint must return a list."""
        catalogs = api_client.list_catalogs()
        assert isinstance(catalogs, list)
