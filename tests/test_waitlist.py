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
async def test_privacy_policy_redirect(async_client: AsyncClient):
    """GET /privacy redirects to the view-only Privacy Policy URL."""
    response = await async_client.get("/privacy", follow_redirects=False)
    assert response.status_code == 307
    assert "1-9Pab8LJ2yupF5v0zMRMrjSvq9tZWC1E" in response.headers["location"]
    assert "preview" in response.headers["location"]


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
    assert "Waitlist" in tag_names
    assert "Tenant" in tag_names
    assert "Agent" in tag_names
    assert "Admin" in tag_names
    assert "Health" in tag_names

    # Verify route grouping
    paths = schema["paths"]
    assert "/v1/waitlist" in paths
    assert "Waitlist" in paths["/v1/waitlist"]["post"]["tags"]
    assert "/v1/waitlist/tenant" in paths
    assert "Tenant" in paths["/v1/waitlist/tenant"]["post"]["tags"]
    assert "/v1/waitlist/agent" in paths
    assert "Agent" in paths["/v1/waitlist/agent"]["post"]["tags"]
    assert "/v1/admin/waitlist/entries" in paths
    assert "/v1/admin/waitlist/entries/tenant" in paths
    assert "/v1/admin/waitlist/entries/agent" in paths
    assert "Admin" in paths["/v1/admin/waitlist/export"]["get"]["tags"]

    # Verify redundant routes are hidden from OpenAPI docs
    assert "/api/v1/waitlist" not in paths
    assert "/api/v1/waitlist/tenant" not in paths
    assert "/api/v1/waitlist/agent" not in paths


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


@pytest.mark.asyncio
async def test_v1_tenant_and_agent_dedicated_endpoints(async_client: AsyncClient, db_session: AsyncSession):
    """POST /v1/waitlist/tenant and /v1/waitlist/agent register entries properly."""
    tenant_payload = {
        "name": "Fatima Musa",
        "phone": "08011223344",
        "email": "fatima@example.com",
        "areas": "Arab road",
        "budget": "Under ₦500k",
        "timing": "Within a month",
    }
    t_res = await async_client.post("/v1/waitlist/tenant", json=tenant_payload)
    assert t_res.status_code == 201
    assert t_res.json()["success"] is True

    agent_payload = {
        "name": "Emeka Properties",
        "phone": "08099881122",
        "email": "emeka@props.ng",
        "role": "Agent",
        "areas": "FO1, Chikakore",
        "listings": "4–10",
    }
    a_res = await async_client.post("/v1/waitlist/agent", json=agent_payload)
    assert a_res.status_code == 201
    assert a_res.json()["success"] is True


@pytest.mark.asyncio
async def test_admin_entries_tenant_and_agent_shortcuts(async_client: AsyncClient, db_session: AsyncSession):
    """GET /v1/admin/waitlist/entries/tenant and /agent return filtered entries."""
    from app.core.config import settings

    headers = {"Authorization": f"Bearer {settings.ADMIN_API_KEY}"}

    t_res = await async_client.get("/v1/admin/waitlist/entries/tenant", headers=headers)
    assert t_res.status_code == 200
    assert "entries" in t_res.json()

    a_res = await async_client.get("/v1/admin/waitlist/entries/agent", headers=headers)
    assert a_res.status_code == 200
    assert "entries" in a_res.json()


