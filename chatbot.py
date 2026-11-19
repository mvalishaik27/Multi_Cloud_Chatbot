"""
Enterprise Multi-Cloud Provisioning Chatbot.
Interactive, conversational assistant for AWS, Azure, and GCP cloud requests.

Run with:
    streamlit run chatbot.py
"""

import os
import json
import time
import streamlit as st
import pandas as pd

from database import (
    init_database,
    get_all_projects,
    get_project_by_code,
    get_all_aws_emails,
    get_available_aws_email,
    get_audit_logs,
)
from servicenow_client import ServiceNowClient
from approval_workflow import ApprovalWorkflow
from cloud_provisioner import CloudProvisioner
from notification_service import NotificationService
from chatbot_engine import ChatbotEngine, DATA_CLASSIFICATIONS

# Initialize database
init_database()

st.set_page_config(
    page_title="Multi-Cloud Provisioning Chatbot",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
<style>
    .main-header {
        font-size: 26px;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 2px;
    }
    .sub-header {
        font-size: 14px;
        color: #4B5563;
        margin-bottom: 18px;
    }
    .badge-aws {
        background-color: #FF9900;
        color: white;
        padding: 3px 8px;
        border-radius: 10px;
        font-size: 12px;
        font-weight: bold;
    }
    .badge-azure {
        background-color: #0078D4;
        color: white;
        padding: 3px 8px;
        border-radius: 10px;
        font-size: 12px;
        font-weight: bold;
    }
    .badge-gcp {
        background-color: #34A853;
        color: white;
        padding: 3px 8px;
        border-radius: 10px;
        font-size: 12px;
        font-weight: bold;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Load Acceptable Use Agreement file content for download
AUA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "documents", "Acceptable_Use_Agreement.md")
with open(AUA_PATH, "r", encoding="utf-8") as f:
    AUA_TEXT = f.read()

# Sidebar: Live Request State & Governance Metrics
st.sidebar.image("https://img.icons8.com/clouds/200/cloud.png", width=80)
st.sidebar.markdown("### **Cloud Governance Assistant**")
st.sidebar.markdown("*Enterprise Provisioning Chatbot*")
st.sidebar.divider()

# Session State for Chatbot
if "chatbot_engine" not in st.session_state:
    st.session_state.chatbot_engine = ChatbotEngine()

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {"role": "assistant", "content": st.session_state.chatbot_engine.get_prompt_for_step()}
    ]

# Sidebar Live Captured Parameters
st.sidebar.markdown("### 📋 Captured Parameters")
p = st.session_state.chatbot_engine.params

prov = p.get("cloud_provider")
if prov == "AWS":
    st.sidebar.markdown('**Provider:** <span class="badge-aws">AWS</span>', unsafe_allow_html=True)
elif prov == "Azure":
    st.sidebar.markdown('**Provider:** <span class="badge-azure">Azure</span>', unsafe_allow_html=True)
elif prov == "GCP":
    st.sidebar.markdown('**Provider:** <span class="badge-gcp">GCP</span>', unsafe_allow_html=True)
else:
    st.sidebar.markdown("**Provider:** *Pending selection*")

st.sidebar.markdown(f"**Resource Name:** `{p.get('resource_name') or 'Pending'}`")

if p.get("project_code"):
    st.sidebar.success(
        f"**Project:** {p.get('project_code')} - {p.get('project_name')}\n\n"
        f"- **PM:** {p.get('pm_name')} (`{p.get('pm_email')}`)\n"
        f"- **BFM:** {p.get('bfm_name')} (`{p.get('bfm_email')}`)\n"
        f"- **BISO:** {p.get('biso_name')} (`{p.get('biso_email')}`)"
    )
else:
    st.sidebar.info("**Project Code:** *Pending entry*")

if prov == "AWS":
    if p.get("aws_account_email"):
        st.sidebar.warning(f"🔑 **AWS Pool Email:** `{p.get('aws_account_email')}`")
    else:
        avail = get_available_aws_email()
        st.sidebar.caption(f"Next available root email: `{avail or 'None'}`")

curr = p.get("cost_currency", "$")
cost_str = f"{curr}{p.get('estimated_cost')}" if p.get("estimated_cost") else "Pending"
st.sidebar.markdown(f"**Budget / Month:** `{cost_str}`")
st.sidebar.markdown(f"**Duration:** `{p.get('project_duration') or 'Pending'}`")
st.sidebar.markdown(f"**Data Tier:** `{p.get('data_classification') or 'Pending'}`")
st.sidebar.markdown(f"**Owners:** `{p.get('primary_owner') or 'Pending'}` / `{p.get('secondary_owner') or 'Pending'}`")
st.sidebar.markdown(f"**AUA Accepted:** `{'✅ Yes' if p.get('acceptable_use_agreed') else '❌ Pending'}`")

