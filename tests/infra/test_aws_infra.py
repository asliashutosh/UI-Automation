"""
tests/infra/test_aws_infra.py
------------------------------
AWS infrastructure assertions using boto3.
These validate cloud-side state (IAM, S3, CloudFormation) independently of the UI.
"""
import pytest

from helpers.aws_helper import AWSHelper


@pytest.mark.aws
@pytest.mark.infra
class TestAWSInfra:
    """Sanity checks for AWS resources used by e6data."""

    def test_aws_credentials_are_valid(self, aws_helper: AWSHelper):
        """boto3 session must be able to call STS get-caller-identity."""
        sts = aws_helper._session.client("sts")
        identity = sts.get_caller_identity()
        assert identity.get("Account"), "STS did not return an account ID"

    def test_test_bucket_exists(self, aws_helper: AWSHelper):
        """The configured test S3 bucket must be accessible."""
        from config.settings import config
        response = aws_helper._s3.head_bucket(Bucket=config.test_bucket)
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    def test_engine_role_arn_format(self):
        """Engine role ARN in config must match expected IAM ARN pattern."""
        import re
        from config.settings import config
        arn_pattern = r"^arn:aws:iam::\d{12}:role/.+"
        assert re.match(arn_pattern, config.test_engine_role_arn), (
            f"Invalid engine role ARN format: {config.test_engine_role_arn}"
        )
