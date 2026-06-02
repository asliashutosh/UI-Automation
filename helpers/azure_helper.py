"""
helpers/azure_helper.py
-----------------------
Thin wrapper around the Azure SDK for test utilities.
Uses DefaultAzureCredential so it works with:
  - Environment variables (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID)
  - Azure CLI login (`az login`)
  - Managed Identity (when running in Azure)
"""
import logging
from typing import Dict, List, Optional

from azure.identity import DefaultAzureCredential, ClientSecretCredential
from azure.mgmt.containerservice import ContainerServiceClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)


class AzureHelper:
    """
    Utility class for interacting with Azure resources in tests.
    """

    def __init__(
        self,
        subscription_id: str,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self.subscription_id = subscription_id
        self._credential = self._build_credential(tenant_id, client_id, client_secret)

        self._resource_client = ResourceManagementClient(self._credential, subscription_id)
        self._storage_client = StorageManagementClient(self._credential, subscription_id)
        self._aks_client = ContainerServiceClient(self._credential, subscription_id)

    # ------------------------------------------------------------------
    # Credential
    # ------------------------------------------------------------------

    def _build_credential(
        self,
        tenant_id: Optional[str],
        client_id: Optional[str],
        client_secret: Optional[str],
    ):
        if tenant_id and client_id and client_secret:
            logger.info("AzureHelper: using service principal credential")
            return ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )
        logger.info("AzureHelper: using DefaultAzureCredential (env / CLI / managed identity)")
        return DefaultAzureCredential()

    # ------------------------------------------------------------------
    # Resource Groups
    # ------------------------------------------------------------------

    def resource_group_exists(self, name: str) -> bool:
        return self._resource_client.resource_groups.check_existence(name)

    def list_resource_groups(self) -> List[str]:
        return [rg.name for rg in self._resource_client.resource_groups.list()]

    def get_resource_group(self, name: str):
        return self._resource_client.resource_groups.get(name)

    # ------------------------------------------------------------------
    # Storage Accounts
    # ------------------------------------------------------------------

    def list_storage_accounts(self, resource_group: str) -> List[str]:
        """Return storage account names in a resource group."""
        accounts = self._storage_client.storage_accounts.list_by_resource_group(resource_group)
        return [a.name for a in accounts]

    def storage_account_exists(self, resource_group: str, account_name: str) -> bool:
        try:
            self._storage_client.storage_accounts.get_properties(resource_group, account_name)
            return True
        except ResourceNotFoundError:
            return False

    def get_storage_account_keys(self, resource_group: str, account_name: str) -> Dict[str, str]:
        """Return a dict of key_name -> key_value for a storage account."""
        keys = self._storage_client.storage_accounts.list_keys(resource_group, account_name)
        return {k.key_name: k.value for k in keys.keys}

    def list_blob_containers(self, resource_group: str, account_name: str) -> List[str]:
        containers = self._storage_client.blob_containers.list(resource_group, account_name)
        return [c.name for c in containers]

    # ------------------------------------------------------------------
    # AKS (Azure Kubernetes Service)
    # ------------------------------------------------------------------

    def list_aks_clusters(self, resource_group: str) -> List[str]:
        """Return AKS cluster names in a resource group."""
        clusters = self._aks_client.managed_clusters.list_by_resource_group(resource_group)
        return [c.name for c in clusters]

    def get_aks_cluster(self, resource_group: str, cluster_name: str):
        return self._aks_client.managed_clusters.get(resource_group, cluster_name)

    def get_aks_cluster_state(self, resource_group: str, cluster_name: str) -> str:
        """Return the provisioning state of an AKS cluster (e.g. 'Succeeded', 'Creating')."""
        cluster = self.get_aks_cluster(resource_group, cluster_name)
        return cluster.provisioning_state or "Unknown"

    def aks_cluster_exists(self, resource_group: str, cluster_name: str) -> bool:
        try:
            self.get_aks_cluster(resource_group, cluster_name)
            return True
        except ResourceNotFoundError:
            return False

    def get_aks_node_count(self, resource_group: str, cluster_name: str) -> int:
        """Return total node count across all agent pool profiles."""
        cluster = self.get_aks_cluster(resource_group, cluster_name)
        pools = cluster.agent_pool_profiles or []
        return sum(p.count or 0 for p in pools)

    # ------------------------------------------------------------------
    # Generic resource listing
    # ------------------------------------------------------------------

    def list_resources_in_group(self, resource_group: str) -> List[Dict[str, str]]:
        """Return all resources in a resource group as a list of dicts."""
        resources = self._resource_client.resources.list_by_resource_group(resource_group)
        return [{"name": r.name, "type": r.type, "location": r.location} for r in resources]
