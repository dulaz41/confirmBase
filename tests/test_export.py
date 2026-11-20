from __future__ import annotations

import csv
import io
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WaitlistEntry
from app.services.csv_service import sanitize_csv_cell


def test_sanitize_csv_cell_formula_injection():
    """Unit test for CSV formula injection neutralization."""
    # Formulas that could execute in spreadsheets
    dangerous_inputs = [
        "=SUM(A1:A10)",
        "+cmd|' /C calc'!A0",
        "-1+1",
        "@SUM(1,2)",
        "\tmalicious_tab",
        "\rmalicious_cr",
    ]
    for val in dangerous_inputs:
        sanitized = sanitize_csv_cell(val)
        assert sanitized.startswith("'"), f"Failed to neutralize: {val}"

    # Safe inputs
    assert sanitize_csv_cell("user@example.com") == "user@example.com"
    assert sanitize_csv_cell("normal_text") == "normal_text"
    assert sanitize_csv_cell("") == ""


@pytest.mark.asyncio
async def test_csv_export_headers_and_records(
    async_client: AsyncClient, admin_headers: dict[str, str]
):
    """Admin CSV export returns proper headers, UTF-8 content, and records."""
    # Seed records
    await async_client.post("/api/v1/waitlist", json={"email": "alpha@example.com"})
    await async_client.post("/api/v1/waitlist", json={"email": "beta@example.com"})

    response = await async_client.get(
        "/api/v1/admin/waitlist/export",
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "attachment; filename=" in response.headers["content-disposition"]

    csv_text = response.text
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    # Verify header contains ConfirmBase fields
    assert len(rows) >= 3
    assert "email" in rows[0]
    assert "phone" in rows[0]
    assert "type" in rows[0]
    assert "created_at" in rows[0]

    email_idx = rows[0].index("email")
    # Verify email contents
    emails = [row[email_idx] for row in rows[1:]]
    assert "alpha@example.com" in emails
    assert "beta@example.com" in emails


@pytest.mark.asyncio
async def test_csv_export_emails_only(
    async_client: AsyncClient, admin_headers: dict[str, str]
):
    """Admin CSV export with emails_only=true returns email-focused list without missing email entries."""
    # Seed one with email and one without email
    await async_client.post("/api/v1/waitlist", json={"name": "Alice", "phone": "08011112222", "email": "alice@example.com", "areas": "Kubwa"})
    await async_client.post("/api/v1/waitlist", json={"name": "Bob No Email", "phone": "08033334444", "email": "", "areas": "FO1"})

    response = await async_client.get(
        "/api/v1/admin/waitlist/export?emails_only=true",
        headers=admin_headers,
    )
    assert response.status_code == 200
    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)

    # Header must be clean for bulk mailers
    assert rows[0] == ["email", "name", "type", "created_at"]
    exported_emails = [r[0] for r in rows[1:]]
    assert "alice@example.com" in exported_emails
    # Bob has no email so must not be in emails_only list
    assert "" not in exported_emails


@pytest.mark.asyncio
async def test_csv_export_mitigates_formula_injection(
    async_client: AsyncClient, admin_headers: dict[str, str], db_session: AsyncSession
):
    """Ensure records with formula-like characters are escaped in exported CSV."""
    # Insert entry with leading formula character directly or via model
    entry = WaitlistEntry(
        email="+special_user@example.com",
        email_normalized="+special_user@example.com",
    )
    db_session.add(entry)
    await db_session.commit()

    response = await async_client.get(
        "/api/v1/admin/waitlist/export",
        headers=admin_headers,
    )
    assert response.status_code == 200
    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)

    email_idx = rows[0].index("email")
    emails = [row[email_idx] for row in rows[1:]]
    # Neutralized cell should start with single quote
    assert "'+special_user@example.com'" in str(emails) or "'+special_user@example.com" in emails


