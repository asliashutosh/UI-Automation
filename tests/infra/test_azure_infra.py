"""
tests/infra/test_azure_infra.py
--------------------------------
Azure infrastructure assertions.
Skipped automatically when Azure credentials are not configured.
"""
import pytest

from helpers.azure_helper import AzureHelper


@pytest.mark.azure
@pytest.mark.infra
class TestAzureInfra:
    """Sanity checks for Azure resources used by e6data."""

    def test_resource_group_exists(self, azure_helper: AzureHelper):
        """The configured Azure resource group must exist."""
        from config.settings import config
        exists = azure_helper.resource_group_exists(config.azure_resource_group)
        assert exists, f"Resource group '{config.azure_resource_group}' not found"

    def test_aks_cluster_exists(self, azure_helper: AzureHelper):
        """The configured AKS cluster must exist in the resource group."""
        from config.settings import config
        exists = azure_helper.aks_cluster_exists(
            resource_group=config.azure_resource_group,
            cluster_name=config.azure_aks_cluster,
        )
        assert exists, (
            f"AKS cluster '{config.azure_aks_cluster}' not found "
            f"in resource group '{config.azure_resource_group}'"
        )

    def test_aks_cluster_is_succeeded(self, azure_helper: AzureHelper):
        """AKS cluster provisioning state must be Succeeded."""
        from config.settings import config
        state = azure_helper.get_aks_cluster_state(
            resource_group=config.azure_resource_group,
            cluster_name=config.azure_aks_cluster,
        )
        assert state == "Succeeded", f"AKS cluster state is '{state}', expected 'Succeeded'"

    def test_storage_account_exists(self, azure_helper: AzureHelper):
        """The configured Azure storage account must exist."""
        from config.settings import config
        exists = azure_helper.storage_account_exists(
            resource_group=config.azure_resource_group,
            account_name=config.azure_storage_account,
        )
        assert exists, (
            f"Storage account '{config.azure_storage_account}' not found "
            f"in resource group '{config.azure_resource_group}'"
        )
