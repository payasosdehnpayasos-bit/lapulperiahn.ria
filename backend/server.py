from fastapi import FastAPI, APIRouter, HTTPException, Cookie, Response, Header, WebSocket, WebSocketDisconnect, File, UploadFile, Form
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import re
import base64
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Literal, Dict, Set
import uuid
from datetime import datetime, timezone, timedelta
import httpx
import asyncio
import json

# ============================================
# LA PULPERÍA v1.0 - Backend API
# Arquitectura refactorizada con módulos separados
# ============================================

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Importar modelos desde módulo separado
from models.schemas import (
    User, Pulperia, PulperiaCreate, Product, ProductCreate,
    Order, OrderItem, OrderCreate, OrderStatusUpdate,
    Review, ReviewCreate, Job, JobCreate, JobApplication,
    Service, ServiceCreate, Advertisement, AdvertisementCreate,
    AdAssignmentLog, AdminAdActivation, FeaturedAd, FeaturedAdSlot,
    PulperiaAchievement, PulperiaStats, SessionRequest, UserTypeChange,
    AnnouncementCreate, ClosePulperiaRequest
)

# Importar configuración de logros
from config.achievements import ACHIEVEMENT_DEFINITIONS, AD_PLANS

# Importar servicio de emails
from services.email_service import (
    send_order_notification,
    send_order_accepted,
    send_order_ready,
    send_job_application_notification,
    send_application_accepted,
    send_application_rejected
)

# ============================================
# v1.1 - NUEVOS MODELOS
# ============================================

class ProfilePictureUpdate(BaseModel):
    picture_url: str

class PriceHistory(BaseModel):
    product_id: str
    old_price: float
    new_price: float
    changed_at: datetime

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'la_pulperia_db')]

app = FastAPI(title="La Pulpería API", version="1.0.0", description="Backend para La Pulpería - Marketplace de pulperías hondureñas")
api_router = APIRouter(prefix="/api")

# Admin email for special access
ADMIN_EMAIL = "onol4sco05@gmail.com"

# Emergent Auth URL for Google OAuth
EMERGENT_AUTH_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================
# AUTHENTICATION HELPERS
# ============================================

async def get_current_user(authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Get current authenticated user from session token"""
    token = None
    
    if session_token:
        token = session_token
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
    
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    
    session_doc = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session_doc:
        raise HTTPException(status_code=401, detail="Sesión inválida")
    
    expires_at = session_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Sesión expirada")
    
    user_doc = await db.users.find_one({"user_id": session_doc["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Check if user is admin
    user_doc["is_admin"] = user_doc.get("email") == ADMIN_EMAIL
    
    return User(**user_doc)

async def get_admin_user(authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Get current user and verify admin access"""
    user = await get_current_user(authorization, session_token)
    if user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Acceso denegado. Solo el administrador puede acceder.")
    return user

# ============================================
# FUZZY SEARCH HELPER
# ============================================

def normalize_text(text: str) -> str:
    """Normalize text for fuzzy matching"""
    if not text:
        return ""
    # Remove accents and convert to lowercase
    text = text.lower()
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ü': 'u', 'ñ': 'n'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text

def create_search_pattern(search_term: str) -> str:
    """Create a flexible regex pattern for fuzzy search"""
    normalized = normalize_text(search_term)
    # Remove trailing 's' for singular/plural matching
    if normalized.endswith('s') and len(normalized) > 2:
        normalized = normalized[:-1]
    # Create pattern that matches the base term
    return normalized

async def fuzzy_search_products(search_term: str) -> list:
    """Search products with fuzzy matching"""
    base_pattern = create_search_pattern(search_term)
    
    # Search with multiple patterns
    products = await db.products.find(
        {
            "$or": [
                {"name": {"$regex": base_pattern, "$options": "i"}},
                {"name": {"$regex": f".*{base_pattern}.*", "$options": "i"}},
                {"description": {"$regex": base_pattern, "$options": "i"}},
                {"category": {"$regex": base_pattern, "$options": "i"}}
            ],
            "available": True
        },
        {"_id": 0}
    ).to_list(100)
    
    return products

# ============================================
# AUTHENTICATION ENDPOINTS
# ============================================

# Google OAuth configuration for custom domain
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
CUSTOM_DOMAIN = os.environ.get('CUSTOM_DOMAIN', 'lapulperiastore.net')



# ===== GOOGLE OAUTH - ELIMINADO =====
# Todos los endpoints de Google OAuth han sido removidos
# La aplicación usa SOLO Emergent Auth ahora
# Sin configuración externa necesaria

# Si necesitas reactivar Google OAuth en el futuro, el código está en el historial de git

@api_router.post("/auth/session")
async def create_session(request: SessionRequest, response: Response):
    """Create user session from Emergent Auth session_id"""
    logger.info("[AUTH] Processing session request")
    
    async with httpx.AsyncClient() as http_client:
        try:
            emergent_response = await http_client.get(
                EMERGENT_AUTH_URL,
                headers={"X-Session-ID": request.session_id},
                timeout=15
            )
            emergent_response.raise_for_status()
            auth_data = emergent_response.json()
            logger.info(f"[AUTH] Google OAuth successful for: {auth_data.get('email')}")
        except httpx.HTTPStatusError as e:
            logger.error(f"[AUTH] Auth validation failed: {e.response.status_code}")
            raise HTTPException(status_code=401, detail="Autenticación fallida")
        except Exception as e:
            logger.error(f"[AUTH] Auth service error: {str(e)}")
            raise HTTPException(status_code=502, detail="Error del servicio de autenticación")
    
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    session_token = auth_data["session_token"]
    
    existing_user = await db.users.find_one({"email": auth_data["email"]}, {"_id": 0})
    
    if existing_user:
        user_id = existing_user["user_id"]
        logger.info(f"[AUTH] Existing user: {user_id}")
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "name": auth_data["name"],
                "picture": auth_data["picture"]
            }}
        )
        is_new_user = False
    else:
        logger.info(f"[AUTH] Creating new user: {user_id}")
        user_doc = {
            "user_id": user_id,
            "email": auth_data["email"],
            "name": auth_data["name"],
            "picture": auth_data["picture"],
            "user_type": None,
            "location": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one(user_doc)
        is_new_user = True
    
    session_doc = {
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),  # 1 year persistent session
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_sessions.insert_one(session_doc)
    logger.info(f"[AUTH] Session created for: {user_id}")
    
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=365 * 24 * 60 * 60,  # 1 year
        path="/"
    )
    
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    user["is_new_user"] = is_new_user
    user["is_admin"] = user.get("email") == ADMIN_EMAIL
    return user

@api_router.get("/auth/me")
async def get_me(authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Get current authenticated user"""
    user = await get_current_user(authorization, session_token)
    return user

@api_router.post("/auth/logout")
async def logout(response: Response, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Logout user and clear session"""
    token = session_token or (authorization.replace("Bearer ", "") if authorization else None)
    
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    
    response.delete_cookie(key="session_token", path="/")
    return {"message": "Sesión cerrada exitosamente"}

@api_router.post("/auth/set-user-type")
async def set_user_type(user_type: Literal["cliente", "pulperia"], authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Set user type (cliente or pulperia)"""
    user = await get_current_user(authorization, session_token)
    
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {"user_type": user_type}}
    )
    
    updated_user = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    updated_user["is_admin"] = updated_user.get("email") == ADMIN_EMAIL
    return updated_user

@api_router.post("/auth/change-user-type")
async def change_user_type(type_change: UserTypeChange, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Change user type between cliente and pulperia"""
    user = await get_current_user(authorization, session_token)
    
    # If changing to cliente from pulperia, update name to pulperia name if they have one
    new_name = user.name
    if type_change.new_type == "cliente" and user.user_type == "pulperia":
        pulperia = await db.pulperias.find_one({"owner_user_id": user.user_id}, {"_id": 0})
        if pulperia:
            new_name = pulperia["name"]
    
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {"user_type": type_change.new_type, "name": new_name}}
    )
    
    updated_user = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    updated_user["is_admin"] = updated_user.get("email") == ADMIN_EMAIL
    return updated_user

@api_router.put("/auth/profile-picture")
async def update_profile_picture(data: ProfilePictureUpdate, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Update user profile picture"""
    user = await get_current_user(authorization, session_token)
    
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {"picture": data.picture_url, "custom_picture": True}}
    )
    
    updated_user = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    updated_user["is_admin"] = updated_user.get("email") == ADMIN_EMAIL
    return updated_user

# ============================================
# REPORTES Y ESTADÍSTICAS (v1.1)
# ============================================

@api_router.get("/pulperias/{pulperia_id}/reports")
async def get_pulperia_reports(pulperia_id: str, period: str = "week", authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Get sales reports for a pulperia"""
    user = await get_current_user(authorization, session_token)
    
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    if pulperia["owner_user_id"] != user.user_id and user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="No tienes permiso para ver estos reportes")
    
    # Calculate date range
    now = datetime.now(timezone.utc)
    if period == "day":
        start_date = now - timedelta(days=1)
    elif period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:
        start_date = now - timedelta(days=7)
    
    # Get orders in period
    orders = await db.orders.find({
        "pulperia_id": pulperia_id,
        "status": "completed",
        "created_at": {"$gte": start_date.isoformat()}
    }, {"_id": 0}).to_list(1000)
    
    # Calculate metrics
    total_sales = len(orders)
    total_revenue = sum(order.get("total", 0) for order in orders)
    
    # Products sold count
    product_counts = {}
    for order in orders:
        for item in order.get("items", []):
            pid = item.get("product_id", "unknown")
            pname = item.get("product_name", "Desconocido")
            if pid not in product_counts:
                product_counts[pid] = {"name": pname, "quantity": 0, "revenue": 0}
            product_counts[pid]["quantity"] += item.get("quantity", 0)
            product_counts[pid]["revenue"] += item.get("price", 0) * item.get("quantity", 0)
    
    # Top 5 products
    top_products = sorted(product_counts.values(), key=lambda x: x["quantity"], reverse=True)[:5]
    
    # Sales by hour
    sales_by_hour = {}
    for order in orders:
        try:
            created = order.get("created_at", "")
            if isinstance(created, str):
                hour = datetime.fromisoformat(created.replace("Z", "+00:00")).hour
            else:
                hour = created.hour
            sales_by_hour[hour] = sales_by_hour.get(hour, 0) + 1
        except:
            pass
    
    # Peak hours
    peak_hours = sorted(sales_by_hour.items(), key=lambda x: x[1], reverse=True)[:3]
    
    # Customer frequency
    customer_counts = {}
    for order in orders:
        cid = order.get("customer_user_id", "unknown")
        cname = order.get("customer_name", "Cliente")
        if cid not in customer_counts:
            customer_counts[cid] = {"name": cname, "orders": 0}
        customer_counts[cid]["orders"] += 1
    
    frequent_customers = sorted(customer_counts.values(), key=lambda x: x["orders"], reverse=True)[:5]
    
    return {
        "period": period,
        "total_sales": total_sales,
        "total_revenue": total_revenue,
        "average_order": round(total_revenue / total_sales, 2) if total_sales > 0 else 0,
        "top_products": top_products,
        "peak_hours": [{"hour": h, "orders": c} for h, c in peak_hours],
        "frequent_customers": frequent_customers,
        "sales_trend": [{"date": (now - timedelta(days=i)).strftime("%d/%m"), "sales": len([o for o in orders if o.get("created_at", "").startswith((now - timedelta(days=i)).strftime("%Y-%m-%d"))])} for i in range(6, -1, -1)]
    }

