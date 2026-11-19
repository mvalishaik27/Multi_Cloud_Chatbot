"""
Database layer for Multi-Cloud Provisioning Chatbot.
Handles SQLite operations for Projects, AWS Email Pool, ServiceNow Tickets, and Audit Trail.
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloud_governance.db")


def get_db_connection() -> sqlite3.Connection:
    """Creates a database connection with dict-like row access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initializes the database schema and seeds initial enterprise data."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Projects Table (Project Code -> Project Name, PM, BFM, BISO, Dept)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        project_code TEXT PRIMARY KEY,
        project_name TEXT NOT NULL,
        department TEXT NOT NULL,
        pm_name TEXT NOT NULL,
        pm_email TEXT NOT NULL,
        bfm_name TEXT NOT NULL,
        bfm_email TEXT NOT NULL,
        biso_name TEXT NOT NULL,
        biso_email TEXT NOT NULL,
        is_active INTEGER DEFAULT 1
    )
    """)

    # 2. AWS Email Pool Table (Available emails for AWS Account Creation)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS aws_email_pool (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email_id TEXT UNIQUE NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('AVAILABLE', 'RESERVED', 'ASSIGNED')),
        assigned_ticket TEXT,
        assigned_account_name TEXT,
        updated_at TEXT
    )
    """)

    # 3. ServiceNow Tickets Table (Tracks full lifecycle, approvals, cloud provisioning)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS servicenow_tickets (
        ticket_number TEXT PRIMARY KEY,
        cloud_provider TEXT NOT NULL,
        resource_name TEXT NOT NULL,
        project_code TEXT NOT NULL,
        project_name TEXT NOT NULL,
        aws_account_email TEXT,
        estimated_cost REAL NOT NULL,
        cost_currency TEXT NOT NULL,
        project_duration TEXT NOT NULL,
        business_justification TEXT NOT NULL,
        primary_owner TEXT NOT NULL,
        secondary_owner TEXT NOT NULL,
        data_classification TEXT NOT NULL,
        user_access_emails TEXT NOT NULL,
        acceptable_use_agreed INTEGER NOT NULL DEFAULT 1,
        
        status TEXT NOT NULL DEFAULT 'PENDING_PM_APPROVAL',
        current_stage TEXT NOT NULL DEFAULT 'Stage 1: Project Manager Approval',
        assignment_group TEXT NOT NULL DEFAULT 'Enterprise Cloud Governance',
        assigned_to TEXT,
        
        pm_email TEXT NOT NULL,
        pm_status TEXT DEFAULT 'PENDING',
        pm_comment TEXT,
        pm_action_date TEXT,
        
        bfm_email TEXT NOT NULL,
        bfm_status TEXT DEFAULT 'PENDING',
        bfm_comment TEXT,
        bfm_action_date TEXT,
        
        biso_email TEXT NOT NULL,
        biso_status TEXT DEFAULT 'PENDING',
        biso_comment TEXT,
        biso_action_date TEXT,
        
        cloud_team_status TEXT DEFAULT 'PENDING',
        cloud_team_comment TEXT,
        cloud_team_action_date TEXT,
        cloud_team_inputs TEXT,
        
        rejection_reason TEXT,
        rejection_stage TEXT,
        
        provisioned_account_id TEXT,
        provisioning_status TEXT DEFAULT 'NOT_STARTED',
        provisioning_payload TEXT,
        
        notification_status TEXT DEFAULT 'PENDING',
        notification_payload TEXT,
        
        resolution_notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        closed_at TEXT
    )
    """)

    # 4. Audit Trail Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_number TEXT NOT NULL,
        action TEXT NOT NULL,
        performed_by TEXT NOT NULL,
        details TEXT,
        timestamp TEXT NOT NULL
    )
    """)

    conn.commit()

    # Seed Initial Enterprise Projects if empty
    cursor.execute("SELECT COUNT(*) FROM projects")
    if cursor.fetchone()[0] == 0:
        seed_projects = [
            (
                "PRJ-AI-101",
                "Enterprise GenAI Discovery Platform",
                "Applied AI & Innovation",
                "Sarah Jenkins",
                "sarah.jenkins@enterprise.corp",
                "Michael Chang",
                "michael.chang@enterprise.corp",
                "Elena Rostova",
                "biso-ai@enterprise.corp",
            ),
            (
                "PRJ-FIN-202",
                "Core Financial Modernization",
                "FinTech & Banking Solutions",
                "Robert Sterling",
                "robert.sterling@enterprise.corp",
                "David Vance",
                "david.vance.bfm@enterprise.corp",
                "Marcus Aurelius",
                "biso-finance@enterprise.corp",
            ),
            (
                "PRJ-DATA-303",
                "Unified Lakehouse & Analytics",
                "Enterprise Data Engineering",
                "Ananya Sharma",
                "ananya.sharma@enterprise.corp",
                "Rajesh Kothari",
                "rajesh.kothari.bfm@enterprise.corp",
                "Carlos Mendez",
                "biso-data@enterprise.corp",
            ),
            (
                "PRJ-ECOM-404",
                "Omnichannel Retail Experience",
                "Digital Commerce",
                "Emily Watson",
                "emily.watson@enterprise.corp",
                "Claire Beauchamp",
                "claire.b.bfm@enterprise.corp",
                "Kevin Patel",
                "biso-digital@enterprise.corp",
            ),
            (
                "PRJ-INFRA-505",
                "Hybrid Cloud Edge Services",
                "Global Infrastructure Operations",
                "Vikram Malhotra",
                "vikram.malhotra@enterprise.corp",
                "Jennifer Lopez-Fin",
                "jennifer.l.bfm@enterprise.corp",
                "Security Governance Board",
                "biso-core@enterprise.corp",
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO projects (project_code, project_name, department, pm_name, pm_email, bfm_name, bfm_email, biso_name, biso_email)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            seed_projects,
        )

    # Seed Initial AWS Email Pool if empty
    cursor.execute("SELECT COUNT(*) FROM aws_email_pool")
    if cursor.fetchone()[0] == 0:
        seed_emails = [
            ("aws-root-app-pool01@enterprise.corp", "AVAILABLE"),
            ("aws-root-app-pool02@enterprise.corp", "AVAILABLE"),
            ("aws-root-data-pool03@enterprise.corp", "AVAILABLE"),
            ("aws-root-ml-pool04@enterprise.corp", "AVAILABLE"),
            ("aws-root-core-pool05@enterprise.corp", "AVAILABLE"),
            ("aws-root-devops-pool06@enterprise.corp", "AVAILABLE"),
            ("aws-root-sandbox-pool07@enterprise.corp", "AVAILABLE"),
            ("aws-root-prod-pool08@enterprise.corp", "AVAILABLE"),
        ]
        cursor.executemany(
            """
            INSERT INTO aws_email_pool (email_id, status, updated_at)
            VALUES (?, ?, datetime('now'))
            """,
            seed_emails,
        )

    conn.commit()
    conn.close()


def get_all_projects() -> List[Dict[str, Any]]:
    """Retrieves all active projects from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE is_active = 1 ORDER BY project_code ASC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_project_by_code(project_code: str) -> Optional[Dict[str, Any]]:
    """Looks up project details by project code (case-insensitive)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE UPPER(project_code) = UPPER(?)", (project_code.strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_available_aws_email() -> Optional[str]:
    """Retrieves the first available email address from the AWS email pool."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email_id FROM aws_email_pool WHERE status = 'AVAILABLE' ORDER BY id ASC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return row["email_id"] if row else None


def reserve_aws_email(email_id: str, ticket_number: str, account_name: str) -> bool:
    """Reserves an available AWS email for a pending request."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute(
        """
        UPDATE aws_email_pool 
        SET status = 'RESERVED', assigned_ticket = ?, assigned_account_name = ?, updated_at = ?
        WHERE email_id = ? AND status = 'AVAILABLE'
        """,
        (ticket_number, account_name, now, email_id),
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def assign_aws_email(email_id: str, ticket_number: str) -> bool:
    """Marks an AWS email as permanently ASSIGNED upon successful creation."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute(
        """
        UPDATE aws_email_pool 
        SET status = 'ASSIGNED', updated_at = ?
        WHERE email_id = ?
        """,
        (now, email_id),
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def release_aws_email(email_id: str) -> bool:
    """Releases a reserved AWS email back to AVAILABLE status (e.g. upon rejection/cancellation)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute(
        """
        UPDATE aws_email_pool 
        SET status = 'AVAILABLE', assigned_ticket = NULL, assigned_account_name = NULL, updated_at = ?
        WHERE email_id = ?
        """,
        (now, email_id),
    )
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def get_all_aws_emails() -> List[Dict[str, Any]]:
    """Retrieves all emails in the AWS email pool."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM aws_email_pool ORDER BY id ASC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def add_aws_pool_email(email_id: str) -> bool:
    """Adds a new root alias email to the pool."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    try:
        cursor.execute(
            "INSERT INTO aws_email_pool (email_id, status, updated_at) VALUES (?, 'AVAILABLE', ?)",
            (email_id.strip(), now),
        )
        conn.commit()
        success = True
    except sqlite3.IntegrityError:
        success = False
    finally:
        conn.close()
    return success


def log_audit(ticket_number: str, action: str, performed_by: str, details: str = ""):
    """Inserts a record into the audit log."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO audit_logs (ticket_number, action, performed_by, details, timestamp)
        VALUES (?, ?, ?, ?, ?)
        """,
        (ticket_number, action, performed_by, details, now),
    )
    conn.commit()
    conn.close()


def get_audit_logs(ticket_number: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches audit logs, optionally filtered by ticket number."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if ticket_number:
        cursor.execute("SELECT * FROM audit_logs WHERE ticket_number = ? ORDER BY id DESC", (ticket_number,))
    else:
        cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 100")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


# Run initialization on import
init_database()
