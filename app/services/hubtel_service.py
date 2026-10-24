import uuid
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional
import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.config import settings
from app.models.payment import PaymentModel
from app.models.school import StudentModel
from app.models.sync import SyncLogModel
from app.schemas.payment import (
    HubtelInitiateRequest,
    HubtelInitiateResponse,
    HubtelCallbackPayload
)

HUBTEL_INITIATE_URL = "https://payproxyapi.hubtel.com/items/initiate"
HUBTEL_STATUS_URL = "https://api-txnstatus.hubtel.com/transactions/{account}/status"


def sanitize_description(desc: str) -> str:
    """Removes special characters not accepted by Hubtel."""
    return re.sub(r"[^a-zA-Z0-9\s\-_.,]", "", desc)[:100]


def initiate_hubtel_payment(
    db: Session,
    request: HubtelInitiateRequest
) -> HubtelInitiateResponse:
    """
    Initiates an Online Checkout session with Hubtel.
    - Generates clientReference <= 32 chars.
    - In Sandbox: returns a simulated checkout URL and logs intent.
    - In Live: calls POST https://payproxyapi.hubtel.com/items/initiate with Basic Auth.
    """
    student = db.get(StudentModel, request.student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student '{request.student_id}' not found"
        )

    # 1. Generate clientReference (Hubtel max 32 chars constraint)
    # E.g. "HUB" + 20 hex chars = 23 characters total
    client_ref = f"HUB{uuid.uuid4().hex[:20]}"

    # 2. Store checkout intent in sync_log so the webhook callback can resolve student_id and term
    intent_log = SyncLogModel(
        table="hubtel_intents",
        row_id=client_ref,
        action="INITIATE",
        payload={
            "client_reference": client_ref,
            "student_id": student.id,
            "admission_no": student.admission_no,
            "student_name": student.name,
            "term": request.term,
            "amount": str(request.amount),
            "phone": request.customer_phone
        },
        synced=True,
        created_at=datetime.now(timezone.utc)
    )
    db.add(intent_log)
    db.commit()

    # 3. Sandbox mode simulation
    if settings.HUBTEL_SANDBOX:
        return HubtelInitiateResponse(
            status="Initiated",
            checkout_url=f"https://sandbox.hubtel.com/checkout/{client_ref}",
            checkout_direct_url=f"https://sandbox.hubtel.com/checkout/{client_ref}/direct",
            checkout_id=uuid.uuid4().hex,
            client_reference=client_ref,
            message=f"Sandbox checkout initiated for {student.name}. Amount: GHS {request.amount}"
        )

    # 4. Live Hubtel API Call
    payload = {
        "totalAmount": float(request.amount),
        "description": sanitize_description(request.description or f"Fees for {student.name}"),
        "callbackUrl": settings.HUBTEL_CALLBACK_URL,
        "returnUrl": settings.HUBTEL_RETURN_URL,
        "cancellationUrl": settings.HUBTEL_CANCELLATION_URL,
        "merchantAccountNumber": settings.HUBTEL_MERCHANT_ACCOUNT_NUMBER,
        "clientReference": client_ref,
        "payeeName": student.name,
        "payeeMobileNumber": request.customer_phone
    }

    auth = (settings.HUBTEL_CLIENT_ID, settings.HUBTEL_CLIENT_SECRET)

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                HUBTEL_INITIATE_URL,
                json=payload,
                auth=auth,
                headers={"Content-Type": "application/json", "Accept": "application/json"}
            )

        if resp.status_code in [200, 201]:
            data = resp.json()
            if data.get("status") == "Success" or data.get("responseCode") == "0000":
                hubtel_data = data.get("data", {})
                return HubtelInitiateResponse(
                    status="Success",
                    checkout_url=hubtel_data.get("checkoutUrl"),
                    checkout_direct_url=hubtel_data.get("checkoutDirectUrl"),
                    checkout_id=hubtel_data.get("checkoutId"),
                    client_reference=client_ref,
                    message="Checkout session successfully created"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Hubtel error: {data.get('message', 'Failed to initiate payment')}"
                )
        else:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Hubtel API returned status {resp.status_code}: {resp.text}"
            )

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Network error communicating with Hubtel: {str(exc)}"
        )


