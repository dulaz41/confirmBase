from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WaitlistEntry
from app.core.config import settings
from app.services.email.base import BaseEmailProvider
from app.services.email.console import ConsoleEmailProvider
from app.services.email.smtp import SMTPEmailProvider
from app.services.email.resend import ResendEmailProvider
from app.services.email.sendgrid import SendGridEmailProvider
from app.services.email.service import EmailService, email_service
from app.services.email.templates import (
    render_confirmation_html,
    render_confirmation_text,
)


def test_email_template_rendering():
    """Verify HTML and plain-text email templates render with correct variables for tenants and include Privacy and Unsubscribe."""
    recipient = "subscriber@example.com"
    product = "SuperApp"
    company = "SuperApp Inc."

    text = render_confirmation_text(recipient, product, company)
    assert product in text
    assert "list for Kubwa" in text
    assert "Join the Kubwa tenants WhatsApp group" in text
    assert "Privacy" in text
    assert "Unsubscribe" in text
    assert "/v1/waitlist/unsubscribe?email=subscriber@example.com" in text

    html = render_confirmation_html(recipient, product, company)
    assert product in html
    assert "You’re on the list" in html or "You're on the list" in html
    assert "Join the Kubwa tenants WhatsApp group" in html
    assert "<!DOCTYPE html>" in html
    assert "Privacy" in html
    assert "Unsubscribe" in html
    assert "/v1/waitlist/unsubscribe?email=subscriber@example.com" in html


def test_agent_email_template_rendering():
    """Verify HTML and plain-text email templates render specifically for agents/landlords without leaking personal phone number."""
    recipient = "agent@example.com"
    product = "ConfirmBase"
    company = "ConfirmBase Ltd."

    text = render_confirmation_text(
        recipient,
        product,
        company,
        user_type="agent",
        name="Tunde",
        phone="+2348011112222",
        areas="Lekki Phase 1, Ikoyi",
        role="Licensed Agent",
    )
    assert "Hi Tunde" in text
    assert "listing on ConfirmBase" in text
    assert "keep your full commission" in text.lower()
    assert "Join the Kubwa agents WhatsApp group" in text
    assert "+2348011112222" not in text
    assert "Privacy" in text
    assert "Unsubscribe" in text
    assert "The ConfirmBase Team" in text
    assert "Axce" not in text
    assert "Founder" not in text

    html = render_confirmation_html(
        recipient,
        product,
        company,
        user_type="agent",
        name="Tunde",
        phone="+2348011112222",
        areas="Lekki Phase 1, Ikoyi",
        role="Licensed Agent",
    )
    assert "Hi Tunde" in html
    assert "Request received" in html
    assert "Serious tenants" in html
    assert "Join the Kubwa agents WhatsApp group" in html
    assert "+2348011112222" not in html
    assert "Privacy" in html
    assert "Unsubscribe" in html
    assert "The ConfirmBase Team" in html
    assert "Axce" not in html
    assert "Founder" not in html



@pytest.mark.asyncio
async def test_console_email_provider():
    """ConsoleEmailProvider successfully logs and returns True."""
    provider = ConsoleEmailProvider()
    result = await provider.send_email(
        to_email="dev@example.com",
        subject="Welcome",
        text_content="Hello world",
        html_content="<p>Hello world</p>",
    )
    assert result is True


def test_provider_factory_resolution(monkeypatch):
    """EmailService resolves the correct provider based on EMAIL_PROVIDER setting."""
    svc = EmailService()

    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "console")
    assert isinstance(svc.provider, ConsoleEmailProvider)

    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "smtp")
    assert isinstance(svc.provider, SMTPEmailProvider)

    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "resend")
    assert isinstance(svc.provider, ResendEmailProvider)

    monkeypatch.setattr(settings, "EMAIL_PROVIDER", "sendgrid")
    assert isinstance(svc.provider, SendGridEmailProvider)


