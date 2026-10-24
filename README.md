# School Fee Management System

An offline-first, dual-node school fee management API built with **FastAPI**, **SQLite** (local), and **PostgreSQL** (cloud).

```
Local FastAPI + SQLite  <-- sync -->  Cloud FastAPI + Postgres  <-- Hubtel callback
```

- **API only**: Swagger docs at `http://localhost:8000/docs` serve as the interface.
- **Offline First**: The local node handles cash and manual bank entries offline at the school.
- **Hubtel Online Webhook**: Hits the cloud node, which records the payment. The local node pulls it down on the next sync.
- **Append-Only Payments**: Payments are never modified or deleted. Any mistake creates a reversing row (`reverses_id`).
- **Dynamic Balance Calculation**:
  `Balance = Fee for student's class and term - sum of active payments`
  - `paid`: `Balance <= 0`
  - `partial`: `0 < Balance < Fee`
  - `unpaid`: `Balance == Fee` (or no payment made)
- **Client UUIDs**: All records use UUIDv4 generated on creation to prevent offline key collisions.

---

## 1. Quick Start

### Step 1: Activate Environment & Dependencies
The Python virtual environment is already created in `.venv`.
```powershell
.\.venv\Scripts\Activate.ps1
```

### Step 2: Seed Demo Data
Populate classes (Grade 1, Grade 2, JHS 1), fees, students, and sample payments:
```powershell
.\.venv\Scripts\python.exe scripts\seed_demo_data.py
```

### Step 3: Start the Local Node
```powershell
.\run_local.ps1
# or: .\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open your browser to:
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

---

## 2. API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/classes` | Create a class (UUID auto-generated) |
| `GET` | `/classes` | List all classes |
| `POST` | `/fees` | Define term fees for a class |
| `GET` | `/fees` | List fees (filter by `class_id` or `term`) |
| `POST` | `/students` | Register student (unique `admission_no`) |
| `GET` | `/students` | List students (search with `?q=`, filter with `?class_id=`) |
| `POST` | `/payments` | Record offline cash or bank payment |
| `POST` | `/payments/{id}/reverse` | Reverse an erroneous payment (append-only) |
| `GET` | `/payments` | List payments for a student or term |
| `POST` | `/payments/hubtel/initiate` | Initiate mobile money prompt for parent |
| `POST` | `/payments/hubtel/callback` | Webhook receiver (cloud only, idempotent on reference) |
| `GET` | `/dashboard/students` | **Live financial dashboard**: `?class_id=&term=&status=paid\|partial\|unpaid&sort=balance:desc&q=` |
| `POST` | `/sync/push` | Cloud endpoint to receive offline mutations |
| `GET` | `/sync/pull` | Cloud endpoint returning updates since timestamp |
| `POST` | `/sync/trigger` | Local one-click trigger to push pending records and pull cloud updates |

---

## 3. Running Automated Tests

Run the full pytest suite:
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

All 7 test suites verify:
- Class and student creation with client UUID generation.
- Dynamic balance calculation across partial payment, full payment, and overpayment.
- Append-only payment reversals.
- Dashboard filtering (`status=paid`, `status=partial`, `status=unpaid`, `sort=balance:desc`).
- Hubtel callback idempotency and cloud-only gating.
- Dual-node sync push and pull reconciliation.