@pytest.mark.asyncio
async def test_step2_enrichment_flow_checklist(async_client: AsyncClient, db_session: AsyncSession):
    """
    Verification checklist from frontend handoff:
    1. New tenant -> 201 with position
    2. Same payload again -> 409 already_on_list
    3. New agent -> 201
    4. redflags as comma-separated string -> also 201
    5. Honeypot filled -> must NOT persist
    6. Step-2 enrichment: POST the phone from check 1 with only a preference field
       -> returns 200 {ok: true, updated: true, position: N}
       -> taste is updated in DB
       -> budget/timing/redflags are NOT blanked by omission
    7. Same step-2 payload again -> returns 409 already_on_list (nothing needed writing)
    """
    # 1. New tenant -> 201 with a position
    p1 = {
        "type": "tenant",
        "name": "Frontend Test",
        "phone": "08012345678",
        "email": "test@getconfirmbase.ng",
        "areas": "Arab road, Kubwa",
        "budget": "₦1,000,000 – ₦2,000,000",
        "timing": "Within a month",
        "redflags": ["Bad access road", "No steady water"],
        "taste": "Tiled floors",
        "submitted_at": "2026-10-13T06:39:31.635Z",
    }
    res1 = await async_client.post("/v1/waitlist", json=p1)
    assert res1.status_code == 201
    d1 = res1.json()
    assert d1["ok"] is True
    assert isinstance(d1["position"], int)
    pos1 = d1["position"]

    # 2. Same payload again -> 409 already_on_list
    res2 = await async_client.post("/v1/waitlist", json=p1)
    assert res2.status_code == 409
    d2 = res2.json()
    assert d2["ok"] is False
    assert d2["error"] == "already_on_list"

    # 3. New agent -> 201
    p3 = {
        "type": "agent",
        "name": "Bello Properties",
        "phone": "08098765432",
        "email": "bello@agency.ng",
        "role": "Agent",
        "areas": "Kubwa, Arab road",
        "listings": "4–10",
    }
    res3 = await async_client.post("/v1/waitlist", json=p3)
    assert res3.status_code == 201
    assert res3.json()["ok"] is True

    # 4. redflags as a comma-separated string -> also 201
    p4 = {
        "type": "tenant",
        "name": "String Flags User",
        "phone": "08077665544",
        "email": "flags@example.com",
        "areas": "Kubwa",
        "redflags": "Bad access road, No steady water",
    }
    res4 = await async_client.post("/v1/waitlist", json=p4)
    assert res4.status_code == 201
    assert res4.json()["ok"] is True

    # 5. Honeypot filled -> must NOT persist
    p5 = {
        "type": "tenant",
        "name": "Bot",
        "phone": "08000000000",
        "areas": "X",
        "website": "http://spam",
    }
    res5 = await async_client.post("/v1/waitlist", json=p5)
    assert res5.status_code == 201
    stmt_bot = select(WaitlistEntry).where(WaitlistEntry.name == "Bot")
    assert (await db_session.execute(stmt_bot)).scalar_one_or_none() is None

    # 6. Step-2 enrichment: POST phone from check 1 with only taste field
    p6 = {
        "type": "tenant",
        "name": "Frontend Test",
        "phone": "08012345678",
        "taste": "Quiet street",
    }
    res6 = await async_client.post("/v1/waitlist", json=p6)
    assert res6.status_code == 200
    d6 = res6.json()
    assert d6["ok"] is True
    assert d6["updated"] is True
    assert d6["position"] == pos1

    # Verify DB: taste was updated, but budget, timing, redflags were NOT blanked!
    stmt_entry = select(WaitlistEntry).where(WaitlistEntry.phone_normalized == "+2348012345678")
    entry = (await db_session.execute(stmt_entry)).scalar_one_or_none()
    assert entry is not None
    assert entry.taste == "Quiet street"
    assert entry.budget == "₦1,000,000 – ₦2,000,000"
    assert entry.timing == "Within a month"
    assert "Bad access road" in entry.redflags
    assert entry.email == "test@getconfirmbase.ng"

    # 7. Resubmitting check 6 again -> nothing changed -> 409 already_on_list
    res7 = await async_client.post("/v1/waitlist", json=p6)
    assert res7.status_code == 409
    assert res7.json()["ok"] is False
    assert res7.json()["error"] == "already_on_list"


@pytest.mark.asyncio
async def test_step2_adding_email_to_phone_only_signup(async_client: AsyncClient, db_session: AsyncSession):
    """Step 1 collects phone only, Step 2 adds email and preferences."""
    # Step 1: phone only
    res1 = await async_client.post(
        "/v1/waitlist",
        json={"type": "tenant", "name": "Phone Only User", "phone": "08044445555", "areas": "Kubwa"},
    )
    assert res1.status_code == 201

    # Step 2: enrich with email and budget
    res2 = await async_client.post(
        "/v1/waitlist",
        json={
            "type": "tenant",
            "phone": "08044445555",
            "email": "added_later@example.com",
            "budget": "₦500k–₦1m",
        },
    )
    assert res2.status_code == 200
    d2 = res2.json()
    assert d2["ok"] is True
    assert d2["updated"] is True

    stmt = select(WaitlistEntry).where(WaitlistEntry.phone_normalized == "+2348044445555")
    entry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert entry is not None
    assert entry.email == "added_later@example.com"
    assert entry.email_normalized == "added_later@example.com"
    assert entry.budget == "₦500k–₦1m"
    assert entry.name == "Phone Only User"
    assert entry.areas == "Kubwa"


@pytest.mark.asyncio
async def test_step2_agent_enrichment(async_client: AsyncClient, db_session: AsyncSession):
    """Agent signs up with basic details in step 1 and provides role/listings in step 2."""
    res1 = await async_client.post(
        "/v1/waitlist",
        json={"type": "agent", "name": "Agent Demo", "phone": "08066667777", "areas": "Arab road"},
    )
    assert res1.status_code == 201

    res2 = await async_client.post(
        "/v1/waitlist",
        json={
            "type": "agent",
            "phone": "08066667777",
            "role": "Property manager",
            "listings": "11–30",
        },
    )
    assert res2.status_code == 200
    assert res2.json()["ok"] is True
    assert res2.json()["updated"] is True

    stmt = select(WaitlistEntry).where(WaitlistEntry.phone_normalized == "+2348066667777")
    entry = (await db_session.execute(stmt)).scalar_one_or_none()
    assert entry is not None
    assert entry.role == "Property manager"
    assert entry.listings == "11–30"

