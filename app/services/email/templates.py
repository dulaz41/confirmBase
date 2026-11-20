from __future__ import annotations

from typing import Optional
from app.core.config import settings


def render_confirmation_text(
    recipient_email: str,
    product_name: str,
    company_name: str,
    user_type: str = "tenant",
    name: Optional[str] = None,
    phone: Optional[str] = None,
    areas: Optional[str] = None,
    role: Optional[str] = None,
    founder_name: Optional[str] = None,
    share_link: Optional[str] = None,
    whatsapp_group_url: Optional[str] = None,
    privacy_url: Optional[str] = None,
    unsubscribe_url: Optional[str] = None,
) -> str:
    """Renders plain-text fallback version of the waitlist confirmation email."""
    first_name = name.strip().split()[0] if name and name.strip() else ""
    salutation = f"Hi {first_name}," if first_name else "Hi,"
    sign_off_name = founder_name or getattr(settings, "FOUNDER_NAME", "The ConfirmBase Team")
    if "team" in sign_off_name.lower():
        sign_off_block = sign_off_name
    else:
        sign_off_block = f"{sign_off_name}\nFounder, {product_name}"
    share = share_link or getattr(
        settings, "WAITLIST_URL", "https://getconfirmbase.com"
    )
    privacy = privacy_url or getattr(
        settings,
        "PRIVACY_POLICY_URL",
        "https://docs.google.com/document/d/1-9Pab8LJ2yupF5v0zMRMrjSvq9tZWC1E/preview",
    )
    base_url = getattr(settings, "WAITLIST_URL", "https://getconfirmbase.com").rstrip(
        "/"
    )
    unsub = (
        unsubscribe_url
        or getattr(settings, "UNSUBSCRIBE_URL", None)
        or f"{base_url}/v1/waitlist/unsubscribe?email={recipient_email}"
    )

    if user_type == "agent":
        group_url = whatsapp_group_url or getattr(
            settings,
            "WHATSAPP_AGENT_GROUP_URL",
            "https://chat.whatsapp.com/JzyeEqqgIgMJVWsuAYMKWK?s=cl&p=a&mlu=4&ilr=4",
        )
        return f"""{salutation}

Thanks for your interest in listing on {product_name}. Your request is in, and we review every one personally. Here’s what happens next.

What happens next

We’ll be in touch: we’ll let you know once we’ve reviewed your request, and before we open in Kubwa.
Serious tenants: your houses are matched with tenants whose taste they suit.
Direct deals: you deal directly with tenants and keep your full commission.

While you wait

Join the Kubwa agents WhatsApp group: {group_url}

Know another agent in Kubwa who should hear about this? Send them this link: {share}

Thanks again,
{sign_off_block}

---
{product_name}, Kubwa, Abuja · Reply to this email anytime · Privacy: {privacy} · Unsubscribe: {unsub}
"""

    # Tenant template
    group_url = whatsapp_group_url or getattr(
        settings,
        "WHATSAPP_TENANT_GROUP_URL",
        "https://chat.whatsapp.com/EifxSYFTE1J3oO4LsQUBdu?s=cl&p=a&mlu=4&ilr=4",
    )
    return f"""{salutation}

Thanks for backing {product_name} early. You’re on the list for Kubwa, and here’s what happens next.

What happens next

Personalised matches: instead of endless scrolling, you’ll see a short list of homes that fit your taste and budget.
Fewer wasted trips: your red flags are left out, so you spend less time inspecting places that were never right for you.
We’ll let you know: you’ll hear from us before we open, so you’re among the first to see your matches.

While you wait

Join the Kubwa tenants WhatsApp group: {group_url}

Know someone else house hunting in Kubwa? Send them this link: {share}

Talk soon,
{sign_off_block}

---
{product_name}, Kubwa, Abuja · Reply to this email anytime · Privacy: {privacy} · Unsubscribe: {unsub}
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
    founder_name: Optional[str] = None,
    share_link: Optional[str] = None,
    whatsapp_group_url: Optional[str] = None,
    privacy_url: Optional[str] = None,
    unsubscribe_url: Optional[str] = None,
) -> str:
    """Renders responsive HTML version of the waitlist confirmation email."""
    first_name = name.strip().split()[0] if name and name.strip() else ""
    salutation = f"Hi {first_name}," if first_name else "Hi,"
    sign_off_name = founder_name or getattr(settings, "FOUNDER_NAME", "The ConfirmBase Team")
    if "team" in sign_off_name.lower():
        sign_off_html = f'<p style="margin: 4px 0 0 0; font-weight: 700; color: #00140e;">{sign_off_name}</p>'
    else:
        sign_off_html = f'''<p style="margin: 4px 0 0 0; font-weight: 700; color: #00140e;">{sign_off_name}</p>
            <p style="margin: 2px 0 0 0; color: #666666; font-size: 14px;">Founder, {product_name}</p>'''
    share = share_link or getattr(
        settings, "WAITLIST_URL", "https://getconfirmbase.com"
    )
    privacy = privacy_url or getattr(
        settings,
        "PRIVACY_POLICY_URL",
        "https://docs.google.com/document/d/1-9Pab8LJ2yupF5v0zMRMrjSvq9tZWC1E/preview",
    )
    base_url = getattr(settings, "WAITLIST_URL", "https://getconfirmbase.com").rstrip(
        "/"
    )
    unsub = (
        unsubscribe_url
        or getattr(settings, "UNSUBSCRIBE_URL", None)
        or f"{base_url}/v1/waitlist/unsubscribe?email={recipient_email}"
    )

    if user_type == "agent":
        header_title = "Request received"
        preheader_text = "We review every request personally and will be in touch."
        group_url = whatsapp_group_url or getattr(
            settings,
            "WHATSAPP_AGENT_GROUP_URL",
            "https://chat.whatsapp.com/JzyeEqqgIgMJVWsuAYMKWK?s=cl&p=a&mlu=4&ilr=4",
        )
        intro_text = (
            f"Thanks for your interest in listing on <strong>{product_name}</strong>. "
            "Your request is in, and we review every one personally. Here’s what happens next."
        )
        steps_html = """
          <ul class="steps-list">
            <li><strong>We’ll be in touch:</strong> we’ll let you know once we’ve reviewed your request, and before we open in Kubwa.</li>
            <li><strong>Serious tenants:</strong> your houses are matched with tenants whose taste they suit.</li>
            <li><strong>Direct deals:</strong> you deal directly with tenants and keep your full commission.</li>
          </ul>
        """
        whatsapp_button_text = "Join the Kubwa agents WhatsApp group &rarr;"
        share_text = f'Know another agent in Kubwa who should hear about this? Send them this link: <a href="{share}" class="link-share" style="color: #00614d; font-weight: 600; text-decoration: underline;">{share}</a>'
        sign_off_phrase = "Thanks again,"
    else:
        header_title = "You’re on the list"
        preheader_text = "We’ll let you know before we open in Kubwa."
        group_url = whatsapp_group_url or getattr(
            settings,
            "WHATSAPP_TENANT_GROUP_URL",
            "https://chat.whatsapp.com/EifxSYFTE1J3oO4LsQUBdu?s=cl&p=a&mlu=4&ilr=4",
        )
        intro_text = (
            f"Thanks for backing <strong>{product_name}</strong> early. "
            "You’re on the list for Kubwa, and here’s what happens next."
        )
        steps_html = """
          <ul class="steps-list">
            <li><strong>Personalised matches:</strong> instead of endless scrolling, you’ll see a short list of homes that fit your taste and budget.</li>
            <li><strong>Fewer wasted trips:</strong> your red flags are left out, so you spend less time inspecting places that were never right for you.</li>
            <li><strong>We’ll let you know:</strong> you’ll hear from us before we open, so you’re among the first to see your matches.</li>
          </ul>
        """
        whatsapp_button_text = "Join the Kubwa tenants WhatsApp group &rarr;"
        share_text = f'Know someone else house hunting in Kubwa? Send them this link: <a href="{share}" class="link-share" style="color: #00614d; font-weight: 600; text-decoration: underline;">{share}</a>'
        sign_off_phrase = "Talk soon,"

    brand_logo_html = (
        '<div class="logo" style="font-size: 21px; font-weight: 700; letter-spacing: -0.03em; margin-bottom: 12px; color: #ffffff;">confirm<span class="logo-base" style="color: #d8b36a;">Base</span></div>'
        if "confirmbase" in product_name.lower()
        else f'<div class="logo" style="font-size: 21px; font-weight: 700; letter-spacing: -0.03em; margin-bottom: 12px; color: #ffffff;">{product_name}</div>'
    )

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
      background-color: #f5f4f3;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #262626;
      -webkit-font-smoothing: antialiased;
    }}
    .wrapper {{
      width: 100%;
      table-layout: fixed;
      background-color: #f5f4f3;
      padding: 40px 16px;
    }}
    .container {{
      max-width: 580px;
      margin: 0 auto;
      background-color: #ffffff;
      border-radius: 16px;
      border: 1px solid #e5e5e5;
      overflow: hidden;
      box-shadow: 0 4px 20px rgba(0, 20, 14, 0.08);
    }}
    .header {{
      background: #00140e;
      border-bottom: 3px solid #ffc760;
      padding: 34px 28px 30px 28px;
      text-align: center;
      color: #ffffff;
    }}
    .logo {{
      font-size: 21px;
      font-weight: 700;
      letter-spacing: -0.03em;
      margin-bottom: 12px;
      color: #ffffff;
    }}
    .logo-base {{
      color: #d8b36a;
    }}
    .header h1 {{
      margin: 0;
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: #ffffff;
    }}
    .content {{
      padding: 32px 28px 24px 28px;
      line-height: 1.6;
      font-size: 15px;
      color: #363636;
    }}
    .section-title {{
      margin-top: 26px;
      margin-bottom: 10px;
      font-size: 16px;
      font-weight: 700;
      color: #00140e;
    }}
    .steps-list {{
      margin: 12px 0 20px 0;
      padding-left: 20px;
    }}
    .steps-list li {{
      margin-bottom: 12px;
      line-height: 1.5;
    }}
    .steps-list strong {{
      color: #00140e;
    }}
    .btn-whatsapp,
    .btn-whatsapp:link,
    .btn-whatsapp:visited,
    .btn-whatsapp:hover,
    .btn-whatsapp:active {{
      display: inline-block;
      background-color: #00614d;
      color: #ffffff !important;
      text-decoration: none !important;
      font-size: 15px;
      font-weight: 700;
      padding: 13px 22px;
      border-radius: 10px;
      text-align: center;
    }}
    .btn-whatsapp span {{
      color: #ffffff !important;
      text-decoration: none !important;
    }}
    .link-share {{
      color: #00614d;
      font-weight: 600;
      text-decoration: underline;
    }}
    .footer {{
      padding: 22px 28px;
      background-color: #f5f4f3;
      border-top: 1px solid #e5e5e5;
      text-align: center;
      font-size: 12px;
      color: #737373;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <!-- Hidden preheader text for email client snippet preview -->
  <div style="display:none;font-size:1px;color:#ffffff;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;mso-hide:all;">
    {preheader_text}
  </div>

  <div class="wrapper">
    <table class="container" role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width: 580px; margin: 0 auto; background-color: #ffffff; border-radius: 16px; border: 1px solid #e5e5e5; overflow: hidden; box-shadow: 0 4px 20px rgba(0, 20, 14, 0.08);">
      <tr>
        <td class="header" style="background-color: #00140e; border-bottom: 3px solid #ffc760; padding: 34px 28px 30px 28px; text-align: center; color: #ffffff;">
          {brand_logo_html}
          <h1 style="margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.02em; color: #ffffff;">{header_title}</h1>
        </td>
      </tr>
      <tr>
        <td class="content" style="padding: 32px 28px 24px 28px; line-height: 1.6; font-size: 15px; color: #363636;">
          <p>{salutation}</p>
          <p style="margin-top: 14px;">{intro_text}</p>

          <h3 class="section-title">What happens next</h3>
          {steps_html}

          <h3 class="section-title">While you wait</h3>
          <div style="margin: 16px 0 20px 0;">
            <a href="{group_url}" target="_blank" class="btn-whatsapp" style="display: inline-block; background-color: #00614d; color: #ffffff !important; text-decoration: none !important; font-size: 15px; font-weight: 700; padding: 13px 22px; border-radius: 10px; text-align: center; -webkit-text-size-adjust: none;">
              <span style="color: #ffffff !important; text-decoration: none !important; font-weight: 700;">{whatsapp_button_text}</span>
            </a>
          </div>

          <p style="margin-top: 16px; font-size: 14.5px; color: #555555; line-height: 1.5;">
            {share_text}
          </p>

          <div style="margin-top: 28px; line-height: 1.5;">
            <p style="margin: 0;">{sign_off_phrase}</p>
            {sign_off_html}
          </div>
        </td>
      </tr>
      <tr>
        <td class="footer" style="padding: 22px 28px; background-color: #f5f4f3; border-top: 1px solid #e5e5e5; text-align: center; font-size: 12px; color: #737373; line-height: 1.5;">
          <p style="margin: 0 0 6px 0;">
            {product_name}, Kubwa, Abuja &middot; Reply to this email anytime
          </p>
          <p style="margin: 0; font-size: 11.5px; color: #737373;">
            <a href="{privacy}" target="_blank" style="color: #737373; text-decoration: underline;">Privacy</a> &middot; <a href="{unsub}" target="_blank" style="color: #737373; text-decoration: underline;">Unsubscribe</a>
          </p>
        </td>
      </tr>
    </table>
  </div>
</body>
</html>
"""
