"""
CreateCredentialDialog
-----------------------
Page object for the "New Storage Credential" modal dialog.

Fields:
  - Name (text input)
  - Description (text input / textarea)
  - Cloud provider (AWS / Azure dropdown or radio)
  - Auth mode (dropdown)
  - Region (text input or dropdown)
  - IAM role ARN (text input)
  - External ID (read-only, auto-generated UUID)

After filling and saving the credential appears in the list with status "Pending".
"""
import logging
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class CreateCredentialDialog(BasePage):
    # ------------------------------------------------------------------
    # Dialog container
    # ------------------------------------------------------------------
    DIALOG = "[role='dialog'], .modal, .ant-modal-content, [data-testid='create-credential-dialog']"

    # ------------------------------------------------------------------
    # Field selectors (inside the dialog)
    # ------------------------------------------------------------------
    NAME_INPUT = (
        "[data-testid='credential-name'], "
        "input[name='name'], "
        "input[placeholder*='name' i], "
        "label:has-text('Name') + * input, "
        "#credential-name"
    )
    DESCRIPTION_INPUT = (
        "[data-testid='credential-description'], "
        "textarea[name='description'], "
        "input[name='description'], "
        "input[placeholder*='description' i], "
        "label:has-text('Description') + * input, "
        "label:has-text('Description') + * textarea"
    )

    # Cloud provider — could be a <select>, radio buttons, or custom cards
    CLOUD_PROVIDER_SELECT = (
        "[data-testid='cloud-provider'], "
        "select[name='cloudProvider'], "
        "select[name='cloud']"
    )
    CLOUD_AWS_OPTION = (
        "[data-value='AWS'], "
        "input[value='AWS'], "
        "[data-testid='cloud-aws'], "
        "label:has-text('AWS')"
    )
    CLOUD_AZURE_OPTION = (
        "[data-value='Azure'], "
        "input[value='Azure'], "
        "[data-testid='cloud-azure'], "
        "label:has-text('Azure')"
    )

    AUTH_MODE_SELECT = (
        "[data-testid='auth-mode'], "
        "select[name='authMode'], "
        "select[name='auth_mode']"
    )

    REGION_INPUT = (
        "[data-testid='region'], "
        "input[name='region'], "
        "input[placeholder*='region' i], "
        "select[name='region']"
    )

    IAM_ROLE_ARN_INPUT = (
        "[data-testid='iam-role-arn'], "
        "input[name='roleArn'], "
        "input[name='iamRoleArn'], "
        "input[placeholder*='role ARN' i], "
        "input[placeholder*='arn:aws:iam' i], "
        "label:has-text('IAM role ARN') + * input"
    )

    EXTERNAL_ID_DISPLAY = (
        "[data-testid='external-id'], "
        "input[name='externalId'][readonly], "
        "input[name='externalId']:disabled, "
        ".external-id-value, "
        "label:has-text('External ID') + * input, "
        "label:has-text('External ID') + * span, "
        "label:has-text('External ID') ~ * code"
    )

    # ------------------------------------------------------------------
    # Action buttons
    # ------------------------------------------------------------------
    SAVE_BUTTON = (
        "button[type='submit']:has-text('Save'), "
        "button:has-text('Create'), "
        "button:has-text('Add'), "
        "[data-testid='save-credential-btn']"
    )
    CANCEL_BUTTON = (
        "button:has-text('Cancel'), "
        "[data-testid='cancel-credential-btn']"
    )

    def __init__(self, page: Page):
        super().__init__(page)

    # ------------------------------------------------------------------
    # Dialog lifecycle
    # ------------------------------------------------------------------

    def wait_for_dialog_open(self) -> None:
        """Wait until the dialog is visible."""
        self.wait_for_selector(self.DIALOG, timeout=self.DEFAULT_TIMEOUT)
        logger.info("Create-credential dialog is open")

    def is_dialog_open(self) -> bool:
        return self.is_visible(self.DIALOG, timeout=3000)

    # ------------------------------------------------------------------
    # Field interactions
    # ------------------------------------------------------------------

    def enter_name(self, name: str) -> None:
        self._fill_first_visible(self.NAME_INPUT.split(", "), name, "Name")

    def enter_description(self, description: str) -> None:
        self._fill_first_visible(self.DESCRIPTION_INPUT.split(", "), description, "Description")

    def select_cloud_aws(self) -> None:
        """Select AWS as the cloud provider."""
        # Try <select> first
        if self._try_select_option(
            [s.strip() for s in self.CLOUD_PROVIDER_SELECT.split(",")], "AWS"
        ):
            return
        # Try clicking a card / radio
        aws_selectors = [s.strip() for s in self.CLOUD_AWS_OPTION.split(",")]
        for sel in aws_selectors:
            if self.is_visible(sel, timeout=3000):
                self.click(sel)
                logger.info("Selected AWS cloud provider via: %s", sel)
                return
        raise RuntimeError("Unable to select AWS cloud provider — no matching element found")

    def select_cloud_azure(self) -> None:
        """Select Azure as the cloud provider."""
        if self._try_select_option(
            [s.strip() for s in self.CLOUD_PROVIDER_SELECT.split(",")], "Azure"
        ):
            return
        azure_selectors = [s.strip() for s in self.CLOUD_AZURE_OPTION.split(",")]
        for sel in azure_selectors:
            if self.is_visible(sel, timeout=3000):
                self.click(sel)
                return
        raise RuntimeError("Unable to select Azure cloud provider")

    def select_auth_mode(self, mode: str) -> None:
        """Select an auth mode (e.g. 'IAM Role')."""
        self._try_select_option(
            [s.strip() for s in self.AUTH_MODE_SELECT.split(",")], mode
        )

    def enter_region(self, region: str) -> None:
        self._fill_first_visible(self.REGION_INPUT.split(", "), region, "Region")

    def enter_iam_role_arn(self, arn: str) -> None:
        self._fill_first_visible(self.IAM_ROLE_ARN_INPUT.split(", "), arn, "IAM Role ARN")

    def get_external_id(self) -> str:
        """
        Read and return the auto-generated External ID shown in the dialog.
        This UUID is assigned by e6data and needed for the trust policy.
        """
        ext_selectors = [s.strip() for s in self.EXTERNAL_ID_DISPLAY.split(",")]
        for sel in ext_selectors:
            if self.is_visible(sel, timeout=3000):
                # Try as input value first (readonly field)
                loc = self.page.locator(sel).first
                try:
                    val = loc.input_value()
                    if val:
                        return val.strip()
                except Exception:
                    pass
                text = (loc.inner_text() or "").strip()
                if text:
                    return text
        # Fallback: search for UUID pattern on the page
        import re
        uuid_pattern = re.compile(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
        )
        page_text = self.page.content()
        match = uuid_pattern.search(page_text)
        if match:
            return match.group()
        return ""

    # ------------------------------------------------------------------
    # Composite: fill the whole form
    # ------------------------------------------------------------------

    def fill_credential_form(
        self,
        name: str,
        description: str = "",
        cloud: str = "AWS",
        auth_mode: Optional[str] = None,
        region: str = "us-east-1",
        iam_role_arn: str = "",
    ) -> str:
        """
        Fill all fields in the credential creation dialog.
        Returns the External ID (UUID) shown in the dialog.
        """
        self.wait_for_dialog_open()
        self.enter_name(name)
        if description:
            self.enter_description(description)
        if cloud.upper() == "AWS":
            self.select_cloud_aws()
        else:
            self.select_cloud_azure()
        if auth_mode:
            self.select_auth_mode(auth_mode)
        if region:
            self.enter_region(region)
        if iam_role_arn:
            self.enter_iam_role_arn(iam_role_arn)
        external_id = self.get_external_id()
        logger.info("External ID shown in dialog: %s", external_id)
        return external_id

    # ------------------------------------------------------------------
    # Save / Cancel
    # ------------------------------------------------------------------

    def click_save(self) -> None:
        """Click the Save / Create button."""
        save_selectors = [s.strip() for s in self.SAVE_BUTTON.split(",")]
        for sel in save_selectors:
            if self.is_visible(sel, timeout=5000):
                self.click(sel)
                logger.info("Clicked Save button in credential dialog")
                self.wait_for_network_idle()
                return
        # role-based fallback
        self.page.get_by_role("button", name="Save").click()
        self.wait_for_network_idle()

    def click_cancel(self) -> None:
        """Click the Cancel button."""
        cancel_selectors = [s.strip() for s in self.CANCEL_BUTTON.split(",")]
        for sel in cancel_selectors:
            if self.is_visible(sel, timeout=3000):
                self.click(sel)
                return
        self.close_dialog()

    def save_and_wait_for_dismiss(self) -> None:
        """Save the form and wait for the dialog to close."""
        self.click_save()
        # Wait for dialog to disappear
        try:
            dialog_loc = self.page.locator(self.DIALOG).first
            dialog_loc.wait_for(state="hidden", timeout=self.DEFAULT_TIMEOUT)
        except PlaywrightTimeoutError:
            logger.warning("Dialog did not close after save — checking for error messages")
        self.wait_for_network_idle()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fill_first_visible(self, selectors: list, value: str, field_name: str) -> None:
        for sel in selectors:
            sel = sel.strip()
            if not sel:
                continue
            try:
                loc = self.page.locator(sel).first
                loc.wait_for(state="visible", timeout=3000)
                loc.clear()
                loc.fill(value)
                logger.info("Filled %s field via selector: %s", field_name, sel)
                return
            except PlaywrightTimeoutError:
                continue
        raise RuntimeError(
            f"Could not find visible input for field '{field_name}'. "
            f"Tried selectors: {selectors}"
        )

    def _try_select_option(self, selectors: list, value: str) -> bool:
        for sel in selectors:
            sel = sel.strip()
            if not sel:
                continue
            try:
                loc = self.page.locator(sel).first
                loc.wait_for(state="visible", timeout=3000)
                loc.select_option(value)
                return True
            except Exception:
                continue
        return False
