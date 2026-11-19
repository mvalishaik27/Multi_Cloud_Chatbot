"""
ServiceNow Integration Layer for Multi-Cloud Provisioning.
Simulates and manages ServiceNow Request Item (RITM) lifecycle, state transitions,
assignment groups, audit logs, and ticket closure.
"""

import json
from datetime import datetime
from typing import Optional, Dict, Any, List
from database import (
    get_db_connection,
    log_audit,
    reserve_aws_email,
    assign_aws_email,
    release_aws_email,
)


class ServiceNowClient:
    """Manages ServiceNow RITM tickets, states, assignment groups, and resolution tracking."""

    @staticmethod
    def _generate_ticket_number() -> str:
        """Generates the next sequential ServiceNow RITM number."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ticket_number FROM servicenow_tickets ORDER BY ticket_number DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()

        if row and row["ticket_number"].startswith("RITM"):
            try:
                num = int(row["ticket_number"].replace("RITM", "")) + 1
                return f"RITM{num:07d}"
            except ValueError:
                pass
        return "RITM0010201"

    @classmethod
    def create_request_ticket(cls, payload: Dict[str, Any]) -> str:
        """
        Creates a new ServiceNow Ticket (RITM) based on captured chatbot parameters.
        Initial status: PENDING_PM_APPROVAL.
        """
        ticket_number = cls._generate_ticket_number()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        provider_raw = payload["cloud_provider"].strip().upper()
        if "AWS" in provider_raw:
            cloud_provider = "AWS"
            cost_currency = "$"
        elif "AZURE" in provider_raw:
            cloud_provider = "Azure"
            cost_currency = "₹"
        else:
            cloud_provider = "GCP"
            cost_currency = "₹"

        resource_name = payload["resource_name"].strip()
        project_code = payload["project_code"].strip().upper()
        project_name = payload["project_name"].strip()
        aws_email = payload.get("aws_account_email")

        estimated_cost = float(payload.get("estimated_cost", 0.0))
        project_duration = payload.get("project_duration", "6 Months")
        business_justification = payload.get("business_justification", "").strip()
        primary_owner = payload.get("primary_owner", "").strip()
        secondary_owner = payload.get("secondary_owner", "").strip()
        data_classification = payload.get("data_classification", "Confidential")
        user_access_emails = payload.get("user_access_emails", "")
        acceptable_use_agreed = 1 if payload.get("acceptable_use_agreed", True) else 0

        # Approver Emails from DB lookup
        pm_email = payload.get("pm_email", "")
        bfm_email = payload.get("bfm_email", "")
        biso_email = payload.get("biso_email", "")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO servicenow_tickets (
                ticket_number, cloud_provider, resource_name, project_code, project_name,
                aws_account_email, estimated_cost, cost_currency, project_duration,
                business_justification, primary_owner, secondary_owner, data_classification,
                user_access_emails, acceptable_use_agreed,
                status, current_stage, assignment_group,
                pm_email, bfm_email, biso_email,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                'PENDING_PM_APPROVAL', 'Stage 1: Project Manager Approval', 'Enterprise Cloud Governance',
                ?, ?, ?,
                ?, ?
            )
            """,
            (
                ticket_number,
                cloud_provider,
                resource_name,
                project_code,
                project_name,
                aws_email,
                estimated_cost,
                cost_currency,
                project_duration,
                business_justification,
                primary_owner,
                secondary_owner,
                data_classification,
                user_access_emails,
                acceptable_use_agreed,
                pm_email,
                bfm_email,
                biso_email,
                now,
                now,
            ),
        )
        conn.commit()
        conn.close()

        # If AWS, reserve the allocated email
        if cloud_provider == "AWS" and aws_email:
            reserve_aws_email(aws_email, ticket_number, resource_name)

        log_audit(
            ticket_number=ticket_number,
            action="RITM_CREATED",
            performed_by=primary_owner or "Cloud Chatbot User",
            details=f"Created ticket for {cloud_provider} resource '{resource_name}' (Project: {project_code} - {project_name}). Initial approver: PM ({pm_email}).",
        )

        return ticket_number

    @staticmethod
    def get_ticket(ticket_number: str) -> Optional[Dict[str, Any]]:
        """Retrieves ticket details by ticket number."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM servicenow_tickets WHERE ticket_number = ?", (ticket_number,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_all_tickets() -> List[Dict[str, Any]]:
        """Retrieves all ServiceNow tickets ordered by created_at DESC."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM servicenow_tickets ORDER BY created_at DESC")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    @classmethod
    def assign_to_cloud_team_for_manual(
        cls, ticket_number: str, rejection_stage: str, rejection_reason: str, rejected_by: str
    ) -> bool:
        """
        When a request is rejected by PM, BFM, BISO, or Cloud Team:
        As per requirement: 'If rejected ticket will be assigned to Cloud Team - For Manual Implementation'
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE servicenow_tickets
            SET status = 'ASSIGNED_TO_CLOUD_TEAM_MANUAL',
                current_stage = 'Manual Implementation by Cloud Team',
                assignment_group = 'Cloud Infrastructure Engineering - Manual Implementation',
                rejection_stage = ?,
                rejection_reason = ?,
                updated_at = ?
            WHERE ticket_number = ?
            """,
            (rejection_stage, rejection_reason, now, ticket_number),
        )
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        log_audit(
            ticket_number=ticket_number,
            action="REJECTED_ROUTED_TO_MANUAL",
            performed_by=rejected_by,
            details=f"Rejected at '{rejection_stage}' by {rejected_by}. Reason: {rejection_reason}. Re-assigned to Cloud Team for Manual Implementation.",
        )

        return affected > 0

    @classmethod
    def close_ticket(cls, ticket_number: str, resolution_notes: str, closed_by: str = "Cloud Automation Engine") -> bool:
        """
        Closes the ServiceNow ticket with status 'CLOSED_COMPLETE' and resolution notes.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE servicenow_tickets
            SET status = 'CLOSED_COMPLETE',
                current_stage = 'Closed Complete',
                resolution_notes = ?,
                updated_at = ?,
                closed_at = ?
            WHERE ticket_number = ?
            """,
            (resolution_notes, now, now, ticket_number),
        )
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        ticket = cls.get_ticket(ticket_number)
        if ticket and ticket.get("cloud_provider") == "AWS" and ticket.get("aws_account_email"):
            assign_aws_email(ticket["aws_account_email"], ticket_number)

        log_audit(
            ticket_number=ticket_number,
            action="TICKET_CLOSED_COMPLETE",
            performed_by=closed_by,
            details=f"Ticket marked Closed Complete. Resolution: {resolution_notes}",
        )

        return affected > 0
