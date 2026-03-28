"""Email notification service using AWS SES."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EmailConfig:
    """Email service configuration."""

    enabled: bool
    sender_email: str
    sender_name: str
    region: str

    @classmethod
    def from_env(cls) -> "EmailConfig":
        return cls(
            enabled=os.getenv("EMAIL_ENABLED", "0") == "1",
            sender_email=os.getenv("EMAIL_SENDER", "noreply@opensre.io"),
            sender_name=os.getenv("EMAIL_SENDER_NAME", "OpenSRE"),
            region=os.getenv("AWS_REGION", "us-west-2"),
        )


def get_ses_client():
    """Get AWS SES client."""
    import boto3

    config = EmailConfig.from_env()
    return boto3.client("ses", region_name=config.region)


def send_email(
    to_addresses: List[str],
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> bool:
    """Send an email via AWS SES.

    Returns True if successful, False otherwise.
    """
    config = EmailConfig.from_env()

    if not config.enabled:
        logger.info(f"Email disabled, would send to {to_addresses}: {subject}")
        return True

    if not to_addresses:
        logger.warning("No recipients for email")
        return False

    try:
        ses = get_ses_client()

        response = ses.send_email(
            Source=f"{config.sender_name} <{config.sender_email}>",
            Destination={"ToAddresses": to_addresses},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                    **(
                        {"Text": {"Data": text_body, "Charset": "UTF-8"}}
                        if text_body
                        else {}
                    ),
                },
            },
        )

        logger.info(f"Email sent: {response.get('MessageId')} to {to_addresses}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_addresses}: {e}")
        return False


# =============================================================================
# Email Templates
# =============================================================================


def _base_template(
    content: str, action_url: Optional[str] = None, action_text: Optional[str] = None
) -> str:
    """Base HTML email template."""
    action_button = ""
    if action_url and action_text:
        action_button = f"""
        <tr>
          <td style="padding: 24px 0;">
            <a href="{action_url}" style="display: inline-block; padding: 12px 24px; background-color: #ea580c; color: white; text-decoration: none; border-radius: 8px; font-weight: 600;">
              {action_text}
            </a>
          </td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #f3f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f3f4f6; padding: 32px 16px;">
        <tr>
          <td align="center">
            <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 560px; background-color: white; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
              <!-- Header -->
              <tr>
                <td style="padding: 24px; border-bottom: 1px solid #e5e7eb;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td>
                        <span style="display: inline-flex; align-items: center; gap: 8px; font-size: 18px; font-weight: 700; color: #111827;">
                          🦊 OpenSRE
                        </span>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
              
              <!-- Content -->
              <tr>
                <td style="padding: 24px;">
                  {content}
                </td>
              </tr>
              
              <!-- Action Button -->
              {action_button}
              
              <!-- Footer -->
              <tr>
                <td style="padding: 24px; border-top: 1px solid #e5e7eb; text-align: center;">
                  <p style="margin: 0; font-size: 12px; color: #6b7280;">
                    This is an automated message from OpenSRE.
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """


def send_token_expiry_warning(
    to_email: str,
    token_name: str,
    team_name: str,
    expires_at: datetime,
    days_remaining: int,
    dashboard_url: str,
) -> bool:
    """Send token expiry warning email."""
    subject = f"⚠️ Token '{token_name}' expires in {days_remaining} days"

    content = f"""
    <h2 style="margin: 0 0 16px 0; font-size: 20px; color: #111827;">Token Expiry Warning</h2>
    <p style="margin: 0 0 16px 0; color: #374151; line-height: 1.6;">
      The token <strong>{token_name}</strong> for team <strong>{team_name}</strong> will expire on:
    </p>
    <p style="margin: 0 0 16px 0; padding: 16px; background-color: #fef3c7; border-radius: 8px; color: #92400e; font-weight: 600;">
      {expires_at.strftime("%B %d, %Y at %H:%M UTC")} ({days_remaining} days remaining)
    </p>
    <p style="margin: 0 0 16px 0; color: #374151; line-height: 1.6;">
      Please renew or replace this token before it expires to avoid service interruption.
    </p>
    """

    html_body = _base_template(
        content, action_url=dashboard_url, action_text="Manage Tokens"
    )

    return send_email([to_email], subject, html_body)


def send_token_revoked_notification(
    to_email: str,
    token_name: str,
    team_name: str,
    reason: str,
    revoked_by: str,
) -> bool:
    """Send token revoked notification email."""
    subject = f"🔒 Token '{token_name}' has been revoked"

    content = f"""
    <h2 style="margin: 0 0 16px 0; font-size: 20px; color: #111827;">Token Revoked</h2>
    <p style="margin: 0 0 16px 0; color: #374151; line-height: 1.6;">
      The token <strong>{token_name}</strong> for team <strong>{team_name}</strong> has been revoked.
    </p>
    <table style="width: 100%; margin: 16px 0; border-collapse: collapse;">
      <tr>
        <td style="padding: 8px 0; color: #6b7280; width: 100px;">Reason:</td>
        <td style="padding: 8px 0; color: #111827; font-weight: 500;">{reason}</td>
      </tr>
      <tr>
        <td style="padding: 8px 0; color: #6b7280;">Revoked by:</td>
        <td style="padding: 8px 0; color: #111827; font-weight: 500;">{revoked_by}</td>
      </tr>
    </table>
    <p style="margin: 16px 0 0 0; color: #374151; line-height: 1.6;">
      If this was unexpected, please contact your administrator.
    </p>
    """

    html_body = _base_template(content)

    return send_email([to_email], subject, html_body)


def send_pending_approval_notification(
    to_emails: List[str],
    change_type: str,
    team_name: str,
    requested_by: str,
    change_summary: str,
    dashboard_url: str,
) -> bool:
    """Send notification about a pending config change requiring approval."""
    subject = f"🔔 Approval required: {change_type} change for {team_name}"

    content = f"""
    <h2 style="margin: 0 0 16px 0; font-size: 20px; color: #111827;">Approval Required</h2>
    <p style="margin: 0 0 16px 0; color: #374151; line-height: 1.6;">
      A configuration change requires your approval:
    </p>
    <table style="width: 100%; margin: 16px 0; border-collapse: collapse; background-color: #f9fafb; border-radius: 8px;">
      <tr>
        <td style="padding: 12px 16px; color: #6b7280; border-bottom: 1px solid #e5e7eb;">Change Type:</td>
        <td style="padding: 12px 16px; color: #111827; font-weight: 500; border-bottom: 1px solid #e5e7eb;">{change_type}</td>
      </tr>
      <tr>
        <td style="padding: 12px 16px; color: #6b7280; border-bottom: 1px solid #e5e7eb;">Team:</td>
        <td style="padding: 12px 16px; color: #111827; font-weight: 500; border-bottom: 1px solid #e5e7eb;">{team_name}</td>
      </tr>
      <tr>
        <td style="padding: 12px 16px; color: #6b7280; border-bottom: 1px solid #e5e7eb;">Requested by:</td>
        <td style="padding: 12px 16px; color: #111827; font-weight: 500; border-bottom: 1px solid #e5e7eb;">{requested_by}</td>
      </tr>
      <tr>
        <td style="padding: 12px 16px; color: #6b7280;">Summary:</td>
        <td style="padding: 12px 16px; color: #111827;">{change_summary}</td>
      </tr>
    </table>
    """

    html_body = _base_template(
        content, action_url=dashboard_url, action_text="Review Changes"
    )

    return send_email(to_emails, subject, html_body)


def send_change_approved_notification(
    to_email: str,
    change_type: str,
    team_name: str,
    approved_by: str,
    comment: Optional[str] = None,
) -> bool:
    """Send notification that a config change was approved."""
    subject = f"✅ Your {change_type} change was approved"

    comment_section = ""
    if comment:
        comment_section = f"""
        <p style="margin: 16px 0 0 0; padding: 12px 16px; background-color: #f0fdf4; border-left: 4px solid #22c55e; color: #166534;">
          "{comment}"
        </p>
        """

    content = f"""
    <h2 style="margin: 0 0 16px 0; font-size: 20px; color: #111827;">Change Approved</h2>
    <p style="margin: 0 0 16px 0; color: #374151; line-height: 1.6;">
      Your <strong>{change_type}</strong> change for team <strong>{team_name}</strong> has been approved and applied.
    </p>
    <p style="margin: 0; color: #6b7280;">
      Approved by: <strong>{approved_by}</strong>
    </p>
    {comment_section}
    """

    html_body = _base_template(content)

    return send_email([to_email], subject, html_body)


def send_change_rejected_notification(
    to_email: str,
    change_type: str,
    team_name: str,
    rejected_by: str,
    comment: Optional[str] = None,
) -> bool:
    """Send notification that a config change was rejected."""
    subject = f"❌ Your {change_type} change was rejected"

    comment_section = ""
    if comment:
        comment_section = f"""
        <p style="margin: 16px 0 0 0; padding: 12px 16px; background-color: #fef2f2; border-left: 4px solid #ef4444; color: #991b1b;">
          "{comment}"
        </p>
        """

    content = f"""
    <h2 style="margin: 0 0 16px 0; font-size: 20px; color: #111827;">Change Rejected</h2>
    <p style="margin: 0 0 16px 0; color: #374151; line-height: 1.6;">
      Your <strong>{change_type}</strong> change for team <strong>{team_name}</strong> has been rejected.
    </p>
    <p style="margin: 0; color: #6b7280;">
      Rejected by: <strong>{rejected_by}</strong>
    </p>
    {comment_section}
    """

    html_body = _base_template(content)

    return send_email([to_email], subject, html_body)
