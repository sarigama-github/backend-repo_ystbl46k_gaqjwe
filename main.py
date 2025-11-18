import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from database import db, create_document, get_documents
from schemas import (
    User as UserSchema,
    Organization as OrganizationSchema,
    Reseller as ResellerSchema,
    DigitalBusinessCard as CardSchema,
    ContactLead as LeadSchema,
    AnalyticsEvent as EventSchema,
)
import hashlib

app = FastAPI(title="Dlynq API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Utilities ----------
class TenantContext(BaseModel):
    tenant_id: str

def get_tenant(
    x_tenant_id: Optional[str] = Header(None),
    tenant: Optional[str] = Query(default=None)
) -> TenantContext:
    tenant_id = x_tenant_id or tenant
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id required via X-Tenant-ID header or ?tenant=")
    return TenantContext(tenant_id=tenant_id)

# ---------- Basic health ----------
@app.get("/")
def read_root():
    return {"name": "Dlynq API", "status": "ok"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, 'name', None) or "Unknown"
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but error: {str(e)[:80]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response

# ---------- Auth (lightweight) ----------
class SignupBody(BaseModel):
    email: EmailStr
    name: str
    password: str

class LoginBody(BaseModel):
    email: EmailStr
    password: str

@app.post("/api/auth/signup")
def signup(body: SignupBody, ctx: TenantContext = Depends(get_tenant)):
    # simple hash (demo only)
    pwd_hash = hashlib.sha256(body.password.encode()).hexdigest()
    doc = UserSchema(
        tenant_id=ctx.tenant_id,
        email=body.email,
        name=body.name,
        password_hash=pwd_hash,
        roles=["user"],
    ).model_dump()
    # unique check
    existing = db["user"].find_one({"tenant_id": ctx.tenant_id, "email": body.email})
    if existing:
        raise HTTPException(400, detail="User already exists")
    user_id = create_document("user", doc)
    return {"user_id": user_id, "token": f"demo-{user_id}", "tenant_id": ctx.tenant_id}

@app.post("/api/auth/login")
def login(body: LoginBody, ctx: TenantContext = Depends(get_tenant)):
    user = db["user"].find_one({"tenant_id": ctx.tenant_id, "email": body.email})
    if not user:
        raise HTTPException(401, detail="Invalid credentials")
    pwd_hash = hashlib.sha256(body.password.encode()).hexdigest()
    if user.get("password_hash") != pwd_hash:
        raise HTTPException(401, detail="Invalid credentials")
    return {"token": f"demo-{str(user.get('_id'))}", "user": {"email": user["email"], "name": user.get("name")}}

# ---------- Tenant resources ----------
class OrgBody(BaseModel):
    name: str
    slug: str
    reseller_id: Optional[str] = None

@app.post("/api/orgs")
def create_org(body: OrgBody, ctx: TenantContext = Depends(get_tenant)):
    data = OrganizationSchema(tenant_id=ctx.tenant_id, name=body.name, slug=body.slug, reseller_id=body.reseller_id).model_dump()
    org_id = create_document("organization", data)
    return {"org_id": org_id}

class ResellerBody(BaseModel):
    name: str
    slug: str
    domain: Optional[str] = None

@app.post("/api/resellers")
def create_reseller(body: ResellerBody, ctx: TenantContext = Depends(get_tenant)):
    data = ResellerSchema(tenant_id=ctx.tenant_id, name=body.name, slug=body.slug, domain=body.domain).model_dump()
    reseller_id = create_document("reseller", data)
    return {"reseller_id": reseller_id}

# ---------- Cards ----------
class CardCreateBody(BaseModel):
    user_id: str
    org_id: Optional[str] = None
    slug: str
    profile: Dict[str, Any] = {}
    contact: Dict[str, Any] = {}
    social: Dict[str, Any] = {}
    about: Optional[str] = None
    design: Dict[str, Any] = {}
    seo: Dict[str, Any] = {}

@app.post("/api/cards")
def create_card(body: CardCreateBody, ctx: TenantContext = Depends(get_tenant)):
    # ensure slug unique per tenant
    if db["digitalbusinesscard"].find_one({"tenant_id": ctx.tenant_id, "slug": body.slug}):
        raise HTTPException(400, detail="Slug already in use")
    data = CardSchema(
        tenant_id=ctx.tenant_id,
        user_id=body.user_id,
        org_id=body.org_id,
        slug=body.slug,
        profile=body.profile,
        contact=body.contact,
        social=body.social,
        about=body.about,
        design=body.design,
        seo=body.seo,
    ).model_dump()
    card_id = create_document("digitalbusinesscard", data)
    return {"card_id": card_id}

@app.get("/api/cards")
def list_cards(user_id: Optional[str] = None, ctx: TenantContext = Depends(get_tenant)):
    filt: Dict[str, Any] = {"tenant_id": ctx.tenant_id}
    if user_id:
        filt["user_id"] = user_id
    cards = get_documents("digitalbusinesscard", filt, limit=100)
    for c in cards:
        c["_id"] = str(c["_id"])  # make serializable
    return {"items": cards}

@app.get("/api/public/cards/{slug}")
def get_public_card(slug: str, ctx: TenantContext = Depends(get_tenant)):
    card = db["digitalbusinesscard"].find_one({"tenant_id": ctx.tenant_id, "slug": slug, "status": {"$ne": "archived"}})
    if not card:
        raise HTTPException(404, detail="Card not found")
    card["_id"] = str(card["_id"])  # serialize
    return {"card": card}

# ---------- Leads ----------
class LeadBody(BaseModel):
    source_card_id: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    message: Optional[str] = None
    tags: List[str] = []

@app.post("/api/leads")
def create_lead(body: LeadBody, ctx: TenantContext = Depends(get_tenant)):
    data = LeadSchema(tenant_id=ctx.tenant_id, **body.model_dump()).model_dump()
    lead_id = create_document("contactlead", data)
    return {"lead_id": lead_id}

@app.get("/api/leads")
def list_leads(card_id: Optional[str] = None, ctx: TenantContext = Depends(get_tenant)):
    filt: Dict[str, Any] = {"tenant_id": ctx.tenant_id}
    if card_id:
        filt["source_card_id"] = card_id
    leads = get_documents("contactlead", filt, limit=200)
    for l in leads:
        l["_id"] = str(l["_id"])  # serialize
    return {"items": leads}

# ---------- Analytics ----------
class EventBody(BaseModel):
    card_id: Optional[str] = None
    user_id: Optional[str] = None
    org_id: Optional[str] = None
    event_type: str
    metadata: Dict[str, Any] = {}

@app.post("/api/events")
def track_event(body: EventBody, ctx: TenantContext = Depends(get_tenant)):
    data = EventSchema(tenant_id=ctx.tenant_id, **body.model_dump()).model_dump()
    event_id = create_document("analyticsevent", data)
    return {"event_id": event_id}

@app.get("/api/analytics/summary")
def analytics_summary(ctx: TenantContext = Depends(get_tenant)):
    # simple counts
    total_cards = db["digitalbusinesscard"].count_documents({"tenant_id": ctx.tenant_id})
    total_leads = db["contactlead"].count_documents({"tenant_id": ctx.tenant_id})
    total_events = db["analyticsevent"].count_documents({"tenant_id": ctx.tenant_id})
    recent_events = get_documents("analyticsevent", {"tenant_id": ctx.tenant_id}, limit=20)
    for e in recent_events:
        e["_id"] = str(e["_id"])  # serialize
    return {
        "cards": total_cards,
        "leads": total_leads,
        "events": total_events,
        "recent_events": recent_events,
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
