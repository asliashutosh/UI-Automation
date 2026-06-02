"""
helpers/k8s_helper.py
---------------------
Thin wrapper around the kubernetes Python client.
Supports both local kubeconfig and in-cluster auth automatically.
"""
import logging
import time
from typing import Dict, List, Optional

from kubernetes import client, config as k8s_config
from kubernetes.client.exceptions import ApiException

logger = logging.getLogger(__name__)


class K8sHelper:
    """
    Utility class for interacting with Kubernetes resources in tests.

    Authentication priority:
    1. Explicit kubeconfig_path if provided
    2. KUBECONFIG env var / ~/.kube/config (local dev)
    3. In-cluster service account (when running inside a pod)
    """

    def __init__(
        self,
        kubeconfig_path: Optional[str] = None,
        context: Optional[str] = None,
        namespace: str = "default",
    ):
        self.namespace = namespace
        self._load_config(kubeconfig_path, context)
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.batch_v1 = client.BatchV1Api()

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def _load_config(self, kubeconfig_path: Optional[str], context: Optional[str]) -> None:
        try:
            k8s_config.load_incluster_config()
            logger.info("K8sHelper: using in-cluster config")
        except k8s_config.ConfigException:
            k8s_config.load_kube_config(config_file=kubeconfig_path, context=context)
            logger.info("K8sHelper: using kubeconfig (context=%s)", context or "current")

    # ------------------------------------------------------------------
    # Pods
    # ------------------------------------------------------------------

    def list_pods(self, namespace: Optional[str] = None, label_selector: str = "") -> List[client.V1Pod]:
        """Return all pods in a namespace, optionally filtered by label selector."""
        ns = namespace or self.namespace
        resp = self.core_v1.list_namespaced_pod(namespace=ns, label_selector=label_selector)
        return resp.items

    def get_pod(self, name: str, namespace: Optional[str] = None) -> client.V1Pod:
        """Return a single pod by name."""
        ns = namespace or self.namespace
        return self.core_v1.read_namespaced_pod(name=name, namespace=ns)

    def get_pod_phase(self, name: str, namespace: Optional[str] = None) -> str:
        """Return the phase of a pod (Pending, Running, Succeeded, Failed, Unknown)."""
        pod = self.get_pod(name, namespace)
        return pod.status.phase or "Unknown"

    def wait_for_pod_running(
        self, name: str, namespace: Optional[str] = None, timeout: int = 120, poll_interval: int = 5
    ) -> bool:
        """Poll until pod is Running or timeout expires. Returns True if reached Running."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            phase = self.get_pod_phase(name, namespace)
            if phase == "Running":
                return True
            if phase in ("Failed", "Unknown"):
                logger.warning("Pod %s entered terminal phase: %s", name, phase)
                return False
            logger.debug("Pod %s phase=%s, waiting…", name, phase)
            time.sleep(poll_interval)
        logger.warning("Timed out waiting for pod %s to be Running", name)
        return False

    def get_pod_logs(self, name: str, namespace: Optional[str] = None, tail_lines: int = 100) -> str:
        """Return the last N lines of logs from a pod."""
        ns = namespace or self.namespace
        return self.core_v1.read_namespaced_pod_log(
            name=name, namespace=ns, tail_lines=tail_lines
        )

    # ------------------------------------------------------------------
    # Deployments
    # ------------------------------------------------------------------

    def list_deployments(self, namespace: Optional[str] = None) -> List[client.V1Deployment]:
        ns = namespace or self.namespace
        return self.apps_v1.list_namespaced_deployment(namespace=ns).items

    def get_deployment(self, name: str, namespace: Optional[str] = None) -> client.V1Deployment:
        ns = namespace or self.namespace
        return self.apps_v1.read_namespaced_deployment(name=name, namespace=ns)

    def get_deployment_ready_replicas(self, name: str, namespace: Optional[str] = None) -> int:
        """Return the number of ready replicas for a deployment."""
        dep = self.get_deployment(name, namespace)
        return dep.status.ready_replicas or 0

    def wait_for_deployment_ready(
        self, name: str, namespace: Optional[str] = None, timeout: int = 300, poll_interval: int = 10
    ) -> bool:
        """Poll until all desired replicas are ready."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            dep = self.get_deployment(name, namespace)
            desired = dep.spec.replicas or 0
            ready = dep.status.ready_replicas or 0
            if desired > 0 and ready >= desired:
                logger.info("Deployment %s is ready (%d/%d)", name, ready, desired)
                return True
            logger.debug("Deployment %s ready=%d/%d, waiting…", name, ready, desired)
            time.sleep(poll_interval)
        return False

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    def list_services(self, namespace: Optional[str] = None) -> List[client.V1Service]:
        ns = namespace or self.namespace
        return self.core_v1.list_namespaced_service(namespace=ns).items

    def get_service(self, name: str, namespace: Optional[str] = None) -> client.V1Service:
        ns = namespace or self.namespace
        return self.core_v1.read_namespaced_service(name=name, namespace=ns)

    # ------------------------------------------------------------------
    # ConfigMaps & Secrets
    # ------------------------------------------------------------------

    def get_configmap(self, name: str, namespace: Optional[str] = None) -> Dict[str, str]:
        """Return the data dict of a ConfigMap."""
        ns = namespace or self.namespace
        cm = self.core_v1.read_namespaced_config_map(name=name, namespace=ns)
        return cm.data or {}

    def get_secret_data(self, name: str, namespace: Optional[str] = None) -> Dict[str, bytes]:
        """Return the decoded data of a Secret (values are base64-decoded bytes)."""
        import base64
        ns = namespace or self.namespace
        secret = self.core_v1.read_namespaced_secret(name=name, namespace=ns)
        return {k: base64.b64decode(v) for k, v in (secret.data or {}).items()}

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    def get_job(self, name: str, namespace: Optional[str] = None) -> client.V1Job:
        ns = namespace or self.namespace
        return self.batch_v1.read_namespaced_job(name=name, namespace=ns)

    def is_job_complete(self, name: str, namespace: Optional[str] = None) -> bool:
        job = self.get_job(name, namespace)
        conditions = job.status.conditions or []
        return any(c.type == "Complete" and c.status == "True" for c in conditions)

    def is_job_failed(self, name: str, namespace: Optional[str] = None) -> bool:
        job = self.get_job(name, namespace)
        conditions = job.status.conditions or []
        return any(c.type == "Failed" and c.status == "True" for c in conditions)

    # ------------------------------------------------------------------
    # Namespace helpers
    # ------------------------------------------------------------------

    def namespace_exists(self, name: str) -> bool:
        try:
            self.core_v1.read_namespace(name=name)
            return True
        except ApiException as exc:
            if exc.status == 404:
                return False
            raise

    def list_namespaces(self) -> List[str]:
        return [ns.metadata.name for ns in self.core_v1.list_namespace().items]
