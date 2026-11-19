"""
Cloud Provisioning Engine for Multi-Cloud Chatbot.
Handles automated provisioning across AWS, Azure, and GCP.
Simulates realistic enterprise account factory APIs with progressive status checks,
builds complete landing zone payloads, and marks resources ready for handoff.
"""

import time
import json
import uuid
import random
from datetime import datetime
from typing import Dict, Any, Generator
from database import get_db_connection, log_audit, assign_aws_email
from servicenow_client import ServiceNowClient


class CloudProvisioner:
    """Automates and monitors cloud account, subscription, and project provisioning."""

    @classmethod
    def provision_resource(
        cls, ticket_number: str, simulated_delay: float = 0.5
    ) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
        """
        Executes cloud resource creation with progressive milestone reporting.
        Yields intermediate status updates for UI progress bars and waits until active.
        Returns final provisioning payload dictionary.
        """
        ticket = ServiceNowClient.get_ticket(ticket_number)
        if not ticket:
            raise ValueError(f"Ticket {ticket_number} not found.")

        provider = ticket["cloud_provider"].upper()
        resource_name = ticket["resource_name"]
        cloud_inputs = json.loads(ticket["cloud_team_inputs"] or "{}")

        # Update ticket status to PROVISIONING_IN_PROGRESS
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE servicenow_tickets 
            SET status = 'PROVISIONING_IN_PROGRESS',
                current_stage = 'Cloud Infrastructure Provisioning in Progress',
                provisioning_status = 'IN_PROGRESS',
                updated_at = ?
            WHERE ticket_number = ?
            """,
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ticket_number),
        )
        conn.commit()
        conn.close()

        log_audit(
            ticket_number=ticket_number,
            action="PROVISIONING_STARTED",
            performed_by="Automated Cloud Provisioner",
            details=f"Initiating {provider} provisioning for '{resource_name}'.",
        )

        steps = [
            (10, f"Validating {provider} organization quotas and IAM permissions..."),
            (30, f"Invoking {provider} Account Factory / Provisioning API..."),
            (55, f"Allocating network boundary & security guardrails..."),
            (75, f"Configuring budget alert ({ticket['cost_currency']}{ticket['estimated_cost']}/month)..."),
            (90, f"Enforcing IAM roles, SCPs/Azure Policies/Org Policies & tagging..."),
            (100, f"{provider} environment successfully provisioned and verified!"),
        ]

        for percent, message in steps:
            yield {"percent": percent, "status": message}
            if simulated_delay > 0:
                time.sleep(simulated_delay)

        # Generate realistic Provider-specific payload
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if provider == "AWS":
            account_id = "".join([str(random.randint(0, 9)) for _ in range(12)])
            payload = {
                "cloud_provider": "AWS",
                "account_name": resource_name,
                "account_id": account_id,
                "root_email": ticket.get("aws_account_email"),
                "organizational_unit": cloud_inputs.get("target_ou", "ou-core-workloads-01"),
                "iam_role_arn": f"arn:aws:iam::{account_id}:role/OrganizationAccountAccessRole",
                "sso_portal_url": "https://enterprise-cloud.awsapps.com/start",
                "landing_zone_vpc": cloud_inputs.get("vpc_cidr", "10.140.0.0/20"),
                "budget_alert": {
                    "monthly_limit": f"${ticket['estimated_cost']}",
                    "thresholds": ["50%", "80%", "100%"],
                    "notification_emails": [ticket["primary_owner"], ticket["bfm_email"]],
                },
                "security_controls": [
                    "AWS Organizations SCP: Deny Root User API",
                    "AWS Control Tower Guardrails: S3 Public Access Block Enforced",
                    "CloudTrail & GuardDuty Centralized to Security Account",
                ],
                "provisioned_at": now_str,
            }
            res_id = account_id

        elif provider == "AZURE" or provider == "Azure":
            sub_id = str(uuid.uuid4())
            payload = {
                "cloud_provider": "Azure",
                "subscription_name": resource_name,
                "subscription_id": sub_id,
                "tenant_id": "8a329d44-2f22-411a-9892-91e84a20b831",
                "management_group": cloud_inputs.get("target_ou", "mg-enterprise-applications"),
                "billing_account": "EA-Enterprise-920194",
                "azure_portal_url": f"https://portal.azure.com/#@enterprise.corp/resource/subscriptions/{sub_id}",
                "virtual_network": cloud_inputs.get("vpc_cidr", "10.220.0.0/20"),
                "budget_alert": {
                    "monthly_limit": f"₹{ticket['estimated_cost']}",
                    "thresholds": ["50%", "80%", "100%"],
                    "notification_emails": [ticket["primary_owner"], ticket["bfm_email"]],
                },
                "security_controls": [
                    "Azure Policy: Deny Public Storage Blobs",
                    "Defender for Cloud Standard Tier enabled",
                    "Azure Activity Log forwarded to Central Log Analytics",
                ],
                "provisioned_at": now_str,
            }
            res_id = sub_id

        else:  # GCP
            random_suffix = random.randint(10000, 99999)
            clean_name = resource_name.lower().replace(" ", "-").replace("_", "-")[:20]
            project_id = f"{clean_name}-{random_suffix}"
            project_number = "".join([str(random.randint(0, 9)) for _ in range(12)])
            payload = {
                "cloud_provider": "GCP",
                "project_name": resource_name,
                "project_id": project_id,
                "project_number": project_number,
                "organization_id": "organizations/7821940182",
                "folder_id": cloud_inputs.get("target_ou", "folders/8910248102"),
                "billing_account_id": "01A8E2-29FB40-8C9102",
                "gcp_console_url": f"https://console.cloud.google.com/welcome?project={project_id}",
                "vpc_network": cloud_inputs.get("vpc_cidr", "10.240.0.0/20"),
                "budget_alert": {
                    "monthly_limit": f"₹{ticket['estimated_cost']}",
                    "thresholds": ["50%", "80%", "100%"],
                    "notification_emails": [ticket["primary_owner"], ticket["bfm_email"]],
                },
                "security_controls": [
                    "Organization Policy: compute.restrictPublicIp = ENFORCED",
                    "Organization Policy: storage.uniformBucketLevelAccess = ENFORCED",
                    "Security Command Center Premium Active",
                ],
                "provisioned_at": now_str,
            }
            res_id = project_id

        # Update database with provisioned payload and status
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE servicenow_tickets 
            SET status = 'PROVISIONED',
                current_stage = 'Cloud Resource Provisioned - Handover Pending',
                provisioning_status = 'COMPLETED',
                provisioned_account_id = ?,
                provisioning_payload = ?,
                updated_at = ?
            WHERE ticket_number = ?
            """,
            (res_id, json.dumps(payload), now_str, ticket_number),
        )
        conn.commit()
        conn.close()

        # If AWS, mark email as permanently ASSIGNED
        if provider == "AWS" and ticket.get("aws_account_email"):
            assign_aws_email(ticket["aws_account_email"], ticket_number)

        log_audit(
            ticket_number=ticket_number,
            action="PROVISIONING_COMPLETED",
            performed_by="Automated Cloud Provisioner",
            details=f"Successfully provisioned {provider} resource '{resource_name}' with ID: {res_id}.",
        )

        return payload

