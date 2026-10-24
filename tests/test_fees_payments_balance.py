from decimal import Decimal


def test_fees_payments_and_balance_flow(client):
    # 1. Setup Class, Student, Fee
    c_res = client.post("/classes", json={"name": "Primary 1"})
    class_id = c_res.json()["id"]

    s_res = client.post("/students", json={
        "admission_no": "P1-001",
        "name": "Ama Serwaa",
        "guardian_phone": "0501234567",
        "class_id": class_id,
        "status": "active"
    })
    student_id = s_res.json()["id"]

    # Term Fee is 1000.00
    f_res = client.post("/fees", json={
        "class_id": class_id,
        "term": "2026-Term-1",
        "amount": 1000.00
    })
    assert f_res.status_code == 201

    # 2. Check initial status -> unpaid, balance = 1000.00
    dash_res = client.get("/dashboard/students?term=2026-Term-1")
    assert dash_res.status_code == 200
    data = dash_res.json()
    assert len(data["students"]) == 1
    stud = data["students"][0]
    assert Decimal(str(stud["balance"])) == Decimal("1000.00")
    assert stud["status"] in ("owing", "unpaid")
    assert Decimal(str(stud["total_paid"])) == Decimal("0.00")

    # 3. Pay 400.00 Cash -> partial, balance = 600.00
    p1_res = client.post("/payments", json={
        "student_id": student_id,
        "term": "2026-Term-1",
        "amount": 400.00,
        "method": "cash"
    })
    assert p1_res.status_code == 201
    p1_id = p1_res.json()["id"]

    dash_res = client.get("/dashboard/students?term=2026-Term-1")
    stud = dash_res.json()["students"][0]
    assert Decimal(str(stud["balance"])) == Decimal("600.00")
    assert stud["status"] in ("part", "partial")
    assert Decimal(str(stud["total_paid"])) == Decimal("400.00")

    # 4. Pay remaining 600.00 Bank -> paid, balance = 0.00
    p2_res = client.post("/payments", json={
        "student_id": student_id,
        "term": "2026-Term-1",
        "amount": 600.00,
        "method": "bank"
    })
    assert p2_res.status_code == 201
    p2_id = p2_res.json()["id"]

    dash_res = client.get("/dashboard/students?term=2026-Term-1")
    stud = dash_res.json()["students"][0]
    assert Decimal(str(stud["balance"])) == Decimal("0.00")
    assert stud["status"] == "paid"
    assert Decimal(str(stud["total_paid"])) == Decimal("1000.00")

    # 5. Reverse the 600.00 payment (e.g., bounced cheque or bursar mistake)
    rev_res = client.post(f"/payments/{p2_id}/reverse", json={"reason": "Wrong bank receipt entry"})
    assert rev_res.status_code == 201
    rev_data = rev_res.json()
    assert rev_data["reverses_id"] == p2_id

    # Check dashboard again -> status should dynamically revert back to partial, balance = 600.00!
    dash_res = client.get("/dashboard/students?term=2026-Term-1")
    stud = dash_res.json()["students"][0]
    assert Decimal(str(stud["balance"])) == Decimal("600.00")
    assert stud["status"] in ("part", "partial")
    assert Decimal(str(stud["total_paid"])) == Decimal("400.00")

    # 6. Attempting to reverse an already-reversed payment should fail
    dup_rev = client.post(f"/payments/{p2_id}/reverse")
    assert dup_rev.status_code == 400
    assert "already been reversed" in dup_rev.json()["detail"]

    # 7. Attempting to reverse a reversal entry should fail
    rev_rev = client.post(f"/payments/{rev_data['id']}/reverse")
    assert rev_rev.status_code == 400
    assert "already a reversal record" in rev_rev.json()["detail"]