@pytest.mark.asyncio
async def test_email_service_disabled_toggle(monkeypatch):
    """When SEND_CONFIRMATION_EMAIL=False, email sending is skipped."""
    monkeypatch.setattr(settings, "SEND_CONFIRMATION_EMAIL", False)
    mock_provider = MagicMock(spec=BaseEmailProvider)
    mock_provider.send_email = AsyncMock(return_value=True)

    svc = EmailService(provider=mock_provider)
    result = await svc.send_confirmation_email("test@example.com")
    assert result is False
    mock_provider.send_email.assert_not_called()


@pytest.mark.asyncio
async def test_smtp_provider_dispatch(monkeypatch):
    """SMTPEmailProvider constructs and dispatches emails via smtplib."""
    mock_smtp_instance = MagicMock()
    mock_smtp_class = MagicMock(return_value=mock_smtp_instance)

    monkeypatch.setattr("smtplib.SMTP", mock_smtp_class)
    monkeypatch.setattr(settings, "SMTP_TLS", True)
    monkeypatch.setattr(settings, "SMTP_USER", "smtp_user")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "smtp_pass")

    provider = SMTPEmailProvider()
    result = await provider.send_email(
        to_email="smtp_test@example.com",
        subject="Test Subject",
        text_content="Text body",
        html_content="<p>HTML body</p>",
    )

    assert result is True
    mock_smtp_instance.starttls.assert_called_once()
    mock_smtp_instance.login.assert_called_once_with("smtp_user", "smtp_pass")
    mock_smtp_instance.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_resend_provider_dispatch(monkeypatch):
    """ResendEmailProvider dispatches payload to Resend API endpoint."""
    monkeypatch.setattr(settings, "RESEND_API_KEY", "re_test_key_12345")
    provider = ResendEmailProvider()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = Response(status_code=200, json={"id": "email_123"})

        result = await provider.send_email(
            to_email="resend_test@example.com",
            subject="Welcome",
            text_content="Text",
            html_content="<p>HTML</p>",
        )

        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["to"] == ["resend_test@example.com"]
        assert "re_test_key_12345" in call_kwargs["headers"]["Authorization"]


@pytest.mark.asyncio
async def test_sendgrid_provider_dispatch(monkeypatch):
    """SendGridEmailProvider dispatches payload to SendGrid v3 API endpoint."""
    monkeypatch.setattr(settings, "SENDGRID_API_KEY", "SG.test_key_12345")
    provider = SendGridEmailProvider()

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = Response(status_code=202)

        result = await provider.send_email(
            to_email="sendgrid_test@example.com",
            subject="Welcome",
            text_content="Text",
            html_content="<p>HTML</p>",
        )

        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["personalizations"][0]["to"][0]["email"] == "sendgrid_test@example.com"
        assert "SG.test_key_12345" in call_kwargs["headers"]["Authorization"]


@pytest.mark.asyncio
async def test_waitlist_registration_triggers_confirmation_email(
    async_client: AsyncClient, monkeypatch
):
    """New registration triggers email_service.send_confirmation_email; duplicates do not."""
    send_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(email_service, "send_confirmation_email", send_mock)

    # 1. New registration -> Should dispatch email
    res1 = await async_client.post(
        "/api/v1/waitlist",
        json={"email": "notify_me@example.com"},
    )
    assert res1.status_code == 201
    send_mock.assert_called_once()
    assert send_mock.call_args.kwargs["to_email"] == "notify_me@example.com"

    # 2. Duplicate registration -> Should NOT dispatch email again
    send_mock.reset_mock()
    res2 = await async_client.post(
        "/api/v1/waitlist",
        json={"email": "notify_me@example.com"},
    )
    assert res2.status_code == 200
    send_mock.assert_not_called()


