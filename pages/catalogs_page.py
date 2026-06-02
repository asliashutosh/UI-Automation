"""
CatalogsPage
------------
Represents the /catalogs page.

Key actions:
  - Open "Create Catalog" dialog
  - Fill: Catalog name, Type (AWS Glue), Storage Credential (dropdown),
           AWS Account ID, Region
  - Submit and verify catalog appears in list
"""
import logging
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class CatalogsPage(BasePage):
    # ------------------------------------------------------------------
    # Page-level selectors
    # ------------------------------------------------------------------
    CATALOGS_HEADER = (
        "h1:has-text('Catalogs'), "
        "h2:has-text('Catalogs'), "
        "[data-testid='catalogs-header']"
    )
    CREATE_CATALOG_BUTTON = (
        "button:has-text('Create catalog'), "
        "button:has-text('New catalog'), "
        "button:has-text('+ Catalog'), "
        "[data-testid='create-catalog-btn']"
    )
    CATALOGS_TABLE = (
        "[data-testid='catalogs-table'], "
        ".catalogs-table, "
        "table"
    )

    # ------------------------------------------------------------------
    # Create-catalog dialog selectors
    # ------------------------------------------------------------------
    DIALOG = (
        "[role='dialog'], "
        ".modal, "
        ".ant-modal-content, "
        "[data-testid='create-catalog-dialog']"
    )

    CATALOG_NAME_INPUT = (
        "[data-testid='catalog-name'], "
        "input[name='catalogName'], "
        "input[name='name'], "
        "input[placeholder*='catalog name' i], "
        "label:has-text('Catalog name') + * input, "
        "label:has-text('Name') + * input"
    )
    CATALOG_TYPE_SELECT = (
        "[data-testid='catalog-type'], "
        "select[name='catalogType'], "
        "select[name='type']"
    )
    CATALOG_TYPE_GLUE_OPTION = (
        "[data-value='AWS Glue'], "
        "[data-value='glue'], "
        "option[value='AWS Glue'], "
        "option[value='glue']"
    )
    STORAGE_CREDENTIAL_SELECT = (
        "[data-testid='storage-credential'], "
        "select[name='storageCredential'], "
        "select[name='credentialId']"
    )
    AWS_ACCOUNT_ID_INPUT = (
        "[data-testid='aws-account-id'], "
        "input[name='awsAccountId'], "
        "input[name='accountId'], "
        "input[placeholder*='account ID' i], "
        "input[placeholder*='account id' i], "
        "label:has-text('AWS Account ID') + * input"
    )
    REGION_INPUT = (
        "[data-testid='catalog-region'], "
        "input[name='region'], "
        "select[name='region'], "
        "input[placeholder*='region' i]"
    )

    SAVE_BUTTON = (
        "button[type='submit']:has-text('Save'), "
        "button:has-text('Create'), "
        "button:has-text('Add'), "
        "[data-testid='save-catalog-btn']"
    )
    CANCEL_BUTTON = (
        "button:has-text('Cancel'), "
        "[data-testid='cancel-catalog-btn']"
    )

    # Column indices (0-based)
    COL_NAME = 0
    COL_TYPE = 1
    COL_STATUS = 2

    def __init__(self, page: Page):
        super().__init__(page)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to_catalogs(self, base_url: str) -> None:
        self.navigate(f"{base_url}/catalogs")
        self._wait_for_page_ready()

    def _wait_for_page_ready(self) -> None:
        self.wait_for_network_idle()
        header_selectors = [s.strip() for s in self.CATALOGS_HEADER.split(",")]
        for sel in header_selectors:
            if self.is_visible(sel, timeout=10_000):
                return

    # ------------------------------------------------------------------
    # Create Catalog dialog
    # ------------------------------------------------------------------

    def click_create_catalog(self) -> None:
        """Click the '+ Create catalog' button to open the dialog."""
        button_selectors = [s.strip() for s in self.CREATE_CATALOG_BUTTON.split(",")]
        for sel in button_selectors:
            if self.is_visible(sel, timeout=5000):
                self.click(sel)
                self._wait_for_dialog_open()
                return
        self.page.get_by_role("button", name="Create catalog").click()
        self._wait_for_dialog_open()

    def _wait_for_dialog_open(self) -> None:
        dialog_selectors = [s.strip() for s in self.DIALOG.split(",")]
        for sel in dialog_selectors:
            if self.is_visible(sel, timeout=10_000):
                logger.info("Create-catalog dialog opened")
                return
        logger.warning("Dialog selector not matched — assuming dialog is open")

    # ------------------------------------------------------------------
    # Field interactions
    # ------------------------------------------------------------------

    def enter_catalog_name(self, name: str) -> None:
        self._fill_first_visible(
            [s.strip() for s in self.CATALOG_NAME_INPUT.split(",")], name, "Catalog name"
        )

    def select_type_aws_glue(self) -> None:
        """Select 'AWS Glue' as the catalog type."""
        type_selectors = [s.strip() for s in self.CATALOG_TYPE_SELECT.split(",")]
        for sel in type_selectors:
            if self.is_visible(sel, timeout=5000):
                loc = self.page.locator(sel).first
                try:
                    loc.select_option("AWS Glue")
                    return
                except Exception:
                    try:
                        loc.select_option("glue")
                        return
                    except Exception:
                        pass

        # Custom dropdown: look for a clickable trigger then pick the Glue option
        trigger_selectors = [
            "[data-testid='catalog-type-trigger']",
            "div[role='combobox']:near(:text('Type'))",
            ".select__control:near(:text('Type'))",
        ]
        for sel in trigger_selectors:
            if self.is_visible(sel, timeout=3000):
                self.click(sel)
                glue_option_selectors = [
                    "[role='option']:has-text('AWS Glue')",
                    "li:has-text('AWS Glue')",
                    ".select__option:has-text('AWS Glue')",
                ]
                for opt_sel in glue_option_selectors:
                    if self.is_visible(opt_sel, timeout=3000):
                        self.click(opt_sel)
                        return

    def select_storage_credential(self, credential_name: str) -> None:
        """Select a storage credential from the dropdown by name."""
        cred_selectors = [s.strip() for s in self.STORAGE_CREDENTIAL_SELECT.split(",")]
        for sel in cred_selectors:
            if self.is_visible(sel, timeout=5000):
                loc = self.page.locator(sel).first
                try:
                    loc.select_option(label=credential_name)
                    return
                except Exception:
                    try:
                        loc.select_option(value=credential_name)
                        return
                    except Exception:
                        pass

        # Custom dropdown fallback
        trigger_selectors = [
            "[data-testid='storage-credential-trigger']",
            "div[role='combobox']:near(:text('Storage Credential'))",
            ".select__control:near(:text('Storage Credential'))",
        ]
        for sel in trigger_selectors:
            if self.is_visible(sel, timeout=3000):
                self.click(sel)
                option_selectors = [
                    f"[role='option']:has-text('{credential_name}')",
                    f"li:has-text('{credential_name}')",
                    f".select__option:has-text('{credential_name}')",
                ]
                for opt_sel in option_selectors:
                    if self.is_visible(opt_sel, timeout=5000):
                        self.click(opt_sel)
                        return
        raise RuntimeError(f"Could not select storage credential '{credential_name}'")

    def enter_aws_account_id(self, account_id: str) -> None:
        self._fill_first_visible(
            [s.strip() for s in self.AWS_ACCOUNT_ID_INPUT.split(",")], account_id, "AWS Account ID"
        )

    def enter_region(self, region: str) -> None:
        region_selectors = [s.strip() for s in self.REGION_INPUT.split(",")]
        for sel in region_selectors:
            if self.is_visible(sel, timeout=3000):
                loc = self.page.locator(sel).first
                try:
                    loc.select_option(region)
                    return
                except Exception:
                    pass
                loc.clear()
                loc.fill(region)
                return

    # ------------------------------------------------------------------
    # Composite: fill entire catalog form
    # ------------------------------------------------------------------

    def fill_catalog_form(
        self,
        catalog_name: str,
        storage_credential: str,
        aws_account_id: str,
        region: str,
        catalog_type: str = "AWS Glue",
    ) -> None:
        """Fill all fields in the create-catalog dialog."""
        self.enter_catalog_name(catalog_name)
        if catalog_type == "AWS Glue":
            self.select_type_aws_glue()
        self.select_storage_credential(storage_credential)
        self.enter_aws_account_id(aws_account_id)
        self.enter_region(region)

    # ------------------------------------------------------------------
    # Save / Cancel
    # ------------------------------------------------------------------

    def click_save(self) -> None:
        save_selectors = [s.strip() for s in self.SAVE_BUTTON.split(",")]
        for sel in save_selectors:
            if self.is_visible(sel, timeout=5000):
                self.click(sel)
                self.wait_for_network_idle()
                return
        self.page.get_by_role("button", name="Create").click()
        self.wait_for_network_idle()

    def save_and_wait_for_dismiss(self) -> None:
        self.click_save()
        try:
            dialog_loc = self.page.locator(self.DIALOG).first
            dialog_loc.wait_for(state="hidden", timeout=self.DEFAULT_TIMEOUT)
        except PlaywrightTimeoutError:
            logger.warning("Dialog did not close after catalog save")
        self.wait_for_network_idle()

    # ------------------------------------------------------------------
    # Table inspection
    # ------------------------------------------------------------------

    def find_catalog_row(self, catalog_name: str) -> Optional[object]:
        row_selectors = [
            f"tr:has-text('{catalog_name}')",
            f"[data-testid='catalog-row']:has-text('{catalog_name}')",
        ]
        for sel in row_selectors:
            loc = self.page.locator(sel)
            if loc.count() > 0:
                return loc.first
        return None

    def catalog_exists(self, catalog_name: str) -> bool:
        return self.find_catalog_row(catalog_name) is not None

    def delete_catalog(self, catalog_name: str) -> None:
        """Delete a catalog by name."""
        row = self.find_catalog_row(catalog_name)
        if row is None:
            logger.warning("Catalog '%s' not found for deletion", catalog_name)
            return
        action_selectors = [
            "button[aria-label='Actions']",
            ".actions-btn",
            "[aria-haspopup='menu']",
        ]
        for sel in action_selectors:
            btn = row.locator(sel)
            if btn.count() > 0:
                btn.first.click()
                break
        else:
            row.locator("td").last.click()

        delete_selectors = [
            "text=Delete",
            "[role='menuitem']:has-text('Delete')",
            "button:has-text('Delete')",
        ]
        for sel in delete_selectors:
            if self.is_visible(sel, timeout=3000):
                self.click(sel)
                break

        confirm_selectors = [
            "button:has-text('Confirm')",
            "button:has-text('Yes, delete')",
            "button:has-text('Delete')",
        ]
        for sel in confirm_selectors:
            if self.is_visible(sel, timeout=5000):
                self.click(sel)
                break

        self.wait_for_network_idle()
        logger.info("Deleted catalog: %s", catalog_name)

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
                return
            except PlaywrightTimeoutError:
                continue
        raise RuntimeError(
            f"Could not find visible input for field '{field_name}'. Tried: {selectors}"
        )
