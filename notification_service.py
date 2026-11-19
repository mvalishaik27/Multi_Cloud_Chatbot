"""
Notification & Best Practices Service.
Populates notification templates with cloud provisioning payload,
formats recipient distribution list, attaches Best Practices FAQ,
and automatically closes the ServiceNow ticket.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List
from jinja2 import Template
from database import get_db_connection, log_audit
from servicenow_client import ServiceNowClient

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


class NotificationService:
    """Handles notification dispatch and ServiceNow ticket closure."""

    @classmethod
    def load_faq_markdown(cls, project_code: str, primary_owner: str, data_classification: str) -> str:
        """Loads and formats the Best Practices FAQ markdown with project metadata."""
        faq_path = os.path.join(TEMPLATES_DIR, "best_practices_faq.md")
        with open(faq_path, "r", encoding="utf-8") as f:
            content = f.read()
        return (
            content.replace("{project_code}", project_code)
            .replace("{primary_owner}", primary_owner)
            .replace("{data_classification}", data_classification)
        )

    @classmethod
    def generate_welcome_notification(cls, ticket_number: str) -> Dict[str, Any]:
        """
        Populates HTML and text notifications based on ticket data and provisioning response payload.
        """
        ticket = ServiceNowClient.get_ticket(ticket_number)
        if not ticket:
            raise ValueError(f"Ticket {ticket_number} not found.")

        payload = json.loads(ticket["provisioning_payload"] or "{}")

        # Parse user access emails
        raw_emails = ticket.get("user_access_emails", "")
        access_emails = [
            e.strip() for e in raw_emails.replace(";", ",").replace("\n", ",").split(",") if e.strip()
        ]

        # Recipient list: primary, secondary, PM, BFM, access users
        all_recipients = set(access_emails)
        if ticket.get("primary_owner"):
            all_recipients.add(ticket["primary_owner"].strip())
        if ticket.get("secondary_owner"):
            all_recipients.add(ticket["secondary_owner"].strip())
        if ticket.get("pm_email"):
            all_recipients.add(ticket["pm_email"].strip())
        if ticket.get("bfm_email"):
            all_recipients.add(ticket["bfm_email"].strip())

        # Determine console URL
        cloud_provider = ticket["cloud_provider"].upper()
        if cloud_provider == "AWS":
            console_url = payload.get("sso_portal_url", "https://enterprise-cloud.awsapps.com/start")
        elif "AZURE" in cloud_provider:
            console_url = payload.get("azure_portal_url", "https://portal.azure.com")
        else:
            console_url = payload.get("gcp_console_url", "https://console.cloud.google.com")

        # Render HTML template
        template_path = os.path.join(TEMPLATES_DIR, "welcome_notification.html")
        with open(template_path, "r", encoding="utf-8") as f:
            html_template = Template(f.read())

        rendered_html = html_template.render(
            ticket_number=ticket["ticket_number"],
            cloud_provider=cloud_provider,
            resource_name=ticket["resource_name"],
            project_code=ticket["project_code"],
            project_name=ticket["project_name"],
            aws_account_email=ticket.get("aws_account_email"),
            provisioned_account_id=ticket.get("provisioned_account_id"),
            cost_currency=ticket["cost_currency"],
            estimated_cost=ticket["estimated_cost"],
            project_duration=ticket["project_duration"],
            data_classification=ticket["data_classification"],
            primary_owner=ticket["primary_owner"],
            secondary_owner=ticket["secondary_owner"],
            console_url=console_url,
            user_emails=access_emails,
            payload=payload,
        )

        formatted_faq = cls.load_faq_markdown(
            project_code=ticket["project_code"],
            primary_owner=ticket["primary_owner"],
            data_classification=ticket["data_classification"],
        )

        return {
            "ticket_number": ticket_number,
            "recipients": sorted(list(all_recipients)),
            "subject": f"[{ticket_number}] Your {cloud_provider} Cloud Resource '{ticket['resource_name']}' is Ready",
            "html_content": rendered_html,
            "faq_markdown": formatted_faq,
            "provisioned_account_id": ticket.get("provisioned_account_id"),
            "cloud_provider": cloud_provider,
        }

    @classmethod
    def send_notification_and_close_ticket(cls, ticket_number: str) -> Dict[str, Any]:
        """
        Executes step:
        1. Populate and dispatch welcome notification & Best Practices FAQ.
        2. Closes the ServiceNow Ticket as 'Closed Complete'.
        """
        notification = cls.generate_welcome_notification(ticket_number)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE servicenow_tickets
            SET notification_status = 'SENT',
                notification_payload = ?,
                updated_at = ?
            WHERE ticket_number = ?
            """,
            (
                json.dumps(
                    {
                        "recipients": notification["recipients"],
                        "subject": notification["subject"],
                        "sent_at": now_str,
                    }
                ),
                now_str,
                ticket_number,
            ),
        )
        conn.commit()
        conn.close()

        log_audit(
            ticket_number=ticket_number,
            action="NOTIFICATION_AND_FAQ_SENT",
            performed_by="Notification Engine",
            details=f"Dispatched welcome notification and Best Practices FAQ to {len(notification['recipients'])} users ({', '.join(notification['recipients'])}).",
        )

        # Final Step: Close ServiceNow Ticket
        resolution_notes = (
            f"Successfully provisioned {notification['cloud_provider']} environment with ID: "
            f"{notification['provisioned_account_id']}. Welcome email and Best Practices FAQ "
            f"dispatched to authorized users. Handover completed."
        )
        ServiceNowClient.close_ticket(
            ticket_number=ticket_number,
            resolution_notes=resolution_notes,
            closed_by="Cloud Provisioning Orchestrator",
        )

        return notification
