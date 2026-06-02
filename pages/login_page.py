"""
pages/login_page.py
--------------------
Page object for the e6data login flow (OTP-based).
"""
import logging

from pages.base_page import BasePage

logger = logging.getLogger(__name__)


class LoginPage(BasePage):

    def navigate(self):
        self.page.goto("/login")
        self.page.wait_for_load_state("networkidle")
        logger.info("Navigated to /login")

    def enter_email(self, email: str):
        self.page.get_by_role("textbox", name="Email").click()
        self.page.get_by_role("textbox", name="Email").fill(email)
        logger.info("Entered email: %s", email)

    def click_continue(self):
        self.page.get_by_role("button", name="Continue").click()
        logger.info("Clicked Continue")

    def wait_for_otp_input(self, timeout: int = 10_000):
        """Wait for the OTP input box to appear."""
        self.page.get_by_role("textbox", name="Verification Code").wait_for(timeout=timeout)
        logger.info("OTP input is visible")

    def fill_otp(self, otp: str):
        """Fill the OTP code into the verification input."""
        self.page.get_by_role("textbox", name="Verification Code").click()
        self.page.get_by_role("textbox", name="Verification Code").fill(otp)
        logger.info("Filled OTP: %s", otp)

    def click_verify(self):
        """Click the Verify & Sign In button."""
        self.page.get_by_role("button", name="Verify & Sign In").click()
        logger.info("Clicked Verify & Sign In")

    def wait_for_login_complete(self, timeout: int = 120_000):
        """
        Wait for the user to complete login manually.
        Detects success by waiting for the URL to move away from /login.
        """
        self.page.wait_for_url(lambda url: "/login" not in url, timeout=timeout)
        logger.info("Login completed — URL is now: %s", self.page.url)

    def switch_organization(self, org_name: str):
        """Click 'Switch organization' and select the given org."""
        self.page.get_by_role("button", name="Switch organization").click()
        self.page.get_by_role("option", name=org_name).click()
        self.page.wait_for_load_state("networkidle")
        logger.info("Switched to organization: %s", org_name)
