from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, List, Literal, Optional, Union
from email_validator import validate_email, EmailNotValidError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def clean_normalized_phone(phone: Optional[str]) -> Optional[str]:
    """Returns normalized phone number with country prefix (+234 by default for 080... local numbers)."""
    if not phone:
        return None
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    if cleaned.startswith("0") and len(cleaned) == 11:
        return "+234" + cleaned[1:]
    if cleaned.startswith("234") and len(cleaned) == 13:
        return "+" + cleaned
    if not cleaned.startswith("+") and len(cleaned) >= 10:
        return "+" + cleaned
    return cleaned


def clean_normalized_email(email: Optional[str]) -> Optional[str]:
    """Returns lowercased, trimmed email address for duplicate checking."""
    if email:
        return email.strip().lower()
    return None


class TenantWaitlistCreate(BaseModel):
    """
    Schema for Tenant registration on ConfirmBase.
    Collects tenant's target areas, budget range, moving timeframe, and deal-breaker red flags.
    """
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "name": "Chidi Okonkwo",
                "phone": "08031234567",
                "email": "chidi@example.com",
                "areas": "Arab road, Chikakore, FO1",
                "budget": "₦500,000 – ₦1,000,000",
                "timing": "Within a month",
                "redflags": "Landlord in the Compound, Bad access road, No steady water",
                "taste": "A quiet street, tiled floors, space for a small garden",
            }
        },
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Full name of tenant",
        examples=["Chidi Okonkwo"],
    )
    phone: str = Field(
        ...,
        min_length=5,
        max_length=50,
        description="WhatsApp phone number (e.g. 080XXXXXXXX)",
        examples=["08031234567"],
    )
    email: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional email address for product launch updates",
        examples=["chidi@example.com"],
    )
    areas: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Which area(s) do you want to live in? (e.g. Arab road, Chikakore, FO1)",
        examples=["Arab road, Chikakore, FO1"],
    )
    budget: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Yearly rent budget range (Under ₦500k, ₦500k–₦1m, ₦1m–₦2m, ₦2m–₦4m, Above ₦4m)",
        examples=["₦500,000 – ₦1,000,000"],
    )
    timing: Optional[str] = Field(
        default=None,
        max_length=100,
        description="When do you need to move? (As soon as possible, Within a month, 1–3 months, Just exploring)",
        examples=["Within a month"],
    )
    redflags: Optional[Union[List[str], str]] = Field(
        default=None,
        description="Deal-breaker red flags (list of strings or comma-separated string)",
        examples=["Landlord in the Compound, Bad access road, No steady water"],
    )
    taste: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Anything else about your taste? (e.g. quiet street, tiled floors, garden)",
        examples=["A quiet street, tiled floors, space for a small garden"],
    )
    submitted_at: Optional[datetime] = Field(
        default=None,
        description="Client submission timestamp (ISO 8601)",
    )
    website: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Hidden honeypot field. Must remain empty.",
    )
    hp_field: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Hidden legacy honeypot field. Must remain empty.",
    )

    @field_validator("redflags", mode="before")
    @classmethod
    def clean_redflags(cls, v: Any) -> Optional[str]:
        if isinstance(v, list):
            cleaned = [str(item).strip() for item in v if str(item).strip()]
            return ", ".join(cleaned) if cleaned else None
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator(
        "budget", "timing", "taste", "website", "hp_field",
        mode="before"
    )
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("email", mode="before")
    @classmethod
    def validate_email_syntax(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str):
            return str(v)
        trimmed = v.strip()
        if not trimmed:
            return None
        if any(c in trimmed for c in "\r\n\t\x00"):
            raise ValueError("Email contains invalid characters.")
        try:
            valid = validate_email(trimmed, check_deliverability=False)
            return valid.normalized
        except EmailNotValidError as exc:
            raise ValueError(f"Invalid email syntax: {exc}")

    @field_validator("phone")
    @classmethod
    def validate_phone_syntax(cls, v: str) -> str:
        digits = [c for c in v if c.isdigit()]
        if len(digits) < 7:
            raise ValueError("Phone number must contain at least 7 digits.")
        return v

    @property
    def type(self) -> str:
        return "tenant"

    @property
    def role(self) -> None:
        return None

    @property
    def listings(self) -> None:
        return None

    @property
    def normalized_phone(self) -> Optional[str]:
        return clean_normalized_phone(self.phone)

    @property
    def normalized_email(self) -> Optional[str]:
        return clean_normalized_email(self.email)


