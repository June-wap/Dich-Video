from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class LicenseStatus(str, Enum):
    ACTIVE = "ACTIVE"
    UNLICENSED = "UNLICENSED"
    EXPIRED = "EXPIRED"
    INVALID = "INVALID"
    MACHINE_MISMATCH = "MACHINE_MISMATCH"
    CLOCK_TAMPERED = "CLOCK_TAMPERED"
    BLOCKED = "BLOCKED"
    DEVICE_LIMIT_REACHED = "DEVICE_LIMIT_REACHED"
    REVOKED = "REVOKED"
    LEASE_EXPIRED = "LEASE_EXPIRED"


class LicenseType(str, Enum):
    LIFETIME = "lifetime"
    TIME_LIMITED = "time_limited"


class LicenseStatusResponse(BaseModel):
    status: LicenseStatus
    is_active: bool
    machine_id: str
    customer_name: Optional[str] = None
    license_type: Optional[LicenseType] = None
    issued_at: Optional[str] = None
    expires_at: Optional[str] = None
    days_left: Optional[int] = None
    time_left_str: Optional[str] = None
    is_trial: bool = False
    message: str
    is_cloud_managed: bool = False
    validation_until: Optional[str] = None
    grace_period_active: bool = False


class ActivateLicenseRequest(BaseModel):
    license_key: str = Field(..., min_length=10, description="Chuỗi mã kích hoạt bản quyền do người bán cung cấp")


class ActivateLicenseResponse(BaseModel):
    ok: bool
    status: LicenseStatusResponse


class RefreshLicenseResponse(BaseModel):
    ok: bool
    status: LicenseStatusResponse

