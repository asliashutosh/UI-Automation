"""
helpers/shell_helper.py
------------------------
Runs the downloaded e6data setup shell script and extracts the IAM Role ARN
from its output.

The script sets up AWS IAM roles via the AWS CLI. When it completes it prints
something like:
    Role ARN: arn:aws:iam::123456789012:role/some-role-name
or the ARN appears anywhere in stdout.
"""
import logging
import os
import re
import subprocess

logger = logging.getLogger(__name__)

# Pattern to match any IAM Role ARN in the script output
ARN_PATTERN = re.compile(r"arn:aws:iam::\d{12}:role/[\w+=,.@/-]+")


def run_setup_script(script_path: str, timeout: int = 300) -> str:
    """
    Execute the e6data setup shell script and extract the created Role ARN.

    Args:
        script_path: Absolute path to the downloaded .sh script.
        timeout:     Max seconds to wait for the script to finish (default 5 min).

    Returns:
        The IAM Role ARN string.

    Raises:
        RuntimeError: If the script fails or no ARN is found in the output.
    """
    logger.info("Running setup script: %s", script_path)

    # Pass current environment so AWS_* credentials are available
    env = os.environ.copy()

    result = subprocess.run(
        ["bash", script_path],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )

    combined_output = result.stdout + "\n" + result.stderr
    logger.debug("Script stdout:\n%s", result.stdout)

    if result.returncode != 0:
        logger.error("Script failed (exit %d):\n%s", result.returncode, result.stderr)
        raise RuntimeError(
            f"Setup script exited with code {result.returncode}.\n"
            f"stderr: {result.stderr[:1000]}"
        )

    # Extract IAM Role ARN from output
    match = ARN_PATTERN.search(combined_output)
    if not match:
        raise RuntimeError(
            f"Could not find a Role ARN in script output.\n"
            f"stdout: {result.stdout[:1000]}"
        )

    role_arn = match.group(0)
    logger.info("Extracted Role ARN: %s", role_arn)
    return role_arn
