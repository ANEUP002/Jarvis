# =========================
# EMAIL TOOLS
# =========================

import json
import os
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv
from app.event_streaming import event_stream
from .base_tool import BaseTool

# Load environment variables from project root
project_root = Path(__file__).parent.parent
load_dotenv(project_root / '.env')

# Email storage directory
EMAIL_DIR = Path(__file__).parent.parent / "memory" / "emails"
EMAIL_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_recipients(value):
    if not value:
        return []
    if isinstance(value, list):
        return [item.strip() for item in value if item]
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[;,\n]", value) if item.strip()]
    return []


def _clean_env(value):
    if value is None:
        return ""
    return value.strip().strip('"').strip("'")


class SendEmailTool(BaseTool):
    """Send an email message."""
    
    name = "send_email"
    description = "Send an email message via SMTP or save it locally when SMTP is not configured"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Send an email.
        
        Args:
            to: Recipient email address(es) - can be string or list
            subject: Email subject
            body: Email body/message
            cc: Optional CC recipients
            bcc: Optional BCC recipients
            send_via_smtp: Whether to attempt SMTP delivery (default: True)
        """
        try:
            to = kwargs.get("to", "")
            subject = kwargs.get("subject", "")
            body = kwargs.get("body", "")
            cc = kwargs.get("cc", "")
            bcc = kwargs.get("bcc", "")
            send_via_smtp = kwargs.get("send_via_smtp", True)

            recipients = _normalize_recipients(to)
            cc_list = _normalize_recipients(cc)
            bcc_list = _normalize_recipients(bcc)

            if not recipients:
                default_to = os.getenv("EMAIL_DEFAULT_TO", "")
                recipients = _normalize_recipients(default_to)

            if not recipients:
                return {
                    "success": False,
                    "error": "Recipient email address(es) are required via 'to' or EMAIL_DEFAULT_TO"
                }

            event_stream.emit(
                "tool_progress",
                {
                    "tool_name": self.name,
                    "stage": "email_prepared",
                    "recipient_count": len(recipients),
                    "subject": subject[:120],
                },
            )

            if not subject:
                return {
                    "success": False,
                    "error": "Email subject is required"
                }

            if not body:
                return {
                    "success": False,
                    "error": "Email body is required"
                }

            # Create email record
            email_id = datetime.now().isoformat()
            record = {
                "id": email_id,
                "timestamp": datetime.now().isoformat(),
                "to": recipients,
                "cc": cc_list,
                "bcc": bcc_list,
                "subject": subject,
                "body": body,
                "status": "saved",
            }

            smtp_server = _clean_env(os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")) or "smtp.gmail.com"
            smtp_port = int(_clean_env(os.getenv("EMAIL_SMTP_PORT", "587")) or 587)
            smtp_username = _clean_env(os.getenv("EMAIL_USERNAME"))
            smtp_password = _clean_env(os.getenv("EMAIL_PASSWORD"))
            smtp_use_ssl = _clean_env(os.getenv("EMAIL_USE_SSL", "false")).lower() in ("1", "true", "yes")
            smtp_use_tls = _clean_env(os.getenv("EMAIL_USE_TLS", "true")).lower() in ("1", "true", "yes")
            from_address = _clean_env(os.getenv("EMAIL_FROM", smtp_username or "no-reply@example.com")) or (smtp_username or "no-reply@example.com")

            if send_via_smtp and smtp_server and smtp_username and smtp_password:
                try:
                    event_stream.emit(
                        "external_service_accessed",
                        {
                            "tool_name": self.name,
                            "service": "smtp",
                            "server": smtp_server,
                            "port": smtp_port,
                        },
                    )
                    event_stream.emit(
                        "tool_progress",
                        {
                            "tool_name": self.name,
                            "stage": "smtp_send_started",
                            "server": smtp_server,
                            "recipient_count": len(recipients),
                        },
                    )
                    self._send_smtp(
                        smtp_server,
                        smtp_port,
                        smtp_username,
                        smtp_password,
                        from_address,
                        recipients,
                        subject,
                        body,
                        cc_list,
                        bcc_list,
                        smtp_use_ssl,
                        smtp_use_tls,
                    )
                    record["status"] = "sent"
                    record["sent_via"] = "smtp"
                    event_stream.emit(
                        "tool_progress",
                        {
                            "tool_name": self.name,
                            "stage": "smtp_send_completed",
                            "server": smtp_server,
                            "recipient_count": len(recipients),
                        },
                    )
                except Exception as smtp_error:
                    record["status"] = "failed"
                    record["error"] = str(smtp_error)
                    event_stream.emit(
                        "tool_progress",
                        {
                            "tool_name": self.name,
                            "stage": "smtp_send_failed",
                            "server": smtp_server,
                            "error": str(smtp_error),
                        },
                        level="error",
                    )
                    email_file = EMAIL_DIR / f"failed_{email_id.replace(':', '-')}.json"
                    with open(email_file, "w", encoding="utf-8") as f:
                        json.dump(record, f, indent=2)
                    return {
                        "success": False,
                        "error": f"SMTP send failed: {smtp_error}",
                        "saved_to": str(email_file)
                    }
            else:
                record["status"] = "saved"
                event_stream.emit(
                    "tool_progress",
                    {
                        "tool_name": self.name,
                        "stage": "email_saved_local_only",
                        "recipient_count": len(recipients),
                    },
                )

            # Save email record locally
            email_file = EMAIL_DIR / f"sent_{email_id.replace(':', '-')}.json"
            with open(email_file, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)

            return {
                "success": True,
                "result": {
                    "email_id": email_id,
                    "to": recipients,
                    "subject": subject,
                    "status": record["status"],
                    "saved_to": str(email_file),
                    "sent_via": record.get("sent_via", "local")
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _send_smtp(
        self,
        server: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        to: List[str],
        subject: str,
        body: str,
        cc: List[str],
        bcc: List[str],
        use_ssl: bool,
        use_tls: bool,
    ) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = from_address
        message["To"] = ", ".join(to)
        if cc:
            message["Cc"] = ", ".join(cc)
        message.set_content(body)

        recipients = to + cc + bcc

        if use_ssl:
            smtp = smtplib.SMTP_SSL(server, port, timeout=30)
        else:
            smtp = smtplib.SMTP(server, port, timeout=30)
            smtp.ehlo()
            if use_tls:
                smtp.starttls()
                smtp.ehlo()

        smtp.login(username, password)
        smtp.send_message(message, from_addr=from_address, to_addrs=recipients)
        smtp.quit()


class ListEmailsTool(BaseTool):
    """List sent/received emails."""
    
    name = "list_emails"
    description = "List sent and received emails"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        List emails.
        
        Args:
            folder: "sent", "received", or "all" (default: "all")
            limit: Maximum emails to return (default: 10)
        """
        try:
            folder = kwargs.get("folder", "all")
            limit = kwargs.get("limit", 10)
            
            emails = []
            
            if folder in ("sent", "all"):
                sent_files = sorted(EMAIL_DIR.glob("sent_*.json"), reverse=True)
                for file in sent_files[:limit]:
                    with open(file) as f:
                        emails.append(json.load(f))
            
            if folder in ("received", "all"):
                recv_files = sorted(EMAIL_DIR.glob("received_*.json"), reverse=True)
                for file in recv_files[:limit]:
                    with open(file) as f:
                        emails.append(json.load(f))
            
            # Sort by timestamp
            emails = sorted(emails, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
            
            return {
                "success": True,
                "result": {
                    "count": len(emails),
                    "emails": emails
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class GetEmailTool(BaseTool):
    """Get a specific email by ID."""
    
    name = "get_email"
    description = "Get a specific email by ID"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Get an email.
        
        Args:
            email_id: The email ID to retrieve
        """
        try:
            email_id = kwargs.get("email_id", "")
            
            if not email_id:
                return {
                    "success": False,
                    "error": "email_id is required"
                }
            
            # Search for email file
            email_file = None
            for file in EMAIL_DIR.glob("*_*.json"):
                if email_id in file.name:
                    email_file = file
                    break
            
            if not email_file or not email_file.exists():
                return {
                    "success": False,
                    "error": f"Email {email_id} not found"
                }
            
            with open(email_file) as f:
                email = json.load(f)
            
            return {
                "success": True,
                "result": email
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class SearchEmailsTool(BaseTool):
    """Search emails by subject or body."""
    
    name = "search_emails"
    description = "Search emails by subject or body content"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Search emails.
        
        Args:
            query: Search term
            field: "subject", "body", or "all" (default: "all")
            limit: Maximum results (default: 10)
        """
        try:
            query = kwargs.get("query", "")
            field = kwargs.get("field", "all")
            limit = kwargs.get("limit", 10)
            
            if not query:
                return {
                    "success": False,
                    "error": "query is required"
                }
            
            results = []
            query_lower = query.lower()
            
            for file in EMAIL_DIR.glob("*_*.json"):
                with open(file) as f:
                    email = json.load(f)
                
                match = False
                if field in ("subject", "all"):
                    if query_lower in email.get("subject", "").lower():
                        match = True
                
                if field in ("body", "all"):
                    if query_lower in email.get("body", "").lower():
                        match = True
                
                if match:
                    results.append(email)
            
            # Sort by timestamp descending
            results = sorted(results, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]
            
            return {
                "success": True,
                "result": {
                    "query": query,
                    "count": len(results),
                    "emails": results
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
