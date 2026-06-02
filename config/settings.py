"""
Central configuration module.
Loads variables from .env file (or environment) and exposes a typed Config object.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Resolve the .env file relative to this file's parent (playwright-tests/)
_ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_FILE, override=False)


def _require(name: str) -> str:
    """Return the env var value or raise a descriptive error."""
    value = os.getenv(name)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is not set. "
            f"Copy .env.example to .env and fill in the values."
        )
    return value


@dataclass(frozen=True)
class Config:
    # e6data platform
    base_url: str
    session_cookie: str
    user_email: str
    org_name: str

    # AWS
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_session_token: str
    aws_region: str

    # Test parameters
    test_bucket: str
    test_vpce: str
    test_engine_role_arn: str
    test_stack_name: str
    credential_name: str

    # Kubernetes (optional — tests are skipped when not configured)
    k8s_namespace: str
    k8s_engine_deployment: str
    k8s_kubeconfig_path: str  # empty = auto-detect (KUBECONFIG / in-cluster)
    k8s_context: str          # empty = current context

    # Azure (optional — tests are skipped when not configured)
    azure_subscription_id: str
    azure_tenant_id: str
    azure_client_id: str
    azure_client_secret: str
    azure_resource_group: str
    azure_aks_cluster: str
    azure_storage_account: str

    # Derived / computed
    settings_url: str = field(init=False)
    catalogs_url: str = field(init=False)
    sql_editor_url: str = field(init=False)

    def __post_init__(self):
        # dataclass with frozen=True requires object.__setattr__ for post-init assignment
        object.__setattr__(self, "settings_url", f"{self.base_url}/settings")
        object.__setattr__(self, "catalogs_url", f"{self.base_url}/catalogs")
        object.__setattr__(self, "sql_editor_url", f"{self.base_url}/sql-editor")


def load_config() -> Config:
    """Build and return a Config instance from environment variables."""
    return Config(
        base_url=_require("E6DATA_BASE_URL").rstrip("/"),
        session_cookie=_require("E6DATA_SESSION_COOKIE"),
        user_email=_require("E6DATA_USER_EMAIL"),
        org_name=os.getenv("E6DATA_ORG_NAME", "qa-test"),
        aws_access_key_id=_require("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_require("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=os.getenv("AWS_SESSION_TOKEN", ""),
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        test_bucket=_require("TEST_BUCKET"),
        test_vpce=_require("TEST_VPCE"),
        test_engine_role_arn=_require("TEST_ENGINE_ROLE_ARN"),
        test_stack_name=os.getenv("TEST_STACK_NAME", "playwright-auto-test"),
        credential_name=os.getenv("CREDENTIAL_NAME", "playwright-test-cred"),
        # Kubernetes
        k8s_namespace=os.getenv("K8S_NAMESPACE", "default"),
        k8s_engine_deployment=os.getenv("K8S_ENGINE_DEPLOYMENT", "e6data-engine"),
        k8s_kubeconfig_path=os.getenv("K8S_KUBECONFIG_PATH", ""),
        k8s_context=os.getenv("K8S_CONTEXT", ""),
        # Azure
        azure_subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID", ""),
        azure_tenant_id=os.getenv("AZURE_TENANT_ID", ""),
        azure_client_id=os.getenv("AZURE_CLIENT_ID", ""),
        azure_client_secret=os.getenv("AZURE_CLIENT_SECRET", ""),
        azure_resource_group=os.getenv("AZURE_RESOURCE_GROUP", ""),
        azure_aks_cluster=os.getenv("AZURE_AKS_CLUSTER", ""),
        azure_storage_account=os.getenv("AZURE_STORAGE_ACCOUNT", ""),
    )


# Singleton – import this directly where needed
config = load_config()
