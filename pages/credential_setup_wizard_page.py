"""
pages/credential_setup_wizard_page.py
---------------------------------------
Page object for the e6data Storage Credential Setup Wizard.
(Opens as a popup from the workspace settings page)

Covers the full wizard flow:
  1. Add S3 bucket
  2. Enable Glue catalog
  3. Fill stack name, Engine Role ARN, External ID, VPCE
  4. Continue to Setup
  5. Select AWS CLI → Download setup script
"""
import logging
import os
import tempfile

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class CredentialSetupWizardPage(BasePage):

    # ------------------------------------------------------------------
    # Step 1 — S3 Bucket
    # ------------------------------------------------------------------

    def fill_s3_bucket(self, bucket: str):
        """Fill the S3 bucket name input."""
        self.page.get_by_role("textbox").first.click()
        self.page.get_by_role("textbox").first.fill(bucket)
        logger.info("Filled S3 bucket: %s", bucket)

    def click_add_bucket(self):
        """Click the Add button to add the bucket to the list."""
        self.page.get_by_role("button", name="Add").first.click()
        logger.info("Clicked Add bucket")

    def enable_glue_catalog(self):
        """Check the 'Using AWS Glue Catalog?' checkbox."""
        self.page.locator("label").filter(
            has_text="Using AWS Glue Catalog?"
        ).get_by_role("checkbox").click()
        logger.info("Enabled AWS Glue Catalog")

    # ------------------------------------------------------------------
    # Step 2 — Stack & Connection Details
    # ------------------------------------------------------------------

    def fill_stack_name(self, name: str):
        """Fill the CloudFormation stack name (placeholder: 'e6data')."""
        self.page.get_by_role("textbox", name="e6data", exact=True).click()
        self.page.get_by_role("textbox", name="e6data", exact=True).fill(name)
        logger.info("Filled stack name: %s", name)

    def fill_engine_role_arn(self, arn: str):
        """Fill the Engine Role ARN field."""
        self.page.get_by_role("textbox", name="arn:aws:iam::").click()
        self.page.get_by_role("textbox", name="arn:aws:iam::").fill(arn)
        logger.info("Filled Engine Role ARN: %s", arn)

    def fill_external_id(self, external_id: str):
        """Fill the External ID field."""
        self.page.get_by_role("textbox", name="paste the value shown in").click()
        self.page.get_by_role("textbox", name="paste the value shown in").fill(external_id)
        logger.info("Filled External ID: %s", external_id)

    def fill_vpce(self, vpce: str):
        """Fill the VPC Endpoint ID field."""
        self.page.get_by_role("textbox", name="vpce-0abc123def456").click()
        self.page.get_by_role("textbox", name="vpce-0abc123def456").fill(vpce)
        logger.info("Filled VPCE: %s", vpce)

    def click_continue_to_setup(self):
        """Click Continue to Setup to move to the next step."""
        self.page.get_by_role("button", name="Continue to Setup").click()
        self.page.wait_for_load_state("networkidle")
        logger.info("Clicked Continue to Setup")

    # ------------------------------------------------------------------
    # Step 3 — AWS CLI + Download
    # ------------------------------------------------------------------

    def select_aws_cli(self):
        """Select the AWS CLI option."""
        self.page.get_by_role("button", name="AWS CLI").click()
        logger.info("Selected AWS CLI option")

    def download_setup_script(self) -> str:
        """
        Click 'Download e6data-all.sh', save to a temp directory,
        and return the full path to the downloaded script.
        """
        with self.page.expect_download() as download_info:
            self.page.get_by_role("button", name="Download e6data-all.sh").click()
        download = download_info.value

        temp_dir = tempfile.mkdtemp()
        script_path = os.path.join(temp_dir, download.suggested_filename or "e6data-all.sh")
        download.save_as(script_path)
        os.chmod(script_path, 0o755)

        logger.info("Setup script downloaded: %s", script_path)
        return script_path
