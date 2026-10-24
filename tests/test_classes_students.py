import uuid


def test_create_and_list_classes(client):
    res = client.post("/classes", json={"name": "Grade 1"})
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Grade 1"
    assert "id" in data
    assert len(data["id"]) == 36  # UUID length

    # List classes
    list_res = client.get("/classes")
    assert list_res.status_code == 200
    classes = list_res.json()
    assert len(classes) == 1
    assert classes[0]["name"] == "Grade 1"


def test_create_and_list_students(client):
    # 1. Create class
    class_res = client.post("/classes", json={"name": "Grade 2"})
    class_id = class_res.json()["id"]

    # 2. Create student
    stud_payload = {
        "admission_no": "ADM-001",
        "name": "Kofi Mensah",
        "guardian_phone": "0244123456",
        "class_id": class_id,
        "status": "active"
    }
    stud_res = client.post("/students", json=stud_payload)
    assert stud_res.status_code == 201
    stud_data = stud_res.json()
    assert stud_data["name"] == "Kofi Mensah"
    assert stud_data["admission_no"] == "ADM-001"
    assert stud_data["class_id"] == class_id

    # 3. Duplicate admission_no should fail
    dup_res = client.post("/students", json=stud_payload)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"]

    # 4. List students
    list_res = client.get("/students")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    # 5. Search students with q
    search_res = client.get("/students?q=Mensah")
    assert search_res.status_code == 200
    assert len(search_res.json()) == 1

    no_match = client.get("/students?q=NonExistent")
    assert no_match.status_code == 200
    assert len(no_match.json()) == 0


def test_get_student_payments(client):
    # 1. Setup class and student
    class_res = client.post("/classes", json={"name": "JHS 1"})
    class_id = class_res.json()["id"]

    stud_res = client.post("/students", json={
        "admission_no": "JHS-001",
        "name": "Yaw Mensah",
        "guardian_phone": "0240000000",
        "class_id": class_id
    })
    student_id = stud_res.json()["id"]

    # 2. Record payment
    pay_res = client.post("/payments", json={
        "student_id": student_id,
        "term": "Term-1",
        "amount": 500.0,
        "method": "cash"
    })
    assert pay_res.status_code == 201

    # 3. Fetch student payments
    history_res = client.get(f"/students/{student_id}/payments")
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) == 1
    assert history[0]["amount"] == 500.0
    assert history[0]["status"] == "active"
    assert "receipt_no" in history[0]
