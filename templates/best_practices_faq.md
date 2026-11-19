# ENTERPRISE CLOUD BEST PRACTICES & FREQUENTLY ASKED QUESTIONS (FAQ)

---

### General Cloud Governance & Identity
**Q1: How do authorized users access the newly provisioned cloud environment?**  
- **AWS**: Access is provisioned via Enterprise AWS IAM Identity Center (SSO). Navigate to your company SSO portal (`https://enterprise-cloud.awsapps.com/start`) and log in with corporate credentials and MFA.  
- **Azure**: Navigate to `https://portal.azure.com`. Filter subscriptions by your Subscription Name/ID. Role assignments (RBAC) are linked to enterprise Entra ID security groups.  
- **GCP**: Access Google Cloud Console (`https://console.cloud.google.com`) using your corporate email account. Switch the project selector to your provisioned Project ID.

**Q2: Can I create permanent root credentials, access keys, or service account JSON keys?**  
- **Strictly Prohibited**: Never create or download IAM user access keys (`AKIA...`), Azure Storage account master keys, or GCP Service Account JSON key files for local workstations.
- Always use short-lived temporary credentials (AWS IAM Roles / STS, Azure Managed Identities / Workload Identity Federation, GCP Workload Identity Federation).

---

### Security, Compliance & Data Protection
**Q3: What are the security rules for cloud storage buckets?**  
- **S3 / Azure Blob / GCS Public Access Block**: All cloud buckets have organizational public access block enforced by default. Attempting to disable this policy will trigger immediate automated remediation and SOC alert.
- **Encryption**: All data at rest must use AES-256 (KMS/Cloud KMS/Key Vault).
- **Versioning & Retention**: Enable bucket versioning and lifecycle rules to transition cold data to lower-cost tiers (AWS Glacier, Azure Cool/Archive, GCP Nearline/Coldline).

**Q4: How do I securely connect to virtual machines without public IPs?**  
- Inbound SSH (port 22) and RDP (port 3389) from `0.0.0.0/0` are blocked by perimeter firewalls.
- Use zero-trust connection tools:
  - **AWS**: AWS Systems Manager (SSM) Session Manager.
  - **Azure**: Azure Bastion or Just-In-Time (JIT) VM Access.
  - **GCP**: Identity-Aware Proxy (IAP) TCP forwarding (`gcloud compute ssh --tunnel-through-iap`).

---

### Cost Optimization & Financial Accountability
**Q5: What happens when the monthly budget threshold is approached?**  
- Automated email alerts will trigger at **50%, 80%, and 100%** of your declared budget limit.
- If your workload reaches 100% budget, notify your BFM immediately to adjust the budget forecast or right-size compute resources.
- Development and non-production instances must be configured with automated start/stop schedules outside business hours.

**Q6: What mandatory resource tags must be applied?**  
Every cloud resource created inside this account/subscription/project must include:
- `ProjectCode`: e.g., `{project_code}`
- `Owner`: `{primary_owner}`
- `Environment`: `Dev` / `Staging` / `Prod`
- `CostCenter`: Enterprise Financial Cost Center
- `DataClassification`: `{data_classification}`

---

### Incident Escalation & Support
**Q7: Who do I contact for cloud architecture guidance or security incidents?**  
- **Security Incident**: Enterprise SOC (24x7 Hot-line: `#soc-emergency` or `soc@enterprise.corp`).
- **Cloud Team Support**: Cloud Center of Excellence (CCoE) at `#cloud-platform-support` or submit an incident in ServiceNow.
