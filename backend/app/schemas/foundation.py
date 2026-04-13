"""Pydantic request/response schemas for Domain 1 — Foundation."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ═══════════════════════════════════════════════════════════════════════════
# Projects
# ═══════════════════════════════════════════════════════════════════════════

class ProjectCreate(BaseModel):
    name: str
    project_number: str | None = None
    status: str = "active"
    project_type: str | None = None
    address_line1: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    contract_value: float | None = None
    square_footage: float | None = None
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    project_number: str | None = None
    status: str | None = None
    project_type: str | None = None
    address_line1: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    contract_value: float | None = None
    square_footage: float | None = None
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    project_number: str | None
    status: str
    project_type: str | None
    address_line1: str | None
    city: str | None
    state: str | None
    zip: str | None
    start_date: date | None
    end_date: date | None
    contract_value: float | None
    square_footage: float | None
    description: str | None
    latitude: float | None
    longitude: float | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Companies
# ═══════════════════════════════════════════════════════════════════════════

class CompanyCreate(BaseModel):
    name: str
    trade: str | None = None
    company_type: str
    status: str = "active"
    phone: str | None = None
    email: str | None = None
    address_line1: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    license_number: str | None = None
    insurance_expiry: date | None = None
    insurance_carrier: str | None = None
    bonding_capacity: float | None = None
    notes: str | None = None
    mobile_phone: str | None = None
    website: str | None = None


class CompanyUpdate(BaseModel):
    name: str | None = None
    trade: str | None = None
    company_type: str | None = None
    status: str | None = None
    phone: str | None = None
    email: str | None = None
    address_line1: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    license_number: str | None = None
    insurance_expiry: date | None = None
    insurance_carrier: str | None = None
    bonding_capacity: float | None = None
    notes: str | None = None
    mobile_phone: str | None = None
    website: str | None = None


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    trade: str | None
    company_type: str
    status: str
    phone: str | None
    email: str | None
    address_line1: str | None
    city: str | None
    state: str | None
    zip: str | None
    license_number: str | None
    insurance_expiry: date | None
    insurance_carrier: str | None
    bonding_capacity: float | None
    notes: str | None
    mobile_phone: str | None
    website: str | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# People
# ═══════════════════════════════════════════════════════════════════════════

class PersonCreate(BaseModel):
    company_id: UUID | None = None
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    title: str | None = None
    role_type: str
    is_active: bool = True
    notes: str | None = None


class PersonUpdate(BaseModel):
    company_id: UUID | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    title: str | None = None
    role_type: str | None = None
    is_active: bool | None = None
    notes: str | None = None


class PersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID | None
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    title: str | None
    role_type: str
    is_active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Role Templates
# ═══════════════════════════════════════════════════════════════════════════

class RoleTemplateCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    is_internal: bool = True
    default_access_level: str
    visible_tools: list[Any] = []
    visible_panels: list[Any] = []
    quick_action_groups: list[Any] = []
    can_write: list[Any] = []
    can_approve: list[Any] = []
    notification_defaults: dict[str, Any] = {}
    home_screen: str = "my_day"
    is_system: bool = False
    sort_order: int = 0


class RoleTemplateUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    is_internal: bool | None = None
    default_access_level: str | None = None
    visible_tools: list[Any] | None = None
    visible_panels: list[Any] | None = None
    quick_action_groups: list[Any] | None = None
    can_write: list[Any] | None = None
    can_approve: list[Any] | None = None
    notification_defaults: dict[str, Any] | None = None
    home_screen: str | None = None
    is_system: bool | None = None
    sort_order: int | None = None


class RoleTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    description: str | None
    is_internal: bool
    default_access_level: str
    visible_tools: list[Any]
    visible_panels: list[Any]
    quick_action_groups: list[Any]
    can_write: list[Any]
    can_approve: list[Any]
    notification_defaults: dict[str, Any]
    home_screen: str
    is_system: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Project Members
# ═══════════════════════════════════════════════════════════════════════════

class ProjectMemberCreate(BaseModel):
    project_id: UUID
    person_id: UUID
    company_id: UUID | None = None
    role_template_id: UUID | None = None
    access_level: str | None = None
    is_primary: bool = False
    is_active: bool = True
    start_date: date | None = None
    end_date: date | None = None


class ProjectMemberUpdate(BaseModel):
    company_id: UUID | None = None
    role_template_id: UUID | None = None
    access_level: str | None = None
    is_primary: bool | None = None
    is_active: bool | None = None
    start_date: date | None = None
    end_date: date | None = None


class ProjectMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    person_id: UUID
    company_id: UUID | None
    role_template_id: UUID | None
    access_level: str | None
    is_primary: bool
    is_active: bool
    start_date: date | None
    end_date: date | None
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════════════════
# Connector Mappings
# ═══════════════════════════════════════════════════════════════════════════

class ConnectorMappingCreate(BaseModel):
    rex_table: str
    rex_id: UUID
    connector: str
    external_id: str
    external_url: str | None = None
    synced_at: datetime | None = None


class ConnectorMappingUpdate(BaseModel):
    external_url: str | None = None
    synced_at: datetime | None = None


class ConnectorMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    rex_table: str
    rex_id: UUID
    connector: str
    external_id: str
    external_url: str | None
    synced_at: datetime | None
    created_at: datetime
