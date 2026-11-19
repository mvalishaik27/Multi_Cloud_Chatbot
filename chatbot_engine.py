"""
Chatbot Conversational Engine for Multi-Cloud Provisioning.
Guides users interactively step-by-step or through multi-parameter natural language inputs.
Performs real-time SQLite lookups (Project Code -> Project Name, PM, BFM, BISO, AWS Email Pool),
enforces currency & validation rules, provides downloadable Acceptable Use Agreement,
and triggers ServiceNow ticket creation and approval orchestration.
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from database import (
    get_project_by_code,
    get_available_aws_email,
    get_all_projects,
    get_all_aws_emails,
)
from servicenow_client import ServiceNowClient

STEPS = [
    "cloud_provider",
    "resource_name",
    "project_code",
    "estimated_cost",
    "project_duration",
    "business_justification",
    "primary_owner",
    "secondary_owner",
    "data_classification",
    "user_access_emails",
    "acceptable_use_agreed",
    "confirmation",
]

DATA_CLASSIFICATIONS = [
    "Public (Open to everyone)",
    "Internal (Company confidential)",
    "Confidential (Sensitive business data)",
    "Restricted (PII / PHI / PCI / Highly Sensitive)",
]


class ChatbotEngine:
    """Conversational engine for capturing multi-cloud provisioning parameters."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.step_index = 0
        self.params: Dict[str, Any] = {
            "cloud_provider": None,
            "resource_name": None,
            "project_code": None,
            "project_name": None,
            "aws_account_email": None,
            "pm_name": None,
            "pm_email": None,
            "bfm_name": None,
            "bfm_email": None,
            "biso_name": None,
            "biso_email": None,
            "estimated_cost": None,
            "cost_currency": "$",
            "project_duration": None,
            "business_justification": None,
            "primary_owner": None,
            "secondary_owner": None,
            "data_classification": None,
            "user_access_emails": None,
            "acceptable_use_agreed": False,
        }
        self.completed = False
        self.created_ticket_number = None

    def get_current_step(self) -> str:
        if self.step_index < len(STEPS):
            return STEPS[self.step_index]
        return "completed"

    def get_prompt_for_step(self, step: Optional[str] = None) -> str:
        current = step or self.get_current_step()
        provider = self.params.get("cloud_provider") or "Cloud"

        if current == "cloud_provider":
            return (
                "👋 **Welcome to Enterprise Multi-Cloud Provisioning!**\n\n"
                "I am your AI Cloud Provisioning Assistant. I will guide you through requesting a new cloud environment "
                "with enterprise governance, automated database lookups, multi-stage ServiceNow approvals, and automated account setup.\n\n"
                "**Step 1:** Which **Cloud Service Provider** would you like to provision for?\n"
                "- **AWS** (Amazon Web Services)\n"
                "- **Azure** (Microsoft Azure)\n"
                "- **GCP** (Google Cloud Platform)\n\n"
                "*(You can also say something like: 'I need an AWS account named dev-ai for project PRJ-AI-101 with $1500 budget')*"
            )

        elif current == "resource_name":
            if provider == "AWS":
                return "🏷️ **Step 2:** What is the **AWS Account Name** you wish to create? *(e.g. `ecommerce-prod-workloads`)*"
            elif provider == "Azure":
                return "🏷️ **Step 2:** What is the **Subscription Name** for your Azure workload? *(e.g. `sub-fintech-analytics-dev`)*"
            else:
                return "🏷️ **Step 2:** What is the **GCP Project Name** you want to establish? *(e.g. `genai-discovery-poc`)*"

        elif current == "project_code":
            all_projs = get_all_projects()
            available_codes = ", ".join([f"`{p['project_code']}`" for p in all_projs])
            return (
                f"🏢 **Step 3:** Enter your internal **Project Code**.\n\n"
                f"*(I will automatically look up the Project Name, Project Manager, BFM, and BISO emails from our SQLite database).* \n\n"
                f"📌 *Sample active project codes:* {available_codes}"
            )

        elif current == "estimated_cost":
            if provider == "AWS":
                return "💰 **Step 4:** What is your **Estimated Cost per Month**?\n📌 *Currency Rule: AWS budgets must be entered in **USD ($)**.* (e.g. `1500`)"
            elif provider == "Azure":
                return "💰 **Step 4:** What is your **Estimated Cost per Month**?\n📌 *Currency Rule: Azure budgets must be entered in **INR (₹)**.* (e.g. `85000`)"
            else:
                return "💰 **Step 4:** What is your **Estimated Cost per Month**?\n📌 *Currency Rule: GCP budgets must be entered in **INR (₹)**.* (e.g. `95000`)"

        elif current == "project_duration":
            return (
                "⏳ **Step 5:** What is the anticipated **Project Duration**?\n"
                "*(e.g., `3 Months`, `6 Months`, `12 Months`, or `Permanent / Ongoing`)*"
            )

        elif current == "business_justification":
            return (
                "📝 **Step 6:** Please provide the **Business Justification** for this cloud environment.\n"
                "*(Describe the project goals, intended architecture, and why this dedicated cloud boundary is required)*"
            )

        elif current == "primary_owner":
            return "👤 **Step 7:** Who is the **Primary Project Owner**? *(Enter Full Name or Corporate Email, e.g. `alice.dev@enterprise.corp`)*"

        elif current == "secondary_owner":
            return "👥 **Step 8:** Who is the **Secondary Project Owner**? *(Enter Full Name or Corporate Email, e.g. `bob.techlead@enterprise.corp`)*"

        elif current == "data_classification":
            options = "\n".join([f"- **{c}**" for c in DATA_CLASSIFICATIONS])
            return (
                f"🛡️ **Step 9:** **Declaration on Type of Data**.\n"
                f"Select the classification level of data that will be processed or stored:\n{options}"
            )

        elif current == "user_access_emails":
            return (
                "📧 **Step 10:** Provide the **List of user emails who require access** to this cloud environment.\n"
                "*(Separate multiple emails by commas or new lines, e.g. `dev1@enterprise.corp, dev2@enterprise.corp, analyst@enterprise.corp`)*"
            )

        elif current == "acceptable_use_agreed":
            return (
                "📜 **Step 11:** **Cloud 'Acceptable Use Agreement' (AUA)**.\n\n"
                "You must review and download the Enterprise Cloud Acceptable Use Agreement before proceeding.\n"
                "*(Downloadable from the sidebar or by replying 'download aua').*\n\n"
                "Do you agree to abide by all cloud security, MFA, zero-trust, and budgetary policies? *(Reply 'I Agree' or 'Yes')*"
            )

        elif current == "confirmation":
            return self.get_summary_review_text()

        return "🎉 Request process completed!"

    def handle_global_commands(self, text: str) -> Optional[Tuple[bool, str]]:
        """Handles general intent queries like help, status lookup, project listing, or reset."""
        lower = text.lower().strip()

        if lower in ["help", "/help", "what can you do", "commands"]:
            return True, (
                "🤖 **Cloud Provisioning Chatbot Commands & Capabilities:**\n\n"
                "- **New Request:** Just type your cloud details or follow my step-by-step prompts.\n"
                "- **`projects` / `list projects`:** View all valid enterprise project codes from SQLite.\n"
                "- **`emails` / `aws emails`:** View available root emails in the AWS email pool.\n"
                "- **`status <TICKET_NUMBER>`:** Check real-time ServiceNow approval status (e.g. `status RITM0010201`).\n"
                "- **`aua` / `agreement`:** Read or download the Cloud Acceptable Use Agreement.\n"
                "- **`reset`:** Start over with a fresh cloud request."
            )

        if lower in ["projects", "list projects", "/projects"]:
            projs = get_all_projects()
            lines = [f"- **`{p['project_code']}`**: {p['project_name']} (PM: `{p['pm_email']}`, BFM: `{p['bfm_email']}`)" for p in projs]
            return True, "📋 **Active Enterprise Projects in Database:**\n\n" + "\n".join(lines)

        if lower in ["emails", "aws emails", "/emails"]:
            emails = get_all_aws_emails()
            avail = [e['email_id'] for e in emails if e['status'] == 'AVAILABLE']
            assigned = [e['email_id'] for e in emails if e['status'] == 'ASSIGNED']
            return True, (
                f"🔑 **AWS Root Email Pool Status:**\n\n"
                f"- **Available ({len(avail)}):** {', '.join([f'`{e}`' for e in avail]) or 'None'}\n"
                f"- **Assigned ({len(assigned)}):** {', '.join([f'`{e}`' for e in assigned]) or 'None'}"
            )

        if lower.startswith("status ") or lower.startswith("/status "):
            tnum = lower.split()[-1].upper()
            ticket = ServiceNowClient.get_ticket(tnum)
            if ticket:
                return True, (
                    f"📌 **Status for Ticket `{tnum}`:**\n\n"
                    f"- **Provider:** {ticket['cloud_provider']} (`{ticket['resource_name']}`)\n"
                    f"- **Status:** `{ticket['status']}`\n"
                    f"- **Current Stage:** `{ticket['current_stage']}`\n"
                    f"- **Assignment Group:** `{ticket['assignment_group']}`\n"
                    f"- **PM Approval:** `{ticket['pm_status']}`\n"
                    f"- **BFM Approval:** `{ticket['bfm_status']}`\n"
                    f"- **BISO Approval:** `{ticket['biso_status']}`\n"
                    f"- **Cloud Team Approval:** `{ticket['cloud_team_status']}`\n"
                    f"- **Provisioned ID:** `{ticket['provisioned_account_id'] or 'Not yet provisioned'}`"
                )
            else:
                return True, f"❌ Ticket `{tnum}` was not found in ServiceNow."

        if lower in ["reset", "/reset", "restart", "start over"]:
            self.reset()
            return True, "🔄 Conversation reset! Let's start fresh.\n\n" + self.get_prompt_for_step()

        return None

    def try_multi_parameter_extraction(self, text: str) -> bool:
        """Attempts to parse multiple parameters from a natural sentence."""
        extracted_any = False

        # 1. Cloud Provider
        if not self.params["cloud_provider"]:
            if re.search(r"\baws\b", text, re.IGNORECASE):
                self.params["cloud_provider"] = "AWS"
                self.params["cost_currency"] = "$"
                extracted_any = True
            elif re.search(r"\bazure\b", text, re.IGNORECASE):
                self.params["cloud_provider"] = "Azure"
                self.params["cost_currency"] = "₹"
                extracted_any = True
            elif re.search(r"\bgcp\b", text, re.IGNORECASE):
                self.params["cloud_provider"] = "GCP"
                self.params["cost_currency"] = "₹"
                extracted_any = True

        # 2. Project Code
        if not self.params["project_code"]:
            m_proj = re.search(r"\b(PRJ-[A-Z0-9]+-\d+|PRJ-\d+)\b", text, re.IGNORECASE)
            if m_proj:
                code = m_proj.group(1).upper()
                proj = get_project_by_code(code)
                if proj:
                    self.params["project_code"] = proj["project_code"]
                    self.params["project_name"] = proj["project_name"]
                    self.params["pm_name"] = proj["pm_name"]
                    self.params["pm_email"] = proj["pm_email"]
                    self.params["bfm_name"] = proj["bfm_name"]
                    self.params["bfm_email"] = proj["bfm_email"]
                    self.params["biso_name"] = proj["biso_name"]
                    self.params["biso_email"] = proj["biso_email"]
                    if self.params["cloud_provider"] == "AWS" and not self.params["aws_account_email"]:
                        self.params["aws_account_email"] = get_available_aws_email()
                    extracted_any = True

        # 3. Budget / Cost
        if not self.params["estimated_cost"]:
            m_cost = re.search(r"(?:budget|cost|price|limit)?\s*[:=]?\s*[\$₹]?\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:usd|inr|dollars|rupees|per month|/month)?", text, re.IGNORECASE)
            if m_cost:
                val = float(m_cost.group(1).replace(",", ""))
                if val > 0:
                    self.params["estimated_cost"] = val
                    extracted_any = True

        # 4. Duration
        if not self.params["project_duration"]:
            m_dur = re.search(r"\b(\d+\s*(?:months?|weeks?|years?)|permanent|ongoing)\b", text, re.IGNORECASE)
            if m_dur:
                self.params["project_duration"] = m_dur.group(1).title()
                extracted_any = True

        # Update step index to the first missing parameter
        for idx, step_name in enumerate(STEPS):
            if step_name == "cloud_provider" and not self.params["cloud_provider"]:
                self.step_index = idx
                break
            elif step_name == "resource_name" and not self.params["resource_name"]:
                self.step_index = idx
                break
            elif step_name == "project_code" and not self.params["project_code"]:
                self.step_index = idx
                break
            elif step_name == "estimated_cost" and not self.params["estimated_cost"]:
                self.step_index = idx
                break
            elif step_name == "project_duration" and not self.params["project_duration"]:
                self.step_index = idx
                break
            elif step_name == "business_justification" and not self.params["business_justification"]:
                self.step_index = idx
                break
            elif step_name == "primary_owner" and not self.params["primary_owner"]:
                self.step_index = idx
                break
            elif step_name == "secondary_owner" and not self.params["secondary_owner"]:
                self.step_index = idx
                break
            elif step_name == "data_classification" and not self.params["data_classification"]:
                self.step_index = idx
                break
            elif step_name == "user_access_emails" and not self.params["user_access_emails"]:
                self.step_index = idx
                break
            elif step_name == "acceptable_use_agreed" and not self.params["acceptable_use_agreed"]:
                self.step_index = idx
                break
            elif step_name == "confirmation" and not self.completed:
                self.step_index = idx
                break

        return extracted_any

    def process_input(self, user_input: str) -> Tuple[bool, str]:
        """
        Validates user input for current step and advances state machine.
        Returns: (success: bool, response_message: str)
        """
        text = user_input.strip()

        # Check global commands
        cmd_result = self.handle_global_commands(text)
        if cmd_result is not None:
            return cmd_result

        # Try multi-parameter extraction if sentence has multiple words
        if len(text.split()) > 3 and self.step_index < 6:
            multi_extracted = self.try_multi_parameter_extraction(text)
            if multi_extracted:
                p = self.params
                feedback = [
                    f"- Provider: `{p['cloud_provider']}`" if p["cloud_provider"] else None,
                    f"- Project: `{p['project_code']}` ({p['project_name']})" if p["project_code"] else None,
                    f"- Budget: `{p.get('cost_currency', '$')}{p['estimated_cost']}`" if p["estimated_cost"] else None,
                    f"- Duration: `{p['project_duration']}`" if p["project_duration"] else None,
                ]
                valid_f = [f for f in feedback if f]
                feedback_str = "✨ **Extracted parameters from your message:**\n" + "\n".join(valid_f)
                return True, f"{feedback_str}\n\n---\n" + self.get_prompt_for_step()

        current_step = self.get_current_step()

        if current_step == "cloud_provider":
            val = text.upper()
            if "AWS" in val:
                self.params["cloud_provider"] = "AWS"
                self.params["cost_currency"] = "$"
            elif "AZURE" in val:
                self.params["cloud_provider"] = "Azure"
                self.params["cost_currency"] = "₹"
            elif "GCP" in val:
                self.params["cloud_provider"] = "GCP"
                self.params["cost_currency"] = "₹"
            else:
                return False, "❌ Please select a valid Cloud Service Provider: **AWS**, **Azure**, or **GCP**."

            self.step_index += 1
            return True, self.get_prompt_for_step()

        elif current_step == "resource_name":
            if len(text) < 3:
                return False, "❌ Resource name must be at least 3 characters long."
            self.params["resource_name"] = text
            self.step_index += 1
            return True, self.get_prompt_for_step()

        elif current_step == "project_code":
            proj = get_project_by_code(text)
            if not proj:
                all_projs = get_all_projects()
                codes = ", ".join([f"`{p['project_code']}`" for p in all_projs])
                return False, f"❌ Project Code '{text}' not found in SQLite Database. Valid codes are: {codes}"

            self.params["project_code"] = proj["project_code"]
            self.params["project_name"] = proj["project_name"]
            self.params["pm_name"] = proj["pm_name"]
            self.params["pm_email"] = proj["pm_email"]
            self.params["bfm_name"] = proj["bfm_name"]
            self.params["bfm_email"] = proj["bfm_email"]
            self.params["biso_name"] = proj["biso_name"]
            self.params["biso_email"] = proj["biso_email"]

            # Check AWS email pool if AWS
            extra_msg = ""
            if self.params["cloud_provider"] == "AWS":
                avail_email = get_available_aws_email()
                if avail_email:
                    self.params["aws_account_email"] = avail_email
                    extra_msg = (
                        f"\n\n🔑 **AWS Root Email Allocated from Database Pool:** `{avail_email}`"
                    )
                else:
                    return (
                        False,
                        "❌ Critical: No available email found in SQLite `aws_email_pool` for AWS account creation! Please replenish pool.",
                    )

            lookup_feedback = (
                f"✅ **Database Lookup Successful!**\n"
                f"- **Project Name:** {proj['project_name']} ({proj['department']})\n"
                f"- **Project Manager (Stage 1 Approver):** {proj['pm_name']} (`{proj['pm_email']}`)\n"
                f"- **BFM (Stage 2 Approver):** {proj['bfm_name']} (`{proj['bfm_email']}`)\n"
                f"- **BISO (Stage 3 Approver):** {proj['biso_name']} (`{proj['biso_email']}`)"
                f"{extra_msg}"
            )

            self.step_index += 1
            return True, f"{lookup_feedback}\n\n---\n" + self.get_prompt_for_step()

        elif current_step == "estimated_cost":
            clean_num = re.sub(r"[^\d.]", "", text)
            try:
                val = float(clean_num)
                if val <= 0:
                    return False, "❌ Estimated cost must be greater than 0."
                self.params["estimated_cost"] = val
            except ValueError:
                return False, f"❌ Invalid cost number. Please enter a numeric monthly budget in {self.params['cost_currency']}."

            self.step_index += 1
            return True, self.get_prompt_for_step()

        elif current_step == "project_duration":
            if len(text) < 2:
                return False, "❌ Please enter a valid project duration (e.g. '6 Months')."
            self.params["project_duration"] = text
            self.step_index += 1
            return True, self.get_prompt_for_step()

        elif current_step == "business_justification":
            if len(text) < 10:
                return False, "❌ Business justification is too short. Please provide at least 10 characters."
            self.params["business_justification"] = text
            self.step_index += 1
            return True, self.get_prompt_for_step()

        elif current_step == "primary_owner":
            if len(text) < 3:
                return False, "❌ Please provide a valid Primary Project Owner name or email."
            self.params["primary_owner"] = text
            self.step_index += 1
            return True, self.get_prompt_for_step()

        elif current_step == "secondary_owner":
            if len(text) < 3:
                return False, "❌ Please provide a valid Secondary Project Owner name or email."
            self.params["secondary_owner"] = text
            self.step_index += 1
            return True, self.get_prompt_for_step()

        elif current_step == "data_classification":
            matched = None
            for item in DATA_CLASSIFICATIONS:
                if text.lower() in item.lower() or item.split()[0].lower() == text.lower():
                    matched = item.split()[0]
                    break
            if not matched:
                matched = text if text in ["Public", "Internal", "Confidential", "Restricted"] else "Confidential"
            self.params["data_classification"] = matched
            self.step_index += 1
            return True, self.get_prompt_for_step()

        elif current_step == "user_access_emails":
            emails = [e.strip() for e in text.replace(";", ",").replace("\n", ",").split(",") if e.strip()]
            if not emails:
                return False, "❌ Please provide at least one user email address."
            self.params["user_access_emails"] = ", ".join(emails)
            self.step_index += 1
            return True, self.get_prompt_for_step()

        elif current_step == "acceptable_use_agreed":
            if any(term in text.lower() for term in ["agree", "yes", "accept", "confirm", "ok", "y"]):
                self.params["acceptable_use_agreed"] = True
                self.step_index += 1
                return True, self.get_prompt_for_step()
            else:
                return (
                    False,
                    "⚠️ You must review and agree to the Acceptable Use Agreement to proceed. Please type 'I Agree'.",
                )

        elif current_step == "confirmation":
            if any(term in text.lower() for term in ["confirm", "submit", "yes", "proceed", "create", "ok"]):
                ticket_num = ServiceNowClient.create_request_ticket(self.params)
                self.created_ticket_number = ticket_num
                self.completed = True
                self.step_index += 1
                return (
                    True,
                    f"🎉 **ServiceNow Ticket Created Successfully!**\n\n"
                    f"📌 **Ticket Number:** `{ticket_num}`\n"
                    f"🔄 **Current State:** `PENDING_PM_APPROVAL`\n"
                    f"📨 **First Approver:** Project Manager ({self.params['pm_email']})\n\n"
                    f"The request is now routing through the 4-stage governance pipeline:\n"
                    f"1. 👤 **PM Approval** (`{self.params['pm_email']}`)\n"
                    f"2. 💼 **BFM Approval** (`{self.params['bfm_email']}`)\n"
                    f"3. 🛡️ **BISO Approval** (`{self.params['biso_email']}`)\n"
                    f"4. ☁️ **Cloud Team Review**\n\n"
                    f"*(Tip: You can say 'status {ticket_num}' anytime to check live progress)*",
                )
            else:
                return (
                    False,
                    "To create the ServiceNow ticket, please type **'Confirm'** or **'Submit'**. (Or type 'reset' to restart).",
                )

        return True, "All steps completed!"

    def get_summary_review_text(self) -> str:
        """Generates a comprehensive summary markdown card."""
        p = self.params
        curr = p.get("cost_currency", "$")
        aws_email_line = (
            f"- **AWS Root Email (Allocated from DB Pool):** `{p.get('aws_account_email')}`\n"
            if p.get("cloud_provider") == "AWS"
            else ""
        )

        return (
            "📋 **Step 12: Please Review Your Cloud Request Details**\n\n"
            f"- **Cloud Service Provider:** `{p.get('cloud_provider')}`\n"
            f"- **Resource Name:** `{p.get('resource_name')}`\n"
            f"- **Project Code & Name:** `{p.get('project_code')}` - **{p.get('project_name')}**\n"
            f"{aws_email_line}"
            f"- **Monthly Budget Limit:** **{curr}{p.get('estimated_cost')}**\n"
            f"- **Project Duration:** {p.get('project_duration')}\n"
            f"- **Business Justification:** {p.get('business_justification')}\n"
            f"- **Primary Owner:** {p.get('primary_owner')}\n"
            f"- **Secondary Owner:** {p.get('secondary_owner')}\n"
            f"- **Data Classification:** `{p.get('data_classification')}`\n"
            f"- **Users Requiring Access:** `{p.get('user_access_emails')}`\n"
            f"- **Acceptable Use Agreement:** `Accepted (Downloadable copy acknowledged)`\n\n"
            f"**Automated Approval Chain Configured from Database:**\n"
            f"1. 👤 **Project Manager (Stage 1):** `{p.get('pm_email')}`\n"
            f"2. 💼 **BFM (Stage 2):** `{p.get('bfm_email')}`\n"
            f"3. 🛡️ **BISO (Stage 3):** `{p.get('biso_email')}`\n"
            f"4. ☁️ **Cloud Team (Stage 4):** Cloud Infrastructure Review & Inputs\n\n"
            f"👉 Ready to create your ticket? Type **'Confirm'** to submit to ServiceNow!"
        )
