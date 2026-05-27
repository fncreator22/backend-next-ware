import logging
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.config import settings

logger = logging.getLogger("wareops_erp.utils.email")

async def send_invitation_email(
    recipient_email: str,
    recipient_name: str,
    company_name: str,
    role: str,
    temp_password: str,
    warehouse_name: str,
    signin_url: str = "http://localhost:8080/#/login"
) -> bool:
    """
    Asynchronously send an invitation email to a newly created workforce member.
    If SMTP server configurations are not found, falls back safely to logging the formatted email.
    Includes robust retry logic with exponential backoff.
    """
    subject = f"Welcome to {company_name} on WareOps ERP!"
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #1e293b; background-color: #f8fafc; padding: 24px;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); padding: 32px;">
            <div style="font-size: 24px; font-weight: bold; color: #6366f1; margin-bottom: 20px; display: flex; align-items: center; gap: 8px;">
                ⚡ WareOps ERP
            </div>
            <h2 style="font-size: 20px; font-weight: 800; color: #0f172a; margin-bottom: 12px;">Hello, {recipient_name}!</h2>
            <p>You have been invited by your Super Admin to join <strong>{company_name}</strong> as an enterprise workforce member.</p>
            
            <div style="background-color: #f1f5f9; border-radius: 8px; padding: 16px 20px; margin: 24px 0;">
                <h3 style="margin-top: 0; font-size: 14px; text-transform: uppercase; color: #475569; letter-spacing: 0.05em;">Your Account Profile Details</h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <tr>
                        <td style="padding: 4px 0; color: #64748b; width: 140px;"><strong>Assigned Role:</strong></td>
                        <td style="padding: 4px 0; color: #0f172a; font-weight: 600;">{role.replace('_', ' ').title()}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: #64748b;"><strong>Primary Location:</strong></td>
                        <td style="padding: 4px 0; color: #0f172a; font-weight: 600;">{warehouse_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: #64748b;"><strong>Login Email:</strong></td>
                        <td style="padding: 4px 0; color: #0f172a; font-family: monospace; font-size: 13px;">{recipient_email}</td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 0; color: #64748b;"><strong>Temporary Password:</strong></td>
                        <td style="padding: 4px 0; color: #e11d48; font-family: monospace; font-size: 13px; font-weight: bold;">{temp_password}</td>
                    </tr>
                </table>
            </div>

            <div style="text-align: center; margin: 32px 0 20px 0;">
                <a href="{signin_url}" style="background-color: #6366f1; color: #ffffff; text-decoration: none; padding: 12px 28px; border-radius: 8px; font-weight: bold; font-size: 15px; box-shadow: 0 4px 6px -1px rgba(99,102,241,0.4);">
                    Sign In to Portal
                </a>
            </div>
            
            <p style="font-size: 12px; color: #64748b; margin-top: 32px; border-top: 1px solid #e2e8f0; padding-top: 16px; text-align: center;">
                This is an automated operational notification. Please configure a custom password immediately upon first login.
            </p>
        </div>
    </body>
    </html>
    """

    # If SMTP_HOST is not configured, fall back to print logging (development mode)
    if not settings.SMTP_HOST:
        logger.info(
            f"\n[SMTP Fallback Logging Mode] No SMTP server configured. Displaying email invitation below:\n"
            f"================================================================================\n"
            f"TO: {recipient_name} <{recipient_email}>\n"
            f"SUBJECT: {subject}\n"
            f"--------------------------------------------------------------------------------\n"
            f"Welcome to {company_name} as {role.replace('_', ' ').title()}.\n"
            f"Assigned Warehouse Hub: {warehouse_name}\n"
            f"Temporary Password: {temp_password}\n"
            f"Sign In URL: {signin_url}\n"
            f"================================================================================\n"
        )
        return True

    # SMTP Configuration is present - send standard MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = recipient_email
    msg.attach(MIMEText(html_content, "html"))

    # Implement retries with exponential backoff
    max_retries = 3
    delay = 1
    
    for attempt in range(max_retries):
        try:
            # Execute smtplib synchronously in a separate thread so as not to block FastAPI main loop
            def send():
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                        server.starttls()
                        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    server.sendmail(settings.SMTP_FROM, recipient_email, msg.as_string())
            
            await asyncio.to_thread(send)
            logger.info(f"Successfully sent workforce invitation email to '{recipient_email}' via SMTP.")
            return True
        except Exception as e:
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries} failed to send email to '{recipient_email}': {e}. "
                f"Retrying in {delay} seconds..."
            )
            await asyncio.sleep(delay)
            delay *= 2
            
    logger.error(f"Failed to send workforce invitation email to '{recipient_email}' after {max_retries} attempts.")
    return False
