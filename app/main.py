from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
# Import all models to ensure metadata registration
import app.models  # noqa: F401
from app.routers import (
    classes,
    students,
    fees,
    payments,
    dashboard,
    sync,
    auth
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=f"School Fee Management API ({settings.NODE_TYPE.capitalize()} Node)",
    description=(
        "Offline-First School Fee Management System.\n\n"
        "- **Local Node**: Handles offline cash and manual entries with SQLite.\n"
        "- **Cloud Node**: Handles online Hubtel callbacks and Postgres synchronization.\n"
        "- **Balance**: Computed dynamically (Fee minus active payments). Never hardcoded.\n"
        "- **Payments**: Append-only with reversing records for audit safety."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS
origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
if not origins:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True if origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(classes.router)
app.include_router(students.router)
app.include_router(fees.router)
app.include_router(payments.router)
app.include_router(dashboard.router)
app.include_router(sync.router)
app.include_router(auth.router)


@app.get("/", tags=["Health"])
def root_info():
    return {
        "service": "School Fee Management API",
        "node_type": settings.NODE_TYPE,
        "database": "sqlite" if settings.DATABASE_URL.startswith("sqlite") else "postgres",
        "docs_url": "/docs",
        "status": "online"
    }
