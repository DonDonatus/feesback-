# School Fee Management System (Backend API)

The backend service for the **School Fees Management System** (powering the `fees` Next.js frontend). Built with **FastAPI**, **SQLAlchemy 2.0**, and configured for both offline-first local deployment (**SQLite**) and cloud deployment (**Render + Supabase PostgreSQL**).

---

## 1. Architectural Highlights

- **Designed for School Operations:** Serves the Next.js staff interface (`fees`) used by the Bursar, Headteacher/Admin, and Accounts Clerks.
- **Cash & Bank First:** Primary day-to-day operations focus on in-person **Cash** and **Bank slip/deposit** entries with automatic receipt generation (`REC-2026-XXXX`). *(External Mobile Money/Hubtel webhook endpoints exist strictly as optional/dormant stubs and are not required for core operations).*
- **Append-Only Financial Integrity:** Payment records are strictly immutable. Corrections or bounced cheques are handled by creating offsetting reversal entries (`reverses_id`) that track who reversed the payment and why.
- **Dynamic Balance Calculation:** Nothing is hardcoded or stored in student records; student balances and statuses are computed on the fly:
  $$\text{Balance} = \text{Fee for Class \& Term} - (\sum \text{Active Payments})$$
  - `paid`: $\text{Balance} \le 0$ (including overpayments)
  - `part`: $0 < \text{Balance} < \text{Fee}$
  - `owing`: $\text{Balance} = \text{Fee}$ (no active payments made)
- **PIN-Based Staff Identity:** Role-based access control (`admin`, `bursar`, `clerk`) authenticated via 4-digit numeric PINs for fast, terminal-friendly school logins.
- **Idempotency Guard:** `POST /payments` accepts a client-generated `client_id` UUID to prevent double submissions from network glitches or accidental double clicks.

---

## 2. Tech Stack

- **Framework:** FastAPI (Python 3.11+)
- **ORM / Database:** SQLAlchemy 2.0
  - Local: SQLite (`data/local.db`)
  - Cloud: PostgreSQL (Supabase / Render) via `psycopg`
- **Authentication:** Bearer token session with 4-digit PIN verification
- **Validation & Serialization:** Pydantic v2
- **Testing:** `pytest` + Starlette TestClient (11 test suites covering 100% of frontend contracts)

---

## 3. Quick Start (Local Development)

### Step 1: Virtual Environment
The virtual environment is in `.venv`:
```powershell
.\.venv\Scripts\Activate.ps1
```

### Step 2: Seed Demo Data
Seed default staff users (`Akua Mensah`, `Kwame Asante`, `Abena Osei`), all 11 classes (`KG 1` to `JHS 3`), student enrollment, and sample fee payments:
```powershell
.\.venv\Scripts\python.exe scripts\seed_demo_data.py
```

### Step 3: Start the Backend Server
```powershell
.\run_local.ps1
# or: .\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```
Swagger UI interactive docs:
👉 **[http://localhost:8000/docs](http://localhost:8000/docs)**

---

## 4. Default Staff Credentials (Demo / Seed)

| Staff Member | Role | User ID | PIN | Permissions |
| :--- | :--- | :--- | :--- | :--- |
| **Akua Mensah** | Bursar | `usr_1` | `1234` | Full access, Record Payments, Reverse Payments, Daily Reports |
| **Kwame Asante** | Admin | `usr_2` | `5678` | Full access, Audit Logs, Reversals, Settings |
| **Abena Osei** | Clerk | `usr_3` | `4321` | Record Payments, View Students (No reversals) |

---

## 5. API Endpoints

### Authentication & Staff
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/auth/login` | Authenticate with `{ user_id, pin }` $\rightarrow$ returns `{ token, user }` |
| `GET` | `/auth/me` | Fetch active user session |
| `GET` | `/users` | List staff members (`id`, `name`) for login selector |

### Financial Dashboard
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/dashboard/summary` | Top-level summary cards (Expected, Collected, Outstanding, Collection rate, status counts) |
| `GET` | `/dashboard/today` | Today's collections breakdown by method (Cash, Bank) and by cashier |
| `GET` | `/dashboard/students` | Filterable, sortable, paginated student roster with dynamic balance & status |

### Payments & Student History
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/payments` | Record payment (Cash / Bank) with receipt generation & idempotency |
| `GET` | `/payments` | Filterable payment audit log (search by student, cashier, date, status) |
| `GET` | `/students/{id}/payments` | Full chronological payment & reversal history for a student |
| `POST` | `/payments/{id}/reverse` | Reverse a payment (creates reversing entry; captures user & reason) |

### Academic & Student Records
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/classes` | List all school classes (KG 1 – JHS 3) |
| `POST` | `/classes` | Create a new class |
| `GET` | `/students` | List/search students by name or admission number |
| `POST` | `/students` | Register a new student |
| `GET` | `/fees` | Get term fee structures |
| `POST` | `/fees` | Define or update class term fees |

### Sync (Offline-to-Cloud)
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/sync/trigger` | Trigger push of local `sync_log` and pull cloud updates |
| `POST` | `/sync/push` | Cloud ingestion endpoint for offline mutation batches |
| `GET` | `/sync/pull` | Cloud endpoint returning mutations since timestamp |

---

## 6. Connecting the Next.js Frontend (`fees`)

1. In the frontend repo (`../fees`):
   Open `src/lib/api.ts` and set:
   ```typescript
   export const USE_MOCK = false;
   ```
2. Configure `.env.local` in `fees`:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```
3. Run `npm run dev` in `fees`. The frontend will now communicate directly with this FastAPI backend!

---

## 7. Deploying to Render

This repository includes a [`render.yaml`](render.yaml) blueprint and [`Procfile`](Procfile) for zero-config deployment to Render:

### Deploy Steps:
1. Push this repository to GitHub/GitLab:
   ```bash
   git remote add origin https://github.com/Softmind-Labs/fees_backend.git
   git push -u origin main
   ```
2. In the [Render Dashboard](https://dashboard.render.com):
   - Click **New +** $\rightarrow$ **Web Service**.
   - Connect the `fees_backend` repository.
   - **Environment:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Set the Environment Variables in Render:
   - `NODE_TYPE`: `cloud`
   - `DATABASE_URL`: Your Supabase PostgreSQL URL (e.g., from `.env.cloud`)
   - `CORS_ORIGINS`: `*` (or your production frontend URL)
   - `PYTHON_VERSION`: `3.11.9`
4. Once deployed, set your frontend's `NEXT_PUBLIC_API_URL` to your Render URL:
   ```env
   NEXT_PUBLIC_API_URL=https://fees-backend.onrender.com
   ```

---

## 8. Automated Testing

Run the complete test suite:
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

All 7 test suites verify:
- PIN authentication, token issuance, and session lookup.
- Class and student enrollment with client-side UUID generation.
- Dynamic balance calculation (partial payment, full payment, overpayment).
- Append-only payment reversals and balance restoration.
- Dashboard summary cards, today's cashier breakdown, and student pagination.
- Full 12-contract integration suite matching the Next.js frontend.
