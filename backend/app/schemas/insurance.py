"""Pydantic schemas for insurance certificates."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

PolicyType = Literal["gl", "wc", "auto", "umbrella", "other"]
CertStatus = Literal["current", "expiring_soon", "expired", "missing"]


class InsuranceCertificateCreate(BaseModel):
    company_id: UUID
    policy_type: PolicyType
    carrier: str | None = None
    policy_number: str | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    limit_amount: float | None = None
    status: CertStatus = "current"
    attachment_id: UUID | None = None
    notes: str | None = None


class InsuranceCertificateUpdate(BaseModel):
    policy_type: PolicyType | None = None
    carrier: str | None = None
    policy_number: str | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    limit_amount: float | None = None
    status: CertStatus | None = None
    attachment_id: UUID | None = None
    notes: str | None = None


class InsuranceCertificateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    company_id: UUID
    policy_type: str
    carrier: str | None
    policy_number: str | None
    effective_date: date | None
    expiry_date: date | None
    limit_amount: float | None
    status: str
    attachment_id: UUID | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class InsuranceCertificateSummaryResponse(BaseModel):
    total: int
    current: int
    expiring_soon: int  # within 60 days
    expired: int
    missing: int  # companies with no certs (computed at endpoint level)


class InsuranceRefreshResponse(BaseModel):
    total_certs: int
    updated_count: int
    by_status: dict[str, int]