@pytest.mark.asyncio
async def test_admin_stats_and_delete(
    async_client: AsyncClient, admin_headers: dict[str, str], db_session: AsyncSession
):
    """Admin can view aggregate stats and delete individual records."""
    # Register an entry
    await async_client.post("/api/v1/waitlist", json={"email": "delete_me@example.com"})

    # Check stats
    stats_res = await async_client.get("/api/v1/admin/waitlist/stats", headers=admin_headers)
    assert stats_res.status_code == 200
    assert stats_res.json()["total_entries"] == 1

    # Fetch entry id from db
    from sqlalchemy import select
    res = await db_session.execute(select(WaitlistEntry).where(WaitlistEntry.email_normalized == "delete_me@example.com"))
    entry = res.scalar_one()

    # Delete entry
    del_res = await async_client.delete(f"/api/v1/admin/waitlist/{entry.id}", headers=admin_headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Try deleting again (should be 404)
    del_res2 = await async_client.delete(f"/api/v1/admin/waitlist/{entry.id}", headers=admin_headers)
    assert del_res2.status_code == 404


@pytest.mark.asyncio
async def test_admin_list_entries_separated_by_type(
    async_client: AsyncClient, admin_headers: dict[str, str]
):
    """Admin can query tenants and agents separately with all attached profile details."""
    # Register a tenant
    await async_client.post(
        "/api/v1/waitlist/tenant",
        json={
            "name": "Kelechi Tenant",
            "phone": "08012345678",
            "email": "kelechi@tenant.com",
            "areas": "Maitama",
            "budget": "₦2m - ₦3m",
            "timing": "Immediately",
            "redflags": "Flooding, Bad Road",
            "taste": "Spacious duplex",
        },
    )

    # Register an agent
    await async_client.post(
        "/api/v1/waitlist/agent",
        json={
            "name": "Emeka Agent",
            "phone": "08087654321",
            "email": "emeka@agent.com",
            "areas": "Wuse 2",
            "role": "Direct Landlord",
            "listings": "10-20 per month",
        },
    )

    # 1. Query only tenants
    res_tenants = await async_client.get(
        "/api/v1/admin/waitlist/entries?type=tenant",
        headers=admin_headers,
    )
    assert res_tenants.status_code == 200
    tenant_data = res_tenants.json()
    assert tenant_data["total"] >= 1
    assert all(e["type"] == "tenant" for e in tenant_data["entries"])

    kelechi = next(e for e in tenant_data["entries"] if e["email"] == "kelechi@tenant.com")
    assert kelechi["budget"] == "₦2m - ₦3m"
    assert kelechi["redflags"] == "Flooding, Bad Road"
    assert kelechi["taste"] == "Spacious duplex"
    assert kelechi["role"] is None

    # 2. Query only agents
    res_agents = await async_client.get(
        "/api/v1/admin/waitlist/entries?type=agent",
        headers=admin_headers,
    )
    assert res_agents.status_code == 200
    agent_data = res_agents.json()
    assert agent_data["total"] >= 1
    assert all(e["type"] == "agent" for e in agent_data["entries"])

    emeka = next(e for e in agent_data["entries"] if e["email"] == "emeka@agent.com")
    assert emeka["role"] == "Direct Landlord"
    assert emeka["listings"] == "10-20 per month"
    assert emeka["budget"] is None


@pytest.mark.asyncio
async def test_csv_export_separated_by_type(
    async_client: AsyncClient, admin_headers: dict[str, str]
):
    """Admin can export tenants and agents separately to individual CSV files."""
    await async_client.post(
        "/api/v1/waitlist/tenant",
        json={"name": "Tenant One", "phone": "08111110001", "email": "t1@example.com", "areas": "Garki"},
    )
    await async_client.post(
        "/api/v1/waitlist/agent",
        json={"name": "Agent One", "phone": "08122220002", "email": "a1@example.com", "role": "Agency Broker", "areas": "Wuse 2"},
    )

    # 1. Export tenants only
    res_tenant_csv = await async_client.get(
        "/api/v1/admin/waitlist/export?type=tenant",
        headers=admin_headers,
    )
    assert res_tenant_csv.status_code == 200
    assert "waitlist_tenants_" in res_tenant_csv.headers["content-disposition"]
    reader_t = csv.reader(io.StringIO(res_tenant_csv.text))
    rows_t = list(reader_t)
    email_idx = rows_t[0].index("email")
    emails_t = [r[email_idx] for r in rows_t[1:]]
    assert "t1@example.com" in emails_t
    assert "a1@example.com" not in emails_t

    # 2. Export agents only
    res_agent_csv = await async_client.get(
        "/api/v1/admin/waitlist/export?type=agent",
        headers=admin_headers,
    )
    assert res_agent_csv.status_code == 200
    assert "waitlist_agents_" in res_agent_csv.headers["content-disposition"]
    reader_a = csv.reader(io.StringIO(res_agent_csv.text))
    rows_a = list(reader_a)
    emails_a = [r[email_idx] for r in rows_a[1:]]
    assert "a1@example.com" in emails_a
    assert "t1@example.com" not in emails_a

    # 3. Export agents only with emails_only=true
    res_agent_emails = await async_client.get(
        "/api/v1/admin/waitlist/export?type=agent&emails_only=true",
        headers=admin_headers,
    )
    assert res_agent_emails.status_code == 200
    reader_ae = csv.reader(io.StringIO(res_agent_emails.text))
    rows_ae = list(reader_ae)
    assert rows_ae[0] == ["email", "name", "type", "created_at"]
    emails_ae = [r[0] for r in rows_ae[1:]]
    assert "a1@example.com" in emails_ae
    assert "t1@example.com" not in emails_ae

