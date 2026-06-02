"""
helpers/gmail_helper.py
------------------------
Automatically reads OTP codes from Gmail using the Google Gmail API.

Prerequisites (one-time setup):
  1. pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
  2. Place credentials.json in the project root
  3. Run read_gmail.py once to generate token.json
     (token.json auto-refreshes after that — no manual action needed)

OTP sender for e6data: no-reply@e6.run
"""
import base64
import logging
import re
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
PROJECT_ROOT = Path(__file__).parent.parent


class GmailOTPHelper:
    """Fetches OTP codes from Gmail using the Gmail API."""

    def __init__(
        self,
        token_path: str = None,
        credentials_path: str = None,
    ):
        self._token_path = token_path or str(PROJECT_ROOT / "token.json")
        self._credentials_path = credentials_path or str(PROJECT_ROOT / "credentials.json")
        self._service = self._build_service()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _build_service(self):
        creds = Credentials.from_authorized_user_file(self._token_path, SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                logger.info("Refreshing Gmail token...")
                creds.refresh(Request())
                with open(self._token_path, "w") as f:
                    f.write(creds.to_json())
            else:
                raise RuntimeError(
                    "Gmail token is invalid. Delete token.json and run "
                    "read_gmail.py again to re-authenticate."
                )
        return build("gmail", "v1", credentials=creds)

    # ------------------------------------------------------------------
    # Email parsing
    # ------------------------------------------------------------------

    def _extract_body(self, payload: dict) -> str | None:
        """Recursively extract plain-text body from email payload."""
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    data = part["body"].get("data")
                    if data:
                        return base64.urlsafe_b64decode(data).decode("utf-8")
                elif "parts" in part:
                    result = self._extract_body(part)
                    if result:
                        return result
        else:
            data = payload.get("body", {}).get("data")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8")
        return None

    def _extract_otp(self, body: str, subject: str) -> str | None:
        """Extract the first 6-digit number from body or subject."""
        match = re.search(r"\b(\d{6})\b", body or "") or re.search(
            r"\b(\d{6})\b", subject or ""
        )
        return match.group(1) if match else None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_otp(
        self,
        sender: str = "no-reply@e6.run",
        received_after: float = None,
    ) -> str | None:
        """
        Fetch the latest email from `sender` and extract the OTP.

        Args:
            sender:         Email address of the OTP sender.
            received_after: Unix timestamp (seconds). Only accept emails
                            received AFTER this time — prevents stale OTPs
                            from previous sessions being reused.

        Returns the 6-digit OTP string, or None if not found.
        """
        query = f"from:{sender} is:unread"

        results = self._service.users().messages().list(
            userId="me", maxResults=5, q=query
        ).execute()
        messages = results.get("messages", [])

        if not messages:
            logger.debug("No unread emails from %s", sender)
            return None

        for message in messages:
            msg = self._service.users().messages().get(
                userId="me", id=message["id"]
            ).execute()

            # internalDate is milliseconds since epoch
            email_ts = int(msg.get("internalDate", 0)) / 1000

            if received_after and email_ts < received_after:
                logger.debug(
                    "Skipping email — received at %.0f, cutoff is %.0f",
                    email_ts, received_after,
                )
                continue

            headers = msg["payload"].get("headers", [])
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
            body = self._extract_body(msg["payload"]) or ""

            otp = self._extract_otp(body, subject)
            if otp:
                logger.info("OTP extracted from Gmail: %s", otp)
                return otp

        return None

    def get_otp_with_retry(
        self,
        sender: str = "no-reply@e6.run",
        max_retries: int = 12,
        interval: int = 5,
        received_after: float = None,
    ) -> str:
        """
        Poll Gmail every `interval` seconds until a fresh OTP email arrives.

        Args:
            received_after: Unix timestamp (seconds). Pass time.time() just
                            before triggering the OTP so stale emails are ignored.
        """
        for attempt in range(1, max_retries + 1):
            logger.info(
                "Checking Gmail for OTP (attempt %d/%d)...", attempt, max_retries
            )
            otp = self.fetch_otp(sender=sender, received_after=received_after)
            if otp:
                return otp
            if attempt < max_retries:
                logger.info("OTP not found yet, waiting %ds...", interval)
                time.sleep(interval)

        raise RuntimeError(
            f"OTP email from '{sender}' did not arrive within "
            f"{max_retries * interval}s. Check that the email was sent."
        )
