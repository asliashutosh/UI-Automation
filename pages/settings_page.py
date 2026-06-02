"""
SettingsPage
------------
Represents the /settings page, specifically the "Storage Credentials" tab.

Selectors derived from live HTML inspection of e6f12eab8a-ue1a.e6compute.xyz:
  - Settings uses Radix UI tabs (role="tablist" / role="tab")
  - Trust policy section: <section> with <h3>Trust policy setup</h3>
  - Engine Role ARN: <dt> "Engine Role ARN" + following-sibling <dd> > <span title="arn:...">
  - Trust Policy JSON: single <pre> element on the page
  - Credentials table: <table> with <tbody> rows
"""
import json
import logging
import time
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class SettingsPage(BasePage):
    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to_storage_credentials(self, base_url: str) -> None:
        """
        Navigate to /settings and click the Storage Credentials tab.

        Strategy: the e6data SPA shows a skeleton on initial load; the tablist
        only appears after the sidebar Settings link is clicked.  We therefore:
          1. Navigate to /settings (triggers app boot + domcontentloaded)
          2. Wait for the sidebar nav to appear
          3. Click "Settings" in the sidebar (router renders the settings component)
          4. Wait for [role=tablist] (Radix UI tabs)
          5. Click the Storage Credentials tab
        """
        self.navigate(f"{base_url}/settings")
        # Wait for sidebar navigation to confirm the app has booted
        self.page.wait_for_selector("nav, aside, [role='navigation'], a:has-text('Settings')",
                                    timeout=30_000)
        # Click "Settings" in the sidebar to ensure the settings component renders
        try:
            settings_link = self.page.get_by_role("link", name="Settings").first
            settings_link.wait_for(state="visible", timeout=5_000)
            settings_link.click()
        except Exception:
            # Fallback: click by text
            self.page.get_by_text("Settings", exact=True).first.click()
        # Now wait for Radix UI tablist
        self.page.wait_for_selector('[role="tablist"]', timeout=20_000)
        self.click_storage_credentials_tab()

    def click_storage_credentials_tab(self) -> None:
        """Click the Storage Credentials tab."""
        tab = self.page.get_by_role("tab", name="Storage Credentials")
        tab.wait_for(state="visible", timeout=10_000)
        tab.click()
        # Wait for Trust policy section to appear (confirms tab rendered)
        try:
            self.page.wait_for_selector(
                "h3:has-text('Trust policy setup'), section:has-text('Trust policy setup')",
                timeout=10_000,
            )
        except PlaywrightTimeoutError:
            time.sleep(3)
        logger.info("Clicked Storage Credentials tab")

    def reload(self) -> None:
        """Reload the page (overridden to re-click tab after reload)."""
        super().reload()
        self.page.wait_for_selector('[role="tablist"]', timeout=20_000)

    # ------------------------------------------------------------------
    # Trust Policy section — Engine Role ARN
    # ------------------------------------------------------------------

    def get_engine_role_arn(self) -> str:
        """
        Read the Engine Role ARN value from the Trust Policy Setup section.

        HTML structure (verified):
          <dt class="...">Engine Role ARN</dt>
          <dd class="... font-mono ...">
            <span class="block truncate" title="arn:aws:iam::...">arn:aws:iam::...</span>
          </dd>
        """
        # Primary: XPath from dt → following-sibling dd → span with title attribute
        try:
            dt = self.page.get_by_text("Engine Role ARN", exact=True).first
            dt.wait_for(state="visible", timeout=10_000)
            # Span inside the next dd sibling
            span = dt.locator("xpath=following-sibling::dd[1]//span[contains(@class,'block')]").first
            span.wait_for(state="visible", timeout=5_000)
            # Prefer title attribute (full ARN even if truncated on screen)
            title = span.get_attribute("title") or ""
            if title.startswith("arn:"):
                logger.info("Engine Role ARN (from title): %s", title)
                return title
            text = (span.inner_text() or "").strip()
            if text:
                logger.info("Engine Role ARN (from text): %s", text)
                return text
        except PlaywrightTimeoutError:
            pass

        # Fallback: scan all <span title> attributes for an IAM ARN
        try:
            spans = self.page.locator("span[title^='arn:aws:iam']")
            count = spans.count()
            for i in range(count):
                title = spans.nth(i).get_attribute("title") or ""
                if "role/" in title:
                    logger.info("Engine Role ARN (span scan): %s", title)
                    return title
        except Exception:
            pass

        return ""

    # ------------------------------------------------------------------
    # Trust Policy section — Trust Policy JSON
    # ------------------------------------------------------------------

    def get_trust_policy_json(self) -> dict:
        """
        Read the Trust Policy JSON block and parse it.

        HTML structure (verified):
          <pre class="bg-background ...">{ ... JSON ... }</pre>
        There is exactly one <pre> on this page.
        """
        try:
            pre = self.page.locator("pre").first
            pre.wait_for(state="visible", timeout=10_000)
            raw = (pre.inner_text() or "").strip()
            if "{" in raw:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                return json.loads(raw[start:end])
        except (PlaywrightTimeoutError, json.JSONDecodeError) as exc:
            logger.warning("Failed to parse trust policy JSON: %s", exc)
        return {}

    def get_trust_policy_external_id(self) -> str:
        """
        Extract the ExternalId value from the Trust Policy JSON Condition block.
        Returns the raw string (may be a placeholder if PLT-9085 is present).
        """
        policy = self.get_trust_policy_json()
        try:
            statements = policy.get("Statement", [])
            for stmt in statements:
                condition = stmt.get("Condition", {})
                string_equals = condition.get("StringEquals", {})
                ext_id = string_equals.get("sts:ExternalId", "")
                if ext_id:
                    return ext_id
        except (IndexError, AttributeError, TypeError):
            pass
        return ""

    def get_trust_policy_raw_text(self) -> str:
        """Return the raw text of the <pre> element (for placeholder detection)."""
        try:
            pre = self.page.locator("pre").first
            pre.wait_for(state="visible", timeout=10_000)
            return (pre.inner_text() or "").strip()
        except PlaywrightTimeoutError:
            return ""

    # ------------------------------------------------------------------
    # Credentials table
    # ------------------------------------------------------------------

    # Column indices (0-based) in the credentials table
    COL_NAME = 0
    COL_CLOUD = 1
    COL_CONFIGURED = 2
    COL_CONNECTION = 3
    COL_USED_BY = 4
    COL_CREATED = 5
    COL_ACTIONS = 6

    STATUS_PENDING = "Pending"
    STATUS_CONNECTED = "Connected"
    STATUS_FAILED = "Failed"

    def click_new_credential_button(self) -> None:
        """Click the 'New credential' button."""
        btn = self.page.get_by_role("button", name="New credential")
        btn.wait_for(state="visible", timeout=10_000)
        btn.click()
        # Wait for dialog to open
        try:
            self.page.wait_for_selector("[role='dialog']", timeout=10_000)
        except PlaywrightTimeoutError:
            time.sleep(2)

    def get_credentials_table_row_count(self) -> int:
        """Return the number of data rows in the credentials table."""
        return self.page.locator("table tbody tr").count()

    def find_credential_row(self, credential_name: str) -> Optional[object]:
        """Return the row locator for the given credential name, or None."""
        loc = self.page.locator(f"table tbody tr:has-text('{credential_name}')")
        if loc.count() > 0:
            return loc.first
        return None

    def get_credential_connection_status(self, credential_name: str) -> str:
        """Return the CONNECTION column value for the named credential."""
        row = self.find_credential_row(credential_name)
        if row is None:
            raise AssertionError(
                f"Credential '{credential_name}' not found in the credentials table"
            )
        cells = row.locator("td")
        if cells.count() > self.COL_CONNECTION:
            return (cells.nth(self.COL_CONNECTION).inner_text() or "").strip()
        return ""

    def wait_for_credential_status(
        self, credential_name: str, expected_status: str, timeout_ms: int = 60_000
    ) -> str:
        """Poll until the credential's CONNECTION column shows `expected_status`."""
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            self.page.reload(wait_until="domcontentloaded")
            time.sleep(2)
            self.page.wait_for_selector('[role="tablist"]', timeout=15_000)
            self.click_storage_credentials_tab()
            status = self.get_credential_connection_status(credential_name)
            logger.info("Credential '%s' status: %s", credential_name, status)
            if expected_status.lower() in status.lower():
                return status
            time.sleep(5)
        raise AssertionError(
            f"Credential '{credential_name}' did not reach status '{expected_status}' "
            f"within {timeout_ms}ms."
        )

    def click_credential_actions(self, credential_name: str) -> None:
        """Open the actions menu (⋯ button) for the named credential."""
        row = self.find_credential_row(credential_name)
        if row is None:
            raise AssertionError(f"Credential '{credential_name}' not found")
        # Last cell typically has the actions button
        row.locator("td").last.click()

    def delete_credential(self, credential_name: str) -> None:
        """Delete a credential via the actions menu → Delete option."""
        self.click_credential_actions(credential_name)
        for sel in ["text=Delete", "button:has-text('Delete')", "[role='menuitem']:has-text('Delete')"]:
            if self.is_visible(sel, timeout=3000):
                self.page.locator(sel).first.click()
                break
        # Confirm
        for sel in ["button:has-text('Confirm')", "button:has-text('Yes')", "button:has-text('Delete')"]:
            if self.is_visible(sel, timeout=5000):
                self.page.locator(sel).first.click()
                break
        time.sleep(2)
        logger.info("Deleted credential: %s", credential_name)

    def get_credential_names(self) -> list:
        """Return all credential names visible in the table."""
        rows = self.page.locator("table tbody tr")
        count = rows.count()
        names = []
        for i in range(count):
            cells = rows.nth(i).locator("td")
            if cells.count() > 0:
                names.append((cells.nth(self.COL_NAME).inner_text() or "").strip())
        return names
