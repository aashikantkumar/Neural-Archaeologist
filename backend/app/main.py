from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base, engine, init_db
from app.routes import auth, investigations
import socketio
import logging

logger = logging.getLogger(__name__)

# IMPORTANT: Import models BEFORE init_db() so SQLAlchemy knows about them
from app.models import User, Investigation, AgentLog, RepoCache

# Initialize DB with retry (instead of crashing at import time)
init_db()

# Create FastAPI app
app = FastAPI(
    title="Neural Archaeologist API",
    description="AI-powered codebase archaeology and analysis",
    version="2.0.0"
)

# Configure CORS
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "https://neural-archaeologist.vercel.app",
]

# Add any additional origins from env var
if settings.ALLOWED_ORIGINS:
    allowed_origins.extend([
        origin.strip() 
        for origin in settings.ALLOWED_ORIGINS.split(",")
        if origin.strip()
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(investigations.router, prefix="/api/investigations", tags=["investigations"])

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=allowed_origins,
    logger=True,
    engineio_logger=True
)

# Wrap with Socket.IO ASGI app
socket_app = socketio.ASGIApp(
    sio,
    other_asgi_app=app,
    socketio_path='/socket.io'
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "database": "connected"
    }

@app.get("/")
async def root():
    return {
        "message": "Neural Archaeologist API v2",
        "docs": "/docs",
        "health": "/health"
    }

# Socket.IO event handlers
@sio.event
async def connect(sid, environ):
    logger.info(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")