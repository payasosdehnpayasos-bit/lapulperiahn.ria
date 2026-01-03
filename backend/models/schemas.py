# /app/backend/models/schemas.py
# Modelos Pydantic para La Pulpería v1.0

from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal
from datetime import datetime

# ============================================
# USER MODELS
# ============================================

class User(BaseModel):
    user_id: str
    email: EmailStr
    name: str
    picture: Optional[str] = None
    user_type: Optional[Literal["cliente", "pulperia"]] = None
    location: Optional[dict] = None
    is_admin: Optional[bool] = False
    created_at: datetime

# ============================================
# PULPERIA MODELS
# ============================================

class Pulperia(BaseModel):
    pulperia_id: str
    owner_user_id: str
    name: str
    description: Optional[str] = None
    address: Optional[str] = None
    location: Optional[dict] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    hours: Optional[str] = None
    image_url: Optional[str] = None
    logo_url: Optional[str] = None
    rating: Optional[float] = 0.0
    review_count: Optional[int] = 0
    title_font: Optional[str] = "default"
    background_color: Optional[str] = "#DC2626"
    is_online_only: Optional[bool] = False
    created_at: datetime

class PulperiaCreate(BaseModel):
    name: str
    description: Optional[str] = None
    address: Optional[str] = None
    location: Optional[dict] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    instagram_url: Optional[str] = None
    facebook_url: Optional[str] = None
    twitter_url: Optional[str] = None
    hours: Optional[str] = None
    image_url: Optional[str] = None
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    title_font: Optional[str] = "default"
    background_color: Optional[str] = "#DC2626"
    badge: Optional[str] = None
    is_suspended: Optional[bool] = False
    suspension_reason: Optional[str] = None
    is_online_only: Optional[bool] = False

# ============================================
# PRODUCT MODELS
# ============================================

class Product(BaseModel):
    product_id: str
    pulperia_id: str
    name: str
    description: Optional[str] = None
    price: float
    stock: int = 0
    available: bool = True
    category: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock: int = 0
    available: bool = True
    category: Optional[str] = None
    image_url: Optional[str] = None

# ============================================
# ORDER MODELS
# ============================================

class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    price: float
    pulperia_id: Optional[str] = None
    pulperia_name: Optional[str] = None
    image_url: Optional[str] = None

class Order(BaseModel):
    order_id: str
    customer_user_id: str
    customer_name: str
    pulperia_id: str
    items: List[OrderItem]
    total: float
    status: Literal["pending", "accepted", "ready", "completed", "cancelled"] = "pending"
    order_type: Literal["online", "pickup"] = "pickup"
    created_at: datetime

class OrderCreate(BaseModel):
    customer_name: str
    pulperia_id: str
    items: List[OrderItem]
    total: float
    order_type: Literal["online", "pickup"] = "pickup"

class OrderStatusUpdate(BaseModel):
    status: Literal["pending", "accepted", "ready", "completed", "cancelled"]

# ============================================
# REVIEW MODELS
# ============================================

class Review(BaseModel):
    review_id: str
    pulperia_id: str
    user_id: str
    user_name: str
    rating: int
    comment: Optional[str] = None
    images: List[str] = []
    created_at: datetime

class ReviewCreate(BaseModel):
    rating: int
    comment: Optional[str] = None
    images: List[str] = []

# ============================================
# JOB MODELS
# ============================================

class Job(BaseModel):
    job_id: str
    employer_user_id: str
    employer_name: str
    pulperia_id: Optional[str] = None
    pulperia_name: Optional[str] = None
    pulperia_logo: Optional[str] = None
    title: str
    description: str
    category: str
    pay_rate: float
    pay_currency: Literal["HNL", "USD"]
    location: str
    contact: str
    is_active: Optional[bool] = True
    created_at: datetime

class JobCreate(BaseModel):
    title: str
    description: str
    category: str
    pay_rate: float
    pay_currency: Literal["HNL", "USD"]
    location: str
    contact: str
    pulperia_id: Optional[str] = None

