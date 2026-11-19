# ENTERPRISE CLOUD ACCEPTABLE USE AGREEMENT (AUA)
**Document Version:** 2026.1  
**Classification:** Enterprise Policy Compliance  
**Applicability:** All Users Requesting or Accessing Enterprise Cloud Resources (AWS, Azure, GCP)

---

### 1. Purpose and Scope
This Acceptable Use Agreement ("Agreement") governs the provisioning, administration, access, and usage of all Public Cloud Infrastructure, including Amazon Web Services (AWS) accounts, Microsoft Azure subscriptions, and Google Cloud Platform (GCP) projects provisioned via the Enterprise Cloud Platform Automation.

By requesting cloud resources and accepting this agreement, the Primary and Secondary Project Owners and all authorized users agree to adhere to company security policies, financial governance guidelines, and compliance standards.

---

### 2. Core Governance and Security Requirements
1. **Access Control & Identity:**
   - Multi-Factor Authentication (MFA) is strictly mandatory on all federated identity accounts (SSO / Azure AD / Cloud Identity).
   - Long-lived root or permanent access keys (`AKIA...`, storage connection strings, service account keys) must **NEVER** be created or embedded in source code repositories or unencrypted configuration files.
   - Access must follow the Principle of Least Privilege (PoLP) and role-based access control (RBAC).

2. **Data Classification & Protection:**
   - Data stored, processed, or transmitted in cloud accounts must adhere strictly to the declared data classification (Public, Internal, Confidential, Restricted / PII / PHI / PCI).
   - Storage buckets (AWS S3, Azure Blob Storage, GCP Cloud Storage) must **NEVER** be configured with public read/write permissions unless an explicit security exemption has been signed by the Business Information Security Officer (BISO).
   - Encryption-at-rest (using customer-managed or cloud-provider KMS keys) and encryption-in-transit (TLS 1.2+) are mandatory across all services and endpoints.

3. **Financial Responsibility & Budget Compliance:**
   - The Project Owner and BFM are strictly accountable for maintaining cloud consumption within the declared monthly budget.
   - Automatic cost anomaly alerts and budget thresholds (50%, 80%, 100%) will be enforced. Any projected overruns must be submitted to the BFM for re-budgeting.
   - Idle or unattached resources (unattached EBS/Disks, idle NAT gateways, unassociated Elastic IPs, stopped compute instances) must be decommissioned promptly.

4. **Network & Infrastructure Security:**
   - All cloud compute workloads must reside within enterprise-managed Virtual Private Clouds (VPCs / VNets) and adhere to corporate IP addressing schemes.
   - Inbound SSH (port 22) and RDP (port 3389) from the public Internet (`0.0.0.0/0`) are strictly prohibited and will be automatically remediated by Cloud Security Posture Management (CSPM). Use AWS Systems Manager Session Manager, Azure Bastion, or GCP Identity-Aware Proxy (IAP).

---

### 3. Monitoring, Audit & Incident Reporting
- Every API call and administration event is continuously recorded via enterprise security tools (AWS CloudTrail / GuardDuty, Azure Monitor / Defender for Cloud, GCP Cloud Audit Logs / Security Command Center).
- Any suspected compromise, unauthorized access, or policy violation must be reported immediately (within 1 hour) to the Enterprise Security Operations Center (SOC).

---

### 4. Deprovisioning & Project Conclusion
Upon expiration of the project duration or completion of project milestones, the Project Owner is responsible for initiating the graceful decommission and data archiving procedure via ServiceNow.

---

### 5. Acknowledgment & Undertaking
By confirming **"I Agree to the Acceptable Use Agreement"** in the Cloud Provisioning Chatbot:
- You confirm that you have read, understood, and agree to strictly comply with all terms.
- You understand that violations may result in immediate revocation of cloud access privileges, suspension of project resources, and escalation to enterprise management.
