"""
Comprehensive test suite for Enterprise Multi-Cloud Provisioning Chatbot.
Verifies:
1. SQLite Database initialization and project / AWS email pool seeding
2. Project Code lookup (Project Name, PM Email, BFM Email, BISO Email)
3. AWS Email pool allocation and reservation
4. ServiceNow Ticket creation (RITM format)
5. 4-Stage Approval Workflow (PM -> BFM -> BISO -> Cloud Team)
6. Rejection Workflow (routing to 'Cloud Team - For Manual Implementation')
7. Multi-cloud Resource Provisioning (AWS, Azure, GCP with currency validation)
8. Notification and Best Practices FAQ generation populated with payload
9. ServiceNow Ticket Closure (CLOSED_COMPLETE)
"""

import unittest
from database import (
    init_database,
    get_project_by_code,
    get_available_aws_email,
    reserve_aws_email,
    get_all_projects,
    get_audit_logs,
)
from servicenow_client import ServiceNowClient
from approval_workflow import ApprovalWorkflow
from cloud_provisioner import CloudProvisioner
from notification_service import NotificationService


class TestMultiCloudProvisioning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print("\n=== Initializing Test Suite & Database ===")
        init_database()
        # Reset pool emails to AVAILABLE for clean repeatable test runs
        from database import get_db_connection
        conn = get_db_connection()
        conn.execute("UPDATE aws_email_pool SET status = 'AVAILABLE', assigned_ticket = NULL, assigned_account_name = NULL")
        conn.commit()
        conn.close()

    def test_01_database_project_lookup(self):
        """Test retrieving project details and emails from SQLite."""
        print("\n--- Test 1: Project Lookup by Code ---")
        project = get_project_by_code("PRJ-AI-101")
        self.assertIsNotNone(project)
        self.assertEqual(project["project_name"], "Enterprise GenAI Discovery Platform")
        self.assertEqual(project["pm_email"], "sarah.jenkins@enterprise.corp")
        self.assertEqual(project["bfm_email"], "michael.chang@enterprise.corp")
        self.assertEqual(project["biso_email"], "biso-ai@enterprise.corp")
        print(f"✓ Project: {project['project_name']} (PM: {project['pm_email']})")

        all_projects = get_all_projects()
        self.assertGreaterEqual(len(all_projects), 5)
        print(f"✓ Total active projects seeded: {len(all_projects)}")

    def test_02_aws_email_pool_allocation(self):
        """Test AWS account root email retrieval and reservation from pool."""
        print("\n--- Test 2: AWS Email Pool Allocation ---")
        email = get_available_aws_email()
        self.assertIsNotNone(email)
        self.assertIn("@enterprise.corp", email)
        print(f"✓ Retrieved available email: {email}")

        # Reserve it
        ticket_id = "RITM0099999"
        success = reserve_aws_email(email, ticket_id, "test-aws-sandbox")
        self.assertTrue(success)
        print(f"✓ Reserved email {email} for ticket {ticket_id}")

    def test_03_servicenow_ticket_lifecycle_and_approval_flow(self):
        """Test happy path: RITM creation -> 4-stage sequential approval -> Provisioning -> Notification -> Ticket Close."""
        print("\n--- Test 3: Happy Path AWS Provisioning ---")
        
        # 1. Create ticket
        payload = {
            "cloud_provider": "AWS",
            "resource_name": "aws-production-app",
            "project_code": "PRJ-AI-101",
            "project_name": "Enterprise GenAI Discovery Platform",
            "aws_account_email": get_available_aws_email(),
            "estimated_cost": 2500.0,
            "project_duration": "12 Months",
            "business_justification": "Generative AI customer support platform hosting",
            "primary_owner": "lead.engineer@enterprise.com",
            "secondary_owner": "backup.lead@enterprise.com",
            "data_classification": "Confidential",
            "user_access_emails": "dev1@enterprise.com, dev2@enterprise.com",
            "acceptable_use_agreed": True,
            "pm_email": "sarah.jenkins@enterprise.corp",
            "bfm_email": "michael.chang@enterprise.corp",
            "biso_email": "biso-ai@enterprise.corp",
        }
        ticket_number = ServiceNowClient.create_request_ticket(payload)
        self.assertTrue(ticket_number.startswith("RITM"))
        
        ticket = ServiceNowClient.get_ticket(ticket_number)
        self.assertEqual(ticket["status"], "PENDING_PM_APPROVAL")
        print(f"✓ Ticket Created: {ticket_number} [{ticket['status']}]")

        # 2. Stage 1: PM Approval
        ok, msg = ApprovalWorkflow.process_pm_decision(
            ticket_number=ticket_number,
            decision="APPROVE",
            approver_email=ticket["pm_email"],
            comments="Approved by Project Manager",
        )
        self.assertTrue(ok)
        ticket = ServiceNowClient.get_ticket(ticket_number)
        self.assertEqual(ticket["status"], "PENDING_BFM_APPROVAL")
        print(f"✓ Stage 1 (PM) Approved -> {ticket['status']}")

        # 3. Stage 2: BFM Approval
        ok, msg = ApprovalWorkflow.process_bfm_decision(
            ticket_number=ticket_number,
            decision="APPROVE",
            approver_email=ticket["bfm_email"],
            comments="Financial budget verified",
        )
        self.assertTrue(ok)
        ticket = ServiceNowClient.get_ticket(ticket_number)
        self.assertEqual(ticket["status"], "PENDING_BISO_APPROVAL")
        print(f"✓ Stage 2 (BFM) Approved -> {ticket['status']}")

        # 4. Stage 3: BISO Approval
        ok, msg = ApprovalWorkflow.process_biso_decision(
            ticket_number=ticket_number,
            decision="APPROVE",
            approver_email=ticket["biso_email"],
            comments="Confidential data controls verified",
        )
        self.assertTrue(ok)
        ticket = ServiceNowClient.get_ticket(ticket_number)
        self.assertEqual(ticket["status"], "PENDING_CLOUD_TEAM_APPROVAL")
        print(f"✓ Stage 3 (BISO) Approved -> {ticket['status']}")

        # 5. Stage 4: Cloud Team Approval with optional technical inputs
        cloud_inputs = {
            "target_ou": "Workloads/Production",
            "primary_region": "us-east-1",
            "network_cidr": "10.100.0.0/16",
        }
        ok, msg, trigger = ApprovalWorkflow.process_cloud_team_decision(
            ticket_number=ticket_number,
            decision="APPROVE",
            approver_email="cloud-governance@enterprise.corp",
            comments="Approved and inputs attached",
            cloud_inputs=cloud_inputs,
        )
        self.assertTrue(ok)
        self.assertTrue(trigger)
        ticket = ServiceNowClient.get_ticket(ticket_number)
        self.assertEqual(ticket["status"], "PROVISIONING_TRIGGERED")
        print(f"✓ Stage 4 (Cloud Team) Approved -> {ticket['status']}")

        # 6. Trigger Provisioning
        final_payload = None
        for step in CloudProvisioner.provision_resource(ticket_number, simulated_delay=0.01):
            if step.get("percent") == 100:
                final_payload = step.get("payload")
        
        self.assertIsNotNone(final_payload)
        self.assertEqual(final_payload["status"], "ACTIVE")
        self.assertEqual(len(final_payload["account_id"]), 12)
        print(f"✓ Provisioned AWS Account: {final_payload['account_id']} ({final_payload['account_name']})")

        # 7. Send Notifications & FAQ and Close Ticket
        notif = NotificationService.send_notification_and_close_ticket(ticket_number)
        self.assertIn("recipients", notif)
        self.assertIn("html_content", notif)
        self.assertIn("faq_markdown", notif)

        # Verify ticket status in DB
        updated_ticket = ServiceNowClient.get_ticket(ticket_number)
        self.assertEqual(updated_ticket["status"], "CLOSED_COMPLETE")
        self.assertIsNotNone(updated_ticket["closed_at"])
        print(f"✓ Notifications & FAQ generated; Ticket Closed: {updated_ticket['status']}")

    def test_04_rejection_routing_to_cloud_team_manual(self):
        """Test requirement: If rejected at any stage, ticket is assigned to Cloud Team for Manual Implementation."""
        print("\n--- Test 4: Rejection Handling Workflow ---")
        payload = {
            "cloud_provider": "Azure",
            "resource_name": "sub-fin-analytics-dev",
            "project_code": "PRJ-FIN-202",
            "project_name": "Core Financial Modernization",
            "estimated_cost": 75000.0,
            "project_duration": "6 Months",
            "business_justification": "Financial forecasting pipeline",
            "primary_owner": "fin.lead@enterprise.com",
            "secondary_owner": "fin.backup@enterprise.com",
            "data_classification": "Restricted",
            "user_access_emails": "analyst1@enterprise.com",
            "acceptable_use_agreed": True,
            "pm_email": "robert.sterling@enterprise.corp",
            "bfm_email": "alicia.vance@enterprise.corp",
            "biso_email": "biso-fin@enterprise.corp",
        }
        ticket_number = ServiceNowClient.create_request_ticket(payload)
        print(f"✓ Created Azure Ticket: {ticket_number}")

        # PM rejects ticket
        ok, msg = ApprovalWorkflow.process_pm_decision(
            ticket_number=ticket_number,
            decision="REJECT",
            approver_email="robert.sterling@enterprise.corp",
            comments="Budget justification requires non-standard architecture. Escalating to Cloud Team.",
        )
        self.assertTrue(ok)

        # Check ServiceNow ticket state
        updated_ticket = ServiceNowClient.get_ticket(ticket_number)
        self.assertEqual(updated_ticket["status"], "ASSIGNED_TO_CLOUD_TEAM_MANUAL")
        self.assertEqual(
            updated_ticket["assignment_group"],
            "Cloud Infrastructure Engineering - Manual Implementation"
        )
        print(f"✓ Rejection successfully routed ticket to: {updated_ticket['assignment_group']} [Status: {updated_ticket['status']}]")

    def test_05_gcp_project_creation_currency_rule(self):
        """Test GCP project provisioning with INR currency requirement."""
        print("\n--- Test 5: GCP Project Provisioning with INR (₹) ---")
        payload = {
            "cloud_provider": "GCP",
            "resource_name": "prj-data-mesh-prod",
            "project_code": "PRJ-DATA-303",
            "project_name": "Global Data Analytics Lakehouse",
            "estimated_cost": 120000.0,
            "project_duration": "24 Months",
            "business_justification": "BigQuery & Dataproc enterprise data mesh",
            "primary_owner": "data.architect@enterprise.com",
            "secondary_owner": "data.engineer@enterprise.com",
            "data_classification": "Internal",
            "user_access_emails": "data.team@enterprise.com",
            "acceptable_use_agreed": True,
            "pm_email": "anita.patel@enterprise.corp",
            "bfm_email": "marcus.brody@enterprise.corp",
            "biso_email": "biso-data@enterprise.corp",
        }
        ticket_number = ServiceNowClient.create_request_ticket(payload)
        ticket = ServiceNowClient.get_ticket(ticket_number)
        self.assertEqual(ticket["cost_currency"], "₹")
        print(f"✓ Created GCP Ticket {ticket_number} with Budget: ₹{ticket['estimated_cost']}")


if __name__ == "__main__":
    unittest.main()