class AgentWaitlistCreate(BaseModel):
    """
    Schema for Agent / Landlord registration on ConfirmBase.
    Collects role (Agent, Landlord, Property manager), operational areas, and monthly listing volumes.
    """
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "name": "Grace Bello",
                "phone": "08099887766",
                "email": "grace@agency.ng",
                "role": "Agent",
                "areas": "Kubwa, Arab road, Chikakore",
                "listings": "4–10",
            }
        },
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Full name of agent or property owner",
        examples=["Grace Bello"],
    )
    phone: str = Field(
        ...,
        min_length=5,
        max_length=50,
        description="WhatsApp phone number (e.g. 080XXXXXXXX)",
        examples=["08099887766"],
    )
    email: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional email address",
        examples=["grace@agency.ng"],
    )
    role: Optional[str] = Field(
        default="Agent",
        max_length=100,
        description="You are a... (Agent, Landlord / property owner, Property manager)",
        examples=["Agent"],
    )
    areas: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Area(s) you operate in (e.g. Arab road, Chikakore, FO1)",
        examples=["Kubwa, Arab road, Chikakore"],
    )
    listings: Optional[str] = Field(
        default=None,
        max_length=100,
        description="How many houses do you currently rent in a month? (1–3, 4–10, 11–30, More than 30)",
        examples=["4–10"],
    )
    submitted_at: Optional[datetime] = Field(
        default=None,
        description="Client submission timestamp (ISO 8601)",
    )
    website: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Hidden honeypot field. Must remain empty.",
    )
    hp_field: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Hidden legacy honeypot field. Must remain empty.",
    )

    @field_validator(
        "role", "listings", "website", "hp_field",
        mode="before"
    )
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("email", mode="before")
    @classmethod
    def validate_email_syntax(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str):
            return str(v)
        trimmed = v.strip()
        if not trimmed:
            return None
        if any(c in trimmed for c in "\r\n\t\x00"):
            raise ValueError("Email contains invalid characters.")
        try:
            valid = validate_email(trimmed, check_deliverability=False)
            return valid.normalized
        except EmailNotValidError as exc:
            raise ValueError(f"Invalid email syntax: {exc}")

    @field_validator("phone")
    @classmethod
    def validate_phone_syntax(cls, v: str) -> str:
        digits = [c for c in v if c.isdigit()]
        if len(digits) < 7:
            raise ValueError("Phone number must contain at least 7 digits.")
        return v

    @property
    def type(self) -> str:
        return "agent"

    @property
    def budget(self) -> None:
        return None

    @property
    def timing(self) -> None:
        return None

    @property
    def redflags(self) -> None:
        return None

    @property
    def taste(self) -> None:
        return None

    @property
    def normalized_phone(self) -> Optional[str]:
        return clean_normalized_phone(self.phone)

    @property
    def normalized_email(self) -> Optional[str]:
        return clean_normalized_email(self.email)


class WaitlistCreate(BaseModel):
    """
    Unified schema for ConfirmBase waitlist registration (supporting both tenants and agents).
    Used by frontend forms sending dynamic type ("tenant" or "agent").
    """
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    type: Literal["tenant", "agent"] = Field(
        default="tenant",
        description="Type of user: tenant or agent",
    )
    name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Full name of user",
    )
    phone: Optional[str] = Field(
        default=None,
        max_length=50,
        description="WhatsApp phone number",
    )
    email: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional email address for waitlist notification",
    )
    areas: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Areas interested in or operating in",
    )

    # Tenant-specific fields
    budget: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Yearly rent budget for tenant",
    )
    timing: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Move-in timeframe for tenant",
    )
    redflags: Optional[Union[List[str], str]] = Field(
        default=None,
        description="Deal-breaker red flags (list of strings or comma-separated string)",
    )
    taste: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Specific preferences or taste",
    )

    # Agent-specific fields
    role: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Agent role (Agent, Landlord, Property manager)",
    )
    listings: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Monthly listings count range",
    )

    # Timestamps & bot honeypot protection
    submitted_at: Optional[datetime] = Field(
        default=None,
        description="Client submission timestamp",
    )
    website: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional honeypot field. Must be empty.",
    )
    hp_field: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional legacy honeypot field. Must be empty.",
    )

    @field_validator("redflags", mode="before")
    @classmethod
    def clean_redflags(cls, v: Any) -> Optional[str]:
        if isinstance(v, list):
            cleaned = [str(item).strip() for item in v if str(item).strip()]
            return ", ".join(cleaned) if cleaned else None
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator(
        "name", "phone", "areas", "budget", "timing",
        "taste", "role", "listings", "website", "hp_field",
        mode="before"
    )
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("email", mode="before")
    @classmethod
    def validate_email_syntax(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str):
            return str(v)
        trimmed = v.strip()
        if not trimmed:
            return None
        if any(c in trimmed for c in "\r\n\t\x00"):
            raise ValueError("Email contains invalid characters.")
        try:
            valid = validate_email(trimmed, check_deliverability=False)
            return valid.normalized
        except EmailNotValidError as exc:
            raise ValueError(f"Invalid email syntax: {exc}")

    @field_validator("phone")
    @classmethod
    def validate_phone_syntax(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        digits = [c for c in v if c.isdigit()]
        if len(digits) < 7:
            raise ValueError("Phone number must contain at least 7 digits.")
        return v

    @model_validator(mode="after")
    def verify_contact_method_present(self) -> WaitlistCreate:
        has_phone = bool(self.phone and self.phone.strip())
        has_email = bool(self.email and self.email.strip())
        if not has_phone and not has_email:
            raise ValueError("At least one contact method (WhatsApp phone number or email) must be provided.")
        return self

    @property
    def normalized_phone(self) -> Optional[str]:
        return clean_normalized_phone(self.phone)

    @property
    def normalized_email(self) -> Optional[str]:
        return clean_normalized_email(self.email)


class WaitlistResponse(BaseModel):
    """Safe standard response for waitlist operations."""
    success: bool = True
    message: str
    ok: Optional[bool] = None
    position: Optional[int] = None


class WaitlistContractResponse(BaseModel):
    """Schema matching the frontend /api/join live mode contract."""
    ok: bool
    position: Optional[int] = None
    error: Optional[str] = None


class WaitlistEntryOut(BaseModel):
    """Schema for admin retrieval of a waitlist entry."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    name: Optional[str] = None
    phone: Optional[str] = None
    phone_normalized: Optional[str] = None
    email: Optional[str] = None
    email_normalized: Optional[str] = None
    areas: Optional[str] = None
    budget: Optional[str] = None
    timing: Optional[str] = None
    redflags: Optional[str] = None
    taste: Optional[str] = None
    role: Optional[str] = None
    listings: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
