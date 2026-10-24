from decimal import Decimal


def test_dashboard_filtering_and_sorting(client):
    # Setup 1 class, 3 students, 1 fee
    c = client.post("/classes", json={"name": "JHS 1"}).json()
    c_id = c["id"]

    client.post("/fees", json={"class_id": c_id, "term": "Term-1", "amount": 500.00})

    s1 = client.post("/students", json={
        "admission_no": "J1", "name": "Kwame Paid", "guardian_phone": "0201", "class_id": c_id
    }).json()

    s2 = client.post("/students", json={
        "admission_no": "J2", "name": "Abena Partial", "guardian_phone": "0202", "class_id": c_id
    }).json()

    s3 = client.post("/students", json={
        "admission_no": "J3", "name": "Yaw Unpaid", "guardian_phone": "0203", "class_id": c_id
    }).json()

    # S1 pays 500 (paid)
    client.post("/payments", json={"student_id": s1["id"], "term": "Term-1", "amount": 500.00})
    # S2 pays 200 (partial)
    client.post("/payments", json={"student_id": s2["id"], "term": "Term-1", "amount": 200.00})
    # S3 pays 0 (unpaid)

    # Filter status=paid
    res_paid = client.get("/dashboard/students?term=Term-1&status=paid").json()
    assert len(res_paid["students"]) == 1
    assert res_paid["students"][0]["admission_no"] == "J1"

    # Filter status=partial
    res_part = client.get("/dashboard/students?term=Term-1&status=partial").json()
    assert len(res_part["students"]) == 1
    assert res_part["students"][0]["admission_no"] == "J2"

    # Filter status=unpaid
    res_unpaid = client.get("/dashboard/students?term=Term-1&status=unpaid").json()
    assert len(res_unpaid["students"]) == 1
    assert res_unpaid["students"][0]["admission_no"] == "J3"

    # Sort balance:desc -> S3 (500), S2 (300), S1 (0)
    res_sort = client.get("/dashboard/students?term=Term-1&sort=balance:desc").json()
    balances = [Decimal(str(s["balance"])) for s in res_sort["students"]]
    assert balances == [Decimal("500.00"), Decimal("300.00"), Decimal("0.00")]

    # Check summary totals
    summary = res_sort["summary"]
    assert summary["total_students"] == 3
    assert Decimal(str(summary["total_fees_expected"])) == Decimal("1500.00")
    assert Decimal(str(summary["total_fees_collected"])) == Decimal("700.00")
    assert Decimal(str(summary["total_outstanding_balance"])) == Decimal("800.00")
    assert summary["paid_count"] == 1
    assert summary["partial_count"] == 1
    assert summary["unpaid_count"] == 1


def test_dashboard_summary_and_today(client):
    # Setup class, student, fee
    c = client.post("/classes", json={"name": "Class 1"}).json()
    client.post("/fees", json={"class_id": c["id"], "term": "Term-1", "amount": 1000.00})
    s = client.post("/students", json={"admission_no": "C1-01", "name": "Akosua", "guardian_phone": "0240", "class_id": c["id"]}).json()

    # Record payment
    client.post("/payments", json={"student_id": s["id"], "term": "Term-1", "amount": 400.00, "method": "cash"})

    # Check /dashboard/summary
    summary_res = client.get("/dashboard/summary?term=Term-1")
    assert summary_res.status_code == 200
    s_data = summary_res.json()
    assert s_data["expected"] == 1000.0
    assert s_data["collected"] == 400.0
    assert s_data["outstanding"] == 600.0
    assert s_data["collection_rate"] == 40
    assert s_data["part_count"] == 1
    assert s_data["paid_count"] == 0
    assert s_data["owing_count"] == 0

    # Check /dashboard/today
    today_res = client.get("/dashboard/today?term=Term-1")
    assert today_res.status_code == 200
    t_data = today_res.json()
    assert t_data["collected_today"] == 400.0
    assert t_data["payment_count"] == 1
    assert len(t_data["by_method"]) > 0
    cash_method = next((m for m in t_data["by_method"] if m["method"] == "Cash"), None)
    assert cash_method is not None
    assert cash_method["amount"] == 400.0
