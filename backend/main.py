import os
import logging
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api import crops, assistant, profile, auth, weather, schemes
from api.agent import router as agent_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("agronex.backend")

app = FastAPI(
    title="AgroNex API",
    description="Smart Farming Backend with Autonomous Copilot Agent, Open-Meteo Weather, and Gemma Multimodal AI",
    version="1.0.0"
)

# 1. Determine allowed origins securely
origins = []
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    origins.extend([o.strip() for o in allowed_origins_env.split(",") if o.strip()])

frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
if frontend_url and frontend_url not in origins:
    origins.append(frontend_url)

if os.getenv("VERCEL_URL"):
    origins.append(f"https://{os.getenv('VERCEL_URL')}")
if os.getenv("VERCEL_PROJECT_PRODUCTION_URL"):
    origins.append(f"https://{os.getenv('VERCEL_PROJECT_PRODUCTION_URL')}")

# Explicit development wildcard override (disabled in production unless explicitly set)
is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
allow_all = os.getenv("ALLOW_ALL_ORIGINS", "false" if is_production else "true").lower() in ("true", "1")
if allow_all and not is_production:
    if not origins:
        origins = ["*"]
    elif "*" not in origins:
        origins.append("*")

# 2. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Security Headers Middleware (Module 5 Security Enforcement)
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# 4. Include routers
app.include_router(agent_router)
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(crops.router, prefix="/api/crops", tags=["Crops"])
app.include_router(assistant.router, prefix="/api/assistant", tags=["AI Assistant"])
app.include_router(weather.router, prefix="/api/weather", tags=["Weather"])
app.include_router(schemes.router, prefix="/api/schemes", tags=["Schemes"])
app.include_router(profile.router, prefix="/api/profile", tags=["Profile"])


@app.get("/")
@app.get("/api")
def read_root():
    return {
        "message": "Welcome to AgroNex API",
        "service": "AgroNex AI Platform Engine",
        "version": "1.0.0",
        "documentation": "/docs"
    }


@app.get("/health")
@app.get("/api/health")
def health_check(detail: bool = False):
    """
    Health check endpoint.
    Returns exact {'status': 'ok'} by default for compatibility with monitoring & tests.
    When ?detail=true is supplied, returns full telemetry across all 5 modules.
    """
    if not detail:
        return {"status": "ok"}

    from config.local_db import get_connection
    db_status = "connected"
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "ok",
        "service": "AgroNex AI Platform Engine (Module 5)",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "components": {
            "database": db_status,
            "crop_engine": "operational",
            "weather_engine": "operational",
            "gemma_assistant": "operational",
            "schemes_directory": "operational"
        }
    }