st.sidebar.divider()
st.sidebar.download_button(
    label="📄 Download Acceptable Use Agreement",
    data=AUA_TEXT,
    file_name="Cloud_Acceptable_Use_Agreement.md",
    mime="text/markdown",
    use_container_width=True,
)

if st.sidebar.button("🔄 Restart Chat", use_container_width=True):
    st.session_state.chatbot_engine = ChatbotEngine()
    st.session_state.chat_messages = [
        {"role": "assistant", "content": st.session_state.chatbot_engine.get_prompt_for_step()}
    ]
    st.rerun()

# Main Chat Interface
st.markdown('<div class="main-header">💬 Enterprise Cloud Provisioning Chatbot</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Self-service intake for AWS Accounts, Azure Subscriptions, and GCP Projects with automated database verification, ServiceNow ticketing, 4-stage governance approvals, and automated provisioning.</div>',
    unsafe_allow_html=True,
)

# Render Chat History
for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

current_step = st.session_state.chatbot_engine.get_current_step()

# Interactive Action Buttons per Step
if current_step == "cloud_provider":
    c1, c2, c3 = st.columns(3)
    if c1.button("🟠 AWS (Amazon Web Services)", use_container_width=True):
        ok, reply = st.session_state.chatbot_engine.process_input("AWS")
        st.session_state.chat_messages.append({"role": "user", "content": "AWS"})
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()
    if c2.button("🔵 Azure (Microsoft Azure)", use_container_width=True):
        ok, reply = st.session_state.chatbot_engine.process_input("Azure")
        st.session_state.chat_messages.append({"role": "user", "content": "Azure"})
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()
    if c3.button("🟢 GCP (Google Cloud Platform)", use_container_width=True):
        ok, reply = st.session_state.chatbot_engine.process_input("GCP")
        st.session_state.chat_messages.append({"role": "user", "content": "GCP"})
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()

elif current_step == "project_code":
    projs = get_all_projects()
    st.caption("Quick select active Project Code from SQLite database:")
    cols = st.columns(len(projs))
    for i, prj in enumerate(projs):
        if cols[i].button(prj["project_code"], key=f"btn_prj_{prj['project_code']}", use_container_width=True):
            ok, reply = st.session_state.chatbot_engine.process_input(prj["project_code"])
            st.session_state.chat_messages.append({"role": "user", "content": prj["project_code"]})
            st.session_state.chat_messages.append({"role": "assistant", "content": reply})
            st.rerun()

elif current_step == "data_classification":
    st.caption("Select Data Classification Tier:")
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("Public", use_container_width=True):
        ok, reply = st.session_state.chatbot_engine.process_input("Public")
        st.session_state.chat_messages.append({"role": "user", "content": "Public"})
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()
    if c2.button("Internal", use_container_width=True):
        ok, reply = st.session_state.chatbot_engine.process_input("Internal")
        st.session_state.chat_messages.append({"role": "user", "content": "Internal"})
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()
    if c3.button("Confidential", use_container_width=True):
        ok, reply = st.session_state.chatbot_engine.process_input("Confidential")
        st.session_state.chat_messages.append({"role": "user", "content": "Confidential"})
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()
    if c4.button("Restricted", use_container_width=True):
        ok, reply = st.session_state.chatbot_engine.process_input("Restricted")
        st.session_state.chat_messages.append({"role": "user", "content": "Restricted"})
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()

