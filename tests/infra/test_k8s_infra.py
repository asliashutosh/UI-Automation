"""
tests/infra/test_k8s_infra.py
------------------------------
Kubernetes infrastructure assertions.
Skipped automatically when K8s is not configured (KUBECONFIG / in-cluster).
"""
import pytest

from helpers.k8s_helper import K8sHelper


@pytest.mark.k8s
@pytest.mark.infra
class TestK8sInfra:
    """Sanity checks for Kubernetes resources used by e6data."""

    def test_target_namespace_exists(self, k8s_helper: K8sHelper):
        """The configured K8s namespace must exist in the cluster."""
        from config.settings import config
        exists = k8s_helper.namespace_exists(config.k8s_namespace)
        assert exists, f"Namespace '{config.k8s_namespace}' does not exist in the cluster"

    def test_engine_deployment_is_ready(self, k8s_helper: K8sHelper):
        """e6data engine deployment must have all replicas ready."""
        from config.settings import config
        ready = k8s_helper.wait_for_deployment_ready(
            name=config.k8s_engine_deployment,
            namespace=config.k8s_namespace,
            timeout=60,
        )
        assert ready, (
            f"Deployment '{config.k8s_engine_deployment}' in namespace "
            f"'{config.k8s_namespace}' is not fully ready"
        )

    def test_engine_pods_are_running(self, k8s_helper: K8sHelper):
        """All pods for the engine deployment must be in Running phase."""
        from config.settings import config
        pods = k8s_helper.list_pods(
            namespace=config.k8s_namespace,
            label_selector=f"app={config.k8s_engine_deployment}",
        )
        assert pods, f"No pods found for label app={config.k8s_engine_deployment}"
        non_running = [p.metadata.name for p in pods if p.status.phase != "Running"]
        assert not non_running, f"These pods are not Running: {non_running}"
