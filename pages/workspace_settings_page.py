"""
pages/workspace_settings_page.py
----------------------------------
Page object for the workspace app Settings page.
(Not the control-plane settings — this is inside the workspace itself,
 e.g. https://e659acb63f-ue1a.e6compute.xyz/settings)

Covers: Settings → Storage Credentials tab → create new credential flow.
"""
import logging

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class WorkspaceSettingsPage(BasePage):

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to_storage_credentials(self):
        """Click Settings link then the Storage Credentials tab."""
        self.page.get_by_role("link", name="Settings").click()
        self.page.wait_for_load_state("networkidle")
        self.page.get_by_role("tab", name="Storage Credentials").click()
        self.page.wait_for_load_state("networkidle")
        logger.info("Navigated to Settings → Storage Credentials")

    # ------------------------------------------------------------------
    # New Credential dialog
    # ------------------------------------------------------------------

    def click_new_credential(self):
        """Open the New Credential dialog."""
        self.page.get_by_role("button", name="New credential").click()
        self.page.wait_for_load_state("networkidle")
        logger.info("Opened New Credential dialog")

    def fill_credential_name(self, name: str):
        self.page.get_by_role("textbox", name="Name").click()
        self.page.get_by_role("textbox", name="Name").fill(name)
        logger.info("Filled credential name: %s", name)

    def get_external_id(self) -> str:
        """
        Read the External ID from the credential dialog by clicking the
        first Copy button and reading the clipboard value.
        The External ID is generated server-side when you open the dialog
        — it is NOT available from the federation API.
        """
        # Grant clipboard permissions so we can read what was copied
        self.page.context.grant_permissions(["clipboard-read", "clipboard-write"])
        self.page.get_by_role("button", name="Copy").first.click()
        external_id = self.page.evaluate("navigator.clipboard.readText()")
        logger.info("External ID from dialog: %s", external_id)
        return external_id

    def launch_setup(self):
        """
        Click 'Launch Setup' — opens the setup wizard in a new popup tab.
        Returns the wizard Page.
        """
        with self.page.expect_popup() as popup_info:
            self.page.get_by_role("link", name="Launch Setup").click()
        wizard_page = popup_info.value
        wizard_page.wait_for_load_state("networkidle")
        logger.info("Setup wizard opened at: %s", wizard_page.url)
        return wizard_page

    # ------------------------------------------------------------------
    # After wizard — fill Role ARN and save
    # ------------------------------------------------------------------

    def fill_role_arn(self, role_arn: str):
        """Fill the IAM Role ARN returned by the setup script."""
        # The Role ARN input appears after the wizard completes
        self.page.get_by_role("textbox", name="IAM Role ARN").click()
        self.page.get_by_role("textbox", name="IAM Role ARN").fill(role_arn)
        logger.info("Filled Role ARN: %s", role_arn)

    def click_create_credential(self):
        """Submit the credential form."""
        self.page.get_by_role("button", name="Create").click()
        self.page.wait_for_load_state("networkidle")
        logger.info("Clicked Create credential")

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def credential_exists(self, name: str) -> bool:
        """Check if a credential with the given name appears in the table."""
        return self.page.locator("tr", has_text=name).count() > 0

    def get_credential_status(self, name: str) -> str:
        """Return the connection status of a credential row."""
        row = self.page.locator("tr", has_text=name)
        return row.locator("td").nth(3).inner_text().strip()

    def delete_credential(self, name: str):
        """Delete a credential by name via the actions menu."""
        row = self.page.locator("tr", has_text=name)
        row.get_by_role("button").last.click()
        self.page.get_by_role("menuitem", name="Delete").click()
        self.page.get_by_role("button", name="Delete").click()
        logger.info("Deleted credential '%s'", name)
