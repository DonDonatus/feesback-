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

    # 1. Automatic schema migration: ensure all columns exist in payments table
    from sqlalchemy import inspect, text
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            if "payments" in inspector.get_table_names():
                existing_cols = {col["name"] for col in inspector.get_columns("payments")}
                cols_to_add = [
                    ("receipt_no", "VARCHAR(50)"),
                    ("received_by_name", "VARCHAR(100)"),
                    ("reversed_by_name", "VARCHAR(100)"),
                    ("reversal_reason", "VARCHAR(255)"),
                    ("notes", "VARCHAR(255)"),
                    ("client_id", "VARCHAR(36)"),
                ]
                for col_name, col_type in cols_to_add:
                    if col_name not in existing_cols:
                        conn.execute(text(f"ALTER TABLE payments ADD COLUMN {col_name} {col_type}"))
                conn.commit()
    except Exception as e:
        print(f"[WARN] Schema migration note: {e}")

    # 2. Ensure default staff users, classes, fees, students exist
    from app.database import SessionLocal
    from app.models.user import UserModel
    from app.models.school import ClassModel, StudentModel, FeeModel
    from app.models.payment import PaymentModel
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
            db.flush()

        if not db.query(StudentModel).first():
            students_data = [
                ("stu_01", "ACH-2025-001", "Kwame Mensah", "0244123456", "cls_jhs3"),
                ("stu_02", "ACH-2025-002", "Abena Serwaa Boateng", "0208112233", "cls_jhs3"),
                ("stu_03", "ACH-2025-003", "Kofi Owusu-Ansah", "0277334455", "cls_jhs2"),
                ("stu_04", "ACH-2025-004", "Ama Pokuaa Frimpong", "0543998877", "cls_p6"),
                ("stu_05", "ACH-2025-005", "Yaw Badu Addo", "0245667788", "cls_p5"),
                ("stu_06", "ACH-2025-006", "Akosua Dapaah", "0266123987", "cls_p4"),
                ("stu_07", "ACH-2025-007", "Kojo Antwi Osei", "0244778899", "cls_p3"),
                ("stu_08", "ACH-2025-008", "Efua Sutherland Adjei", "0201234567", "cls_p2"),
                ("stu_09", "ACH-2025-009", "Kwabena Agyemang", "0554321987", "cls_p1"),
            ]
            student_objs = [
                StudentModel(
                    id=sid, admission_no=adm, name=name,
                    guardian_phone=phone, class_id=cid, status="active",
                    created_at=now, updated_at=now
                )
                for sid, adm, name, phone, cid in students_data
            ]
            db.add_all(student_objs)
            db.flush()

        if not db.query(PaymentModel).first():
            payments = [
                PaymentModel(
                    id="pay_01", student_id="stu_01", term="Term 1", amount=Decimal("1800.00"),
                    method="cash", reference="CSH-00142", receipt_no="REC-2026-1042",
                    received_by_name="Akua Mensah", paid_at=now, created_at=now
                ),
                PaymentModel(
                    id="pay_02", student_id="stu_02", term="Term 1", amount=Decimal("1000.00"),
                    method="bank", reference="BNK-55120", receipt_no="REC-2026-1043",
                    received_by_name="Akua Mensah", paid_at=now, created_at=now
                ),
                PaymentModel(
                    id="pay_03", student_id="stu_04", term="Term 1", amount=Decimal("1500.00"),
                    method="cash", reference="CSH-00143", receipt_no="REC-2026-1044",
                    received_by_name="Kwame Asante", paid_at=now, created_at=now
                ),
                PaymentModel(
                    id="pay_05", student_id="stu_07", term="Term 1", amount=Decimal("1400.00"),
                    method="cash", reference="CSH-00144", receipt_no="REC-2026-1046",
                    received_by_name="Abena Osei", paid_at=now, created_at=now
                ),
            ]
            db.add_all(payments)

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[WARN] Startup seed note: {e}")
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

# Configure CORS: allow all origins with credentials
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import JSONResponse
from fastapi import Request

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    origin = request.headers.get("origin", "*")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
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