@pytest.mark.asyncio
async def test_tenant_and_agent_routes_trigger_differentiated_emails(
    async_client: AsyncClient, monkeypatch
):
    """Verify tenant and agent registrations pass differentiated metadata to email_service."""
    send_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(email_service, "send_confirmation_email", send_mock)

    # 1. Tenant registration
    res_tenant = await async_client.post(
        "/api/v1/waitlist/tenant",
        json={
            "phone": "08011223344",
            "email": "tenant_diff@example.com",
            "name": "Chidi",
            "areas": "Maitama",
        },
    )
    assert res_tenant.status_code == 201
    send_mock.assert_called_once_with(
        to_email="tenant_diff@example.com",
        name="Chidi",
        user_type="tenant",
        phone="08011223344",
        areas="Maitama",
    )

    # 2. Agent registration
    send_mock.reset_mock()
    res_agent = await async_client.post(
        "/api/v1/waitlist/agent",
        json={
            "phone": "08055667788",
            "email": "agent_diff@example.com",
            "name": "Bolanle",
            "role": "Direct Landlord",
            "areas": "Garki",
        },
    )
    assert res_agent.status_code == 201
    send_mock.assert_called_once_with(
        to_email="agent_diff@example.com",
        name="Bolanle",
        user_type="agent",
        phone="08055667788",
        areas="Garki",
        role="Direct Landlord",
    )


@pytest.mark.asyncio
async def test_send_confirmation_email_subject_differentiation():
    """Verify EmailService sets different subject lines and contents for agents vs tenants."""
    mock_provider = MagicMock(spec=BaseEmailProvider)
    mock_provider.send_email = AsyncMock(return_value=True)
    svc = EmailService(provider=mock_provider)

    # Tenant email
    await svc.send_confirmation_email(
        to_email="tenant@example.com",
        user_type="tenant",
        name="Tenant User",
    )
    mock_provider.send_email.assert_called_once()
    tenant_call = mock_provider.send_email.call_args[1]
    assert "You’re in, Tenant. Here’s what happens next" in tenant_call["subject"]
    assert "list for kubwa" in tenant_call["text_content"].lower()

    # Agent email
    mock_provider.send_email.reset_mock()
    await svc.send_confirmation_email(
        to_email="agent@example.com",
        user_type="agent",
        name="Agent User",
        role="Property Manager",
    )
    mock_provider.send_email.assert_called_once()
    agent_call = mock_provider.send_email.call_args[1]
    assert "Request received, Agent. Here’s what happens next" in agent_call["subject"]
    assert "listing on ConfirmBase" in agent_call["text_content"]


@pytest.mark.asyncio
async def test_waitlist_unsubscribe_endpoint(async_client: AsyncClient, db_session: AsyncSession):
    """Verify GET /api/v1/waitlist/unsubscribe marks record as unsubscribed and returns confirmation."""
    # 1. Join waitlist
    join_res = await async_client.post(
        "/api/v1/waitlist",
        json={"email": "optout_user@example.com", "name": "Optout Tester"},
    )
    assert join_res.status_code == 201

    # 2. Call unsubscribe endpoint with HTML response
    unsub_res = await async_client.get(
        "/api/v1/waitlist/unsubscribe?email=optout_user@example.com"
    )
    assert unsub_res.status_code == 200
    assert "text/html" in unsub_res.headers["content-type"]
    assert "unsubscribed" in unsub_res.text.lower()
    assert "optout_user@example.com" in unsub_res.text

    # 3. Call v1 alias endpoint with JSON response format
    unsub_json_res = await async_client.get(
        "/v1/waitlist/unsubscribe?email=optout_user@example.com&format=json"
    )
    assert unsub_json_res.status_code == 200
    data = unsub_json_res.json()
    assert data["success"] is True

    # 4. Verify direct /unsubscribe route
    direct_res = await async_client.get("/unsubscribe?email=optout_user@example.com")
    assert direct_res.status_code == 200
    assert "text/html" in direct_res.headers["content-type"]
    assert "unsubscribed" in direct_res.text.lower()

    # 5. Verify direct /unsubscribe without email parameter returns 200 without error
    no_email_res = await async_client.get("/unsubscribe")
    assert no_email_res.status_code == 200
    assert "unsubscribed" in no_email_res.text.lower()

    # 6. Verify DB state: unsubscribed_at is populated and marketing_consent is False
    stmt = select(WaitlistEntry).where(WaitlistEntry.email_normalized == "optout_user@example.com")
    res = await db_session.execute(stmt)
    entry = res.scalar_one()
    assert entry.unsubscribed_at is not None
    assert entry.marketing_consent is False


