"""
CLI Interface for Enterprise Multi-Cloud Provisioning Chatbot.
Provides an interactive terminal session to chat with the bot, view prompts,
simulate 4-stage approvals, trigger provisioning, and inspect generated artifacts.
"""

import sys
import time
from database import init_database, get_all_projects, get_all_aws_emails
from servicenow_client import ServiceNowClient
from approval_workflow import ApprovalWorkflow
from cloud_provisioner import CloudProvisioner
from notification_service import NotificationService
from chatbot_engine import ChatbotEngine


def print_banner():
    print("=" * 75)
    print("      ENTERPRISE MULTI-CLOUD PROVISIONING CHATBOT (AWS / Azure / GCP)      ")
    print("=" * 75)
    print("Commands: 'help', 'projects', 'emails', 'status <TICKET>', 'reset', 'quit'")
    print("-" * 75)


def run_approval_and_provisioning_flow(ticket_number: str):
    """Simulates the 4-stage sequential approval and subsequent provisioning via CLI."""
    print(f"\n" + "=" * 60)
    print(f"  ORCHESTRATING WORKFLOW FOR TICKET: {ticket_number}")
    print("=" * 60)

    ticket = ServiceNowClient.get_ticket(ticket_number)
    if not ticket:
        print(f"Error: Ticket {ticket_number} not found.")
        return

    # Stage 1: PM Approval
    print(f"\n[Stage 1/4] Project Manager Approval -> Approver: {ticket['pm_email']}")
    decision = input(">> PM Decision [A]pprove / [R]eject (default: A): ").strip().lower()
    if decision == "r":
        reason = input("Enter rejection comments: ").strip() or "Budget/Priority misalignment."
        ApprovalWorkflow.process_pm_decision(ticket_number, "REJECT", ticket["pm_email"], reason)
        print(f" Ticket rejected by PM. Assigned to: Cloud Infrastructure Engineering - Manual Implementation.")
        return
    else:
        ApprovalWorkflow.process_pm_decision(ticket_number, "APPROVE", ticket["pm_email"], "PM Approved via CLI.")
        print("✓ Stage 1 Approved.")

    # Stage 2: BFM Approval
    print(f"\n[Stage 2/4] Business Financial Manager Approval -> Approver: {ticket['bfm_email']}")
    decision = input(">> BFM Decision [A]pprove / [R]eject (default: A): ").strip().lower()
    if decision == "r":
        reason = input("Enter rejection comments: ").strip() or "Budget ceiling exceeded."
        ApprovalWorkflow.process_bfm_decision(ticket_number, "REJECT", ticket["bfm_email"], reason)
        print(f" Ticket rejected by BFM. Assigned to: Cloud Infrastructure Engineering - Manual Implementation.")
        return
    else:
        ApprovalWorkflow.process_bfm_decision(ticket_number, "APPROVE", ticket["bfm_email"], "BFM Approved via CLI.")
        print("✓ Stage 2 Approved.")

    # Stage 3: BISO Approval
    print(f"\n[Stage 3/4] BISO Security Approval -> Approver: {ticket['biso_email']}")
    decision = input(">> BISO Decision [A]pprove / [R]eject (default: A): ").strip().lower()
    if decision == "r":
        reason = input("Enter rejection comments: ").strip() or "Data classification risk."
        ApprovalWorkflow.process_biso_decision(ticket_number, "REJECT", ticket["biso_email"], reason)
        print(f" Ticket rejected by BISO. Assigned to: Cloud Infrastructure Engineering - Manual Implementation.")
        return
    else:
        ApprovalWorkflow.process_biso_decision(ticket_number, "APPROVE", ticket["biso_email"], "BISO Approved via CLI.")
        print("✓ Stage 3 Approved.")

    # Stage 4: Cloud Team Review & Technical Inputs
    print("\n[Stage 4/4] Cloud Engineering Team Final Review")
    ou_input = input(">> Target Organizational Unit / Management Group [default: ou-core-workloads-01]: ").strip()
    ou_val = ou_input or "ou-core-workloads-01"
    cidr_input = input(">> Landing Zone VPC CIDR [default: 10.150.0.0/20]: ").strip()
    cidr_val = cidr_input or "10.150.0.0/20"

    cloud_inputs = {"target_ou": ou_val, "vpc_cidr": cidr_val}
    ok, msg, trigger = ApprovalWorkflow.process_cloud_team_decision(
        ticket_number=ticket_number,
        decision="APPROVE",
        approver_email="cloud-operations@enterprise.corp",
        comments="Approved by Cloud Engineering Team with network inputs.",
        cloud_inputs=cloud_inputs,
    )
    print("✓ Stage 4 Approved. All approvals received!")

    # Provisioning
    print(f"\n🚀 Triggering automated {ticket['cloud_provider']} provisioning...")
    final_payload = None
    for step in CloudProvisioner.provision_resource(ticket_number, simulated_delay=0.4):
        pct = step.get("percent", 0)
        status = step.get("status", "")
        bar = "#" * (pct // 5) + "-" * (20 - (pct // 5))
        print(f"\r[{bar}] {pct}% - {status}", end="", flush=True)
        if pct == 100:
            final_payload = step.get("payload")

    print("\n\n🎉 Cloud Resource Provisioning Succeeded!")
    res_id = final_payload.get("account_id") or final_payload.get("subscription_id") or final_payload.get("project_id")
    print(f"   Resource Identifier: {res_id}")
    print(f"   Provider: {final_payload.get('cloud_provider')}")

    # Notifications & FAQ
    print("\n📨 Generating welcome notification and populating Best Practices FAQ...")
    notif = NotificationService.send_notification_and_close_ticket(ticket_number)
    print(f"✓ Notifications and FAQ dispatched to {len(notif['recipients'])} users:")
    for r in notif["recipients"]:
        print(f"  - {r}")

    # Verify closure
    updated = ServiceNowClient.get_ticket(ticket_number)
    print(f"\n🔒 ServiceNow Ticket Status: {updated['status']}")
    print(f"   Resolution Notes: {updated['resolution_notes']}")
    print("=" * 60 + "\n")


def main():
    init_database()
    engine = ChatbotEngine()
    print_banner()

    # Initial prompt
    print(engine.get_prompt_for_step())
    print("-" * 75)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting session. Goodbye!")
            sys.exit(0)

        if not user_input:
            continue

        if user_input.lower() in ["quit", "exit"]:
            print("Goodbye!")
            break

        # Process user message through engine
        response = engine.process_user_message(user_input)
        print(f"\nBot: {response}")

        # Check if a ticket was created
        if engine.completed and engine.created_ticket_number:
            ticket_num = engine.created_ticket_number
            engine.created_ticket_number = None  # prevent re-trigger
            print("\n" + "=" * 60)
            run_flow = input(f"Would you like to run the 4-Stage Approval & Provisioning simulation for {ticket_num} now? (Y/n): ").strip().lower()
            if run_flow in ["", "y", "yes"]:
                run_approval_and_provisioning_flow(ticket_num)


if __name__ == "__main__":
    main()
