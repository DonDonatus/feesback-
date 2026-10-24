r"""
Seed demo data aligned with fees frontend for immediate local and cloud testing.
Run with: .\.venv\Scripts\python.exe scripts\seed_demo_data.py
"""
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import uuid
from decimal import Decimal
from datetime import datetime, timezone
from app.database import SessionLocal, Base, engine
from app.models.user import UserModel
from app.models.school import ClassModel, StudentModel, FeeModel
from app.models.payment import PaymentModel


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        now = datetime.now(timezone.utc)
        term = "Term 1"

        # 1. Seed Users (if not present)
        if not db.query(UserModel).first():
            print("[*] Seeding Staff Users...")
            users = [
                UserModel(id="usr_1", name="Akua Mensah", role="bursar", pin="1234", created_at=now),
                UserModel(id="usr_2", name="Kwame Asante", role="admin", pin="5678", created_at=now),
                UserModel(id="usr_3", name="Abena Osei", role="clerk", pin="4321", created_at=now),
            ]
            db.add_all(users)
            db.flush()

        # 2. Seed Classes (if not present)
        if not db.query(ClassModel).first():
            print("[*] Seeding Classes...")
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

            print("[*] Setting Term Fees...")
            fees = [
                FeeModel(id=f"fee_{cid}", class_id=cid, term=term, amount=Decimal(str(amt)), created_at=now, updated_at=now)
                for cid, amt in [
                    ("cls_kg1", 950), ("cls_kg2", 950),
                    ("cls_p1", 1300), ("cls_p2", 1300), ("cls_p3", 1400),
                    ("cls_p4", 1400), ("cls_p5", 1500), ("cls_p6", 1500),
                    ("cls_jhs1", 1650), ("cls_jhs2", 1650), ("cls_jhs3", 1800),
                ]
            ]
            db.add_all(fees)
            db.flush()

            print("[*] Enrolling Sample Students...")
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

            print("[*] Recording Sample Payments...")
            payments = [
                # stu_01: Paid in full (1800)
                PaymentModel(
                    id="pay_01", student_id="stu_01", term=term, amount=Decimal("1800.00"),
                    method="cash", reference="CSH-00142", receipt_no="REC-2026-1042",
                    received_by_name="Akua Mensah", paid_at=now, created_at=now
                ),
                # stu_02: Part paid (1000 of 1800)
                PaymentModel(
                    id="pay_02", student_id="stu_02", term=term, amount=Decimal("1000.00"),
                    method="bank", reference="BNK-55120", receipt_no="REC-2026-1043",
                    received_by_name="Akua Mensah", paid_at=now, created_at=now
                ),
                # stu_04: Paid in full (1500)
                PaymentModel(
                    id="pay_03", student_id="stu_04", term=term, amount=Decimal("1500.00"),
                    method="cash", reference="CSH-00143", receipt_no="REC-2026-1044",
                    received_by_name="Kwame Asante", paid_at=now, created_at=now
                ),
                # stu_05: Part paid (600 of 1500)
                PaymentModel(
                    id="pay_04", student_id="stu_05", term=term, amount=Decimal("600.00"),
                    method="hubtel", reference="HUB-99124", receipt_no="REC-2026-1045",
                    received_by_name="Momo (online)", paid_at=now, created_at=now
                ),
                # stu_07: Paid in full (1400)
                PaymentModel(
                    id="pay_05", student_id="stu_07", term=term, amount=Decimal("1400.00"),
                    method="cash", reference="CSH-00144", receipt_no="REC-2026-1046",
                    received_by_name="Abena Osei", paid_at=now, created_at=now
                ),
                # stu_08: Part paid (700 of 1300)
                PaymentModel(
                    id="pay_06", student_id="stu_08", term=term, amount=Decimal("700.00"),
                    method="cash", reference="CSH-00145", receipt_no="REC-2026-1047",
                    received_by_name="Akua Mensah", paid_at=now, created_at=now
                ),
            ]
            db.add_all(payments)

        db.commit()
        print("[SUCCESS] Successfully seeded database aligned with Achimota School data!")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Seeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