def process_hubtel_callback(
    db: Session,
    payload: HubtelCallbackPayload
) -> Dict[str, Any]:
    """
    Cloud-only callback handler matching Hubtel's official webhook specification.
    Extracts payment info, checks idempotency on client reference, and records payment.
    """
    if settings.NODE_TYPE != "cloud":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hubtel callback can only be processed on the Cloud node"
        )

    # 1. Extract ClientReference
    client_ref = payload.ClientReference
    if not client_ref and payload.Data:
        client_ref = payload.Data.get("ClientReference")

    if not client_ref:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing ClientReference in callback payload"
        )

    # 2. Idempotency Check: if payment with this reference already exists, return immediately
    existing_payment = db.execute(
        select(PaymentModel).where(PaymentModel.reference == client_ref)
    ).scalar_one_or_none()

    if existing_payment:
        return {
            "ResponseCode": "0000",
            "Status": "Success",
            "status": "already_processed",
            "message": "Payment already recorded",
            "payment_id": existing_payment.id,
            "reference": existing_payment.reference
        }

    # 3. Check Success status (ResponseCode "0000" or Status "Success")
    status_text = payload.Status
    if payload.Data and "Status" in payload.Data:
        status_text = payload.Data.get("Status")

    resp_code = payload.ResponseCode
    is_success = (str(resp_code) == "0000") or (str(status_text).lower() in ["success", "paid"])

    if not is_success:
        return {
            "ResponseCode": "0000",
            "Status": "Ignored",
            "status": "ignored",
            "message": f"Payment status '{status_text}' was not successful"
        }

    # 4. Extract Amount
    amount = payload.Amount
    if amount is None and payload.Data:
        amount = Decimal(str(payload.Data.get("Amount", "0.00")))
    amount = Decimal(str(amount or "0.00"))

    # 5. Resolve Student & Term from stored initiate intent or callback Data
    student_id = None
    term = None

    # Check CustomData if passed
    if payload.Data and "CustomData" in payload.Data:
        custom_data = payload.Data.get("CustomData", {})
        student_id = custom_data.get("student_id")
        term = custom_data.get("term")

    # Look up initiate intent from sync_log
    if not student_id or not term:
        intent = db.execute(
            select(SyncLogModel).where(
                SyncLogModel.table == "hubtel_intents",
                SyncLogModel.row_id == client_ref
            )
        ).scalar_one_or_none()

        if intent and intent.payload:
            student_id = intent.payload.get("student_id")
            term = intent.payload.get("term")

    # Fallback: check student by admission_no prefix from reference (HUB-ADM...)
    if not student_id or not term:
        parts = client_ref.split("-")
        if len(parts) >= 2:
            adm_prefix = parts[1]
            stud = db.execute(
                select(StudentModel).where(StudentModel.admission_no.like(f"{adm_prefix}%"))
            ).scalars().first()
            if stud:
                student_id = stud.id
                term = term or "Current-Term"

    if not student_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to determine student_id from callback or initiate intent"
        )

    # 6. Record append-only payment
    payment_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    payment = PaymentModel(
        id=payment_id,
        student_id=student_id,
        term=term or "Current-Term",
        amount=amount,
        method="hubtel",
        reference=client_ref,
        paid_at=now,
        reverses_id=None,
        created_at=now
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    return {
        "ResponseCode": "0000",
        "Status": "Success",
        "status": "recorded",
        "payment_id": payment.id,
        "reference": payment.reference,
        "amount": str(payment.amount)
    }


def check_hubtel_transaction_status(
    db: Session,
    client_reference: str
) -> Dict[str, Any]:
    """
    Calls Hubtel's Transaction Status Check API:
    GET https://api-txnstatus.hubtel.com/transactions/{account}/status?clientReference={clientReference}
    Used when a callback is delayed or needs manual status verification.
    """
    account_number = settings.HUBTEL_MERCHANT_ACCOUNT_NUMBER
    if not account_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HUBTEL_MERCHANT_ACCOUNT_NUMBER is not configured"
        )

    if settings.HUBTEL_SANDBOX:
        # Check if payment already exists
        existing = db.execute(
            select(PaymentModel).where(PaymentModel.reference == client_reference)
        ).scalar_one_or_none()
        return {
            "client_reference": client_reference,
            "status": "Paid" if existing else "Unpaid",
            "message": "Sandbox status check response"
        }

    url = HUBTEL_STATUS_URL.format(account=account_number)
    auth = (settings.HUBTEL_CLIENT_ID, settings.HUBTEL_CLIENT_SECRET)

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, params={"clientReference": client_reference}, auth=auth)

        if resp.status_code == 200:
            data = resp.json()
            txn_data = data.get("data", {})
            txn_status = txn_data.get("status")  # "Paid", "Unpaid", "Refunded"

            # If status is "Paid" and not yet in our database, record it!
            if txn_status == "Paid":
                existing = db.execute(
                    select(PaymentModel).where(PaymentModel.reference == client_reference)
                ).scalar_one_or_none()
                if not existing:
                    # Find intent to get student_id & term
                    intent = db.execute(
                        select(SyncLogModel).where(
                            SyncLogModel.table == "hubtel_intents",
                            SyncLogModel.row_id == client_reference
                        )
                    ).scalar_one_or_none()
                    if intent and intent.payload:
                        payment = PaymentModel(
                            id=str(uuid.uuid4()),
                            student_id=intent.payload["student_id"],
                            term=intent.payload["term"],
                            amount=Decimal(str(txn_data.get("amount", intent.payload["amount"]))),
                            method="hubtel",
                            reference=client_reference,
                            paid_at=datetime.now(timezone.utc),
                            created_at=datetime.now(timezone.utc)
                        )
                        db.add(payment)
                        db.commit()

            return data
        else:
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"Hubtel Status API returned {resp.status_code}: {resp.text}"
            )

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Network error querying Hubtel status: {str(exc)}"
        )