elif current_step == "acceptable_use_agreed":
    col_d, col_a = st.columns([1, 1])
    with col_d:
        st.download_button(
            label="📥 Download Acceptable Use Agreement",
            data=AUA_TEXT,
            file_name="Cloud_Acceptable_Use_Agreement.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with col_a:
        if st.button("✅ I Read & Agree to Acceptable Use Agreement", type="primary", use_container_width=True):
            ok, reply = st.session_state.chatbot_engine.process_input("I Agree")
            st.session_state.chat_messages.append({"role": "user", "content": "I Agree"})
            st.session_state.chat_messages.append({"role": "assistant", "content": reply})
            st.rerun()

elif current_step == "confirmation":
    if st.button("🚀 Confirm & Submit to ServiceNow", type="primary", use_container_width=True):
        ok, reply = st.session_state.chatbot_engine.process_input("Confirm")
        st.session_state.chat_messages.append({"role": "user", "content": "Confirm"})
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()

# Chat Input Box
if current_step != "completed":
    user_input = st.chat_input("Reply to assistant or type commands ('projects', 'emails', 'reset')...")
    if user_input:
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        ok, reply = st.session_state.chatbot_engine.process_input(user_input)
        st.session_state.chat_messages.append({"role": "assistant", "content": reply})
        st.rerun()

else:
    # Post-Ticket Creation Workflow Stepper & Execution
    ticket_num = st.session_state.chatbot_engine.created_ticket_number
    ticket = ServiceNowClient.get_ticket(ticket_num)

    st.divider()
    st.markdown(f"### 📋 Governance & Provisioning Pipeline for `{ticket_num}`")

    if ticket and ticket["status"] != "CLOSED_COMPLETE" and ticket["status"] != "ASSIGNED_TO_CLOUD_TEAM_MANUAL":
        st.info(
            f"**Current Ticket Status:** `{ticket['status']}` ({ticket['current_stage']})\n\n"
            f"You can execute and inspect each approval step live below:"
        )

        col_flow1, col_flow2 = st.columns([1.5, 1])

        with col_flow1:
            st.markdown("#### ⚖️ Stage-by-Stage Approvals")

            # Stage 1: PM
            if ticket["status"] == "PENDING_PM_APPROVAL":
                st.markdown(f"**👤 Stage 1: Project Manager Approval** (`{ticket['pm_email']}`)")
                c_a, c_r = st.columns(2)
                if c_a.button("✅ PM Approve", key="btn_pm_a", type="primary", use_container_width=True):
                    ApprovalWorkflow.process_pm_decision(ticket_num, "APPROVE", ticket["pm_email"], "PM Scope Approved.")
                    st.rerun()
                if c_r.button("❌ PM Reject (Route to Manual)", key="btn_pm_r", use_container_width=True):
                    ApprovalWorkflow.process_pm_decision(ticket_num, "REJECT", ticket["pm_email"], "Rejected by PM.")
                    st.rerun()

            # Stage 2: BFM
            elif ticket["status"] == "PENDING_BFM_APPROVAL":
                st.markdown(f"**💼 Stage 2: Business Financial Manager Approval** (`{ticket['bfm_email']}`)")
                st.caption(f"Monthly Budget: {ticket['cost_currency']}{ticket['estimated_cost']}")
                c_a, c_r = st.columns(2)
                if c_a.button("✅ BFM Approve", key="btn_bfm_a", type="primary", use_container_width=True):
                    ApprovalWorkflow.process_bfm_decision(ticket_num, "APPROVE", ticket["bfm_email"], "Budget Approved.")
                    st.rerun()
                if c_r.button("❌ BFM Reject (Route to Manual)", key="btn_bfm_r", use_container_width=True):
                    ApprovalWorkflow.process_bfm_decision(ticket_num, "REJECT", ticket["bfm_email"], "Budget Exceeded.")
                    st.rerun()

            # Stage 3: BISO
            elif ticket["status"] == "PENDING_BISO_APPROVAL":
                st.markdown(f"**🛡️ Stage 3: BISO Security Approval** (`{ticket['biso_email']}`)")
                st.caption(f"Data Tier: {ticket['data_classification']}")
                c_a, c_r = st.columns(2)
                if c_a.button("✅ BISO Approve", key="btn_biso_a", type="primary", use_container_width=True):
                    ApprovalWorkflow.process_biso_decision(ticket_num, "APPROVE", ticket["biso_email"], "Security Approved.")
                    st.rerun()
                if c_r.button("❌ BISO Reject (Route to Manual)", key="btn_biso_r", use_container_width=True):
                    ApprovalWorkflow.process_biso_decision(ticket_num, "REJECT", ticket["biso_email"], "Security Concerns.")
                    st.rerun()

            # Stage 4: Cloud Team
            elif ticket["status"] == "PENDING_CLOUD_TEAM_APPROVAL":
                st.markdown("**☁️ Stage 4: Cloud Engineering Review & Technical Inputs**")
                ou_input = st.text_input("Target OU / Mgmt Group / Folder:", value="ou-workloads", key="ct_ou")
                vpc_input = st.text_input("Allocated Landing Zone VPC CIDR:", value="10.140.0.0/20", key="ct_vpc")
                c_a, c_r = st.columns(2)
                if c_a.button("🚀 Approve & Trigger Provisioning", key="btn_ct_a", type="primary", use_container_width=True):
                    ApprovalWorkflow.process_cloud_team_decision(
                        ticket_num, "APPROVE", "cloud-leads@enterprise.corp", "Landing zone verified.",
                        {"target_ou": ou_input, "vpc_cidr": vpc_input}
                    )
                    st.rerun()
                if c_r.button("❌ Reject (Route to Manual)", key="btn_ct_r", use_container_width=True):
                    ApprovalWorkflow.process_cloud_team_decision(
                        ticket_num, "REJECT", "cloud-leads@enterprise.corp", "Custom manual build required."
                    )
                    st.rerun()

            # Provisioning
            elif ticket["status"] in ["PROVISIONING_TRIGGERED", "PROVISIONING_IN_PROGRESS"]:
                st.markdown("#### ⚡ Waiting for Account Creation...")
                progress_bar = st.progress(0)
                status_box = st.empty()

                for step_data in CloudProvisioner.provision_resource(ticket_num, simulated_delay=0.4):
                    progress_bar.progress(step_data["percent"])
                    status_box.markdown(f"**Status:** {step_data['status']}")

                NotificationService.send_notification_and_close_ticket(ticket_num)
                st.success("✅ Account created, welcome notification dispatched, and ServiceNow ticket closed!")
                time.sleep(1)
                st.rerun()

        with col_flow2:
            st.markdown("#### ⚡ Quick Pipeline Simulation")
            st.caption("Run all remaining approvals and provisioning automatically in sequence:")
            if st.button("🚀 Fast-Track Full Pipeline", type="primary", use_container_width=True):
                with st.status("Executing End-to-End Governance...", expanded=True) as s:
                    st.write("1. PM Approval...")
                    ApprovalWorkflow.process_pm_decision(ticket_num, "APPROVE", ticket["pm_email"], "Scope OK")
                    st.write("2. BFM Approval...")
                    ApprovalWorkflow.process_bfm_decision(ticket_num, "APPROVE", ticket["bfm_email"], "Budget OK")
                    st.write("3. BISO Approval...")
                    ApprovalWorkflow.process_biso_decision(ticket_num, "APPROVE", ticket["biso_email"], "Security OK")
                    st.write("4. Cloud Team Approval...")
                    ApprovalWorkflow.process_cloud_team_decision(
                        ticket_num, "APPROVE", "cloud-leads@enterprise.corp", "Landing zone OK",
                        {"target_ou": "ou-core-workloads", "vpc_cidr": "10.140.0.0/20"}
                    )
                    st.write("5. Automated Cloud Creation...")
                    pbar = st.progress(0)
                    for step_data in CloudProvisioner.provision_resource(ticket_num, simulated_delay=0.3):
                        pbar.progress(step_data["percent"])
                        st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ {step_data['status']}")
                    st.write("6. Sending Notification & Best Practices FAQ...")
                    notif = NotificationService.send_notification_and_close_ticket(ticket_num)
                    s.update(label="Complete! Provisioned & Closed.", state="complete")

                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": (
                        f"🎉 **Cloud Resource Successfully Provisioned & Closed!**\n\n"
                        f"- **Ticket:** `{ticket_num}` (`CLOSED_COMPLETE`)\n"
                        f"- **Provisioned ID:** `{ServiceNowClient.get_ticket(ticket_num)['provisioned_account_id']}`\n"
                        f"- **Welcome Notification & FAQ Sent to:** {', '.join(notif['recipients'])}\n"
                    )
                })
                st.rerun()

    elif ticket and ticket["status"] == "ASSIGNED_TO_CLOUD_TEAM_MANUAL":
        st.warning(
            f"⚠️ **Ticket Assigned to Cloud Team for Manual Implementation!**\n\n"
            f"- **Status:** `{ticket['status']}`\n"
            f"- **Assignment Group:** `{ticket['assignment_group']}`\n"
            f"- **Rejection Stage:** `{ticket['rejection_stage']}`\n"
            f"- **Reason:** {ticket['rejection_reason']}"
        )

    elif ticket and ticket["status"] == "CLOSED_COMPLETE":
        st.success(
            f"🎉 **ServiceNow Ticket `{ticket_num}` is CLOSED_COMPLETE!**\n\n"
            f"- **Cloud Provider:** `{ticket['cloud_provider']}`\n"
            f"- **Provisioned Account / Subscription / Project ID:** `{ticket['provisioned_account_id']}`\n"
            f"- **Resolution Notes:** {ticket['resolution_notes']}\n"
            f"- **Closed At:** `{ticket['closed_at']}`"
        )
        notif_data = NotificationService.generate_welcome_notification(ticket_num)
        with st.expander("📧 Preview Dispatched Welcome Notification & Best Practices FAQ"):
            st.html(notif_data["html_content"])
            st.markdown(notif_data["faq_markdown"])
