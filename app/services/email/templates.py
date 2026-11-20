from __future__ import annotations

from typing import Optional


def render_confirmation_text(
    recipient_email: str,
    product_name: str,
    company_name: str,
    user_type: str = "tenant",
    name: Optional[str] = None,
    phone: Optional[str] = None,
    areas: Optional[str] = None,
    role: Optional[str] = None,
) -> str:
    """Renders plain-text fallback version of the waitlist confirmation email."""
    greeting = f"Hi {name.strip()}" if name and name.strip() else "Hello"

    if user_type == "agent":
        role_label = role or "Agent / Landlord"
        return f"""{greeting},

Thank you for requesting an invite to partner with {product_name}!

We have received your request for listings in: {areas or 'your operating areas'}.

Your Submitted Profile:
- Role: {role_label}
- Operating Area(s): {areas or 'Not specified'}
- WhatsApp Number: {phone or 'Not specified'}
- Registered Email: {recipient_email}

What happens next?
1. Personal Review: We review every agent, landlord, and property manager before launch to ensure a verified network.
2. Serious tenants only: Every tenant sent to inspect your properties has paid an inspection fee, eliminating time-wasters and no-shows.
3. Keep full commission: Deal directly with the tenant and keep your full commission without middlemen.
4. WhatsApp Onboarding: Someone from our team will reach out directly on WhatsApp ({phone or 'your number'}) before we launch.

Thank you for your early support!

Best regards,
The {product_name} Team

---
You received this email because you requested an agent/landlord invite at {company_name}.
If you did not request this, you can safely ignore this email.
"""

    # Tenant template
    return f"""{greeting},

Congratulations! You're officially on the waitlist for {product_name}.

We have saved your home search preferences:
- Target Area(s): {areas or 'Not specified'}
- WhatsApp Number: {phone or 'Not specified'}
- Registered Email: {recipient_email}

What happens next?
1. Red flags filtered out: We inspect and verify properties beforehand so you never waste days on places with flooding, bad access roads, or misleading photos.
2. Personalised matches: Instead of endless scrolling, you'll receive a short, curated list matching your taste and budget.
3. WhatsApp notification: We'll message you directly on WhatsApp ({phone or 'your number'}) as soon as verified houses open in your area!

Thank you for your early support!

Best regards,
The {product_name} Team

---
You received this email because you signed up for the waitlist at {company_name}.
If you did not request this, you can safely ignore this email.
"""


