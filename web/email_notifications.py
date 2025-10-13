"""
Email notification system for MSS usage limits
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

def send_usage_warning_email(user_email, user_name, videos_used, monthly_limit, videos_remaining):
    """Send email warning when user is nearing their monthly limit"""

    # Email configuration (use environment variables)
    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER', '')
    smtp_password = os.getenv('SMTP_PASSWORD', '')
    from_email = os.getenv('FROM_EMAIL', smtp_user)

    # Skip if email not configured
    if not smtp_user or not smtp_password:
        print("[EMAIL] Email not configured, skipping notification")
        return False

    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'⚠️ MSS Usage Alert: {videos_remaining} Videos Remaining'
    msg['From'] = f"MSS Studio <{from_email}>"
    msg['To'] = user_email

    # Plain text version
    text = f"""
Hi {user_name},

You're approaching your monthly video limit!

Usage This Month:
- Videos Created: {videos_used}/{monthly_limit}
- Remaining: {videos_remaining}

Upgrade your plan to create more videos: https://manysourcessay.com/pricing

Thanks,
The MSS Team
"""

    # HTML version
    html = f"""
<html>
<body style="font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <h2 style="color: #f59e0b;">⚠️ Usage Alert</h2>
        <p>Hi <strong>{user_name}</strong>,</p>
        <p>You're approaching your monthly video limit!</p>

        <div style="background: #fff3cd; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0;">
            <h3 style="margin-top: 0; color: #f59e0b;">Usage This Month:</h3>
            <p style="font-size: 18px; margin: 10px 0;">
                <strong>{videos_used}/{monthly_limit}</strong> videos created
            </p>
            <p style="font-size: 16px; margin: 10px 0;">
                <strong style="color: #f59e0b;">{videos_remaining} videos remaining</strong>
            </p>
        </div>

        <p>Want to create more videos? <a href="https://manysourcessay.com/pricing" style="color: #3b82f6; text-decoration: none; font-weight: bold;">Upgrade your plan</a> to get more videos every month!</p>

        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
        <p style="color: #6b7280; font-size: 14px;">
            Thanks,<br>
            The MSS Team
        </p>
    </div>
</body>
</html>
"""

    # Attach both versions
    msg.attach(MIMEText(text, 'plain'))
    msg.attach(MIMEText(html, 'html'))

    # Send email
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        print(f"[EMAIL] Sent usage warning to {user_email}")
        return True

    except Exception as e:
        print(f"[EMAIL] Failed to send: {e}")
        return False


def send_limit_reached_email(user_email, user_name, monthly_limit):
    """Send email when user has reached their monthly limit"""

    smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USER', '')
    smtp_password = os.getenv('SMTP_PASSWORD', '')
    from_email = os.getenv('FROM_EMAIL', smtp_user)

    if not smtp_user or not smtp_password:
        print("[EMAIL] Email not configured, skipping notification")
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = '🚫 MSS: Monthly Video Limit Reached'
    msg['From'] = f"MSS Studio <{from_email}>"
    msg['To'] = user_email

    text = f"""
Hi {user_name},

You've reached your monthly video limit of {monthly_limit} videos.

To continue creating videos, please upgrade your plan:
https://manysourcessay.com/pricing

Your usage will reset next month.

Thanks,
The MSS Team
"""

    html = f"""
<html>
<body style="font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <h2 style="color: #ef4444;">🚫 Monthly Limit Reached</h2>
        <p>Hi <strong>{user_name}</strong>,</p>
        <p>You've reached your monthly video limit of <strong>{monthly_limit} videos</strong>.</p>

        <div style="background: #fee2e2; border-left: 4px solid #ef4444; padding: 15px; margin: 20px 0;">
            <p style="margin: 0; font-size: 16px;">
                To continue creating videos, please upgrade your plan.
            </p>
        </div>

        <a href="https://manysourcessay.com/pricing" style="display: inline-block; background: #3b82f6; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; margin: 20px 0;">
            Upgrade Now
        </a>

        <p style="color: #6b7280;">Your usage will reset next month.</p>

        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
        <p style="color: #6b7280; font-size: 14px;">
            Thanks,<br>
            The MSS Team
        </p>
    </div>
</body>
</html>
"""

    msg.attach(MIMEText(text, 'plain'))
    msg.attach(MIMEText(html, 'html'))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

        print(f"[EMAIL] Sent limit reached notification to {user_email}")
        return True

    except Exception as e:
        print(f"[EMAIL] Failed to send: {e}")
        return False