class JobApplication(BaseModel):
    application_id: str
    job_id: str
    job_title: str
    pulperia_id: str
    pulperia_name: str
    applicant_user_id: str
    applicant_name: str
    applicant_email: str
    applicant_city: str
    applicant_age: int
    cv_url: Optional[str] = None
    message: Optional[str] = None
    status: Literal["recibida", "en_revision", "aceptada", "rechazada"] = "recibida"
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

# ============================================
# SERVICE MODELS
# ============================================

class Service(BaseModel):
    service_id: str
    provider_user_id: str
    provider_name: str
    title: str
    description: str
    category: str
    hourly_rate: float
    rate_currency: Literal["HNL", "USD"]
    location: str
    contact: str
    images: List[str] = []
    created_at: datetime

class ServiceCreate(BaseModel):
    title: str
    description: str
    category: str
    hourly_rate: float
    rate_currency: Literal["HNL", "USD"]
    location: str
    contact: str
    images: List[str] = []

# ============================================
# ADVERTISEMENT MODELS
# ============================================

class Advertisement(BaseModel):
    ad_id: str
    pulperia_id: str
    pulperia_name: str
    plan: Literal["basico", "destacado", "premium", "recomendado"]
    status: Literal["pending", "active", "expired"] = "pending"
    payment_method: str
    payment_reference: Optional[str] = None
    amount: float
    duration_days: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    assigned_by: Optional[str] = None
    assigned_at: Optional[datetime] = None
    created_at: datetime

class AdvertisementCreate(BaseModel):
    plan: Literal["basico", "destacado", "premium", "recomendado"]
    payment_method: str
    payment_reference: Optional[str] = None

class AdAssignmentLog(BaseModel):
    log_id: str
    ad_id: str
    pulperia_id: str
    pulperia_name: str
    plan: str
    action: str
    assigned_by: str
    created_at: datetime

class AdminAdActivation(BaseModel):
    pulperia_id: str
    plan: Literal["basico", "destacado", "premium", "recomendado"]
    duration_days: int = 7

# ============================================
# FEATURED ADS MODELS
# ============================================

class FeaturedAd(BaseModel):
    ad_id: str
    pulperia_id: str
    pulperia_name: str
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    link_url: Optional[str] = None
    is_active: bool = True
    created_at: datetime
    expires_at: datetime

class FeaturedAdSlot(BaseModel):
    slot_id: str
    pulperia_id: str
    pulperia_name: str
    enabled_by: str
    enabled_at: datetime
    expires_at: datetime
    is_used: bool = False
    ad_id: Optional[str] = None

# ============================================
# ACHIEVEMENT MODELS
# ============================================

class PulperiaAchievement(BaseModel):
    achievement_id: str
    pulperia_id: str
    badge_id: str
    unlocked_at: datetime

class PulperiaStats(BaseModel):
    pulperia_id: str
    sales_count: int = 0
    products_count: int = 0
    profile_views: int = 0
    happy_customers: int = 0
    avg_response_time: int = 999
    is_verified: bool = False
    updated_at: datetime

# ============================================
# AUTH MODELS
# ============================================

class SessionRequest(BaseModel):
    session_id: str

class UserTypeChange(BaseModel):
    new_type: Literal["cliente", "pulperia"]

# ============================================
# OTHER MODELS
# ============================================

class AnnouncementCreate(BaseModel):
    text: str
    type: Optional[str] = "info"
    expires_at: Optional[datetime] = None

class ClosePulperiaRequest(BaseModel):
    confirmation_phrase: str

# ============================================
# GLOBAL ANNOUNCEMENT MODELS
# ============================================

class GlobalAnnouncement(BaseModel):
    announcement_id: str
    title: str
    content: str
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    priority: int = 0
    is_active: bool = True
    created_at: datetime
    expires_at: Optional[datetime] = None
    created_by: str