def render_confirmation_html(
    recipient_email: str,
    product_name: str,
    company_name: str,
    user_type: str = "tenant",
    name: Optional[str] = None,
    phone: Optional[str] = None,
    areas: Optional[str] = None,
    role: Optional[str] = None,
) -> str:
    """Renders responsive HTML version of the waitlist confirmation email."""
    greeting = f"Hi {name.strip()}" if name and name.strip() else "Hi there"

    if user_type == "agent":
        role_label = role or "Agent / Landlord"
        badge_text = "Agent Partnership Request"
        header_title = "Agent Request Received! 🏢"
        intro_text = f"Thank you for your interest in partnering with <strong>{product_name}</strong>! We have received your request for listings in <strong>{areas or 'your operating areas'}</strong>."
        details_html = f"""
          <div class="highlight-card">
            <p>Role: <strong>{role_label}</strong></p>
            <p style="margin-top: 6px;">Operating Area(s): <strong>{areas or 'Not specified'}</strong></p>
            <p style="margin-top: 6px;">WhatsApp: <strong>{phone or 'Not specified'}</strong></p>
            <p style="margin-top: 6px;">Email: <strong>{recipient_email}</strong></p>
          </div>
        """
        steps_html = f"""
          <ul class="steps-list">
            <li><strong>Personal Verification:</strong> We review every agent, landlord, and property manager before launch to ensure a verified network.</li>
            <li><strong>Serious Tenants Only:</strong> Every tenant sent to inspect your properties has paid an inspection fee, eliminating time-wasters and no-shows.</li>
            <li><strong>Keep Full Commission:</strong> Deal directly with the tenant and keep your full commission without middlemen.</li>
            <li><strong>WhatsApp Onboarding:</strong> Someone from our partnership team will reach out directly on WhatsApp (<strong>{phone or 'your number'}</strong>) before we open.</li>
          </ul>
        """
    else:
        badge_text = "Spot Confirmed"
        header_title = "You're on the waitlist! 🎉"
        intro_text = f"Thank you for your interest in <strong>{product_name}</strong>! You have officially joined our waitlist and your spot is confirmed."
        details_html = f"""
          <div class="highlight-card">
            <p>Target Area(s): <strong>{areas or 'Not specified'}</strong></p>
            <p style="margin-top: 6px;">WhatsApp: <strong>{phone or 'Not specified'}</strong></p>
            <p style="margin-top: 6px;">Registered Email: <strong>{recipient_email}</strong></p>
          </div>
        """
        steps_html = f"""
          <ul class="steps-list">
            <li><strong>Fewer Inspections, Better Houses:</strong> We inspect and filter properties beforehand so you never waste days on places with flooding, bad roads, or misleading photos.</li>
            <li><strong>Personalised Matches:</strong> Instead of endless scrolling, you'll receive a short, curated list matching your taste and budget.</li>
            <li><strong>WhatsApp Notification:</strong> We'll message you on WhatsApp (<strong>{phone or 'your number'}</strong>) as soon as verified houses open in your area.</li>
          </ul>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{header_title}</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #14213a;
      -webkit-font-smoothing: antialiased;
    }}
    .wrapper {{
      width: 100%;
      table-layout: fixed;
      background-color: #f8fafc;
      padding: 40px 16px;
    }}
    .container {{
      max-width: 580px;
      margin: 0 auto;
      background-color: #ffffff;
      border-radius: 14px;
      border: 1px solid #dde3ec;
      overflow: hidden;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
    }}
    .header {{
      background: #0f2342;
      padding: 34px 28px;
      text-align: center;
      color: #ffffff;
    }}
    .header h1 {{
      margin: 0;
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    .badge {{
      display: inline-block;
      margin-top: 10px;
      padding: 5px 14px;
      background-color: #ddf5ea;
      color: #066a47;
      border-radius: 9999px;
      font-size: 13px;
      font-weight: 700;
    }}
    .content {{
      padding: 30px 28px 24px 28px;
      line-height: 1.6;
      font-size: 15px;
      color: #334155;
    }}
    .highlight-card {{
      background-color: #f6f8fb;
      border-left: 4px solid #0e9f6e;
      padding: 16px 20px;
      border-radius: 8px;
      margin: 22px 0;
      font-size: 14.5px;
    }}
    .highlight-card p {{
      margin: 0;
      color: #55627a;
    }}
    .highlight-card strong {{
      color: #0f2342;
    }}
    .steps-list {{
      margin: 18px 0;
      padding-left: 20px;
    }}
    .steps-list li {{
      margin-bottom: 12px;
      line-height: 1.5;
    }}
    .steps-list strong {{
      color: #0f2342;
    }}
    .footer {{
      padding: 22px 28px;
      background-color: #f8fafc;
      border-top: 1px solid #dde3ec;
      text-align: center;
      font-size: 12px;
      color: #8896ab;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <table class="container" role="presentation" cellpadding="0" cellspacing="0" width="100%">
      <tr>
        <td class="header">
          <h1>{header_title}</h1>
          <div class="badge">{badge_text}</div>
        </td>
      </tr>
      <tr>
        <td class="content">
          <p>{greeting},</p>
          <p>{intro_text}</p>
          
          {details_html}

          <h3 style="margin-top: 24px; font-size: 16px; color: #0f2342;">What happens next?</h3>
          {steps_html}

          <p style="margin-top: 24px;">
            Thank you for backing us early!
          </p>
          <p style="margin-bottom: 0;">
            — The <strong>{product_name}</strong> Team
          </p>
        </td>
      </tr>
      <tr>
        <td class="footer">
          <p style="margin: 0 0 6px 0;">© {company_name}. All rights reserved.</p>
          <p style="margin: 0;">You received this email because you registered on ConfirmBase.</p>
        </td>
      </tr>
    </table>
  </div>
</body>
</html>
"""
