import html
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import check_waitlist_rate_limit, get_db
from app.core.config import settings
from app.schemas.waitlist import (
    AgentWaitlistCreate,
    TenantWaitlistCreate,
    WaitlistContractResponse,
    WaitlistCreate,
    WaitlistResponse,
)
from app.services.email import email_service
from app.services.waitlist_service import WaitlistService

router = APIRouter(prefix="/api/v1/waitlist")
v1_router = APIRouter(prefix="/v1/waitlist")


@router.post(
    "/tenant",
    response_model=WaitlistResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_waitlist_rate_limit)],
    tags=["Tenant"],
    summary="Register as Tenant",
    description="Registers a tenant looking for houses on ConfirmBase. Captures budget, timeframe, target areas, and deal-breaker red flags.",
    responses={
        201: {
            "description": "Successfully registered tenant to the early list",
            "content": {"application/json": {"example": {"success": True, "message": "You have successfully joined the waitlist.", "position": 42}}},
        },
        200: {
            "description": "WhatsApp number or email already exists on the waitlist",
            "content": {"application/json": {"example": {"success": True, "message": "This WhatsApp number is already on the waitlist.", "position": 5}}},
        },
        422: {"description": "Validation error (invalid phone format or extra forbidden fields)"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def register_tenant(
    payload: TenantWaitlistCreate,
    response: Response,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> WaitlistResponse:
    """
    Dedicated endpoint for prospective tenant registrations.
    """
    result = await WaitlistService.register_entry(db, payload)

    if result.status == "created":
        if payload.email:
            background_tasks.add_task(
                email_service.send_confirmation_email,
                to_email=payload.email,
                name=payload.name,
                user_type="tenant",
                phone=payload.phone,
                areas=payload.areas,
            )
        return WaitlistResponse(success=True, message=result.message, ok=True, position=result.position)

    if result.status == "updated":
        if result.email_newly_added and payload.email:
            background_tasks.add_task(
                email_service.send_confirmation_email,
                to_email=payload.email,
                name=payload.name,
                user_type="tenant",
                phone=payload.phone,
                areas=payload.areas,
            )
        response.status_code = status.HTTP_200_OK
        return WaitlistResponse(success=True, message=result.message, ok=True, position=result.position, updated=True)

    response.status_code = status.HTTP_200_OK
    return WaitlistResponse(success=True, message=result.message, ok=False, position=result.position, updated=False)


@router.post(
    "/agent",
    response_model=WaitlistResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_waitlist_rate_limit)],
    tags=["Agent"],
    summary="Register as Agent / Landlord",
    description="Registers an agent, landlord, or property manager on ConfirmBase. Captures role, operating areas, and monthly listing volumes.",
    responses={
        201: {
            "description": "Successfully registered agent to the waitlist",
            "content": {"application/json": {"example": {"success": True, "message": "You have successfully joined the waitlist.", "position": 42}}},
        },
        200: {
            "description": "WhatsApp number or email already exists on the waitlist",
            "content": {"application/json": {"example": {"success": True, "message": "This WhatsApp number is already on the waitlist.", "position": 5}}},
        },
        422: {"description": "Validation error (invalid phone format or extra forbidden fields)"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def register_agent(
    payload: AgentWaitlistCreate,
    response: Response,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> WaitlistResponse:
    """
    Dedicated endpoint for real estate agent and landlord registrations.
    """
    result = await WaitlistService.register_entry(db, payload)

    if result.status == "created":
        if payload.email:
            background_tasks.add_task(
                email_service.send_confirmation_email,
                to_email=payload.email,
                name=payload.name,
                user_type="agent",
                phone=payload.phone,
                areas=payload.areas,
                role=payload.role,
            )
        return WaitlistResponse(success=True, message=result.message, ok=True, position=result.position)

    if result.status == "updated":
        if result.email_newly_added and payload.email:
            background_tasks.add_task(
                email_service.send_confirmation_email,
                to_email=payload.email,
                name=payload.name,
                user_type="agent",
                phone=payload.phone,
                areas=payload.areas,
                role=payload.role,
            )
        response.status_code = status.HTTP_200_OK
        return WaitlistResponse(success=True, message=result.message, ok=True, position=result.position, updated=True)

    response.status_code = status.HTTP_200_OK
    return WaitlistResponse(success=True, message=result.message, ok=False, position=result.position, updated=False)


@router.post(
    "",
    response_model=WaitlistResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_waitlist_rate_limit)],
    tags=["Waitlist (Unified)"],
    summary="Unified Waitlist Registration",
    description="Unified endpoint accepting dynamic submissions (either tenant or agent) directly from frontend web forms.",
    responses={
        201: {
            "description": "Successfully registered new entry to the waitlist",
            "content": {"application/json": {"example": {"success": True, "message": "You have successfully joined the waitlist.", "position": 42}}},
        },
        200: {
            "description": "WhatsApp number or email already exists on the waitlist",
            "content": {"application/json": {"example": {"success": True, "message": "This WhatsApp number is already on the waitlist.", "position": 5}}},
        },
        422: {"description": "Validation error (invalid phone/email format or forbidden fields)"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def join_waitlist(
    payload: WaitlistCreate,
    response: Response,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> WaitlistResponse:
    """
    Unified endpoint for the ConfirmBase landing page.
    """
    result = await WaitlistService.register_email(db, payload)

    if result.status == "created":
        if payload.email:
            background_tasks.add_task(
                email_service.send_confirmation_email,
                to_email=payload.email,
                name=payload.name,
                user_type=payload.type,
                phone=payload.phone,
                areas=payload.areas,
                role=payload.role,
            )
        return WaitlistResponse(success=True, message=result.message, ok=True, position=result.position)

    if result.status == "updated":
        if result.email_newly_added and payload.email:
            background_tasks.add_task(
                email_service.send_confirmation_email,
                to_email=payload.email,
                name=payload.name,
                user_type=payload.type,
                phone=payload.phone,
                areas=payload.areas,
                role=payload.role,
            )
        response.status_code = status.HTTP_200_OK
        return WaitlistResponse(success=True, message=result.message, ok=True, position=result.position, updated=True)

    response.status_code = status.HTTP_200_OK
    return WaitlistResponse(success=True, message=result.message, ok=False, position=result.position, updated=False)


@v1_router.post(
    "",
    response_model=WaitlistContractResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_waitlist_rate_limit)],
    tags=["Waitlist"],
    summary="Submit Waitlist Entry (Frontend Contract)",
    description="Dedicated contract endpoint matching frontend /api/join live mode. Returns 201 {ok: true, position}, 200 {ok: true, updated: true, position}, 409 {ok: false, error: 'already_on_list'}, and 422 validation errors.",
    responses={
        201: {
            "description": "New signup accepted into waitlist",
            "content": {"application/json": {"example": {"ok": True, "position": 42}}},
        },
        200: {
            "description": "Existing signup updated with step-2 preferences",
            "content": {"application/json": {"example": {"ok": True, "updated": True, "position": 42}}},
        },
        409: {
            "description": "Already registered on list (deduped on email, then phone)",
            "content": {"application/json": {"example": {"ok": False, "error": "already_on_list"}}},
        },
        422: {
            "description": "Validation error",
            "content": {"application/json": {"example": {"ok": False, "error": "validation", "errors": {"field": "message"}}}},
        },
        429: {"description": "Rate limit exceeded"},
    },
)
async def join_waitlist_contract(
    payload: WaitlistCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Exact contract endpoint matching frontend /api/join live mode:
    POST /v1/waitlist
    """
    result = await WaitlistService.register_entry(db, payload)

    if result.status == "created":
        if payload.email:
            background_tasks.add_task(
                email_service.send_confirmation_email,
                to_email=payload.email,
                name=payload.name,
                user_type=payload.type,
                phone=payload.phone,
                areas=payload.areas,
                role=payload.role,
            )
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "ok": True,
                "position": result.position,
            },
        )

    if result.status == "updated":
        if result.email_newly_added and payload.email:
            background_tasks.add_task(
                email_service.send_confirmation_email,
                to_email=payload.email,
                name=payload.name,
                user_type=payload.type,
                phone=payload.phone,
                areas=payload.areas,
                role=payload.role,
            )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "ok": True,
                "updated": True,
                "position": result.position,
            },
        )

    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "ok": False,
            "error": "already_on_list",
            "position": result.position,
        },
    )


@v1_router.post(
    "/tenant",
    response_model=WaitlistResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_waitlist_rate_limit)],
    tags=["Tenant"],
    summary="Register as Tenant",
    description="Registers a tenant looking for houses on ConfirmBase. Captures budget, timeframe, target areas, and deal-breaker red flags.",
    responses={
        201: {
            "description": "Successfully registered tenant to the early list",
            "content": {"application/json": {"example": {"success": True, "message": "You have successfully joined the waitlist.", "ok": True, "position": 42}}},
        },
        200: {
            "description": "WhatsApp number or email already exists on the waitlist",
            "content": {"application/json": {"example": {"success": True, "message": "This WhatsApp number is already on the waitlist.", "ok": False, "position": 5}}},
        },
        422: {"description": "Validation error (invalid phone format or extra forbidden fields)"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def register_tenant_v1(
    payload: TenantWaitlistCreate,
    response: Response,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> WaitlistResponse:
    """
    Dedicated /v1/waitlist/tenant endpoint for prospective tenant registrations.
    """
    result = await WaitlistService.register_entry(db, payload)

    if result.status == "created":
        if payload.email:
            background_tasks.add_task(
                email_service.send_confirmation_email,
                to_email=payload.email,
                name=payload.name,
                user_type="tenant",
                phone=payload.phone,
                areas=payload.areas,
            )
        return WaitlistResponse(success=True, message=result.message, ok=True, position=result.position)

    if result.status == "updated":
        if result.email_newly_added and payload.email:
            background_tasks.add_task(
                email_service.send_confirmation_email,
                to_email=payload.email,
                name=payload.name,
                user_type="tenant",
                phone=payload.phone,
                areas=payload.areas,
            )
        response.status_code = status.HTTP_200_OK
        return WaitlistResponse(success=True, message=result.message, ok=True, position=result.position, updated=True)

    response.status_code = status.HTTP_200_OK
    return WaitlistResponse(success=True, message=result.message, ok=False, position=result.position, updated=False)


@v1_router.post(
    "/agent",
    response_model=WaitlistResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_waitlist_rate_limit)],
    tags=["Agent"],
    summary="Register as Agent / Landlord",
    description="Registers an agent, landlord, or property manager on ConfirmBase. Captures role, operating areas, and monthly listing volumes.",
    responses={
        201: {
            "description": "Successfully registered agent to the waitlist",
            "content": {"application/json": {"example": {"success": True, "message": "You have successfully joined the waitlist.", "ok": True, "position": 42}}},
        },
        200: {
            "description": "WhatsApp number or email already exists on the waitlist",
            "content": {"application/json": {"example": {"success": True, "message": "This WhatsApp number is already on the waitlist.", "ok": False, "position": 5}}},
        },
        422: {"description": "Validation error (invalid phone format or extra forbidden fields)"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def register_agent_v1(
    payload: AgentWaitlistCreate,
    response: Response,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> WaitlistResponse:
    """
    Dedicated /v1/waitlist/agent endpoint for real estate agent and landlord registrations.
    """
    result = await WaitlistService.register_entry(db, payload)

    if result.status == "created":
        if payload.email:
            background_tasks.add_task(
                email_service.send_confirmation_email,
                to_email=payload.email,
                name=payload.name,
                user_type="agent",
                phone=payload.phone,
                areas=payload.areas,
                role=payload.role,
            )
        return WaitlistResponse(success=True, message=result.message, ok=True, position=result.position)

    if result.status == "updated":
        if result.email_newly_added and payload.email:
            background_tasks.add_task(
                email_service.send_confirmation_email,
                to_email=payload.email,
                name=payload.name,
                user_type="agent",
                phone=payload.phone,
                areas=payload.areas,
                role=payload.role,
            )
        response.status_code = status.HTTP_200_OK
        return WaitlistResponse(success=True, message=result.message, ok=True, position=result.position, updated=True)

    response.status_code = status.HTTP_200_OK
    return WaitlistResponse(success=True, message=result.message, ok=False, position=result.position, updated=False)


def render_unsubscribe_page(email: str = "") -> str:
    clean_email = email.strip() if email else ""
    escaped_email = html.escape(clean_email)
    waitlist_url = html.escape(getattr(settings, "WAITLIST_URL", "https://getconfirmbase.com"))
    if clean_email:
        message_paragraph = f"<p>You have been removed from our waitlist email updates for <strong>{escaped_email}</strong>. We will not send you further marketing or launch notifications.</p>"
    else:
        message_paragraph = "<p>You have been successfully removed from our waitlist email updates. We will not send you further marketing or launch notifications.</p>"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Unsubscribed · ConfirmBase</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #f5f4f3;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #262626;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
    }}
    .card {{
      max-width: 480px;
      margin: 20px;
      background: #ffffff;
      border-radius: 16px;
      border: 1px solid #e5e5e5;
      padding: 40px 32px;
      text-align: center;
      box-shadow: 0 4px 20px rgba(0, 20, 14, 0.08);
    }}
    .logo {{
      font-size: 22px;
      font-weight: 700;
      color: #00140e;
      margin-bottom: 22px;
      letter-spacing: -0.03em;
    }}
    .logo-base {{
      color: #d8b36a;
    }}
    h1 {{
      font-size: 22px;
      margin: 0 0 12px 0;
      color: #00140e;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    p {{
      font-size: 15px;
      color: #555555;
      line-height: 1.6;
      margin: 0 0 24px 0;
    }}
    .btn {{
      display: inline-block;
      background-color: #00140e;
      color: #ffffff !important;
      text-decoration: none;
      padding: 12px 24px;
      border-radius: 10px;
      font-size: 14.5px;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">confirm<span class="logo-base">Base</span></div>
    <h1>You’ve been unsubscribed</h1>
    {message_paragraph}
    <a href="{waitlist_url}" class="btn">Return to ConfirmBase</a>
  </div>
</body>
</html>
"""


@router.get(
    "/unsubscribe",
    response_class=HTMLResponse,
    tags=["Waitlist"],
    summary="Unsubscribe from Waitlist Emails",
    description="Compliant 1-click unsubscription endpoint under NDPA 2023. Revokes marketing consent and records unsubscription timestamp.",
)
async def unsubscribe_waitlist(
    email: Optional[str] = Query(default="", description="Email address to unsubscribe"),
    format: Optional[str] = Query(default=None, description="Optional response format ('json' or 'html')"),
    db: AsyncSession = Depends(get_db),
):
    if email and email.strip():
        await WaitlistService.unsubscribe_by_email(db, email.strip())
    if format == "json":
        return JSONResponse({"success": True, "message": "Successfully unsubscribed from waitlist emails."})
    return HTMLResponse(content=render_unsubscribe_page(email or ""), status_code=status.HTTP_200_OK)


@v1_router.get(
    "/unsubscribe",
    response_class=HTMLResponse,
    tags=["Waitlist"],
    summary="Unsubscribe from Waitlist Emails (v1 alias)",
    description="v1 contract alias for 1-click NDPA 2023 unsubscription.",
)
async def unsubscribe_waitlist_v1(
    email: Optional[str] = Query(default="", description="Email address to unsubscribe"),
    format: Optional[str] = Query(default=None, description="Optional response format ('json' or 'html')"),
    db: AsyncSession = Depends(get_db),
):
    if email and email.strip():
        await WaitlistService.unsubscribe_by_email(db, email.strip())
    if format == "json":
        return JSONResponse({"success": True, "message": "Successfully unsubscribed from waitlist emails."})
    return HTMLResponse(content=render_unsubscribe_page(email or ""), status_code=status.HTTP_200_OK)