# ============================================
# HISTORIAL DE PRECIOS (v1.1)
# ============================================

@api_router.get("/products/{product_id}/price-history")
async def get_price_history(product_id: str):
    """Get price history for a product"""
    history = await db.price_history.find(
        {"product_id": product_id},
        {"_id": 0}
    ).sort("changed_at", -1).to_list(10)
    
    return history

# ============================================
# PULPERIA ENDPOINTS
# ============================================

@api_router.get("/pulperias")
async def get_pulperias(lat: Optional[float] = None, lng: Optional[float] = None, search: Optional[str] = None, sort_by: Optional[str] = None):
    """Get all pulperias with optional search and sorting"""
    query = {}
    if search:
        pattern = create_search_pattern(search)
        query["$or"] = [
            {"name": {"$regex": pattern, "$options": "i"}},
            {"address": {"$regex": pattern, "$options": "i"}}
        ]
    
    sort_options = [("created_at", -1)]
    if sort_by == "rating":
        sort_options = [("rating", -1)]
    
    pulperias = await db.pulperias.find(query, {"_id": 0}).sort(sort_options).to_list(100)
    return pulperias

@api_router.get("/pulperias/{pulperia_id}")
async def get_pulperia(pulperia_id: str):
    """Get single pulperia by ID"""
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    return pulperia

@api_router.post("/pulperias")
async def create_pulperia(pulperia_data: PulperiaCreate, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Create a new pulperia"""
    user = await get_current_user(authorization, session_token)
    
    if user.user_type != "pulperia":
        raise HTTPException(status_code=403, detail="Solo usuarios tipo pulpería pueden crear pulperías")
    
    pulperia_id = f"pulperia_{uuid.uuid4().hex[:12]}"
    pulperia_doc = {
        "pulperia_id": pulperia_id,
        "owner_user_id": user.user_id,
        **pulperia_data.model_dump(),
        "rating": 0.0,
        "review_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.pulperias.insert_one(pulperia_doc)
    return await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})

@api_router.put("/pulperias/{pulperia_id}")
async def update_pulperia(pulperia_id: str, pulperia_data: PulperiaCreate, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Update pulperia"""
    user = await get_current_user(authorization, session_token)
    
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    if pulperia["owner_user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="No tienes permiso para editar esta pulpería")
    
    # Get all data including None values to properly update
    update_data = pulperia_data.model_dump(exclude_unset=False)
    
    # Log for debugging
    logger.info(f"[PULPERIA UPDATE] Updating {pulperia_id} with banner_url: {update_data.get('banner_url', 'NOT SET')}")
    
    await db.pulperias.update_one(
        {"pulperia_id": pulperia_id},
        {"$set": update_data}
    )
    
    return await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})

