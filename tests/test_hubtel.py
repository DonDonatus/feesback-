from decimal import Decimal
from app.config import settings


def test_hubtel_initiate(client):
    # Setup student
    c = client.post("/classes", json={"name": "KG 1"}).json()
    s = client.post("/students", json={
        "admission_no": "KG-01", "name": "Akosua Baby", "guardian_phone": "0541112233", "class_id": c["id"]
    }).json()

    res = client.post("/payments/hubtel/initiate", json={
        "student_id": s["id"],
        "term": "Term-1",
        "amount": 250.00,
        "customer_phone": "0541112233",
        "description": "KG 1 School Fees"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "Initiated"
    assert data["client_reference"].startswith("HUB")
    assert len(data["client_reference"]) <= 32  # Hubtel max 32 chars rule
    assert "checkout_url" in data
    assert "checkout_id" in data


def test_hubtel_callback_cloud_only_and_idempotency(client):
    # Setup student
    c = client.post("/classes", json={"name": "KG 2"}).json()
    s = client.post("/students", json={
        "admission_no": "KG-02", "name": "Yaw Baby", "guardian_phone": "0549998877", "class_id": c["id"]
    }).json()

    # 1. Initiate to store intent
    init_res = client.post("/payments/hubtel/initiate", json={
        "student_id": s["id"],
        "term": "Term-1",
        "amount": 300.00,
        "customer_phone": "0549998877"
    }).json()
    client_ref = init_res["client_reference"]

    # Official Hubtel callback payload structure
    callback_payload = {
        "ResponseCode": "0000",
        "Status": "Success",
        "Data": {
            "CheckoutId": "59e2fbbff4e443b98e09346881ac7e9a",
            "SalesInvoiceId": "e96ccfb4746045bba13f425bd573a31c",
            "ClientReference": client_ref,
            "Status": "Success",
            "Amount": 300.0,
            "CustomerPhoneNumber": "233549998877",
            "Description": "The MTN Mobile Money payment has been approved."
        }
    }

    # 2. On local node, callback should be rejected with 403
    settings.NODE_TYPE = "local"
    res_local = client.post("/payments/hubtel/callback", json=callback_payload)
    assert res_local.status_code == 403
    assert "Cloud node" in res_local.json()["detail"]

    # 3. On cloud node, callback should succeed
    settings.NODE_TYPE = "cloud"
    res_cloud = client.post("/payments/hubtel/callback", json=callback_payload)
    assert res_cloud.status_code == 200
    cloud_data = res_cloud.json()
    assert cloud_data["status"] == "recorded"
    assert cloud_data["reference"] == client_ref

    # 4. Repeat identical callback -> Idempotent response, no duplicate payment
    res_repeat = client.post("/payments/hubtel/callback", json=callback_payload)
    assert res_repeat.status_code == 200
    repeat_data = res_repeat.json()
    assert repeat_data["status"] == "already_processed"
    assert repeat_data["payment_id"] == cloud_data["payment_id"]

    # Verify payments table only has 1 payment
    pay_list = client.get(f"/payments?student_id={s['id']}")
    pay_json = pay_list.json()
    items = pay_json["items"] if isinstance(pay_json, dict) else pay_json
    assert len(items) == 1

    # 5. Check status endpoint
    status_res = client.get(f"/payments/hubtel/status/{client_ref}")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "Paid"

    # Restore node type
    settings.NODE_TYPE = "local"
