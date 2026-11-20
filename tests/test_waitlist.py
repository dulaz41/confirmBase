from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WaitlistEntry


@pytest.mark.asyncio
async def test_root_serves_confirmbase_landing_page(async_client: AsyncClient):
    """GET / serves the ConfirmBase landing page HTML."""
    response = await async_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "ConfirmBase: see only the houses worth inspecting" in response.text


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    """GET /health returns 200 ok without revealing system internals."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_check(async_client: AsyncClient):
    """GET /ready returns database readiness."""
    response = await async_client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_valid_email_accepted(async_client: AsyncClient, db_session: AsyncSession):
    """Valid email is registered with status 201."""
    response = await async_client.post(
        "/api/v1/waitlist",
        json={"email": "tester@example.com"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "You have successfully joined the waitlist."

    # Verify database state
    stmt = select(WaitlistEntry).where(WaitlistEntry.email_normalized == "tester@example.com")
    result = await db_session.execute(stmt)
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.email == "tester@example.com"
    assert entry.email_normalized == "tester@example.com"


@pytest.mark.asyncio
async def test_invalid_email_syntax_rejected(async_client: AsyncClient):
    """Invalid email syntax is rejected with 422."""
    invalid_emails = [
        "not-an-email",
        "@missingusername.com",
        "missingatsign.com",
        "user@",
        "user@.com",
        "user@domain..com",
    ]
    for email in invalid_emails:
        response = await async_client.post(
            "/api/v1/waitlist",
            json={"email": email},
        )
        assert response.status_code == 422, f"Expected 422 for invalid email: {email}"
        data = response.json()
        assert data["success"] is False


@pytest.mark.asyncio
async def test_empty_email_rejected(async_client: AsyncClient):
    """Empty email is rejected with 422."""
    response = await async_client.post(
        "/api/v1/waitlist",
        json={"email": ""},
    )
    assert response.status_code == 422
    assert response.json()["success"] is False


@pytest.mark.asyncio
async def test_whitespace_trimmed_and_accepted(async_client: AsyncClient, db_session: AsyncSession):
    """Email with surrounding whitespace is trimmed and registered cleanly."""
    response = await async_client.post(
        "/api/v1/waitlist",
        json={"email": "   clean_me@example.com   "},
    )
    assert response.status_code == 201

    stmt = select(WaitlistEntry).where(WaitlistEntry.email_normalized == "clean_me@example.com")
    result = await db_session.execute(stmt)
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.email_normalized == "clean_me@example.com"


@pytest.mark.asyncio
async def test_case_insensitive_duplicate_prevented(
    async_client: AsyncClient, db_session: AsyncSession
):
    """
    Submitting test@example.com then TEST@EXAMPLE.COM returns 200 with duplicate message
    and does not create a second record.
    """
    # First submission
    res1 = await async_client.post(
        "/api/v1/waitlist",
        json={"email": "John.Doe@example.com"},
    )
    assert res1.status_code == 201
    assert res1.json()["message"] == "You have successfully joined the waitlist."

    # Second submission with different casing and whitespace
    res2 = await async_client.post(
        "/api/v1/waitlist",
        json={"email": "  JOHN.DOE@EXAMPLE.COM  "},
    )
    assert res2.status_code == 200
    assert res2.json()["success"] is True
    assert res2.json()["message"] == "This email is already on the waitlist."

    # Check database count: must be strictly 1
    stmt = select(WaitlistEntry)
    result = await db_session.execute(stmt)
    entries = result.scalars().all()
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_unexpected_fields_rejected(async_client: AsyncClient):
    """Arbitrary extra fields must be strictly forbidden (extra='forbid')."""
    response = await async_client.post(
        "/api/v1/waitlist",
        json={
            "email": "hacker@example.com",
            "is_admin": True,
            "status": "approved",
            "unauthorized_flag": "exploit",
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert "extra_forbidden" in str(data) or "Extra inputs are not permitted" in str(data)


@pytest.mark.asyncio
async def test_honeypot_silently_ignored(async_client: AsyncClient, db_session: AsyncSession):
    """If bot fills the honeypot field, return 200/201 success but do not save to DB."""
    response = await async_client.post(
        "/api/v1/waitlist",
        json={
            "email": "bot@example.com",
            "hp_field": "I am a bot filling hidden fields",
        },
    )
    assert response.status_code == 201
    assert response.json()["success"] is True

    # Confirm it was NOT saved to the database
    stmt = select(WaitlistEntry).where(WaitlistEntry.email_normalized == "bot@example.com")
    result = await db_session.execute(stmt)
    entry = result.scalar_one_or_none()
    assert entry is None


@pytest.mark.asyncio
async def test_confirmbase_tenant_full_registration(async_client: AsyncClient, db_session: AsyncSession):
    """ConfirmBase tenant registration saves all tenant preferences."""
    payload = {
        "type": "tenant",
        "name": "Chidi Okonkwo",
        "phone": "08031234567",
        "email": "chidi@example.com",
        "areas": "Arab road, Chikakore, FO1",
        "budget": "₦500,000 – ₦1,000,000",
        "timing": "Within a month",
        "redflags": "Landlord, Bad road, No steady water",
        "taste": "A quiet street with tiled floors",
    }
    response = await async_client.post("/api/v1/waitlist", json=payload)
    assert response.status_code == 201
    assert response.json()["success"] is True

    stmt = select(WaitlistEntry).where(WaitlistEntry.phone_normalized == "+2348031234567")
    result = await db_session.execute(stmt)
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.name == "Chidi Okonkwo"
    assert entry.type == "tenant"
    assert entry.phone == "08031234567"
    assert entry.phone_normalized == "+2348031234567"
    assert entry.email == "chidi@example.com"
    assert entry.areas == "Arab road, Chikakore, FO1"
    assert entry.budget == "₦500,000 – ₦1,000,000"
    assert entry.timing == "Within a month"
    assert "Bad road" in entry.redflags
    assert entry.taste == "A quiet street with tiled floors"


@pytest.mark.asyncio
async def test_confirmbase_tenant_without_email(async_client: AsyncClient, db_session: AsyncSession):
    """ConfirmBase tenant registration succeeds when email is omitted (since email is optional)."""
    payload = {
        "type": "tenant",
        "name": "Amina Bello",
        "phone": "08099887766",
        "email": "",
        "areas": "FO1, Kubwa",
        "budget": "₦1,000,000 – ₦2,000,000",
        "timing": "As soon as possible",
    }
    response = await async_client.post("/api/v1/waitlist", json=payload)
    assert response.status_code == 201
    assert response.json()["success"] is True

    stmt = select(WaitlistEntry).where(WaitlistEntry.phone_normalized == "+2348099887766")
    result = await db_session.execute(stmt)
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.name == "Amina Bello"
    assert entry.email is None
    assert entry.email_normalized is None


@pytest.mark.asyncio
async def test_confirmbase_agent_registration(async_client: AsyncClient, db_session: AsyncSession):
    """ConfirmBase agent registration saves role and listings count."""
    payload = {
        "type": "agent",
        "name": "Emeka Properties",
        "phone": "08123456789",
        "email": "emeka@properties.ng",
        "role": "Agent",
        "areas": "Kubwa, Arab road",
        "listings": "4–10",
    }
    response = await async_client.post("/api/v1/waitlist", json=payload)
    assert response.status_code == 201
    assert response.json()["success"] is True

    stmt = select(WaitlistEntry).where(WaitlistEntry.phone_normalized == "+2348123456789")
    result = await db_session.execute(stmt)
    entry = result.scalar_one_or_none()
    assert entry is not None
    assert entry.type == "agent"
    assert entry.role == "Agent"
    assert entry.listings == "4–10"


@pytest.mark.asyncio
async def test_confirmbase_phone_duplicate_prevention(async_client: AsyncClient, db_session: AsyncSession):
    """Submitting the same phone number for the same type returns 200 duplicate message."""
    payload1 = {
        "type": "tenant",
        "name": "Dupe User",
        "phone": "08055667788",
        "areas": "Kubwa",
    }
    res1 = await async_client.post("/api/v1/waitlist", json=payload1)
    assert res1.status_code == 201

    # Second submission with same phone but formatted with spaces
    payload2 = {
        "type": "tenant",
        "name": "Dupe User",
        "phone": " 080 5566 7788 ",
        "areas": "Kubwa",
    }
    res2 = await async_client.post("/api/v1/waitlist", json=payload2)
    assert res2.status_code == 200
    assert res2.json()["success"] is True
    assert "already on the waitlist" in res2.json()["message"]

    stmt = select(WaitlistEntry).where(WaitlistEntry.phone_normalized == "+2348055667788")
    result = await db_session.execute(stmt)
    entries = result.scalars().all()
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_website_honeypot_field(async_client: AsyncClient, db_session: AsyncSession):
    """The HTML website input acts as a honeypot and silently ignores bots."""
    payload = {
        "type": "tenant",
        "name": "Spammer",
        "phone": "08000000000",
        "areas": "Everywhere",
        "website": "http://spamsite.xyz",
    }
    response = await async_client.post("/api/v1/waitlist", json=payload)
    assert response.status_code == 201

    stmt = select(WaitlistEntry).where(WaitlistEntry.name == "Spammer")
    result = await db_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_tenant_dedicated_endpoint(async_client: AsyncClient, db_session: AsyncSession):
    """POST /api/v1/waitlist/tenant registers tenant with tenant-specific schema."""
    payload = {
        "name": "Ibrahim Sani",
        "phone": "08077778888",
        "email": "ibrahim@example.com",
        "areas": "Arab road, Kubwa",
        "budget": "₦1,000,000 – ₦2,000,000",
        "timing": "Within a month",
        "redflags": "Bad access road, Insecure",
        "taste": "Fenced compound with security",
    }
    response = await async_client.post("/api/v1/waitlist/tenant", json=payload)
    assert response.status_code == 201
    assert response.json()["success"] is True

    stmt = select(WaitlistEntry).where(WaitlistEntry.phone_normalized == "+2348077778888")
    entry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert entry is not None
    assert entry.type == "tenant"
    assert entry.name == "Ibrahim Sani"


@pytest.mark.asyncio
async def test_agent_dedicated_endpoint(async_client: AsyncClient, db_session: AsyncSession):
    """POST /api/v1/waitlist/agent registers agent with agent-specific schema."""
    payload = {
        "name": "Ngozi Realty",
        "phone": "08022223333",
        "email": "ngozi@realty.ng",
        "role": "Property manager",
        "areas": "Chikakore, FO1",
        "listings": "11–30",
    }
    response = await async_client.post("/api/v1/waitlist/agent", json=payload)
    assert response.status_code == 201
    assert response.json()["success"] is True

    stmt = select(WaitlistEntry).where(WaitlistEntry.phone_normalized == "+2348022223333")
    entry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert entry is not None
    assert entry.type == "agent"
    assert entry.role == "Property manager"


@pytest.mark.asyncio
async def test_swagger_docs_and_openapi_tags(async_client: AsyncClient):
    """Swagger UI /docs and /openapi.json contain distinct Tenant, Agent, and Admin tag groups."""
    docs_res = await async_client.get("/docs")
    assert docs_res.status_code == 200

    openapi_res = await async_client.get("/openapi.json")
    assert openapi_res.status_code == 200
    schema = openapi_res.json()

    # Verify tags defined in OpenAPI schema
    tag_names = [t["name"] for t in schema.get("tags", [])]
    assert "Tenant" in tag_names
    assert "Agent" in tag_names
    assert "Admin" in tag_names

    # Verify route grouping
    paths = schema["paths"]
    assert "Tenant" in paths["/api/v1/waitlist/tenant"]["post"]["tags"]
    assert "Agent" in paths["/api/v1/waitlist/agent"]["post"]["tags"]
    assert "Admin" in paths["/api/v1/admin/waitlist/export"]["get"]["tags"]


@pytest.mark.asyncio
async def test_frontend_contract_endpoint_success(async_client: AsyncClient, db_session: AsyncSession):
    """POST /v1/waitlist matches frontend live mode: returns 201 {ok: true, position: X}."""
    payload = {
        "type": "tenant",
        "name": "Tola Ade",
        "phone": "08033334444",
        "email": "tola@example.com",
        "areas": "Arab road, Chikakore",
        "budget": "₦1m–₦2m",
        "timing": "Within a month",
        "redflags": ["Landlord in compound", "Bad road", "Poor water"],
        "taste": "High ceiling, big windows",
    }
    response = await async_client.post("/v1/waitlist", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["ok"] is True
    assert isinstance(data["position"], int)
    assert data["position"] >= 1

    # Verify redflags list was converted to clean comma-separated string in DB
    stmt = select(WaitlistEntry).where(WaitlistEntry.email_normalized == "tola@example.com")
    entry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert entry is not None
    assert "Landlord in compound" in entry.redflags
    assert "Bad road" in entry.redflags


@pytest.mark.asyncio
async def test_frontend_contract_endpoint_duplicate_returns_409(async_client: AsyncClient):
    """POST /v1/waitlist returns 409 {ok: false, error: 'already_on_list'} on duplicate."""
    payload = {
        "type": "agent",
        "name": "Segun Properties",
        "phone": "08055556666",
        "email": "segun@properties.ng",
        "role": "Agent",
        "areas": "Kubwa",
        "listings": "4–10",
    }
    res1 = await async_client.post("/v1/waitlist", json=payload)
    assert res1.status_code == 201
    assert res1.json()["ok"] is True

    # Duplicate call with same email and phone
    res2 = await async_client.post("/v1/waitlist", json=payload)
    assert res2.status_code == 409
    data = res2.json()
    assert data["ok"] is False
    assert data["error"] == "already_on_list"


@pytest.mark.asyncio
async def test_frontend_contract_validation_error_returns_422(async_client: AsyncClient):
    """POST /v1/waitlist returns 422 {ok: false, error: 'validation', errors: {...}}."""
    payload = {
        "type": "tenant",
        "name": "Bad Phone User",
        "phone": "123",  # Less than 7 digits
        "email": "badphone@example.com",
    }
    response = await async_client.post("/v1/waitlist", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert data["ok"] is False
    assert data["error"] == "validation"
    assert "phone" in data["errors"]