@api_router.delete("/admin/pulperias/{pulperia_id}")
async def admin_delete_pulperia(pulperia_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Delete a pulperia and all related data"""
    await get_admin_user(authorization, session_token)
    
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    # Delete all related data
    await db.products.delete_many({"pulperia_id": pulperia_id})
    await db.orders.delete_many({"pulperia_id": pulperia_id})
    await db.reviews.delete_many({"pulperia_id": pulperia_id})
    await db.achievements.delete_many({"pulperia_id": pulperia_id})
    await db.announcements.delete_many({"pulperia_id": pulperia_id})
    await db.jobs.delete_many({"pulperia_id": pulperia_id})
    await db.featured_ads.delete_many({"pulperia_id": pulperia_id})
    await db.featured_ad_slots.delete_many({"pulperia_id": pulperia_id})
    await db.pulperias.delete_one({"pulperia_id": pulperia_id})
    
    return {"message": f"Pulpería '{pulperia.get('name', pulperia_id)}' eliminada"}

class ClosePulperiaRequest(BaseModel):
    confirmation_phrase: str  # Debe ser el nombre exacto de la pulpería

@api_router.delete("/pulperias/{pulperia_id}/close")
async def close_own_pulperia(pulperia_id: str, close_request: ClosePulperiaRequest, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Owner: Close/delete their own pulperia with confirmation"""
    user = await get_current_user(authorization, session_token)
    
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    # Solo el dueño puede cerrar su tienda
    if pulperia["owner_user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="Solo el dueño puede cerrar esta pulpería")
    
    # Verificar que la frase de confirmación sea correcta (nombre de la pulpería)
    if close_request.confirmation_phrase.strip().lower() != pulperia["name"].strip().lower():
        raise HTTPException(status_code=400, detail=f"La frase de confirmación no coincide. Escribe '{pulperia['name']}' para confirmar.")
    
    pulperia_name = pulperia.get('name', pulperia_id)
    
    # Eliminar todos los datos relacionados
    await db.products.delete_many({"pulperia_id": pulperia_id})
    await db.orders.delete_many({"pulperia_id": pulperia_id})
    await db.reviews.delete_many({"pulperia_id": pulperia_id})
    await db.achievements.delete_many({"pulperia_id": pulperia_id})
    await db.announcements.delete_many({"pulperia_id": pulperia_id})
    await db.jobs.delete_many({"pulperia_id": pulperia_id})
    await db.featured_ads.delete_many({"pulperia_id": pulperia_id})
    await db.featured_ad_slots.delete_many({"pulperia_id": pulperia_id})
    await db.pulperias.delete_one({"pulperia_id": pulperia_id})
    
    # NO cambiar tipo de usuario - mantener como "pulperia" para que pueda crear otra
    # El usuario sigue siendo tipo pulpería y puede crear una nueva tienda
    
    logger.info(f"[CLOSE STORE] User {user.user_id} closed pulperia '{pulperia_name}'")
    
    return {
        "message": f"Tu pulpería '{pulperia_name}' ha sido cerrada. Puedes crear una nueva cuando quieras.",
        "redirect_to": "/dashboard",
        "can_create_new": True
    }

@api_router.get("/pulperias/{pulperia_id}/products")
async def get_pulperia_products(pulperia_id: str):
    """Get all products for a pulperia"""
    products = await db.products.find({"pulperia_id": pulperia_id}, {"_id": 0}).to_list(100)
    return products

@api_router.get("/pulperias/{pulperia_id}/reviews")
async def get_pulperia_reviews(pulperia_id: str):
    """Get all reviews for a pulperia"""
    reviews = await db.reviews.find({"pulperia_id": pulperia_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return reviews

@api_router.post("/pulperias/{pulperia_id}/reviews")
async def create_review(pulperia_id: str, review_data: ReviewCreate, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Create a review for a pulperia"""
    user = await get_current_user(authorization, session_token)
    
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    existing_review = await db.reviews.find_one({"pulperia_id": pulperia_id, "user_id": user.user_id}, {"_id": 0})
    if existing_review:
        raise HTTPException(status_code=400, detail="Ya has dejado una review para esta pulpería")
    
    if review_data.rating < 1 or review_data.rating > 5:
        raise HTTPException(status_code=400, detail="Rating debe estar entre 1 y 5")
    
    images = review_data.images[:2] if review_data.images else []
    
    review_id = f"review_{uuid.uuid4().hex[:12]}"
    review_doc = {
        "review_id": review_id,
        "pulperia_id": pulperia_id,
        "user_id": user.user_id,
        "user_name": user.name,
        "rating": review_data.rating,
        "comment": review_data.comment,
        "images": images,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.reviews.insert_one(review_doc)
    
    all_reviews = await db.reviews.find({"pulperia_id": pulperia_id}, {"_id": 0}).to_list(1000)
    avg_rating = sum(r["rating"] for r in all_reviews) / len(all_reviews)
    
    await db.pulperias.update_one(
        {"pulperia_id": pulperia_id},
        {"$set": {"rating": round(avg_rating, 1), "review_count": len(all_reviews)}}
    )
    
    return await db.reviews.find_one({"review_id": review_id}, {"_id": 0})

@api_router.get("/pulperias/{pulperia_id}/announcements")
async def get_pulperia_announcements(pulperia_id: str):
    """Get all announcements for a pulperia"""
    announcements = await db.announcements.find({"pulperia_id": pulperia_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return announcements

class AnnouncementCreate(BaseModel):
    content: str = ""
    image_url: Optional[str] = None
    tags: Optional[List[str]] = None

@api_router.post("/pulperias/{pulperia_id}/announcements")
async def create_announcement(pulperia_id: str, data: AnnouncementCreate, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Create an announcement for a pulperia"""
    user = await get_current_user(authorization, session_token)
    
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    if pulperia["owner_user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="Solo el dueño puede crear anuncios")
    
    announcement_id = f"ann_{uuid.uuid4().hex[:12]}"
    announcement_doc = {
        "announcement_id": announcement_id,
        "pulperia_id": pulperia_id,
        "content": data.content,
        "image_url": data.image_url,
        "tags": data.tags or [],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.announcements.insert_one(announcement_doc)
    return await db.announcements.find_one({"announcement_id": announcement_id}, {"_id": 0})

@api_router.delete("/announcements/{announcement_id}")
async def delete_announcement(announcement_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Delete an announcement"""
    user = await get_current_user(authorization, session_token)
    
    announcement = await db.announcements.find_one({"announcement_id": announcement_id}, {"_id": 0})
    if not announcement:
        raise HTTPException(status_code=404, detail="Anuncio no encontrado")
    
    pulperia = await db.pulperias.find_one({"pulperia_id": announcement["pulperia_id"]}, {"_id": 0})
    if pulperia["owner_user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="Solo el dueño puede eliminar anuncios")
    
    await db.announcements.delete_one({"announcement_id": announcement_id})
    return {"message": "Anuncio eliminado"}

@api_router.get("/pulperias/{pulperia_id}/jobs")
async def get_pulperia_jobs(pulperia_id: str):
    """Get all jobs for a pulperia"""
    jobs = await db.jobs.find({"pulperia_id": pulperia_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return jobs

# ============================================
# PRODUCT ENDPOINTS
# ============================================

@api_router.get("/products")
async def search_products(search: Optional[str] = None, category: Optional[str] = None, sort_by: Optional[str] = None):
    """Search products across all pulperias with fuzzy matching"""
    
    if search:
        products = await fuzzy_search_products(search)
    else:
        query = {"available": True}
        if category:
            query["category"] = category
        products = await db.products.find(query, {"_id": 0}).to_list(100)
    
    # Sort results
    if sort_by == "price_asc":
        products.sort(key=lambda x: x.get("price", 0))
    elif sort_by == "price_desc":
        products.sort(key=lambda x: x.get("price", 0), reverse=True)
    
    # Enrich with pulperia info
    pulperia_ids = list(set(p["pulperia_id"] for p in products))
    if pulperia_ids:
        pulperias_list = await db.pulperias.find(
            {"pulperia_id": {"$in": pulperia_ids}},
            {"_id": 0, "pulperia_id": 1, "name": 1, "logo_url": 1}
        ).to_list(len(pulperia_ids))
        pulperias_dict = {p["pulperia_id"]: p for p in pulperias_list}
        
        for product in products:
            pulperia = pulperias_dict.get(product["pulperia_id"])
            if pulperia:
                product["pulperia_name"] = pulperia["name"]
                product["pulperia_logo"] = pulperia.get("logo_url")
    
    return products

@api_router.get("/products/{product_id}")
async def get_product(product_id: str):
    """Get single product by ID"""
    product = await db.products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product

@api_router.post("/products")
async def create_product(product_data: ProductCreate, pulperia_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Create a new product"""
    user = await get_current_user(authorization, session_token)
    
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    if pulperia["owner_user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="No tienes permiso para agregar productos a esta pulpería")
    
    product_id = f"product_{uuid.uuid4().hex[:12]}"
    product_doc = {
        "product_id": product_id,
        "pulperia_id": pulperia_id,
        **product_data.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.products.insert_one(product_doc)
    return await db.products.find_one({"product_id": product_id}, {"_id": 0})

@api_router.put("/products/{product_id}")
async def update_product(product_id: str, product_data: ProductCreate, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Update product"""
    user = await get_current_user(authorization, session_token)
    
    product = await db.products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    pulperia = await db.pulperias.find_one({"pulperia_id": product["pulperia_id"]}, {"_id": 0})
    if pulperia["owner_user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="No tienes permiso para editar este producto")
    
    # Track price changes
    old_price = product.get("price", 0)
    new_price = product_data.price
    
    if old_price != new_price:
        # Save price history
        price_history_doc = {
            "product_id": product_id,
            "old_price": old_price,
            "new_price": new_price,
            "changed_at": datetime.now(timezone.utc),
            "changed_by": user.user_id
        }
        await db.price_history.insert_one(price_history_doc)
    
    await db.products.update_one(
        {"product_id": product_id},
        {"$set": product_data.model_dump()}
    )
    
    return await db.products.find_one({"product_id": product_id}, {"_id": 0})

@api_router.delete("/products/{product_id}")
async def delete_product(product_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Delete product"""
    user = await get_current_user(authorization, session_token)
    
    product = await db.products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    pulperia = await db.pulperias.find_one({"pulperia_id": product["pulperia_id"]}, {"_id": 0})
    if pulperia["owner_user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar este producto")
    
    await db.products.delete_one({"product_id": product_id})
    return {"message": "Producto eliminado exitosamente"}

@api_router.put("/products/{product_id}/availability")
async def toggle_product_availability(product_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Toggle product availability"""
    user = await get_current_user(authorization, session_token)
    
    product = await db.products.find_one({"product_id": product_id}, {"_id": 0})
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    pulperia = await db.pulperias.find_one({"pulperia_id": product["pulperia_id"]}, {"_id": 0})
    if pulperia["owner_user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="No tienes permiso para editar este producto")
    
    new_available = not product.get("available", True)
    
    await db.products.update_one(
        {"product_id": product_id},
        {"$set": {"available": new_available}}
    )
    
    return await db.products.find_one({"product_id": product_id}, {"_id": 0})

# ============================================
# ACHIEVEMENT SYSTEM ENDPOINTS
# ============================================

async def calculate_pulperia_stats(pulperia_id: str) -> dict:
    """Calculate statistics for a pulperia to determine achievements"""
    # Contar productos
    products_count = await db.products.count_documents({"pulperia_id": pulperia_id})
    
    # Contar ventas completadas
    sales_count = await db.orders.count_documents({
        "pulperia_id": pulperia_id,
        "status": "completed"
    })
    
    # Contar clientes felices (reviews con rating >= 4)
    happy_customers = await db.reviews.count_documents({
        "pulperia_id": pulperia_id,
        "rating": {"$gte": 4}
    })
    
    # Obtener visitas al perfil (si existe el contador)
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})
    profile_views = pulperia.get("profile_views", 0) if pulperia else 0
    
    # Verificar si está verificado
    is_verified = pulperia.get("is_verified", False) if pulperia else False
    
    return {
        "pulperia_id": pulperia_id,
        "products_count": products_count,
        "sales_count": sales_count,
        "happy_customers": happy_customers,
        "profile_views": profile_views,
        "is_verified": is_verified,
        "avg_response_time": 999,  # Placeholder
        "growth_rate": 0,  # Placeholder
        "community_score": 0,  # Placeholder
        "top_rank": 999  # Placeholder
    }

async def check_and_award_achievements(pulperia_id: str) -> list:
    """Check stats and award any new achievements"""
    stats = await calculate_pulperia_stats(pulperia_id)
    
    # Obtener logros ya desbloqueados
    existing_achievements = await db.achievements.find(
        {"pulperia_id": pulperia_id},
        {"_id": 0, "badge_id": 1}
    ).to_list(100)
    existing_badges = {a["badge_id"] for a in existing_achievements}
    
    new_achievements = []
    
    # Verificar cada logro
    for badge_id, definition in ACHIEVEMENT_DEFINITIONS.items():
        if badge_id in existing_badges:
            continue
        
        criteria = definition.get("criteria", {})
        unlocked = True
        
        for key, value in criteria.items():
            stat_value = stats.get(key, 0)
            
            if key == "is_verified":
                if stat_value != value:
                    unlocked = False
                    break
            elif key in ["avg_response_time", "top_rank"]:
                # Menor es mejor (top_rank 1 es mejor que 10)
                if stat_value > value:
                    unlocked = False
                    break
            else:
                # Mayor es mejor
                if stat_value < value:
                    unlocked = False
                    break
        
        if unlocked:
            achievement_id = f"achievement_{uuid.uuid4().hex[:12]}"
            achievement_doc = {
                "achievement_id": achievement_id,
                "pulperia_id": pulperia_id,
                "badge_id": badge_id,
                "unlocked_at": datetime.now(timezone.utc).isoformat()
            }
            await db.achievements.insert_one(achievement_doc)
            new_achievements.append({
                "badge_id": badge_id,
                "name": definition["name"],
                "description": definition["description"],
                "tier": definition.get("tier", "gold"),
                "unlocked_at": achievement_doc["unlocked_at"]
            })
    
    return new_achievements

@api_router.get("/achievements/definitions")
async def get_achievement_definitions():
    """Get all available achievement definitions"""
    return ACHIEVEMENT_DEFINITIONS

@api_router.get("/pulperias/{pulperia_id}/achievements")
async def get_pulperia_achievements(pulperia_id: str):
    """Get all achievements for a pulperia"""
    achievements = await db.achievements.find(
        {"pulperia_id": pulperia_id},
        {"_id": 0}
    ).to_list(100)
    
    # Enrich with definition data
    result = []
    for ach in achievements:
        badge_id = ach.get("badge_id")
        definition = ACHIEVEMENT_DEFINITIONS.get(badge_id, {})
        result.append({
            **ach,
            "name": definition.get("name", badge_id),
            "description": definition.get("description", ""),
            "icon": definition.get("icon", "Star"),
            "tier": definition.get("tier", "gold")
        })
    
    return result

@api_router.get("/pulperias/{pulperia_id}/stats")
async def get_pulperia_stats(pulperia_id: str, auto_check: bool = True):
    """Get statistics for a pulperia and optionally check achievements"""
    stats = await calculate_pulperia_stats(pulperia_id)
    
    # Auto-check achievements when stats are fetched
    if auto_check:
        await check_and_award_achievements(pulperia_id)
    
    return stats

@api_router.post("/pulperias/{pulperia_id}/check-achievements")
async def check_achievements(pulperia_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Check and award new achievements for a pulperia"""
    user = await get_current_user(authorization, session_token)
    
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    # Solo el dueño puede verificar logros
    if pulperia["owner_user_id"] != user.user_id and user.email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="No tienes permiso")
    
    new_achievements = await check_and_award_achievements(pulperia_id)
    
    return {
        "new_achievements": new_achievements,
        "message": f"Se desbloquearon {len(new_achievements)} nuevos logros" if new_achievements else "No hay nuevos logros disponibles"
    }

@api_router.post("/pulperias/{pulperia_id}/increment-views")
async def increment_profile_views(pulperia_id: str):
    """Increment the profile view counter for a pulperia"""
    result = await db.pulperias.update_one(
        {"pulperia_id": pulperia_id},
        {"$inc": {"profile_views": 1}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    return {"message": "Vista registrada"}

@api_router.post("/admin/pulperias/{pulperia_id}/verify")
async def verify_pulperia(pulperia_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Verify a pulperia (unlocks 'verificado' achievement)"""
    await get_admin_user(authorization, session_token)
    
    result = await db.pulperias.update_one(
        {"pulperia_id": pulperia_id},
        {"$set": {"is_verified": True}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    # Check achievements after verification
    new_achievements = await check_and_award_achievements(pulperia_id)
    
    return {
        "message": "Pulpería verificada",
        "new_achievements": new_achievements
    }

@api_router.post("/admin/pulperias/{pulperia_id}/award-badge")
async def admin_award_badge(pulperia_id: str, badge_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Manually award a badge to a pulperia"""
    user = await get_admin_user(authorization, session_token)
    
    if badge_id not in ACHIEVEMENT_DEFINITIONS:
        raise HTTPException(status_code=400, detail="Badge inválido")
    
    # Check if already has badge
    existing = await db.achievements.find_one({
        "pulperia_id": pulperia_id,
        "badge_id": badge_id
    })
    
    if existing:
        raise HTTPException(status_code=400, detail="La pulpería ya tiene este logro")
    
    achievement_id = f"achievement_{uuid.uuid4().hex[:12]}"
    achievement_doc = {
        "achievement_id": achievement_id,
        "pulperia_id": pulperia_id,
        "badge_id": badge_id,
        "awarded_by": user.user_id,
        "unlocked_at": datetime.now(timezone.utc).isoformat()
    }
    await db.achievements.insert_one(achievement_doc)
    
    definition = ACHIEVEMENT_DEFINITIONS[badge_id]
    return {
        "message": f"Logro '{definition['name']}' otorgado exitosamente",
        "achievement": {
            **achievement_doc,
            "name": definition["name"],
            "description": definition["description"]
        }
    }

# ============================================
# FEATURED ADS SYSTEM - Anuncios Destacados (1000 Lps/mes)
# ============================================

@api_router.get("/featured-ads")
async def get_featured_ads():
    """Get all active featured ads - visible to everyone"""
    now = datetime.now(timezone.utc)
    
    # Get active ads that haven't expired
    ads = await db.featured_ads.find({
        "is_active": True,
        "expires_at": {"$gt": now.isoformat()}
    }, {"_id": 0}).to_list(50)
    
    return ads

@api_router.get("/featured-ads/my-slot")
async def get_my_ad_slot(authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Get current user's pulperia ad slot status"""
    user = await get_current_user(authorization, session_token)
    
    # Find user's pulperias
    pulperias = await db.pulperias.find({"owner_user_id": user.user_id}, {"_id": 0}).to_list(10)
    
    if not pulperias:
        return {"has_slot": False, "message": "No tienes pulperías registradas"}
    
    pulperia_ids = [p["pulperia_id"] for p in pulperias]
    
    # Check for active slot
    now = datetime.now(timezone.utc)
    slot = await db.featured_ad_slots.find_one({
        "pulperia_id": {"$in": pulperia_ids},
        "expires_at": {"$gt": now.isoformat()}
    }, {"_id": 0})
    
    if not slot:
        return {"has_slot": False, "message": "No tienes un slot habilitado. Contacta al admin."}
    
    # Get the ad if exists
    ad = None
    if slot.get("ad_id"):
        ad = await db.featured_ads.find_one({"ad_id": slot["ad_id"]}, {"_id": 0})
    
    return {
        "has_slot": True,
        "slot": slot,
        "ad": ad,
        "can_upload": not slot.get("is_used", False)
    }

@api_router.post("/featured-ads/upload")
async def upload_featured_ad(
    title: Optional[str] = None,
    description: Optional[str] = None,
    image_url: Optional[str] = None,
    video_url: Optional[str] = None,
    link_url: Optional[str] = None,
    authorization: Optional[str] = Header(None), 
    session_token: Optional[str] = Cookie(None)
):
    """Upload a featured ad (requires enabled slot)"""
    user = await get_current_user(authorization, session_token)
    
    # Find user's pulperia with active slot
    pulperias = await db.pulperias.find({"owner_user_id": user.user_id}, {"_id": 0}).to_list(10)
    
    if not pulperias:
        raise HTTPException(status_code=400, detail="No tienes pulperías registradas")
    
    pulperia_ids = [p["pulperia_id"] for p in pulperias]
    
    now = datetime.now(timezone.utc)
    slot = await db.featured_ad_slots.find_one({
        "pulperia_id": {"$in": pulperia_ids},
        "is_used": False,
        "expires_at": {"$gt": now.isoformat()}
    })
    
    if not slot:
        raise HTTPException(status_code=403, detail="No tienes un slot disponible. Contacta al admin para habilitarlo (1000 Lps/mes).")
    
    if not image_url and not video_url:
        raise HTTPException(status_code=400, detail="Debes subir al menos una imagen o video")
    
    # Get pulperia info
    pulperia = await db.pulperias.find_one({"pulperia_id": slot["pulperia_id"]}, {"_id": 0})
    
    # Create the ad
    ad_id = f"featured_ad_{uuid.uuid4().hex[:12]}"
    expires_at = now + timedelta(days=30)
    
    ad_doc = {
        "ad_id": ad_id,
        "pulperia_id": slot["pulperia_id"],
        "pulperia_name": pulperia["name"] if pulperia else "Pulpería",
        "title": title,
        "description": description,
        "image_url": image_url,
        "video_url": video_url,
        "link_url": link_url or f"/p/{slot['pulperia_id']}",
        "is_active": True,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat()
    }
    
    await db.featured_ads.insert_one(ad_doc)
    
    # Mark slot as used
    await db.featured_ad_slots.update_one(
        {"slot_id": slot["slot_id"]},
        {"$set": {"is_used": True, "ad_id": ad_id}}
    )
    
    return {
        "message": "¡Anuncio destacado creado exitosamente!",
        "ad": {k: v for k, v in ad_doc.items() if k != "_id"},
        "expires_at": expires_at.isoformat()
    }

@api_router.delete("/featured-ads/{ad_id}")
async def delete_my_featured_ad(ad_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Delete own featured ad"""
    user = await get_current_user(authorization, session_token)
    
    # Find user's pulperias
    pulperias = await db.pulperias.find({"owner_user_id": user.user_id}, {"_id": 0}).to_list(10)
    pulperia_ids = [p["pulperia_id"] for p in pulperias]
    
    ad = await db.featured_ads.find_one({"ad_id": ad_id})
    
    if not ad:
        raise HTTPException(status_code=404, detail="Anuncio no encontrado")
    
    if ad["pulperia_id"] not in pulperia_ids:
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar este anuncio")
    
    await db.featured_ads.delete_one({"ad_id": ad_id})
    
    return {"message": "Anuncio eliminado"}

# Admin endpoints for managing featured ad slots
@api_router.post("/admin/featured-ads/enable-slot")
async def admin_enable_ad_slot(
    pulperia_id: str,
    days: int = 30,
    authorization: Optional[str] = Header(None), 
    session_token: Optional[str] = Cookie(None)
):
    """Admin: Enable a featured ad slot for a pulperia (after payment)"""
    admin = await get_admin_user(authorization, session_token)
    
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=days)
    
    # Check if already has active slot
    existing_slot = await db.featured_ad_slots.find_one({
        "pulperia_id": pulperia_id,
        "expires_at": {"$gt": now.isoformat()}
    })
    
    if existing_slot:
        raise HTTPException(status_code=400, detail="Esta pulpería ya tiene un slot activo")
    
    slot_id = f"slot_{uuid.uuid4().hex[:12]}"
    slot_doc = {
        "slot_id": slot_id,
        "pulperia_id": pulperia_id,
        "pulperia_name": pulperia["name"],
        "enabled_by": admin.user_id,
        "enabled_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "is_used": False,
        "ad_id": None
    }
    
    await db.featured_ad_slots.insert_one(slot_doc)
    
    # Create notification for pulperia owner
    notification_doc = {
        "notification_id": f"notif_{uuid.uuid4().hex[:12]}",
        "user_id": pulperia["owner_user_id"],
        "type": "ad_slot_enabled",
        "title": "¡Slot de Anuncio Habilitado!",
        "message": f"Tu slot de anuncio destacado para '{pulperia['name']}' ha sido activado. Tienes {days} días para subir tu anuncio.",
        "read": False,
        "created_at": now.isoformat()
    }
    await db.notifications.insert_one(notification_doc)
    
    return {
        "message": f"Slot habilitado para '{pulperia['name']}' por {days} días",
        "slot": {k: v for k, v in slot_doc.items() if k != "_id"},
        "expires_at": expires_at.isoformat()
    }

@api_router.get("/admin/featured-ads/slots")
async def admin_get_all_slots(authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Get all featured ad slots"""
    await get_admin_user(authorization, session_token)
    
    slots = await db.featured_ad_slots.find({}, {"_id": 0}).sort("enabled_at", -1).to_list(100)
    return slots

@api_router.delete("/admin/featured-ads/slot/{slot_id}")
async def admin_delete_slot(slot_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Delete/revoke a featured ad slot"""
    await get_admin_user(authorization, session_token)
    
    slot = await db.featured_ad_slots.find_one({"slot_id": slot_id})
    if not slot:
        raise HTTPException(status_code=404, detail="Slot no encontrado")
    
    # Also delete the ad if exists
    if slot.get("ad_id"):
        await db.featured_ads.delete_one({"ad_id": slot["ad_id"]})
    
    await db.featured_ad_slots.delete_one({"slot_id": slot_id})
    
    return {"message": "Slot y anuncio eliminados"}

@api_router.delete("/admin/featured-ads/{ad_id}")
async def admin_delete_ad(ad_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Delete any featured ad"""
    await get_admin_user(authorization, session_token)
    
    result = await db.featured_ads.delete_one({"ad_id": ad_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Anuncio no encontrado")
    
    # Also update the slot
    await db.featured_ad_slots.update_one(
        {"ad_id": ad_id},
        {"$set": {"is_used": False, "ad_id": None}}
    )
    
    return {"message": "Anuncio eliminado"}

# ============================================
# FAVORITES ENDPOINTS
# ============================================

@api_router.get("/favorites")
async def get_favorites(authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Get user's favorite pulperias"""
    user = await get_current_user(authorization, session_token)
    
    favorites = await db.favorites.find({"user_id": user.user_id}, {"_id": 0}).to_list(100)
    pulperia_ids = [f["pulperia_id"] for f in favorites]
    
    if not pulperia_ids:
        return []
    
    pulperias = await db.pulperias.find({"pulperia_id": {"$in": pulperia_ids}}, {"_id": 0}).to_list(100)
    return pulperias

@api_router.post("/favorites/{pulperia_id}")
async def add_favorite(pulperia_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Add a pulperia to favorites"""
    user = await get_current_user(authorization, session_token)
    
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    existing = await db.favorites.find_one({"user_id": user.user_id, "pulperia_id": pulperia_id})
    if existing:
        return {"message": "Ya está en favoritos", "is_favorite": True}
    
    await db.favorites.insert_one({
        "user_id": user.user_id,
        "pulperia_id": pulperia_id,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {"message": "Agregado a favoritos", "is_favorite": True}

@api_router.delete("/favorites/{pulperia_id}")
async def remove_favorite(pulperia_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Remove a pulperia from favorites"""
    user = await get_current_user(authorization, session_token)
    
    await db.favorites.delete_one({"user_id": user.user_id, "pulperia_id": pulperia_id})
    return {"message": "Eliminado de favoritos", "is_favorite": False}

@api_router.get("/favorites/{pulperia_id}/check")
async def check_favorite(pulperia_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Check if a pulperia is in favorites"""
    user = await get_current_user(authorization, session_token)
    
    existing = await db.favorites.find_one({"user_id": user.user_id, "pulperia_id": pulperia_id})
    return {"is_favorite": existing is not None}

# ORDER ENDPOINTS
# ============================================

@api_router.get("/orders")
async def get_orders(authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Get orders for current user"""
    user = await get_current_user(authorization, session_token)
    
    if user.user_type == "cliente":
        orders = await db.orders.find({"customer_user_id": user.user_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    else:
        user_pulperias = await db.pulperias.find({"owner_user_id": user.user_id}, {"_id": 0}).to_list(100)
        pulperia_ids = [p["pulperia_id"] for p in user_pulperias]
        orders = await db.orders.find({"pulperia_id": {"$in": pulperia_ids}}, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    return orders

@api_router.post("/orders")
async def create_order(order_data: OrderCreate, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Create a new order"""
    user = await get_current_user(authorization, session_token)
    
    order_id = f"order_{uuid.uuid4().hex[:12]}"
    order_doc = {
        "order_id": order_id,
        "customer_user_id": user.user_id,
        "customer_name": order_data.customer_name,  # Name for the order
        "pulperia_id": order_data.pulperia_id,
        "items": [item.model_dump() for item in order_data.items],
        "total": order_data.total,
        "order_type": order_data.order_type,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.orders.insert_one(order_doc)
    
    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    await broadcast_order_update(order, "new_order")
    
    # Send email notification to pulperia owner
    try:
        pulperia = await db.pulperias.find_one({"pulperia_id": order_data.pulperia_id}, {"_id": 0})
        if pulperia:
            owner = await db.users.find_one({"user_id": pulperia.get("owner_user_id")}, {"_id": 0})
            if owner and owner.get("email"):
                await send_order_notification(
                    owner_email=owner["email"],
                    pulperia_name=pulperia.get("name", "Tu Pulpería"),
                    customer_name=order_data.customer_name,
                    total=order_data.total
                )
                logger.info(f"[EMAIL] Order notification sent to {owner['email']}")
    except Exception as e:
        logger.error(f"[EMAIL] Failed to send order notification: {e}")
    
    return order

@api_router.put("/orders/{order_id}/status")
async def update_order_status(order_id: str, status_update: OrderStatusUpdate, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Update order status"""
    user = await get_current_user(authorization, session_token)
    
    order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    
    pulperia = await db.pulperias.find_one({"pulperia_id": order["pulperia_id"]}, {"_id": 0})
    if pulperia["owner_user_id"] != user.user_id and order["customer_user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="No tienes permiso para actualizar esta orden")
    
    await db.orders.update_one(
        {"order_id": order_id},
        {"$set": {"status": status_update.status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    updated_order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
    event_type = "cancelled" if status_update.status == "cancelled" else "status_changed"
    await broadcast_order_update(updated_order, event_type)
    
    # Send email notification to customer based on status
    try:
        customer = await db.users.find_one({"user_id": order["customer_user_id"]}, {"_id": 0})
        if customer and customer.get("email"):
            if status_update.status == "accepted":
                await send_order_accepted(
                    customer_email=customer["email"],
                    pulperia_name=pulperia.get("name", "La Pulpería")
                )
                logger.info(f"[EMAIL] Order accepted notification sent to {customer['email']}")
            elif status_update.status == "ready":
                await send_order_ready(
                    customer_email=customer["email"],
                    pulperia_name=pulperia.get("name", "La Pulpería"),
                    address=pulperia.get("address", "")
                )
                logger.info(f"[EMAIL] Order ready notification sent to {customer['email']}")
    except Exception as e:
        logger.error(f"[EMAIL] Failed to send order status notification: {e}")
    
    return updated_order

@api_router.get("/orders/completed")
async def get_completed_orders(authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Get completed orders"""
    user = await get_current_user(authorization, session_token)
    
    if user.user_type == "pulperia":
        user_pulperias = await db.pulperias.find({"owner_user_id": user.user_id}, {"_id": 0}).to_list(100)
        pulperia_ids = [p["pulperia_id"] for p in user_pulperias]
        orders = await db.orders.find(
            {"pulperia_id": {"$in": pulperia_ids}, "status": "completed"},
            {"_id": 0}
        ).sort("created_at", -1).to_list(1000)
    else:
        orders = await db.orders.find(
            {"customer_user_id": user.user_id, "status": "completed"},
            {"_id": 0}
        ).sort("created_at", -1).to_list(1000)
    
    return orders

@api_router.get("/orders/stats")
async def get_order_stats(period: str = "day", authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Get order statistics for pulperia owners"""
    user = await get_current_user(authorization, session_token)
    
    if user.user_type != "pulperia":
        raise HTTPException(status_code=403, detail="Solo pulperías pueden ver estadísticas")
    
    user_pulperias = await db.pulperias.find({"owner_user_id": user.user_id}, {"_id": 0}).to_list(100)
    pulperia_ids = [p["pulperia_id"] for p in user_pulperias]
    
    now = datetime.now(timezone.utc)
    if period == "day":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_date = now - timedelta(days=7)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    orders = await db.orders.find(
        {
            "pulperia_id": {"$in": pulperia_ids},
            "status": "completed",
            "created_at": {"$gte": start_date.isoformat()}
        },
        {"_id": 0}
    ).to_list(10000)
    
    total_orders = len(orders)
    total_revenue = sum(order["total"] for order in orders)
    
    product_counts = {}
    for order in orders:
        for item in order.get("items", []):
            product_name = item.get("product_name", "Unknown")
            if product_name in product_counts:
                product_counts[product_name] += item.get("quantity", 1)
            else:
                product_counts[product_name] = item.get("quantity", 1)
    
    top_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    return {
        "period": period,
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "average_order": total_revenue / total_orders if total_orders > 0 else 0,
        "top_products": [{"name": name, "quantity": qty} for name, qty in top_products],
        "orders": orders
    }

@api_router.get("/notifications")
async def get_notifications(authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Get notifications for current user - shows recent orders with full details"""
    user = await get_current_user(authorization, session_token)
    
    # Get user's read notifications
    read_notifications = await db.read_notifications.find(
        {"user_id": user.user_id},
        {"_id": 0, "notification_id": 1}
    ).to_list(100)
    read_ids = set(n["notification_id"] for n in read_notifications)
    
    notifications = []
    
    if user.user_type == "cliente":
        # Clients see their own orders
        orders = await db.orders.find(
            {"customer_user_id": user.user_id},
            {"_id": 0}
        ).sort("created_at", -1).to_list(20)
        
        # Get pulperia names for orders
        pulperia_ids = list(set(o.get("pulperia_id") for o in orders if o.get("pulperia_id")))
        pulperias = await db.pulperias.find({"pulperia_id": {"$in": pulperia_ids}}, {"_id": 0, "pulperia_id": 1, "name": 1}).to_list(100)
        pulperia_map = {p["pulperia_id"]: p["name"] for p in pulperias}
        
        for order in orders:
            items = order.get("items", [])
            total_items = sum(item.get("quantity", 1) for item in items)
            pulperia_name = pulperia_map.get(order.get("pulperia_id"), "Pulpería")
            
            # Create item summary (e.g., "2x Pan, 1x Leche")
            item_summary = ", ".join([f"{item.get('quantity', 1)}x {item.get('product_name', 'Producto')}" for item in items[:3]])
            if len(items) > 3:
                item_summary += f" +{len(items) - 3} más"
            
            notification_id = order["order_id"]
            is_read = notification_id in read_ids
            
            notifications.append({
                "id": notification_id,
                "type": "order_status",
                "title": f"Orden en {pulperia_name}",
                "message": item_summary or "Sin productos",
                "status": order.get("status", "pending"),
                "created_at": order.get("created_at"),
                "order_id": order["order_id"],
                "items": items,
                "total": order.get("total", 0),
                "total_items": total_items,
                "pulperia_name": pulperia_name,
                "role": "customer",
                "read": is_read
            })
    else:
        # Pulperia owners see orders received
        user_pulperias = await db.pulperias.find({"owner_user_id": user.user_id}, {"_id": 0}).to_list(100)
        pulperia_ids = [p["pulperia_id"] for p in user_pulperias]
        pulperia_map = {p["pulperia_id"]: p["name"] for p in user_pulperias}
        
        orders = await db.orders.find(
            {"pulperia_id": {"$in": pulperia_ids}},
            {"_id": 0}
        ).sort("created_at", -1).to_list(20)
        
        for order in orders:
            customer_name = order.get("customer_name", "Cliente")
            items = order.get("items", [])
            total_items = sum(item.get("quantity", 1) for item in items)
            pulperia_name = pulperia_map.get(order.get("pulperia_id"), "Tu Pulpería")
            
            # Create item summary
            item_summary = ", ".join([f"{item.get('quantity', 1)}x {item.get('product_name', 'Producto')}" for item in items[:3]])
            if len(items) > 3:
                item_summary += f" +{len(items) - 3} más"
            
            notification_id = order["order_id"]
            is_read = notification_id in read_ids
            
            notifications.append({
                "id": notification_id,
                "type": "new_order" if order.get("status") == "pending" else "order_update",
                "title": f"Pedido de {customer_name}",
                "message": item_summary or "Sin productos",
                "status": order.get("status", "pending"),
                "created_at": order.get("created_at"),
                "order_id": order["order_id"],
                "customer_name": customer_name,
                "items": items,
                "total": order.get("total", 0),
                "total_items": total_items,
                "pulperia_name": pulperia_name,
                "role": "owner",
                "read": is_read
            })
    
    return notifications


@api_router.post("/notifications/mark-read")
async def mark_notifications_read(notification_ids: List[str], authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Mark notifications as read"""
    user = await get_current_user(authorization, session_token)
    
    for nid in notification_ids:
        await db.read_notifications.update_one(
            {"user_id": user.user_id, "notification_id": nid},
            {"$set": {"user_id": user.user_id, "notification_id": nid, "read_at": datetime.now(timezone.utc)}},
            upsert=True
        )
    
    return {"success": True, "marked": len(notification_ids)}

# ============================================
# JOB ENDPOINTS
# ============================================

@api_router.get("/jobs")
async def get_jobs(category: Optional[str] = None, search: Optional[str] = None):
    """Get all jobs"""
    query = {}
    if category:
        query["category"] = category
    if search:
        pattern = create_search_pattern(search)
        query["$or"] = [
            {"title": {"$regex": pattern, "$options": "i"}},
            {"description": {"$regex": pattern, "$options": "i"}}
        ]
    
    jobs = await db.jobs.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return jobs

@api_router.post("/jobs")
async def create_job(job_data: JobCreate, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Create a new job posting"""
    user = await get_current_user(authorization, session_token)
    
    pulperia_name = None
    pulperia_logo = None
    if job_data.pulperia_id:
        pulperia = await db.pulperias.find_one({"pulperia_id": job_data.pulperia_id}, {"_id": 0})
        if pulperia and pulperia["owner_user_id"] == user.user_id:
            pulperia_name = pulperia["name"]
            pulperia_logo = pulperia.get("logo_url")
    
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job_doc = {
        "job_id": job_id,
        "employer_user_id": user.user_id,
        "employer_name": user.name,
        "pulperia_id": job_data.pulperia_id,
        "pulperia_name": pulperia_name,
        "pulperia_logo": pulperia_logo,
        **{k: v for k, v in job_data.model_dump().items() if k != 'pulperia_id'},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.jobs.insert_one(job_doc)
    return await db.jobs.find_one({"job_id": job_id}, {"_id": 0})

@api_router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Delete a job posting"""
    user = await get_current_user(authorization, session_token)
    
    job = await db.jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Empleo no encontrado")
    
    if job["employer_user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar este empleo")
    
    await db.jobs.delete_one({"job_id": job_id})
    await db.job_applications.delete_many({"job_id": job_id})
    return {"message": "Empleo eliminado"}

# ============================================
# JOB APPLICATIONS ENDPOINTS
# ============================================

class JobApplicationCreate(BaseModel):
    city: str
    age: int
    cv_url: Optional[str] = None
    message: Optional[str] = None

@api_router.post("/jobs/{job_id}/apply")
async def apply_to_job(job_id: str, application_data: JobApplicationCreate, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Apply to a job posting"""
    user = await get_current_user(authorization, session_token)
    
    # Validate age
    if application_data.age < 18:
        raise HTTPException(status_code=400, detail="Debes ser mayor de 18 años para aplicar")
    
    # Get job details
    job = await db.jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Empleo no encontrado")
    
    # Check if user is trying to apply to their own job
    if job["employer_user_id"] == user.user_id:
        raise HTTPException(status_code=400, detail="No puedes aplicar a tu propio empleo")
    
    # Check if already applied
    existing = await db.job_applications.find_one({
        "job_id": job_id,
        "applicant_user_id": user.user_id
    })
    if existing:
        raise HTTPException(status_code=400, detail="Ya has aplicado a este empleo")
    
    application_id = f"app_{uuid.uuid4().hex[:12]}"
    application_doc = {
        "application_id": application_id,
        "job_id": job_id,
        "job_title": job["title"],
        "pulperia_id": job.get("pulperia_id"),
        "pulperia_name": job.get("pulperia_name"),
        "employer_user_id": job["employer_user_id"],
        "applicant_user_id": user.user_id,
        "applicant_name": user.name,
        "applicant_email": user.email,
        "applicant_city": application_data.city,
        "applicant_age": application_data.age,
        "cv_url": application_data.cv_url,
        "message": application_data.message,
        "status": "recibida",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.job_applications.insert_one(application_doc)
    
    # Send notification to employer (WebSocket)
    try:
        await send_ws_notification(
            job["employer_user_id"],
            f"📋 Nueva aplicación de {user.name} para: {job['title']}",
            "job_application"
        )
    except Exception as e:
        logger.warning(f"WebSocket notification failed: {e}")
    
    # Send email notification to employer
    try:
        employer = await db.users.find_one({"user_id": job["employer_user_id"]}, {"_id": 0})
        if employer and employer.get("email"):
            await send_job_application_notification(
                owner_email=employer["email"],
                job_title=job["title"],
                applicant_name=user.name,
                applicant_city=application_data.city,
                applicant_age=application_data.age
            )
            logger.info(f"[EMAIL] Job application notification sent to {employer['email']}")
    except Exception as e:
        logger.error(f"[EMAIL] Failed to send job application notification: {e}")
    
    return await db.job_applications.find_one({"application_id": application_id}, {"_id": 0})

@api_router.get("/jobs/{job_id}/applications")
async def get_job_applications(job_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Get all applications for a job (employer only)"""
    user = await get_current_user(authorization, session_token)
    
    job = await db.jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Empleo no encontrado")
    
    if job["employer_user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="Solo el empleador puede ver las aplicaciones")
    
    applications = await db.job_applications.find(
        {"job_id": job_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return applications

@api_router.get("/my-job-applications")
async def get_my_applications(authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Get all job applications submitted by the current user"""
    user = await get_current_user(authorization, session_token)
    
    applications = await db.job_applications.find(
        {"applicant_user_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return applications

@api_router.get("/my-jobs")
async def get_my_jobs(authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Get all jobs posted by the current user"""
    user = await get_current_user(authorization, session_token)
    
    jobs = await db.jobs.find(
        {"employer_user_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    # Add application count to each job
    for job in jobs:
        count = await db.job_applications.count_documents({"job_id": job["job_id"]})
        job["application_count"] = count
        # Get pending applications count
        pending = await db.job_applications.count_documents({
            "job_id": job["job_id"],
            "status": "recibida"
        })
        job["pending_applications"] = pending
    
    return jobs

@api_router.put("/job-applications/{application_id}/status")
async def update_application_status(
    application_id: str, 
    status: str,
    rejection_reason: Optional[str] = None,
    authorization: Optional[str] = Header(None), 
    session_token: Optional[str] = Cookie(None)
):
    """Update job application status (employer only)"""
    user = await get_current_user(authorization, session_token)
    
    if status not in ["recibida", "en_revision", "aceptada", "rechazada"]:
        raise HTTPException(status_code=400, detail="Estado inválido")
    
    application = await db.job_applications.find_one({"application_id": application_id}, {"_id": 0})
    if not application:
        raise HTTPException(status_code=404, detail="Aplicación no encontrada")
    
    # Verify employer owns the job
    job = await db.jobs.find_one({"job_id": application["job_id"]}, {"_id": 0})
    if not job or job["employer_user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="No tienes permiso para actualizar esta aplicación")
    
    update_data = {
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    if status == "rechazada" and rejection_reason:
        update_data["rejection_reason"] = rejection_reason
    
    await db.job_applications.update_one(
        {"application_id": application_id},
        {"$set": update_data}
    )
    
    # Send notification to applicant
    if status == "aceptada":
        message = f"🎉 ¡Felicidades! Tu aplicación para '{application['job_title']}' fue ACEPTADA"
    elif status == "rechazada":
        message = f"📋 Tu aplicación para '{application['job_title']}' no fue seleccionada. ¡Te animamos a seguir aplicando!"
    else:
        message = f"📋 Tu aplicación para '{application['job_title']}' está en revisión"
    
    try:
        await send_ws_notification(application["applicant_user_id"], message, "application_status")
    except Exception as e:
        logger.warning(f"WebSocket notification failed: {e}")
    
    # Send email notification to applicant
    try:
        applicant = await db.users.find_one({"user_id": application["applicant_user_id"]}, {"_id": 0})
        if applicant and applicant.get("email"):
            pulperia_name = application.get("pulperia_name", "La Pulpería")
            if status == "aceptada":
                await send_application_accepted(
                    applicant_email=applicant["email"],
                    job_title=application["job_title"],
                    pulperia_name=pulperia_name
                )
                logger.info(f"[EMAIL] Application accepted notification sent to {applicant['email']}")
            elif status == "rechazada":
                await send_application_rejected(
                    applicant_email=applicant["email"],
                    job_title=application["job_title"],
                    pulperia_name=pulperia_name
                )
                logger.info(f"[EMAIL] Application rejected notification sent to {applicant['email']}")
    except Exception as e:
        logger.error(f"[EMAIL] Failed to send application status notification: {e}")
    
    return await db.job_applications.find_one({"application_id": application_id}, {"_id": 0})

@api_router.get("/pulperias/{pulperia_id}/job-applications")
async def get_pulperia_job_applications(pulperia_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Get all job applications for a pulperia's jobs"""
    user = await get_current_user(authorization, session_token)
    
    # Verify ownership
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})
    if not pulperia or pulperia["owner_user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="No tienes permiso")
    
    applications = await db.job_applications.find(
        {"pulperia_id": pulperia_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    
    return applications

# ============================================
# SERVICE ENDPOINTS
# ============================================

@api_router.get("/services")
async def get_services(category: Optional[str] = None, search: Optional[str] = None):
    """Get all services"""
    query = {}
    if category:
        query["category"] = category
    if search:
        pattern = create_search_pattern(search)
        query["$or"] = [
            {"title": {"$regex": pattern, "$options": "i"}},
            {"description": {"$regex": pattern, "$options": "i"}}
        ]
    
    services = await db.services.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return services

@api_router.post("/services")
async def create_service(service_data: ServiceCreate, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Create a new service"""
    user = await get_current_user(authorization, session_token)
    
    service_id = f"service_{uuid.uuid4().hex[:12]}"
    service_doc = {
        "service_id": service_id,
        "provider_user_id": user.user_id,
        "provider_name": user.name,
        **service_data.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.services.insert_one(service_doc)
    return await db.services.find_one({"service_id": service_id}, {"_id": 0})

@api_router.delete("/services/{service_id}")
async def delete_service(service_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Delete a service"""
    user = await get_current_user(authorization, session_token)
    
    service = await db.services.find_one({"service_id": service_id}, {"_id": 0})
    if not service:
        raise HTTPException(status_code=404, detail="Servicio no encontrado")
    
    if service["provider_user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar este servicio")
    
    await db.services.delete_one({"service_id": service_id})
    return {"message": "Servicio eliminado"}

# ============================================
# ADVERTISING ENDPOINTS
# ============================================

AD_PLANS = {
    "basico": {"price": 200, "duration": 7, "name": "Básico", "features": ["Aparece en lista destacada"]},
    "destacado": {"price": 400, "duration": 15, "name": "Destacado", "features": ["Aparece primero en búsquedas", "Badge destacado"]},
    "premium": {"price": 600, "duration": 30, "name": "Premium", "features": ["Aparece primero", "Badge premium", "Banner en inicio"]},
    "recomendado": {"price": 1000, "duration": 30, "name": "Recomendado", "features": ["Aparece en Pulperías Recomendadas", "Badge exclusivo", "Máxima visibilidad", "Prioridad en mapa"]}
}

@api_router.get("/ads/plans")
async def get_ad_plans():
    """Get available advertising plans"""
    return AD_PLANS

@api_router.get("/ads/featured")
async def get_featured_pulperias():
    """Get featured/advertised pulperias"""
    now = datetime.now(timezone.utc)
    
    active_ads = await db.advertisements.find(
        {"status": "active", "end_date": {"$gte": now.isoformat()}},
        {"_id": 0}
    ).sort([("plan", -1), ("created_at", -1)]).to_list(20)
    
    featured = []
    for ad in active_ads:
        pulperia = await db.pulperias.find_one({"pulperia_id": ad["pulperia_id"]}, {"_id": 0})
        if pulperia:
            pulperia["ad_plan"] = ad["plan"]
            featured.append(pulperia)
    
    return featured


@api_router.get("/ads/recommended")
async def get_recommended_pulperias():
    """Get pulperias with 'recomendado' plan - Premium tier for featured section"""
    now = datetime.now(timezone.utc)
    
    # Only get ads with 'recomendado' plan that are active
    active_ads = await db.advertisements.find(
        {
            "status": "active", 
            "plan": "recomendado",
            "end_date": {"$gte": now.isoformat()}
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    recommended = []
    for ad in active_ads:
        pulperia = await db.pulperias.find_one({"pulperia_id": ad["pulperia_id"]}, {"_id": 0})
        if pulperia:
            pulperia["ad_plan"] = "recomendado"
            pulperia["ad_end_date"] = ad.get("end_date")
            recommended.append(pulperia)
    
    return recommended

@api_router.get("/ads/my-ads")
async def get_my_ads(authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Get ads for current user's pulperias"""
    user = await get_current_user(authorization, session_token)
    
    user_pulperias = await db.pulperias.find({"owner_user_id": user.user_id}, {"_id": 0}).to_list(100)
    pulperia_ids = [p["pulperia_id"] for p in user_pulperias]
    
    ads = await db.advertisements.find(
        {"pulperia_id": {"$in": pulperia_ids}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return ads

@api_router.post("/ads/create")
async def create_advertisement(ad_data: AdvertisementCreate, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Create a new advertisement request"""
    user = await get_current_user(authorization, session_token)
    
    if user.user_type != "pulperia":
        raise HTTPException(status_code=403, detail="Solo pulperías pueden crear anuncios")
    
    pulperia = await db.pulperias.find_one({"owner_user_id": user.user_id}, {"_id": 0})
    if not pulperia:
        raise HTTPException(status_code=404, detail="No tienes una pulpería registrada")
    
    plan_info = AD_PLANS.get(ad_data.plan)
    if not plan_info:
        raise HTTPException(status_code=400, detail="Plan inválido")
    
    ad_id = f"ad_{uuid.uuid4().hex[:12]}"
    ad_doc = {
        "ad_id": ad_id,
        "pulperia_id": pulperia["pulperia_id"],
        "pulperia_name": pulperia["name"],
        "plan": ad_data.plan,
        "status": "pending",
        "payment_method": ad_data.payment_method,
        "payment_reference": ad_data.payment_reference,
        "amount": plan_info["price"],
        "duration_days": plan_info["duration"],
        "start_date": None,
        "end_date": None,
        "assigned_by": None,
        "assigned_at": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.advertisements.insert_one(ad_doc)
    return await db.advertisements.find_one({"ad_id": ad_id}, {"_id": 0})

@api_router.get("/ads/assignment-log")
async def get_ad_assignment_log():
    """Get public log of ad assignments"""
    logs = await db.ad_assignment_logs.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return logs

# ============================================
# ADMIN ENDPOINTS
# ============================================

@api_router.get("/admin/pulperias")
async def admin_get_all_pulperias(authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Get all pulperias for ad management"""
    await get_admin_user(authorization, session_token)
    pulperias = await db.pulperias.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return pulperias

@api_router.get("/admin/ads")
async def admin_get_all_ads(authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Get all advertisements"""
    await get_admin_user(authorization, session_token)
    ads = await db.advertisements.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return ads

@api_router.post("/admin/ads/activate")
async def admin_activate_ad(activation: AdminAdActivation, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Activate an ad for a pulperia"""
    admin = await get_admin_user(authorization, session_token)
    
    pulperia = await db.pulperias.find_one({"pulperia_id": activation.pulperia_id}, {"_id": 0})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    # Check for existing active ad
    existing = await db.advertisements.find_one({
        "pulperia_id": activation.pulperia_id,
        "status": "active"
    }, {"_id": 0})
    
    if existing:
        # Update existing ad
        now = datetime.now(timezone.utc)
        end_date = now + timedelta(days=activation.duration_days)
        
        await db.advertisements.update_one(
            {"ad_id": existing["ad_id"]},
            {"$set": {
                "plan": activation.plan,
                "end_date": end_date.isoformat(),
                "assigned_by": admin.email,
                "assigned_at": now.isoformat()
            }}
        )
        ad_id = existing["ad_id"]
    else:
        # Create new ad
        now = datetime.now(timezone.utc)
        end_date = now + timedelta(days=activation.duration_days)
        
        ad_id = f"ad_{uuid.uuid4().hex[:12]}"
        ad_doc = {
            "ad_id": ad_id,
            "pulperia_id": activation.pulperia_id,
            "pulperia_name": pulperia["name"],
            "plan": activation.plan,
            "status": "active",
            "payment_method": "admin_assigned",
            "payment_reference": None,
            "amount": 0,
            "duration_days": activation.duration_days,
            "start_date": now.isoformat(),
            "end_date": end_date.isoformat(),
            "assigned_by": admin.email,
            "assigned_at": now.isoformat(),
            "created_at": now.isoformat()
        }
        await db.advertisements.insert_one(ad_doc)
    
    # Log the assignment
    log_id = f"log_{uuid.uuid4().hex[:12]}"
    log_doc = {
        "log_id": log_id,
        "ad_id": ad_id,
        "pulperia_id": activation.pulperia_id,
        "pulperia_name": pulperia["name"],
        "plan": activation.plan,
        "action": "activated",
        "assigned_by": admin.email,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.ad_assignment_logs.insert_one(log_doc)
    
    return await db.advertisements.find_one({"ad_id": ad_id}, {"_id": 0})

@api_router.post("/admin/ads/{ad_id}/deactivate")
async def admin_deactivate_ad(ad_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Deactivate an ad"""
    admin = await get_admin_user(authorization, session_token)
    
    ad = await db.advertisements.find_one({"ad_id": ad_id}, {"_id": 0})
    if not ad:
        raise HTTPException(status_code=404, detail="Anuncio no encontrado")
    
    await db.advertisements.update_one(
        {"ad_id": ad_id},
        {"$set": {"status": "expired"}}
    )
    
    # Log the deactivation
    log_id = f"log_{uuid.uuid4().hex[:12]}"
    log_doc = {
        "log_id": log_id,
        "ad_id": ad_id,
        "pulperia_id": ad["pulperia_id"],
        "pulperia_name": ad["pulperia_name"],
        "plan": ad["plan"],
        "action": "deactivated",
        "assigned_by": admin.email,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.ad_assignment_logs.insert_one(log_doc)
    
    return {"message": "Anuncio desactivado"}

@api_router.post("/admin/pulperias/{pulperia_id}/suspend")
async def admin_suspend_pulperia(pulperia_id: str, reason: str = "", days: int = 7, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Suspend a pulperia temporarily"""
    admin = await get_admin_user(authorization, session_token)
    
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    suspend_until = datetime.now(timezone.utc) + timedelta(days=days)
    
    await db.pulperias.update_one(
        {"pulperia_id": pulperia_id},
        {"$set": {
            "is_suspended": True, 
            "suspension_reason": reason, 
            "suspended_by": admin.email, 
            "suspended_at": datetime.now(timezone.utc).isoformat(),
            "suspend_until": suspend_until.isoformat(),
            "suspend_days": days
        }}
    )
    
    # Create admin message to notify pulperia
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    message_doc = {
        "message_id": message_id,
        "pulperia_id": pulperia_id,
        "pulperia_name": pulperia["name"],
        "from_admin": True,
        "sender": admin.email,
        "message": f"Tu pulpería ha sido suspendida por {days} días. Razón: {reason or 'No especificada'}. Podrás volver a operar el {suspend_until.strftime('%d/%m/%Y')}.",
        "read": False,
        "is_system_message": True,
        "message_type": "suspension",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.admin_messages.insert_one(message_doc)
    
    return {"message": f"Pulpería suspendida por {days} días"}

@api_router.post("/admin/pulperias/{pulperia_id}/unsuspend")
async def admin_unsuspend_pulperia(pulperia_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Unsuspend a pulperia"""
    admin = await get_admin_user(authorization, session_token)
    
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    await db.pulperias.update_one(
        {"pulperia_id": pulperia_id},
        {"$set": {"is_suspended": False, "suspension_reason": None, "suspend_until": None, "suspend_days": None}}
    )
    
    # Create admin message to notify pulperia
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    message_doc = {
        "message_id": message_id,
        "pulperia_id": pulperia_id,
        "pulperia_name": pulperia["name"],
        "from_admin": True,
        "sender": admin.email,
        "message": "¡Tu pulpería ha sido reactivada! Ya puedes volver a operar normalmente.",
        "read": False,
        "is_system_message": True,
        "message_type": "reactivation",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.admin_messages.insert_one(message_doc)
    
    return {"message": "Pulpería reactivada"}

@api_router.post("/admin/pulperias/{pulperia_id}/badge")
async def admin_set_badge(pulperia_id: str, badge: str = "", authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Set a badge for a pulperia"""
    await get_admin_user(authorization, session_token)
    
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    await db.pulperias.update_one(
        {"pulperia_id": pulperia_id},
        {"$set": {"badge": badge if badge else None}}
    )
    
    return {"message": "Badge actualizado"}

@api_router.post("/admin/pulperias/{pulperia_id}/message")
async def admin_send_message(pulperia_id: str, message: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Send a message to a pulperia"""
    admin = await get_admin_user(authorization, session_token)
    
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    message_doc = {
        "message_id": message_id,
        "pulperia_id": pulperia_id,
        "pulperia_name": pulperia["name"],
        "from_admin": True,
        "sender": admin.email,
        "message": message,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.admin_messages.insert_one(message_doc)
    
    # Broadcast via WebSocket if pulperia owner is connected
    owner_id = pulperia.get("owner_user_id")
    if owner_id:
        await ws_manager.broadcast_to_user(owner_id, {
            "type": "admin_message",
            "message": message,
            "from": "Administrador"
        })
    
    return {"message": "Mensaje enviado", "message_id": message_id}

@api_router.get("/admin/messages")
async def admin_get_messages(authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Get all admin messages"""
    await get_admin_user(authorization, session_token)
    
    messages = await db.admin_messages.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return messages

@api_router.get("/pulperias/{pulperia_id}/admin-messages")
async def get_pulperia_admin_messages(pulperia_id: str, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Get admin messages for a pulperia"""
    user = await get_current_user(authorization, session_token)
    
    pulperia = await db.pulperias.find_one({"pulperia_id": pulperia_id}, {"_id": 0})
    if not pulperia:
        raise HTTPException(status_code=404, detail="Pulpería no encontrada")
    
    if pulperia["owner_user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="No tienes permiso")
    
    messages = await db.admin_messages.find({"pulperia_id": pulperia_id}, {"_id": 0}).sort("created_at", -1).to_list(50)
    
    # Mark as read
    await db.admin_messages.update_many(
        {"pulperia_id": pulperia_id, "read": False},
        {"$set": {"read": True}}
    )
    
    return messages

# ============================================
# WEBSOCKET CONNECTION MANAGER
# ============================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.connection_count: Dict[str, int] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
            self.connection_count[user_id] = 0
        
        self.active_connections[user_id].add(websocket)
        self.connection_count[user_id] += 1
        logger.info(f"WebSocket connected for user {user_id}")
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            self.connection_count[user_id] = max(0, self.connection_count.get(user_id, 1) - 1)
            
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                del self.connection_count[user_id]
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
    
    async def broadcast_to_user(self, user_id: str, message: dict):
        if user_id not in self.active_connections:
            return
        
        disconnected = set()
        for connection in self.active_connections[user_id].copy():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to user {user_id}: {e}")
                disconnected.add(connection)
        
        for conn in disconnected:
            self.active_connections[user_id].discard(conn)
    
    def is_user_connected(self, user_id: str) -> bool:
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0

ws_manager = ConnectionManager()

@app.websocket("/ws/orders/{user_id}")
async def websocket_orders_endpoint(websocket: WebSocket, user_id: str):
    if not user_id or len(user_id) < 5:
        await websocket.close(code=4001, reason="Invalid user_id")
        return
    
    await ws_manager.connect(websocket, user_id)
    
    try:
        await ws_manager.send_personal_message({
            "type": "connected",
            "user_id": user_id
        }, websocket)
        
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60)
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await ws_manager.send_personal_message({"type": "pong"}, websocket)
                
            except asyncio.TimeoutError:
                try:
                    await ws_manager.send_personal_message({"type": "ping"}, websocket)
                except Exception:
                    break
                    
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        ws_manager.disconnect(websocket, user_id)

async def broadcast_order_update(order: dict, event_type: str):
    """Broadcast order update to owner and customer with full order details"""
    pulperia = await db.pulperias.find_one({"pulperia_id": order.get("pulperia_id")}, {"_id": 0})
    owner_id = pulperia.get("owner_user_id") if pulperia else None
    customer_id = order.get("customer_user_id")
    pulperia_name = pulperia.get("name", "Pulpería") if pulperia else "Pulpería"
    customer_name = order.get("customer_name", "Cliente")
    
    # Enrich order with pulperia name
    enriched_order = {**order, "pulperia_name": pulperia_name}
    
    # Calculate total items
    items = order.get("items", [])
    total_items = sum(item.get("quantity", 1) for item in items)
    
    # Create item summary for messages
    item_summary = ", ".join([f"{item.get('quantity', 1)}x {item.get('product_name', 'Producto')}" for item in items[:3]])
    if len(items) > 3:
        item_summary += f" +{len(items) - 3} más"
    
    status_messages = {
        "pending": f"Tu orden en {pulperia_name} está pendiente",
        "accepted": f"¡{pulperia_name} aceptó tu orden! Están preparándola",
        "ready": f"🎉 ¡Tu orden en {pulperia_name} está lista para recoger!",
        "completed": f"Orden completada en {pulperia_name}",
        "cancelled": f"Tu orden en {pulperia_name} fue cancelada"
    }
    
    if owner_id:
        owner_notification = {
            "type": "order_update",
            "event": event_type,
            "target": "owner",
            "order": enriched_order,
            "message": f"Nuevo pedido de {customer_name}: {item_summary}" if event_type == "new_order" else f"Orden de {customer_name} actualizada",
            "total_items": total_items,
            "sound": event_type == "new_order",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await ws_manager.broadcast_to_user(owner_id, owner_notification)
    
    if customer_id:
        customer_notification = {
            "type": "order_update",
            "event": event_type,
            "target": "customer",
            "order": enriched_order,
            "message": status_messages.get(order.get("status"), "Estado de orden actualizado"),
            "total_items": total_items,
            "sound": order.get("status") == "ready",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await ws_manager.broadcast_to_user(customer_id, customer_notification)

# ============================================
# IMAGE UPLOAD ENDPOINT
# ============================================

@api_router.post("/upload-image")
async def upload_image(file: UploadFile = File(...), authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Upload an image and return its base64 data URL"""
    await get_current_user(authorization, session_token)
    
    # Validate file type
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Tipo de archivo no permitido. Use JPEG, PNG, GIF o WebP.")
    
    # Read file content
    content = await file.read()
    
    # Check file size (max 15MB - increased from 5MB)
    max_size = 15 * 1024 * 1024  # 15MB
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="Archivo demasiado grande. Máximo 15MB.")
    
    # Convert to base64 data URL
    base64_content = base64.b64encode(content).decode('utf-8')
    data_url = f"data:{file.content_type};base64,{base64_content}"
    
    return {"image_url": data_url, "filename": file.filename, "size": len(content)}

@api_router.post("/upload-cv")
async def upload_cv(file: UploadFile = File(...), authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Upload a CV (PDF or image) and return its base64 data URL"""
    await get_current_user(authorization, session_token)
    
    # Validate file type - allow PDFs and images
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Tipo de archivo no permitido. Use PDF, JPEG, PNG, GIF o WebP.")
    
    # Read file content
    content = await file.read()
    
    # Check file size (max 15MB)
    max_size = 15 * 1024 * 1024  # 15MB
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="Archivo demasiado grande. Máximo 15MB.")
    
    # Convert to base64 data URL
    base64_content = base64.b64encode(content).decode('utf-8')
    data_url = f"data:{file.content_type};base64,{base64_content}"
    
    return {"cv_url": data_url, "filename": file.filename, "size": len(content)}

@api_router.delete("/admin/clear-orders")
async def admin_clear_orders(authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Clear all orders from the system"""
    await get_admin_user(authorization, session_token)
    
    result = await db.orders.delete_many({})
    return {"message": f"Se eliminaron {result.deleted_count} órdenes del sistema"}

@api_router.delete("/admin/clear-data")
async def admin_clear_data(keep_products: bool = True, authorization: Optional[str] = Header(None), session_token: Optional[str] = Cookie(None)):
    """Admin: Clear data from the system"""
    await get_admin_user(authorization, session_token)
    
    deleted = {}
    
    # Clear orders
    result = await db.orders.delete_many({})
    deleted["orders"] = result.deleted_count
    
    # Clear announcements
    result = await db.announcements.delete_many({})
    deleted["announcements"] = result.deleted_count
    
    # Clear reviews (optional)
    # result = await db.reviews.delete_many({})
    # deleted["reviews"] = result.deleted_count
    
    if not keep_products:
        result = await db.products.delete_many({})
        deleted["products"] = result.deleted_count
    
    return {"message": "Datos limpiados", "deleted": deleted}

# ============================================
# GLOBAL ANNOUNCEMENTS SYSTEM (1000 Lps)
# Anuncios que aparecen a TODOS los usuarios
# ============================================

class GlobalAnnouncementCreate(BaseModel):
    title: str
    content: str
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    priority: int = 0  # Mayor = más importante
    expires_days: Optional[int] = 30  # Días hasta expiración

@api_router.get("/global-announcements")
async def get_global_announcements():
    """Get all active global announcements - visible to everyone"""
    now = datetime.now(timezone.utc)
    
    # Get active, non-expired announcements sorted by priority
    announcements = await db.global_announcements.find({
        "is_active": True,
        "$or": [
            {"expires_at": {"$gt": now.isoformat()}},
            {"expires_at": None}
        ]
    }, {"_id": 0}).sort([("priority", -1), ("created_at", -1)]).to_list(50)
    
    return announcements

@api_router.post("/admin/global-announcements")
async def create_global_announcement(
    data: GlobalAnnouncementCreate,
    authorization: Optional[str] = Header(None), 
    session_token: Optional[str] = Cookie(None)
):
    """Admin: Create a global announcement (1000 Lps)"""
    admin = await get_admin_user(authorization, session_token)
    
    now = datetime.now(timezone.utc)
    expires_at = None
    if data.expires_days:
        expires_at = (now + timedelta(days=data.expires_days)).isoformat()
    
    announcement_id = f"global_ann_{uuid.uuid4().hex[:12]}"
    announcement_doc = {
        "announcement_id": announcement_id,
        "title": data.title,
        "content": data.content,
        "image_url": data.image_url,
        "link_url": data.link_url,
        "priority": data.priority,
        "is_active": True,
        "created_at": now.isoformat(),
        "expires_at": expires_at,
        "created_by": admin.user_id
    }
    
    await db.global_announcements.insert_one(announcement_doc)
    
    logger.info(f"[GLOBAL ANN] Admin created announcement: {data.title}")
    
    return {
        "message": "Anuncio global creado exitosamente",
        "announcement": {k: v for k, v in announcement_doc.items() if k != "_id"}
    }

@api_router.put("/admin/global-announcements/{announcement_id}")
async def update_global_announcement(
    announcement_id: str,
    data: GlobalAnnouncementCreate,
    authorization: Optional[str] = Header(None), 
    session_token: Optional[str] = Cookie(None)
):
    """Admin: Update a global announcement"""
    await get_admin_user(authorization, session_token)
    
    announcement = await db.global_announcements.find_one({"announcement_id": announcement_id})
    if not announcement:
        raise HTTPException(status_code=404, detail="Anuncio no encontrado")
    
    now = datetime.now(timezone.utc)
    expires_at = None
    if data.expires_days:
        expires_at = (now + timedelta(days=data.expires_days)).isoformat()
    
    update_data = {
        "title": data.title,
        "content": data.content,
        "image_url": data.image_url,
        "link_url": data.link_url,
        "priority": data.priority,
        "expires_at": expires_at,
        "updated_at": now.isoformat()
    }
    
    await db.global_announcements.update_one(
        {"announcement_id": announcement_id},
        {"$set": update_data}
    )
    
    return {"message": "Anuncio actualizado"}

@api_router.delete("/admin/global-announcements/{announcement_id}")
async def delete_global_announcement(
    announcement_id: str,
    authorization: Optional[str] = Header(None), 
    session_token: Optional[str] = Cookie(None)
):
    """Admin: Delete a global announcement"""
    await get_admin_user(authorization, session_token)
    
    result = await db.global_announcements.delete_one({"announcement_id": announcement_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Anuncio no encontrado")
    
    return {"message": "Anuncio eliminado"}

@api_router.put("/admin/global-announcements/{announcement_id}/toggle")
async def toggle_global_announcement(
    announcement_id: str,
    authorization: Optional[str] = Header(None), 
    session_token: Optional[str] = Cookie(None)
):
    """Admin: Toggle active status of a global announcement"""
    await get_admin_user(authorization, session_token)
    
    announcement = await db.global_announcements.find_one({"announcement_id": announcement_id})
    if not announcement:
        raise HTTPException(status_code=404, detail="Anuncio no encontrado")
    
    new_status = not announcement.get("is_active", True)
    
    await db.global_announcements.update_one(
        {"announcement_id": announcement_id},
        {"$set": {"is_active": new_status}}
    )
    
    return {"message": f"Anuncio {'activado' if new_status else 'desactivado'}", "is_active": new_status}

@api_router.get("/admin/global-announcements")
async def admin_get_all_global_announcements(
    authorization: Optional[str] = Header(None), 
    session_token: Optional[str] = Cookie(None)
):
    """Admin: Get all global announcements (including inactive)"""
    await get_admin_user(authorization, session_token)
    
    announcements = await db.global_announcements.find(
        {}, {"_id": 0}
    ).sort([("priority", -1), ("created_at", -1)]).to_list(100)
    
    return announcements

# ============================================
# CORS MIDDLEWARE
# ============================================

# Dominios permitidos para CORS
ALLOWED_ORIGINS = [
    "https://dashboard-bugfix-5.preview.emergentagent.com",
    "https://lapulperiastore.net",
    "https://www.lapulperiastore.net",
    "https://red-auth-connect.emergent.host",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "*"  # Allow all for deployment flexibility
]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint - MUST be at root level for deployment
@app.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes/deployment"""
    return {"status": "healthy", "service": "lapulperia-backend"}

# Also add health check under /api for nginx routing
@api_router.get("/health")
async def api_health_check():
    """Health check endpoint under /api prefix"""
    return {"status": "healthy", "service": "lapulperia-backend"}

app.include_router(api_router)

@app.on_event("startup")
async def startup_db_client():
    """Create indexes for faster queries on startup"""
    try:
        # Índices para pulperías
        await db.pulperias.create_index("pulperia_id", unique=True)
        await db.pulperias.create_index("owner_user_id")
        await db.pulperias.create_index([("location.lat", 1), ("location.lng", 1)])
        
        # Índices para productos
        await db.products.create_index("product_id", unique=True)
        await db.products.create_index("pulperia_id")
        await db.products.create_index([("name", "text"), ("description", "text")])
        
        # Índices para órdenes
        await db.orders.create_index("order_id", unique=True)
        await db.orders.create_index("pulperia_id")
        await db.orders.create_index("customer_user_id")
        await db.orders.create_index("status")
        
        # Índices para usuarios
        await db.users.create_index("user_id", unique=True)
        await db.users.create_index("email", unique=True)
        
        # Índices para sesiones
        await db.user_sessions.create_index("session_token", unique=True)
        await db.user_sessions.create_index("user_id")
        
        # Índices para logros
        await db.achievements.create_index("pulperia_id")
        await db.achievements.create_index([("pulperia_id", 1), ("badge_id", 1)], unique=True)
        
        # Índices para favoritos
        await db.favorites.create_index([("user_id", 1), ("pulperia_id", 1)], unique=True)
        
        logger.info("[STARTUP] Database indexes created successfully")
    except Exception as e:
        logger.warning(f"[STARTUP] Index creation warning: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
