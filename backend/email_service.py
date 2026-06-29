import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Optional, List
from database import get_admin_config


async def _send_email(subject: str, html_body: str, to_email: str) -> bool:
    """Low-level async SMTP sender using DB-stored config."""
    smtp_host = get_admin_config("smtp_host", "smtp.gmail.com")
    smtp_port = int(get_admin_config("smtp_port", "587"))
    smtp_user = get_admin_config("smtp_user", "")
    smtp_password = get_admin_config("smtp_password", "")
    from_name = get_admin_config("smtp_from_name", "LegalAssist Chatbot")

    if not smtp_user or not smtp_password or not to_email:
        print(f"[Email] Skipping — SMTP not configured (user={smtp_user}, to={to_email})")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{smtp_user}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            username=smtp_user,
            password=smtp_password,
            start_tls=True,
        )
        print(f"[Email] Sent: {subject} -> {to_email}")
        return True
    except Exception as e:
        print(f"[Email] Failed to send: {e}")
        return False


async def send_user_query_email(
    user_email: str,
    user_name: Optional[str],
    query: str,
    page_url: Optional[str],
    session_id: str,
) -> bool:
    """Notify admin immediately when a user submits their email + query."""
    admin_email = get_admin_config("admin_email", "")
    if not admin_email:
        return False

    name_display = user_name or "Not provided"
    page_display = page_url or "Unknown"
    timestamp = datetime.utcnow().strftime("%d %b %Y at %H:%M UTC")

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:Arial,sans-serif;background:#f4f6f9;padding:30px;margin:0">
      <div style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08)">
        <div style="background:linear-gradient(135deg,#0f3460,#1e5f99);padding:28px 32px">
          <h1 style="color:#fff;margin:0;font-size:20px">&#9993; New Lead — Legal Assist Chatbot</h1>
          <p style="color:rgba(255,255,255,0.8);margin:6px 0 0;font-size:14px">{timestamp}</p>
        </div>
        <div style="padding:32px">
          <table style="width:100%;border-collapse:collapse">
            <tr>
              <td style="padding:12px 0;border-bottom:1px solid #eef0f4;color:#666;width:140px;font-size:14px">Name</td>
              <td style="padding:12px 0;border-bottom:1px solid #eef0f4;color:#111;font-weight:600">{name_display}</td>
            </tr>
            <tr>
              <td style="padding:12px 0;border-bottom:1px solid #eef0f4;color:#666;font-size:14px">Email</td>
              <td style="padding:12px 0;border-bottom:1px solid #eef0f4">
                <a href="mailto:{user_email}" style="color:#1e5f99;font-weight:600">{user_email}</a>
              </td>
            </tr>
            <tr>
              <td style="padding:12px 0;border-bottom:1px solid #eef0f4;color:#666;font-size:14px">Page Visited</td>
              <td style="padding:12px 0;border-bottom:1px solid #eef0f4;color:#333;font-size:13px">{page_display}</td>
            </tr>
            <tr>
              <td style="padding:12px 0;color:#666;font-size:14px;vertical-align:top">Query</td>
              <td style="padding:12px 0;color:#111">{query}</td>
            </tr>
          </table>
          <div style="margin-top:28px">
            <a href="mailto:{user_email}?subject=Re: Your Legal Enquiry"
               style="display:inline-block;background:linear-gradient(135deg,#0f3460,#1e5f99);color:#fff;
                      padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px">
              &#8617; Reply to {name_display}
            </a>
          </div>
          <p style="color:#999;font-size:12px;margin-top:24px">Session ID: {session_id} &bull; Legal Assist Chatbot</p>
        </div>
      </div>
    </body>
    </html>
    """
    return await _send_email(
        subject=f"New Chatbot Lead: {user_email}",
        html_body=html,
        to_email=admin_email,
    )


async def send_conversation_transcript(
    session_id: str,
    messages: List[dict],
    user_email: Optional[str],
    started_at: datetime,
) -> bool:
    """Email full conversation transcript to admin when session ends."""
    admin_email = get_admin_config("admin_email", "")
    auto_send = get_admin_config("auto_email_transcripts", "false") == "true"
    if not admin_email or not auto_send:
        return False

    user_display = user_email or "Anonymous"
    started_str = started_at.strftime("%d %b %Y at %H:%M UTC")

    messages_html = ""
    for msg in messages:
        if msg["role"] == "user":
            messages_html += f"""
            <div style="text-align:right;margin:8px 0">
              <span style="background:#0f3460;color:#fff;padding:8px 14px;border-radius:12px 12px 2px 12px;
                           display:inline-block;max-width:75%;font-size:14px;line-height:1.5">
                {msg['content']}
              </span>
            </div>"""
        else:
            messages_html += f"""
            <div style="text-align:left;margin:8px 0">
              <span style="background:#f0f4f8;color:#222;padding:8px 14px;border-radius:12px 12px 12px 2px;
                           display:inline-block;max-width:75%;font-size:14px;line-height:1.5">
                {msg['content']}
              </span>
            </div>"""

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family:Arial,sans-serif;background:#f4f6f9;padding:30px;margin:0">
      <div style="max-width:640px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08)">
        <div style="background:linear-gradient(135deg,#0f3460,#1e5f99);padding:28px 32px">
          <h1 style="color:#fff;margin:0;font-size:20px">&#128172; Chat Transcript</h1>
          <p style="color:rgba(255,255,255,0.8);margin:6px 0 0;font-size:14px">
            User: {user_display} &bull; Started: {started_str}
          </p>
        </div>
        <div style="padding:24px 32px;background:#fafbfc">{messages_html}</div>
        <div style="padding:16px 32px">
          <p style="color:#999;font-size:12px;margin:0">Session ID: {session_id} &bull; Legal Assist Chatbot</p>
        </div>
      </div>
    </body>
    </html>
    """
    return await _send_email(
        subject=f"Chat Transcript — {user_display}",
        html_body=html,
        to_email=admin_email,
    )
