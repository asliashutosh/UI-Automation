"""
AWSSetupWizard
--------------
Page object for the e6data AWS Setup Wizard page.

Sections:
  1. Select Cloud Provider  (AWS card / Azure card)
  2. Your AWS Configuration
     - S3 Bucket Names (multi-value input)
     - Glue checkbox
     - KMS checkbox
     - Apply bucket policies checkbox
     - Stack Name (text input)
     - AWS Region (dropdown / text input)
  3. e6data Configuration
     - Engine Role ARN (text input)
     - VPC Endpoint ID (text input)
  4. "Continue to Setup" button → generates CloudFormation URL
"""
import logging
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class AWSSetupWizard(BasePage):
    # ------------------------------------------------------------------
    # Page-level selectors
    # ------------------------------------------------------------------
    WIZARD_CONTAINER = (
        "[data-testid='aws-setup-wizard'], "
        ".aws-setup-wizard, "
        ".setup-wizard, "
        "main:has-text('Select Cloud Provider')"
    )

    # ------------------------------------------------------------------
    # Section 1: Select Cloud Provider
    # ------------------------------------------------------------------
    AWS_PROVIDER_CARD = (
        "[data-testid='cloud-provider-aws'], "
        ".cloud-provider-card:has-text('AWS'), "
        "div.card:has-text('AWS'), "
        "button:has-text('AWS')"
    )
    AZURE_PROVIDER_CARD = (
        "[data-testid='cloud-provider-azure'], "
        ".cloud-provider-card:has-text('Azure'), "
        "div.card:has-text('Azure'), "
        "button:has-text('Azure')"
    )

    # ------------------------------------------------------------------
    # Section 2: Your AWS Configuration
    # ------------------------------------------------------------------
    S3_BUCKET_INPUT = (
        "[data-testid='s3-bucket-names'], "
        "input[name='s3BucketNames'], "
        "input[name='bucketNames'], "
        "input[placeholder*='bucket' i], "
        "label:has-text('S3 Bucket') + * input, "
        "label:has-text('Bucket') ~ * input"
    )
    ADD_BUCKET_BUTTON = (
        "button:has-text('Add bucket'), "
        "button:has-text('Add'), "
        "[data-testid='add-bucket-btn']"
    )

    GLUE_CHECKBOX = (
        "[data-testid='glue-checkbox'], "
        "input[name='glue'], "
        "input[type='checkbox']:near(:text('Glue')), "
        "label:has-text('Glue') input[type='checkbox']"
    )
    KMS_CHECKBOX = (
        "[data-testid='kms-checkbox'], "
        "input[name='kms'], "
        "input[type='checkbox']:near(:text('KMS')), "
        "label:has-text('KMS') input[type='checkbox']"
    )
    APPLY_BUCKET_POLICIES_CHECKBOX = (
        "[data-testid='apply-bucket-policies'], "
        "input[name='applyBucketPolicies'], "
        "input[type='checkbox']:near(:text('Apply bucket policies')), "
        "label:has-text('Apply bucket policies') input[type='checkbox']"
    )

    STACK_NAME_INPUT = (
        "[data-testid='stack-name'], "
        "input[name='stackName'], "
        "input[placeholder*='stack' i], "
        "label:has-text('Stack Name') + * input"
    )
    AWS_REGION_INPUT = (
        "[data-testid='aws-region'], "
        "input[name='awsRegion'], "
        "select[name='awsRegion'], "
        "input[name='region'], "
        "select[name='region'], "
        "input[placeholder*='region' i]"
    )

    # ------------------------------------------------------------------
    # Section 3: e6data Configuration
    # ------------------------------------------------------------------
    ENGINE_ROLE_ARN_INPUT = (
        "[data-testid='engine-role-arn-input'], "
        "input[name='engineRoleArn'], "
        "input[placeholder*='engine role' i], "
        "input[placeholder*='arn:aws:iam' i], "
        "label:has-text('Engine Role ARN') + * input"
    )
    VPC_ENDPOINT_INPUT = (
        "[data-testid='vpc-endpoint-id'], "
        "input[name='vpcEndpointId'], "
        "input[name='vpceId'], "
        "input[placeholder*='vpce-' i], "
        "label:has-text('VPC Endpoint') + * input"
    )

    # ------------------------------------------------------------------
    # Section 4: Action buttons
    # ------------------------------------------------------------------
    CONTINUE_TO_SETUP_BUTTON = (
        "button:has-text('Continue to Setup'), "
        "button:has-text('Generate CloudFormation'), "
        "button:has-text('Continue'), "
        "[data-testid='continue-setup-btn']"
    )

    # CloudFormation URL result area
    CF_URL_DISPLAY = (
        "[data-testid='cloudformation-url'], "
        ".cloudformation-url, "
        "a[href*='cloudformation'], "
        "input[readonly][value*='cloudformation'], "
        "pre:has-text('cloudformation')"
    )
    CF_URL_COPY_BUTTON = (
        "button:has-text('Copy'), "
        "[data-testid='copy-cf-url'], "
        "button[aria-label='Copy URL']"
    )
    CF_LAUNCH_BUTTON = (
        "a:has-text('Launch Stack'), "
        "button:has-text('Launch Stack'), "
        "[data-testid='launch-stack-btn']"
    )

    def __init__(self, page: Page):
        super().__init__(page)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to_wizard(self, base_url: str) -> None:
        """Navigate to the AWS setup wizard page."""
        # The wizard may be at various paths — try common ones
        wizard_paths = ["/setup/aws", "/setup", "/aws-setup", "/onboarding/aws"]
        for path in wizard_paths:
            self.navigate(f"{base_url}{path}")
            if self.is_visible(self.AWS_PROVIDER_CARD, timeout=5000):
                logger.info("Found wizard at %s%s", base_url, path)
                return
        # If none worked, let the caller handle navigation
        logger.warning("Could not locate wizard via known paths; assuming current page is wizard")

    # ------------------------------------------------------------------
    # Section 1: Cloud Provider
    # ------------------------------------------------------------------

    def select_aws_provider(self) -> None:
        """Click the AWS provider card."""
        selectors = [s.strip() for s in self.AWS_PROVIDER_CARD.split(",")]
        for sel in selectors:
            if self.is_visible(sel, timeout=3000):
                self.click(sel)
                logger.info("Selected AWS provider card")
                return
        raise RuntimeError("AWS provider card not found on the setup wizard page")

    # ------------------------------------------------------------------
    # Section 2: AWS Configuration
    # ------------------------------------------------------------------

    def enter_s3_bucket(self, bucket_name: str) -> None:
        """Enter a single S3 bucket name. For multiple buckets call this method per bucket."""
        selectors = [s.strip() for s in self.S3_BUCKET_INPUT.split(",")]
        for sel in selectors:
            if self.is_visible(sel, timeout=3000):
                loc = self.page.locator(sel).first
                loc.clear()
                loc.fill(bucket_name)
                # Some UIs require pressing Enter or clicking Add after each bucket
                add_btn_selectors = [s.strip() for s in self.ADD_BUCKET_BUTTON.split(",")]
                for btn_sel in add_btn_selectors:
                    if self.is_visible(btn_sel, timeout=2000):
                        self.click(btn_sel)
                        logger.info("Added bucket: %s", bucket_name)
                        return
                # If no add button, press Enter
                loc.press("Enter")
                logger.info("Added bucket via Enter: %s", bucket_name)
                return
        raise RuntimeError(f"S3 bucket input not found. Tried: {self.S3_BUCKET_INPUT}")

    def enable_glue(self) -> None:
        """Check the Glue checkbox."""
        selectors = [s.strip() for s in self.GLUE_CHECKBOX.split(",")]
        for sel in selectors:
            if self.is_visible(sel, timeout=3000):
                self.check_checkbox(sel)
                return

    def enable_kms(self) -> None:
        """Check the KMS checkbox."""
        selectors = [s.strip() for s in self.KMS_CHECKBOX.split(",")]
        for sel in selectors:
            if self.is_visible(sel, timeout=3000):
                self.check_checkbox(sel)
                return

    def enable_apply_bucket_policies(self) -> None:
        """Check the 'Apply bucket policies' checkbox."""
        selectors = [s.strip() for s in self.APPLY_BUCKET_POLICIES_CHECKBOX.split(",")]
        for sel in selectors:
            if self.is_visible(sel, timeout=3000):
                self.check_checkbox(sel)
                return

    def enter_stack_name(self, stack_name: str) -> None:
        selectors = [s.strip() for s in self.STACK_NAME_INPUT.split(",")]
        for sel in selectors:
            if self.is_visible(sel, timeout=3000):
                loc = self.page.locator(sel).first
                loc.clear()
                loc.fill(stack_name)
                return
        raise RuntimeError(f"Stack name input not found")

    def enter_aws_region(self, region: str) -> None:
        selectors = [s.strip() for s in self.AWS_REGION_INPUT.split(",")]
        for sel in selectors:
            if self.is_visible(sel, timeout=3000):
                loc = self.page.locator(sel).first
                # Try as <select> first
                try:
                    loc.select_option(region)
                    return
                except Exception:
                    pass
                loc.clear()
                loc.fill(region)
                return
        raise RuntimeError(f"AWS region input not found")

    # ------------------------------------------------------------------
    # Section 3: e6data Configuration
    # ------------------------------------------------------------------

    def enter_engine_role_arn(self, arn: str) -> None:
        selectors = [s.strip() for s in self.ENGINE_ROLE_ARN_INPUT.split(",")]
        for sel in selectors:
            if self.is_visible(sel, timeout=3000):
                loc = self.page.locator(sel).first
                loc.clear()
                loc.fill(arn)
                return
        raise RuntimeError(f"Engine Role ARN input not found")

    def enter_vpc_endpoint_id(self, vpce_id: str) -> None:
        selectors = [s.strip() for s in self.VPC_ENDPOINT_INPUT.split(",")]
        for sel in selectors:
            if self.is_visible(sel, timeout=3000):
                loc = self.page.locator(sel).first
                loc.clear()
                loc.fill(vpce_id)
                return
        raise RuntimeError(f"VPC Endpoint ID input not found")

    # ------------------------------------------------------------------
    # Section 4: Generate CloudFormation URL
    # ------------------------------------------------------------------

    def click_continue_to_setup(self) -> None:
        """Click 'Continue to Setup' and wait for the CF URL to appear."""
        selectors = [s.strip() for s in self.CONTINUE_TO_SETUP_BUTTON.split(",")]
        for sel in selectors:
            if self.is_visible(sel, timeout=5000):
                self.click(sel)
                logger.info("Clicked 'Continue to Setup'")
                self.wait_for_network_idle()
                return
        raise RuntimeError("'Continue to Setup' button not found")

    def get_cloudformation_url(self) -> str:
        """
        Read the generated CloudFormation launch URL from the page.
        Returns the URL string.
        """
        selectors = [s.strip() for s in self.CF_URL_DISPLAY.split(",")]
        for sel in selectors:
            if self.is_visible(sel, timeout=10_000):
                loc = self.page.locator(sel).first
                # Try href attribute
                href = loc.get_attribute("href")
                if href and "cloudformation" in href:
                    return href
                # Try input value (readonly)
                try:
                    val = loc.input_value()
                    if val:
                        return val.strip()
                except Exception:
                    pass
                # Inner text
                text = (loc.inner_text() or "").strip()
                if text:
                    return text
        # Fallback: search page source for CloudFormation URL
        content = self.page.content()
        import re
        cf_pattern = re.compile(
            r"https://[a-z0-9\-\.]+\.amazonaws\.com/cloudformation[^\s\"'<>]+"
        )
        match = cf_pattern.search(content)
        if match:
            return match.group()
        return ""

    def copy_cloudformation_url(self) -> str:
        """Click the copy button and return the URL via clipboard."""
        copy_selectors = [s.strip() for s in self.CF_URL_COPY_BUTTON.split(",")]
        for sel in copy_selectors:
            if self.is_visible(sel, timeout=5000):
                self.click(sel)
                # Read clipboard — requires browser permission
                try:
                    url = self.page.evaluate("navigator.clipboard.readText()")
                    if url:
                        return url.strip()
                except Exception:
                    pass
        # Fall back to directly reading the URL field
        return self.get_cloudformation_url()

    # ------------------------------------------------------------------
    # Composite: fill wizard and generate CF URL
    # ------------------------------------------------------------------

    def fill_and_generate(
        self,
        bucket_names: list,
        stack_name: str,
        aws_region: str,
        engine_role_arn: str,
        vpc_endpoint_id: str,
        enable_glue: bool = True,
        enable_kms: bool = False,
        apply_bucket_policies: bool = True,
    ) -> str:
        """
        Fill all wizard sections and click 'Continue to Setup'.
        Returns the generated CloudFormation URL.
        """
        self.select_aws_provider()

        for bucket in bucket_names:
            self.enter_s3_bucket(bucket)

        if enable_glue:
            self.enable_glue()
        if enable_kms:
            self.enable_kms()
        if apply_bucket_policies:
            self.enable_apply_bucket_policies()

        self.enter_stack_name(stack_name)
        self.enter_aws_region(aws_region)
        self.enter_engine_role_arn(engine_role_arn)
        self.enter_vpc_endpoint_id(vpc_endpoint_id)

        self.click_continue_to_setup()

        cf_url = self.get_cloudformation_url()
        logger.info("Generated CloudFormation URL: %s", cf_url)
        return cf_url
