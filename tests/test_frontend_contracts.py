"""
Validates all 12 Next.js frontend (fees) contracts against the FastAPI backend (managesys).
"""
import uuid
from decimal import Decimal
from app.models.user import UserModel
from app.models.school import ClassModel, StudentModel, FeeModel
from app.models.payment import PaymentModel


def test_full_12_frontend_contracts(client, db_session):
    # 0. Setup Staff Users
    bursar = UserModel(id="usr_1", name="Akua Mensah", role="bursar", pin="1234")
    admin = UserModel(id="usr_2", name="Kwame Asante", role="admin", pin="5678")
    db_session.add_all([bursar, admin])
    db_session.commit()

    # Contract 1: POST /auth/login
    login_res = client.post("/auth/login", json={"user_id": "usr_1", "pin": "1234"})
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "token" in login_data
    token = login_data["token"]
    assert login_data["user"]["name"] == "Akua Mensah"
    assert login_data["user"]["role"] == "bursar"

    auth_headers = {"Authorization": f"Bearer {token}"}

    # Contract 2: GET /auth/me
    me_res = client.get("/auth/me", headers=auth_headers)
    assert me_res.status_code == 200
    assert me_res.json()["id"] == "usr_1"

    # Contract 3: GET /users
    users_res = client.get("/users")
    assert users_res.status_code == 200
    assert len(users_res.json()) >= 2

    # Contract 4: GET /classes
    c1 = ClassModel(id="cls_p1", name="Class 1")
    c2 = ClassModel(id="cls_jhs3", name="JHS 3")
    db_session.add_all([c1, c2])
    db_session.commit()

    classes_res = client.get("/classes")
    assert classes_res.status_code == 200
    assert len(classes_res.json()) == 2

    # Setup Fees & Students
    term = "Term 1"
    fee_jhs = FeeModel(id="fee_1", class_id="cls_jhs3", term=term, amount=Decimal("1800.00"))
    db_session.add(fee_jhs)

    s1 = StudentModel(id="stu_01", admission_no="ACH-001", name="Kwame Mensah", guardian_phone="02401", class_id="cls_jhs3")
    s2 = StudentModel(id="stu_02", admission_no="ACH-002", name="Abena Boateng", guardian_phone="02402", class_id="cls_jhs3")
    db_session.add_all([s1, s2])
    db_session.commit()

    # Contract 10: POST /payments (with client_id)
    client_id_uuid = str(uuid.uuid4())
    pay_res = client.post(
        "/payments",
        headers=auth_headers,
        json={
            "student_id": "stu_01",
            "term": term,
            "amount": 1800.00,
            "method": "cash",
            "reference": "CSH-001",
            "paid_at": "2026-10-24T10:00:00Z",
            "client_id": client_id_uuid
        }
    )
    assert pay_res.status_code == 201
    pay_data = pay_res.json()
    assert pay_data["balance_after"] == 0.0
    assert pay_data["received_by_name"] == "Akua Mensah"
    assert "receipt_no" in pay_data
    payment_id = pay_data["id"]

    # Idempotency check: posting same client_id should return existing payment
    dup_pay = client.post(
        "/payments",
        headers=auth_headers,
        json={
            "student_id": "stu_01",
            "term": term,
            "amount": 1800.00,
            "method": "cash",
            "client_id": client_id_uuid
        }
    )
    assert dup_pay.status_code == 201
    assert dup_pay.json()["id"] == payment_id

    # Contract 5: GET /dashboard/summary?term=
    summary_res = client.get(f"/dashboard/summary?term={term}")
    assert summary_res.status_code == 200
    sum_data = summary_res.json()
    assert sum_data["expected"] == 3600.0  # 2 students * 1800
    assert sum_data["collected"] == 1800.0
    assert sum_data["outstanding"] == 1800.0
    assert sum_data["paid_count"] == 1
    assert sum_data["owing_count"] == 1
    assert sum_data["online"] is True

    # Contract 6: GET /dashboard/today?term=
    today_res = client.get(f"/dashboard/today?term={term}")
    assert today_res.status_code == 200
    today_data = today_res.json()
    assert "collected_today" in today_data
    assert "by_method" in today_data
    assert "by_cashier" in today_data

    # Contract 7: GET /dashboard/students?...
    students_res = client.get(f"/dashboard/students?term={term}&status=paid")
    assert students_res.status_code == 200
    st_data = students_res.json()
    assert "items" in st_data
    assert len(st_data["items"]) == 1
    assert st_data["items"][0]["name"] == "Kwame Mensah"
    assert st_data["items"][0]["status"] == "paid"
    assert st_data["items"][0]["last_payment_at"] is not None

    # Contract 8: GET /students/{id}/payments
    history_res = client.get("/students/stu_01/payments")
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) == 1
    assert history[0]["status"] == "active"
    assert history[0]["amount"] == 1800.0

    # Contract 9: GET /payments?page=1&page_size=50
    audit_res = client.get("/payments?page=1&page_size=50")
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert "items" in audit_data
    assert audit_data["total"] == 1
    assert audit_data["total_amount"] == 1800.0
    assert audit_data["items"][0]["student_name"] == "Kwame Mensah"

    # Contract 11: POST /payments/{id}/reverse
    rev_res = client.post(f"/payments/{payment_id}/reverse", headers=auth_headers, json={"reason": "Check bounced"})
    assert rev_res.status_code == 201
    rev_data = rev_res.json()
    assert rev_data["id"] is not None

    # Verify history now reflects reversed state
    history_res2 = client.get("/students/stu_01/payments")
    assert len(history_res2.json()) == 2

    # Contract 12: POST /sync/trigger
    sync_res = client.post("/sync/trigger")
    # Will attempt sync and return pushed/pulled keys
    assert sync_res.status_code in (200, 503)
