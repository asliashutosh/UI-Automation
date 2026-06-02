"""
AWSHelper
---------
Wraps boto3 calls needed by the test suite:

  - deploy_cf_stack()        : create or update a CloudFormation stack
  - wait_for_stack()         : poll until stack reaches a terminal state
  - get_stack_outputs()      : return stack Outputs as a dict
  - get_stack_resource()     : return a specific stack resource
  - get_iam_policy_document(): fetch the current policy document for an IAM role
  - get_bucket_policy()      : fetch S3 bucket policy as a dict
  - delete_cf_stack()        : delete a CloudFormation stack and wait

Bug-specific helpers:
  - check_plt_9078_s3_policy_resource()  : verify S3 policy Resource is not `arn:aws:s3:::*`
  - check_plt_9081_failed_buckets()      : verify FailedBuckets output == []
  - check_plt_9081_vpc_endpoint_sid()    : verify bucket policy has e6dataVPCEndpointAccess-{vpce_id}
"""
import json
import logging
import time
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class AWSHelper:
    # CloudFormation terminal states (successful or failed)
    TERMINAL_STATES = {
        "CREATE_COMPLETE",
        "UPDATE_COMPLETE",
        "DELETE_COMPLETE",
        "ROLLBACK_COMPLETE",
        "UPDATE_ROLLBACK_COMPLETE",
        "CREATE_FAILED",
        "DELETE_FAILED",
        "ROLLBACK_FAILED",
        "UPDATE_ROLLBACK_FAILED",
    }

    def __init__(
        self,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        aws_session_token: str = "",
        region: str = "us-east-1",
    ):
        session_kwargs = {
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
            "region_name": region,
        }
        if aws_session_token:
            session_kwargs["aws_session_token"] = aws_session_token

        self._session = boto3.Session(**session_kwargs)
        self._region = region
        self._cf = self._session.client("cloudformation")
        self._iam = self._session.client("iam")
        self._s3 = self._session.client("s3")

    # ------------------------------------------------------------------
    # CloudFormation — stack management
    # ------------------------------------------------------------------

    def deploy_cf_stack(
        self,
        stack_name: str,
        template_url: str,
        parameters: Optional[List[Dict]] = None,
        capabilities: Optional[List[str]] = None,
        tags: Optional[List[Dict]] = None,
    ) -> str:
        """
        Create or update a CloudFormation stack from a template URL.

        Returns the initial stack status string.
        Raises RuntimeError if the API call fails.
        """
        if capabilities is None:
            capabilities = ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"]
        if parameters is None:
            parameters = []
        if tags is None:
            tags = [{"Key": "CreatedBy", "Value": "playwright-test"}]

        common_kwargs: Dict[str, Any] = {
            "StackName": stack_name,
            "TemplateURL": template_url,
            "Parameters": parameters,
            "Capabilities": capabilities,
            "Tags": tags,
        }

        # Check if stack already exists
        existing_status = self._get_stack_status(stack_name)
        if existing_status is None:
            logger.info("Creating CloudFormation stack: %s", stack_name)
            self._cf.create_stack(**common_kwargs)
            return "CREATE_IN_PROGRESS"
        elif existing_status in ("ROLLBACK_COMPLETE", "DELETE_COMPLETE", "CREATE_FAILED"):
            # Stack is in a state where it must be deleted first
            logger.warning(
                "Stack %s is in state %s — deleting before recreating", stack_name, existing_status
            )
            self.delete_cf_stack(stack_name)
            self._cf.create_stack(**common_kwargs)
            return "CREATE_IN_PROGRESS"
        else:
            logger.info("Updating CloudFormation stack: %s (current state: %s)", stack_name, existing_status)
            try:
                self._cf.update_stack(**common_kwargs)
                return "UPDATE_IN_PROGRESS"
            except ClientError as exc:
                if "No updates are to be performed" in str(exc):
                    logger.info("No updates needed for stack %s", stack_name)
                    return existing_status
                raise RuntimeError(f"Failed to update stack {stack_name}: {exc}") from exc

    def wait_for_stack(
        self,
        stack_name: str,
        timeout_seconds: int = 900,
        poll_interval: int = 15,
    ) -> str:
        """
        Poll until the stack reaches a terminal state.
        Returns the final status string.
        Raises TimeoutError if timeout_seconds is exceeded.
        Raises RuntimeError if the stack ends in a failed state.
        """
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            status = self._get_stack_status(stack_name)
            logger.info("Stack %s status: %s", stack_name, status)
            if status in self.TERMINAL_STATES:
                if status in (
                    "CREATE_FAILED",
                    "ROLLBACK_COMPLETE",
                    "ROLLBACK_FAILED",
                    "DELETE_FAILED",
                    "UPDATE_ROLLBACK_FAILED",
                    "UPDATE_ROLLBACK_COMPLETE",
                ):
                    reason = self._get_stack_failure_reason(stack_name)
                    raise RuntimeError(
                        f"CloudFormation stack '{stack_name}' ended in failed state '{status}'. "
                        f"Reason: {reason}"
                    )
                return status
            time.sleep(poll_interval)

        raise TimeoutError(
            f"CloudFormation stack '{stack_name}' did not reach a terminal state within "
            f"{timeout_seconds}s. Last status: {self._get_stack_status(stack_name)}"
        )

    def get_stack_outputs(self, stack_name: str) -> Dict[str, str]:
        """
        Return the CloudFormation stack Outputs as {OutputKey: OutputValue}.
        Returns empty dict if no outputs exist or stack not found.
        """
        try:
            resp = self._cf.describe_stacks(StackName=stack_name)
            stacks = resp.get("Stacks", [])
            if not stacks:
                return {}
            outputs = stacks[0].get("Outputs", [])
            return {o["OutputKey"]: o["OutputValue"] for o in outputs}
        except ClientError as exc:
            logger.error("Failed to get stack outputs for %s: %s", stack_name, exc)
            return {}

    def get_stack_resource(self, stack_name: str, logical_resource_id: str) -> Dict:
        """Return details for a specific stack resource."""
        try:
            resp = self._cf.describe_stack_resource(
                StackName=stack_name,
                LogicalResourceId=logical_resource_id,
            )
            return resp.get("StackResourceDetail", {})
        except ClientError as exc:
            logger.error("Could not get resource %s from stack %s: %s", logical_resource_id, stack_name, exc)
            return {}

    def delete_cf_stack(self, stack_name: str, wait: bool = True, timeout_seconds: int = 600) -> None:
        """
        Delete a CloudFormation stack.
        Optionally waits for deletion to complete.
        """
        try:
            status = self._get_stack_status(stack_name)
            if status is None:
                logger.info("Stack %s does not exist — nothing to delete", stack_name)
                return
            logger.info("Deleting CloudFormation stack: %s", stack_name)
            self._cf.delete_stack(StackName=stack_name)
            if wait:
                self._wait_for_delete(stack_name, timeout_seconds)
        except ClientError as exc:
            logger.error("Failed to delete stack %s: %s", stack_name, exc)
            raise RuntimeError(f"Stack deletion failed for {stack_name}: {exc}") from exc

    # ------------------------------------------------------------------
    # IAM policy inspection
    # ------------------------------------------------------------------

    def get_iam_policy_document(self, role_name: str) -> Dict:
        """
        Fetch all inline and attached policies for an IAM role and return
        the first policy document that contains an S3 statement.

        Returns a dict (deserialized policy JSON) or empty dict.
        """
        # Check inline policies first
        try:
            inline_names = self._iam.list_role_policies(RoleName=role_name).get("PolicyNames", [])
            for policy_name in inline_names:
                resp = self._iam.get_role_policy(RoleName=role_name, PolicyName=policy_name)
                doc = resp.get("PolicyDocument", {})
                if isinstance(doc, str):
                    doc = json.loads(doc)
                # URL-decode if needed (inline policies are URL-encoded)
                import urllib.parse
                raw = resp.get("PolicyDocument", "{}")
                if isinstance(raw, str):
                    doc = json.loads(urllib.parse.unquote(raw))
                logger.info("Found inline policy '%s' for role '%s'", policy_name, role_name)
                return doc
        except ClientError as exc:
            logger.error("Could not list inline policies for role %s: %s", role_name, exc)

        # Fall back to attached managed policies
        try:
            attached = self._iam.list_attached_role_policies(RoleName=role_name).get("AttachedPolicies", [])
            for policy in attached:
                arn = policy["PolicyArn"]
                version_resp = self._iam.get_policy(PolicyArn=arn)
                version_id = version_resp["Policy"]["DefaultVersionId"]
                doc_resp = self._iam.get_policy_version(PolicyArn=arn, VersionId=version_id)
                doc = doc_resp.get("PolicyVersion", {}).get("Document", {})
                logger.info("Found attached policy '%s' for role '%s'", arn, role_name)
                return doc
        except ClientError as exc:
            logger.error("Could not get attached policies for role %s: %s", role_name, exc)

        return {}

    def get_all_policy_statements(self, role_name: str) -> List[Dict]:
        """Return a flat list of all policy statements for an IAM role."""
        doc = self.get_iam_policy_document(role_name)
        return doc.get("Statement", [])

    def get_s3_policy_resources(self, role_name: str) -> List[str]:
        """
        Return all Resource values from S3-related Allow statements for the role.
        Used to verify PLT-9078.
        """
        statements = self.get_all_policy_statements(role_name)
        resources = []
        for stmt in statements:
            if stmt.get("Effect") != "Allow":
                continue
            actions = stmt.get("Action", [])
            if isinstance(actions, str):
                actions = [actions]
            if any("s3:" in a for a in actions):
                res = stmt.get("Resource", [])
                if isinstance(res, str):
                    res = [res]
                resources.extend(res)
        return resources

    # ------------------------------------------------------------------
    # S3 bucket policy inspection
    # ------------------------------------------------------------------

    def get_bucket_policy(self, bucket_name: str) -> Dict:
        """
        Fetch the S3 bucket policy and return it as a dict.
        Returns empty dict if no policy is set.
        """
        try:
            resp = self._s3.get_bucket_policy(Bucket=bucket_name)
            policy_str = resp.get("Policy", "{}")
            return json.loads(policy_str)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchBucketPolicy":
                logger.info("No bucket policy set on %s", bucket_name)
                return {}
            logger.error("Failed to get bucket policy for %s: %s", bucket_name, exc)
            raise

    def get_bucket_policy_sids(self, bucket_name: str) -> List[str]:
        """Return all Statement Sid values from the bucket policy."""
        policy = self.get_bucket_policy(bucket_name)
        return [
            stmt.get("Sid", "")
            for stmt in policy.get("Statement", [])
            if stmt.get("Sid")
        ]

    # ------------------------------------------------------------------
    # Bug-specific check methods
    # ------------------------------------------------------------------

    def check_plt_9078_s3_policy_resource(self, role_name: str, expected_bucket: str) -> Dict:
        """
        PLT-9078: Verify the IAM S3 policy Resource is scoped to specific bucket ARNs
        (not the wildcard `arn:aws:s3:::*`).

        Returns a dict with:
          - 'passed': bool
          - 'resources': list of Resource values found
          - 'wildcard_found': bool
          - 'specific_bucket_found': bool
          - 'message': human-readable summary
        """
        resources = self.get_s3_policy_resources(role_name)
        wildcard_resources = [r for r in resources if r == "arn:aws:s3:::*" or r == "*"]
        expected_arn = f"arn:aws:s3:::{expected_bucket}"
        expected_arn_all = f"arn:aws:s3:::{expected_bucket}/*"

        specific_found = any(
            expected_bucket in r for r in resources
        )
        has_wildcard = len(wildcard_resources) > 0
        passed = specific_found and not has_wildcard

        message = (
            f"PLT-9078 check for role '{role_name}':\n"
            f"  Resources found: {resources}\n"
            f"  Wildcard ('arn:aws:s3:::*') present: {has_wildcard}\n"
            f"  Specific bucket ARN ('{expected_arn}') present: {specific_found}\n"
            f"  Result: {'PASS' if passed else 'FAIL'}"
        )
        logger.info(message)
        return {
            "passed": passed,
            "resources": resources,
            "wildcard_found": has_wildcard,
            "specific_bucket_found": specific_found,
            "message": message,
        }

    def check_plt_9081_failed_buckets(self, stack_name: str) -> Dict:
        """
        PLT-9081 (part 1): Verify that the CloudFormation stack Output 'FailedBuckets' equals [].

        Returns a dict with:
          - 'passed': bool
          - 'failed_buckets_value': raw output value string
          - 'message': human-readable summary
        """
        outputs = self.get_stack_outputs(stack_name)
        raw_value = outputs.get("FailedBuckets", None)

        if raw_value is None:
            message = (
                f"PLT-9081 check: Stack '{stack_name}' has no 'FailedBuckets' output key. "
                f"Available outputs: {list(outputs.keys())}"
            )
            logger.warning(message)
            return {
                "passed": False,
                "failed_buckets_value": None,
                "message": message,
            }

        # Parse as JSON to compare as list
        try:
            parsed = json.loads(raw_value)
        except (json.JSONDecodeError, TypeError):
            parsed = raw_value

        passed = parsed == [] or parsed == "[]"
        message = (
            f"PLT-9081 check (FailedBuckets) for stack '{stack_name}':\n"
            f"  FailedBuckets output: {raw_value!r}\n"
            f"  Parsed value: {parsed!r}\n"
            f"  Expected: []\n"
            f"  Result: {'PASS' if passed else 'FAIL'}"
        )
        logger.info(message)
        return {
            "passed": passed,
            "failed_buckets_value": raw_value,
            "message": message,
        }

    def check_plt_9081_vpc_endpoint_sid(self, bucket_name: str, vpce_id: str) -> Dict:
        """
        PLT-9081 (part 2): Verify that the S3 bucket policy contains a statement
        with Sid == `e6dataVPCEndpointAccess-{vpce_id}`.

        Returns a dict with:
          - 'passed': bool
          - 'sids_found': list of Sid values found
          - 'expected_sid': the expected Sid string
          - 'message': human-readable summary
        """
        expected_sid = f"e6dataVPCEndpointAccess-{vpce_id}"
        sids = self.get_bucket_policy_sids(bucket_name)

        passed = expected_sid in sids
        message = (
            f"PLT-9081 check (VPC endpoint Sid) for bucket '{bucket_name}':\n"
            f"  Expected Sid: '{expected_sid}'\n"
            f"  Sids found in bucket policy: {sids}\n"
            f"  Result: {'PASS' if passed else 'FAIL'}"
        )
        logger.info(message)
        return {
            "passed": passed,
            "sids_found": sids,
            "expected_sid": expected_sid,
            "message": message,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_stack_status(self, stack_name: str) -> Optional[str]:
        """Return the current stack status, or None if the stack does not exist."""
        try:
            resp = self._cf.describe_stacks(StackName=stack_name)
            stacks = resp.get("Stacks", [])
            if stacks:
                return stacks[0]["StackStatus"]
            return None
        except ClientError as exc:
            if "does not exist" in str(exc):
                return None
            raise

    def _get_stack_failure_reason(self, stack_name: str) -> str:
        """Return a human-readable failure reason from stack events."""
        try:
            resp = self._cf.describe_stack_events(StackName=stack_name)
            events = resp.get("StackEvents", [])
            failed_events = [
                e for e in events if "FAILED" in e.get("ResourceStatus", "")
            ]
            if failed_events:
                return failed_events[0].get("ResourceStatusReason", "Unknown")
        except ClientError:
            pass
        return "Unknown"

    def _wait_for_delete(self, stack_name: str, timeout_seconds: int) -> None:
        """Wait until the stack is deleted (status == DELETE_COMPLETE or does not exist)."""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            status = self._get_stack_status(stack_name)
            logger.info("Waiting for delete of stack %s — status: %s", stack_name, status)
            if status is None or status == "DELETE_COMPLETE":
                logger.info("Stack %s deleted", stack_name)
                return
            if status == "DELETE_FAILED":
                raise RuntimeError(f"Stack {stack_name} deletion failed (DELETE_FAILED)")
            time.sleep(10)
        raise TimeoutError(
            f"Stack '{stack_name}' was not deleted within {timeout_seconds}s"
        )
