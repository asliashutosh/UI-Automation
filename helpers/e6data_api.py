"""
E6DataAPIClient
---------------
Lightweight REST client for the e6data platform API (used for setup/teardown
in tests, independent of browser automation).

Key operations:
  - list_storage_credentials()
  - get_storage_credential(name_or_id)
  - create_storage_credential(payload)
  - update_storage_credential(credential_id, payload)
  - delete_storage_credential(credential_id)
  - get_credential_status(credential_id)
  - list_catalogs()
  - delete_catalog(catalog_id)
"""
import logging
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# Default timeout for all HTTP calls
HTTP_TIMEOUT = 30  # seconds


class E6DataAPIClient:
    def __init__(self, base_url: str, session_cookie: str):
        """
        Initialize the client.

        :param base_url: e.g. https://e6f12eab8a-ue1a.e6compute.xyz
        :param session_cookie: JWT value for the e6_session cookie
        """
        self._base_url = base_url.rstrip("/")
        self._session_cookie = session_cookie
        self._session = requests.Session()
        self._session.cookies.set("e6_session", session_cookie, domain=self._extract_domain(base_url))
        self._session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    # ------------------------------------------------------------------
    # Storage Credentials
    # ------------------------------------------------------------------

    def list_storage_credentials(self) -> List[Dict]:
        """Return a list of all storage credential objects."""
        return self._get("/api/v1/storage-credentials")

    def get_storage_credential_by_name(self, name: str) -> Optional[Dict]:
        """Return the first credential matching `name`, or None."""
        creds = self.list_storage_credentials()
        if isinstance(creds, list):
            for cred in creds:
                if cred.get("name") == name:
                    return cred
        return None

    def get_storage_credential(self, credential_id: str) -> Dict:
        """Return a single credential by ID."""
        return self._get(f"/api/v1/storage-credentials/{credential_id}")

    def create_storage_credential(
        self,
        name: str,
        cloud: str = "AWS",
        description: str = "",
        region: str = "us-east-1",
        role_arn: str = "",
        external_id: str = "",
        extra_fields: Optional[Dict] = None,
    ) -> Dict:
        """
        Create a new storage credential.
        Returns the created credential dict (includes assigned ID and externalId).
        """
        payload: Dict[str, Any] = {
            "name": name,
            "cloud": cloud,
            "description": description,
            "region": region,
        }
        if role_arn:
            payload["roleArn"] = role_arn
        if external_id:
            payload["externalId"] = external_id
        if extra_fields:
            payload.update(extra_fields)

        result = self._post("/api/v1/storage-credentials", payload)
        logger.info("Created credential '%s' — id: %s", name, result.get("id"))
        return result

    def update_storage_credential(self, credential_id: str, payload: Dict) -> Dict:
        """Update a credential by ID. Returns updated credential dict."""
        result = self._put(f"/api/v1/storage-credentials/{credential_id}", payload)
        logger.info("Updated credential %s", credential_id)
        return result

    def patch_storage_credential(self, credential_id: str, payload: Dict) -> Dict:
        """Patch a credential by ID (partial update). Returns updated credential dict."""
        result = self._patch(f"/api/v1/storage-credentials/{credential_id}", payload)
        logger.info("Patched credential %s", credential_id)
        return result

    def delete_storage_credential(self, credential_id: str) -> bool:
        """Delete a credential by ID. Returns True on success."""
        try:
            self._delete(f"/api/v1/storage-credentials/{credential_id}")
            logger.info("Deleted credential %s", credential_id)
            return True
        except requests.HTTPError as exc:
            logger.warning("Failed to delete credential %s: %s", credential_id, exc)
            return False

    def delete_credential_by_name(self, name: str) -> bool:
        """Look up a credential by name and delete it. Returns True if deleted."""
        cred = self.get_storage_credential_by_name(name)
        if cred is None:
            logger.info("Credential '%s' not found — nothing to delete", name)
            return False
        return self.delete_storage_credential(cred["id"])

    def get_credential_status(self, credential_id: str) -> str:
        """
        Return the current connection status of a credential.
        Typically one of: 'Pending', 'Connected', 'Failed'.
        """
        cred = self.get_storage_credential(credential_id)
        return cred.get("connectionStatus") or cred.get("status") or ""

    def wait_for_credential_connected(
        self,
        credential_id: str,
        timeout_seconds: int = 300,
        poll_interval: int = 10,
    ) -> str:
        """
        Poll until the credential's connection status is 'Connected'.
        Returns the final status.
        Raises TimeoutError if timeout exceeded.
        """
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            status = self.get_credential_status(credential_id)
            logger.info("Credential %s status: %s", credential_id, status)
            if "connected" in status.lower():
                return status
            if "failed" in status.lower():
                raise RuntimeError(
                    f"Credential {credential_id} moved to 'Failed' status instead of 'Connected'"
                )
            time.sleep(poll_interval)
        raise TimeoutError(
            f"Credential {credential_id} did not reach 'Connected' within {timeout_seconds}s"
        )

    def get_external_id_for_credential(self, credential_id: str) -> str:
        """Return the externalId for a credential (used for trust policy)."""
        cred = self.get_storage_credential(credential_id)
        return cred.get("externalId") or cred.get("external_id") or ""

    # ------------------------------------------------------------------
    # Catalogs
    # ------------------------------------------------------------------

    def list_catalogs(self) -> List[Dict]:
        """Return a list of all catalog objects."""
        return self._get("/api/v1/catalogs")

    def get_catalog_by_name(self, name: str) -> Optional[Dict]:
        """Return the first catalog matching `name`, or None."""
        cats = self.list_catalogs()
        if isinstance(cats, list):
            for cat in cats:
                if cat.get("name") == name:
                    return cat
        return None

    def delete_catalog(self, catalog_id: str) -> bool:
        """Delete a catalog by ID."""
        try:
            self._delete(f"/api/v1/catalogs/{catalog_id}")
            logger.info("Deleted catalog %s", catalog_id)
            return True
        except requests.HTTPError as exc:
            logger.warning("Failed to delete catalog %s: %s", catalog_id, exc)
            return False

    def delete_catalog_by_name(self, name: str) -> bool:
        """Look up and delete a catalog by name."""
        cat = self.get_catalog_by_name(name)
        if cat is None:
            return False
        return self.delete_catalog(cat["id"])

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """Verify the API is reachable and the session cookie is valid."""
        try:
            self._get("/api/v1/health")
            return True
        except Exception as exc:
            logger.warning("Health check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Private HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, path: str) -> Any:
        url = f"{self._base_url}{path}"
        resp = self._session.get(url, timeout=HTTP_TIMEOUT)
        self._raise_for_status(resp)
        return resp.json()

    def _post(self, path: str, data: Dict) -> Any:
        url = f"{self._base_url}{path}"
        resp = self._session.post(url, json=data, timeout=HTTP_TIMEOUT)
        self._raise_for_status(resp)
        return resp.json()

    def _put(self, path: str, data: Dict) -> Any:
        url = f"{self._base_url}{path}"
        resp = self._session.put(url, json=data, timeout=HTTP_TIMEOUT)
        self._raise_for_status(resp)
        return resp.json()

    def _patch(self, path: str, data: Dict) -> Any:
        url = f"{self._base_url}{path}"
        resp = self._session.patch(url, json=data, timeout=HTTP_TIMEOUT)
        self._raise_for_status(resp)
        return resp.json()

    def _delete(self, path: str) -> None:
        url = f"{self._base_url}{path}"
        resp = self._session.delete(url, timeout=HTTP_TIMEOUT)
        self._raise_for_status(resp)

    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        if not resp.ok:
            logger.error(
                "API error %s %s: %s",
                resp.status_code,
                resp.url,
                resp.text[:500],
            )
            resp.raise_for_status()

    @staticmethod
    def _extract_domain(url: str) -> str:
        """Extract just the hostname from a URL."""
        from urllib.parse import urlparse
        return urlparse(url).hostname or ""
