"""
Database Schemas for Dlynq (Multi-tenant SaaS)

Each Pydantic model corresponds to a MongoDB collection. The collection name is the lowercase of the class name.
All documents include tenant_id for isolation.
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, EmailStr, HttpUrl
from datetime import datetime

# ---------- Core helpers ----------
class BaseTenantModel(BaseModel):
    tenant_id: str = Field(..., description="Tenant/organization/reseller identifier")

class PlanFeatureFlags(BaseModel):
    custom_domain: bool = False
    templates_advanced: bool = False
    analytics_full_history: bool = False
    crm_integrations: bool = False
    wallet_passes: bool = False
    nfc_mapping: bool = False
    sso_saml: bool = False
    white_label: bool = False
    audit_logs: bool = False

# ---------- Users & Access ----------
class User(BaseTenantModel):
    email: EmailStr
    name: str
    password_hash: Optional[str] = None
    provider: Literal["email", "google", "microsoft", "sso"] = "email"
    roles: List[Literal[
        "super_admin", "org_owner", "team_admin", "user", "reseller_admin"
    ]] = ["user"]
    org_id: Optional[str] = None
    team_ids: List[str] = []
    is_active: bool = True
    avatar_url: Optional[HttpUrl] = None

class Organization(BaseTenantModel):
    name: str
    slug: str
    reseller_id: Optional[str] = None
    brand: Dict[str, Any] = Field(default_factory=dict, description="colors, logo, fonts")

class Reseller(BaseTenantModel):
    name: str
    slug: str
    domain: Optional[str] = None
    branding: Dict[str, Any] = Field(default_factory=dict)

# ---------- Subscriptions ----------
class Plan(BaseTenantModel):
    name: Literal["Free", "Pro", "Team", "Enterprise", "Reseller"]
    price_monthly_usd: float
    limits: Dict[str, int] = Field(default_factory=dict)
    features: PlanFeatureFlags = Field(default_factory=PlanFeatureFlags)

class Subscription(BaseTenantModel):
    org_id: Optional[str] = None
    reseller_id: Optional[str] = None
    plan_name: Literal["Free", "Pro", "Team", "Enterprise", "Reseller"]
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    status: Literal["trialing", "active", "past_due", "canceled"] = "active"
    trial_end: Optional[datetime] = None

# ---------- Cards & Templates ----------
class CardTemplate(BaseTenantModel):
    name: str
    description: Optional[str] = None
    layout: Dict[str, Any] = Field(default_factory=dict)
    locked_options: Dict[str, Any] = Field(default_factory=dict)

class DigitalBusinessCard(BaseTenantModel):
    user_id: str
    org_id: Optional[str] = None
    slug: str
    status: Literal["active", "archived", "draft"] = "active"
    profile: Dict[str, Any] = Field(default_factory=dict)
    contact: Dict[str, Any] = Field(default_factory=dict)
    social: Dict[str, Any] = Field(default_factory=dict)
    about: Optional[str] = None
    services: List[Dict[str, Any]] = []
    portfolio: List[Dict[str, Any]] = []
    attachments: List[Dict[str, Any]] = []
    experience: List[Dict[str, Any]] = []
    testimonials: List[Dict[str, Any]] = []
    custom_sections: List[Dict[str, Any]] = []
    design: Dict[str, Any] = Field(default_factory=dict)
    seo: Dict[str, Any] = Field(default_factory=dict)
    template_id: Optional[str] = None

# ---------- Leads & Tracking ----------
class ContactLead(BaseTenantModel):
    source_card_id: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    message: Optional[str] = None
    tags: List[str] = []
    status: Literal["new", "contacted", "qualified", "converted", "archived"] = "new"

class AnalyticsEvent(BaseTenantModel):
    card_id: Optional[str] = None
    user_id: Optional[str] = None
    org_id: Optional[str] = None
    event_type: Literal[
        "view", "unique_view", "qr_scan", "click_call", "click_email", "click_whatsapp", "click_website",
        "contact_save", "form_submit", "attachment_click", "wallet_open"
    ]
    metadata: Dict[str, Any] = Field(default_factory=dict)

# ---------- Devices & QR ----------
class NFCDevice(BaseTenantModel):
    serial: str
    label: Optional[str] = None
    card_id: Optional[str] = None

class QRCode(BaseTenantModel):
    card_id: str
    format: Literal["png", "svg"] = "png"
    url: HttpUrl
    label: Optional[str] = None

# ---------- Assets & Integrations ----------
class FileAttachment(BaseTenantModel):
    owner_user_id: Optional[str] = None
    org_id: Optional[str] = None
    filename: str
    url: HttpUrl
    mime_type: str
    size_bytes: int

class IntegrationConfig(BaseTenantModel):
    org_id: Optional[str] = None
    type: Literal["salesforce", "hubspot", "zapier", "webhook", "ga4", "facebook_pixel"]
    config: Dict[str, Any] = Field(default_factory=dict)

# ---------- Signature & Background ----------
class EmailSignatureTemplate(BaseTenantModel):
    name: str
    html: str
    category: Literal["minimal", "corporate", "creative"] = "minimal"

class VirtualBackgroundTemplate(BaseTenantModel):
    name: str
    image_url: Optional[HttpUrl] = None
    config: Dict[str, Any] = Field(default_factory=dict)
