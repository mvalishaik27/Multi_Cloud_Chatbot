"""
Approval Workflow Engine for Multi-Cloud Provisioning.
Orchestrates sequential approvals:
1. Project Manager (from SQLite DB based on Project Code)
2. BFM (from SQLite DB based on Project Code)
3. BISO (Business Information Security Officer)
4. Cloud Team (Review + Add required technical inputs)

If rejected at any stage, re-assigns ticket to Cloud Team for Manual Implementation.
Upon final Cloud Team approval, triggers automated provisioning.
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from database import get_db_connection, log_audit
from servicenow_client import ServiceNowClient


class ApprovalWorkflow:
    """Handles the multi-stage approval pipeline."""

    @classmethod
    def process_pm_decision(
        cls, ticket_number: str, decision: str, approver_email: str, comments: str = ""
    ) -> Tuple[bool, str]:
        """
        Stage 1: Project Manager Decision.
        decision: 'APPROVE' or 'REJECT'
        """
        ticket = ServiceNowClient.get_ticket(ticket_number)
        if not ticket:
            return False, f"Ticket {ticket_number} not found."
        if ticket["status"] != "PENDING_PM_APPROVAL":
            return False, f"Ticket is not awaiting PM Approval (current status: {ticket['status']})."

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if decision.upper() == "APPROVE":
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE servicenow_tickets
                SET pm_status = 'APPROVED',
                    pm_comment = ?,
                    pm_action_date = ?,
                    status = 'PENDING_BFM_APPROVAL',
                    current_stage = 'Stage 2: Business Financial Manager (BFM) Approval',
                    updated_at = ?
                WHERE ticket_number = ?
                """,
                (comments or "Project requirements and resource allocation approved.", now, now, ticket_number),
            )
            conn.commit()
            conn.close()

            log_audit(
                ticket_number=ticket_number,
                action="PM_APPROVED",
                performed_by=approver_email or ticket["pm_email"],
                details=f"PM approved request. Moved to BFM approval ({ticket['bfm_email']}). Comments: {comments}",
            )
            return True, f"PM Approved! Ticket moved to Stage 2: BFM Approval ({ticket['bfm_email']})."

        else:
            # Rejected by PM -> Route to Cloud Team for Manual Implementation
            ServiceNowClient.assign_to_cloud_team_for_manual(
                ticket_number=ticket_number,
                rejection_stage="Stage 1: Project Manager Approval",
                rejection_reason=comments or "Rejected by Project Manager during feasibility/priority review.",
                rejected_by=approver_email or ticket["pm_email"],
            )
            return True, "Request rejected by PM. Assigned to Cloud Team for Manual Implementation."

    @classmethod
    def process_bfm_decision(
        cls, ticket_number: str, decision: str, approver_email: str, comments: str = ""
    ) -> Tuple[bool, str]:
        """
        Stage 2: BFM (Business Financial Manager) Decision.
        decision: 'APPROVE' or 'REJECT'
        """
        ticket = ServiceNowClient.get_ticket(ticket_number)
        if not ticket:
            return False, f"Ticket {ticket_number} not found."
        if ticket["status"] != "PENDING_BFM_APPROVAL":
            return False, f"Ticket is not awaiting BFM Approval (current status: {ticket['status']})."

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if decision.upper() == "APPROVE":
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE servicenow_tickets
                SET bfm_status = 'APPROVED',
                    bfm_comment = ?,
                    bfm_action_date = ?,
                    status = 'PENDING_BISO_APPROVAL',
                    current_stage = 'Stage 3: Business Information Security Officer (BISO) Approval',
                    updated_at = ?
                WHERE ticket_number = ?
                """,
                (
                    comments
                    or f"Budget of {ticket['cost_currency']}{ticket['estimated_cost']}/month confirmed for duration {ticket['project_duration']}.",
                    now,
                    now,
                    ticket_number,
                ),
            )
            conn.commit()
            conn.close()

            log_audit(
                ticket_number=ticket_number,
                action="BFM_APPROVED",
                performed_by=approver_email or ticket["bfm_email"],
                details=f"BFM approved budget. Moved to BISO approval ({ticket['biso_email']}). Comments: {comments}",
            )
            return True, f"BFM Approved! Ticket moved to Stage 3: BISO Approval ({ticket['biso_email']})."

        else:
            ServiceNowClient.assign_to_cloud_team_for_manual(
                ticket_number=ticket_number,
                rejection_stage="Stage 2: Business Financial Manager Approval",
                rejection_reason=comments or "Budget rejected or insufficient financial justification by BFM.",
                rejected_by=approver_email or ticket["bfm_email"],
            )
            return True, "Request rejected by BFM. Assigned to Cloud Team for Manual Implementation."

    @classmethod
    def process_biso_decision(
        cls, ticket_number: str, decision: str, approver_email: str, comments: str = ""
    ) -> Tuple[bool, str]:
        """
        Stage 3: BISO (Business Information Security Officer) Decision.
        decision: 'APPROVE' or 'REJECT'
        """
        ticket = ServiceNowClient.get_ticket(ticket_number)
        if not ticket:
            return False, f"Ticket {ticket_number} not found."
        if ticket["status"] != "PENDING_BISO_APPROVAL":
            return False, f"Ticket is not awaiting BISO Approval (current status: {ticket['status']})."

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if decision.upper() == "APPROVE":
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE servicenow_tickets
                SET biso_status = 'APPROVED',
                    biso_comment = ?,
                    biso_action_date = ?,
                    status = 'PENDING_CLOUD_TEAM_APPROVAL',
                    current_stage = 'Stage 4: Cloud Engineering Team Review & Inputs',
                    assignment_group = 'Cloud Engineering & Architecture',
                    updated_at = ?
                WHERE ticket_number = ?
                """,
                (
                    comments
                    or f"Data classification '{ticket['data_classification']}' verified. Security guardrails required.",
                    now,
                    now,
                    ticket_number,
                ),
            )
            conn.commit()
            conn.close()

            log_audit(
                ticket_number=ticket_number,
                action="BISO_APPROVED",
                performed_by=approver_email or ticket["biso_email"],
                details=f"BISO approved security & data posture. Moved to Cloud Team final review. Comments: {comments}",
            )
            return True, "BISO Approved! Ticket moved to Stage 4: Cloud Team Review & Inputs."

        else:
            ServiceNowClient.assign_to_cloud_team_for_manual(
                ticket_number=ticket_number,
                rejection_stage="Stage 3: Business Information Security Officer (BISO) Approval",
                rejection_reason=comments or "Security or data classification concerns raised by BISO.",
                rejected_by=approver_email or ticket["biso_email"],
            )
            return True, "Request rejected by BISO. Assigned to Cloud Team for Manual Implementation."

    @classmethod
    def process_cloud_team_decision(
        cls,
        ticket_number: str,
        decision: str,
        approver_email: str,
        comments: str = "",
        cloud_inputs: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str, bool]:
        """
        Stage 4: Cloud Team Review & Approval.
        Can add technical inputs (e.g. Target OU, VPC CIDR, Security Baseline, IAM role mapping).
        Returns: (success, message, trigger_provisioning)
        """
        ticket = ServiceNowClient.get_ticket(ticket_number)
        if not ticket:
            return False, f"Ticket {ticket_number} not found.", False
        if ticket["status"] != "PENDING_CLOUD_TEAM_APPROVAL":
            return False, f"Ticket is not awaiting Cloud Team Approval (current status: {ticket['status']}).", False

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        inputs_json = json.dumps(cloud_inputs or {})

        if decision.upper() == "APPROVE":
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE servicenow_tickets
                SET cloud_team_status = 'APPROVED',
                    cloud_team_comment = ?,
                    cloud_team_action_date = ?,
                    cloud_team_inputs = ?,
                    status = 'PROVISIONING_TRIGGERED',
                    current_stage = 'Automated Cloud Provisioning in Progress',
                    updated_at = ?
                WHERE ticket_number = ?
                """,
                (
                    comments or "Cloud architecture and landing zone inputs validated. Approved for automated provisioning.",
                    now,
                    inputs_json,
                    now,
                    ticket_number,
                ),
            )
            conn.commit()
            conn.close()

            log_audit(
                ticket_number=ticket_number,
                action="CLOUD_TEAM_APPROVED",
                performed_by=approver_email or "cloud-leads@enterprise.corp",
                details=f"Cloud Team approved with inputs: {inputs_json}. Triggering automated cloud provisioning.",
            )
            return True, "All approvals complete! Automated account/subscription/project creation triggered.", True

        else:
            # Cloud Team rejected -> assign to Cloud Team for manual implementation
            ServiceNowClient.assign_to_cloud_team_for_manual(
                ticket_number=ticket_number,
                rejection_stage="Stage 4: Cloud Team Approval",
                rejection_reason=comments or "Non-standard architecture or landing zone exceptions require manual setup.",
                rejected_by=approver_email or "cloud-leads@enterprise.corp",
            )
            return True, "Cloud Team requested manual implementation. Assigned to Cloud Team Manual Queue.", False
