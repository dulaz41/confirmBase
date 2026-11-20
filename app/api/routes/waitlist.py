from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi.responses import JSONResponse

from app.api.deps import check_waitlist_rate_limit, get_db
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
    is_new, message, position = await WaitlistService.register_entry(db, payload)

    if not is_new:
        response.status_code = status.HTTP_200_OK
    else:
        if payload.email:
            background_tasks.add_task(
                email_service.send_confirmation_email,
                to_email=payload.email,
                name=payload.name,
                user_type="tenant",
                phone=payload.phone,
                areas=payload.areas,
            )

    return WaitlistResponse(success=True, message=message, ok=is_new, position=position)


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
    is_new, message, position = await WaitlistService.register_entry(db, payload)

    if not is_new:
        response.status_code = status.HTTP_200_OK
    else:
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

    return WaitlistResponse(success=True, message=message, ok=is_new, position=position)


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
    is_new, message, position = await WaitlistService.register_email(db, payload)

    if not is_new:
        response.status_code = status.HTTP_200_OK
    else:
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

    return WaitlistResponse(success=True, message=message, ok=is_new, position=position)


@v1_router.post(
    "",
    response_model=WaitlistContractResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(check_waitlist_rate_limit)],
    tags=["Waitlist (Unified)"],
    summary="Frontend Live Waitlist Submission Contract",
    description="Dedicated contract endpoint matching frontend /api/join live mode. Returns 201 {ok: true, position}, 409 {ok: false, error: 'already_on_list'}, and 422 validation errors.",
    responses={
        201: {
            "description": "New signup accepted into waitlist",
            "content": {"application/json": {"example": {"ok": True, "position": 42}}},
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
    is_new, message, position = await WaitlistService.register_entry(db, payload)

    if not is_new:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "ok": False,
                "error": "already_on_list",
                "position": position,
            },
        )

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
            "position": position,
        },
    )
