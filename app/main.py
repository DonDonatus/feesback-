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

    # Ensure default staff users and classes exist
    from app.database import SessionLocal
    from app.models.user import UserModel
    from app.models.school import ClassModel, FeeModel
    from datetime import datetime, timezone
    from decimal import Decimal

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        if not db.query(UserModel).first():
            users = [
                UserModel(id="usr_1", name="Akua Mensah", role="bursar", pin="1234", created_at=now),
                UserModel(id="usr_2", name="Kwame Asante", role="admin", pin="5678", created_at=now),
                UserModel(id="usr_3", name="Abena Osei", role="clerk", pin="4321", created_at=now),
            ]
            db.add_all(users)
            db.flush()

        if not db.query(ClassModel).first():
            classes_map = {
                "cls_kg1": "KG 1",
                "cls_kg2": "KG 2",
                "cls_p1": "Class 1",
                "cls_p2": "Class 2",
                "cls_p3": "Class 3",
                "cls_p4": "Class 4",
                "cls_p5": "Class 5",
                "cls_p6": "Class 6",
                "cls_jhs1": "JHS 1",
                "cls_jhs2": "JHS 2",
                "cls_jhs3": "JHS 3",
            }
            class_objs = [
                ClassModel(id=cid, name=cname, created_at=now, updated_at=now)
                for cid, cname in classes_map.items()
            ]
            db.add_all(class_objs)
            db.flush()

            fees = [
                FeeModel(id=f"fee_{cid}", class_id=cid, term="Term 1", amount=Decimal(str(amt)), created_at=now, updated_at=now)
                for cid, amt in [
                    ("cls_kg1", 950), ("cls_kg2", 950),
                    ("cls_p1", 1300), ("cls_p2", 1300), ("cls_p3", 1400),
                    ("cls_p4", 1400), ("cls_p5", 1500), ("cls_p6", 1500),
                    ("cls_jhs1", 1650), ("cls_jhs2", 1650), ("cls_jhs3", 1800),
                ]
            ]
            db.add_all(fees)

        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

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
