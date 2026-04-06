# 🦘 AU Payroll Platform

A production-grade, modular payroll system for Australia built as microservices.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend :3000                     │
└─────────────────────────────┬───────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                 API Gateway :8000  (FastAPI)                  │
│          JWT passthrough · CORS · Path routing               │
└──┬──────┬──────┬──────┬──────┬──────┬──────┬───────────────┘
   │      │      │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼      ▼
:8001  :8002  :8003  :8004  :8005  :8006  :8007
 EMP    TIME   PAY    COMP   PMTS   RPT    ORCH
 SVC    SVC    SVC    SVC    SVC    SVC    SVC
   │      │      │      │      │      │      │
   └──────┴──────┴──────┴──────┘      └──────┘
                  │                        │
          ┌───────▼───────┐        ┌───────▼───────┐
          │  PostgreSQL   │        │     Redis      │
          │  (6 schemas)  │        │   (optional)   │
          └───────────────┘        └───────────────┘
```

### Services

| Service | Port | Responsibility |
|---------|------|----------------|
| API Gateway | 8000 | Central entry point, JWT passthrough, routing |
| Employee Service | 8001 | Employee CRUD, user auth, TFN, bank details |
| Timesheet Service | 8002 | Hours capture, leave, approval workflow |
| Payroll Service | 8003 | Gross→net calc, PAYG, super, payslips |
| Compliance Service | 8004 | STP Phase 2, PAYG summaries, ATO simulation |
| Payments Service | 8005 | ABA file generation, super batch payments |
| Reporting Service | 8006 | CSV reports: payroll, tax, super |
| Integration Service | 8007 | Orchestration engine, workflow coordination |

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- (Optional) Python 3.11+ for running tests locally

### 1. Clone and configure

```bash
git clone <repo>
cd au-payroll
cp .env.example .env
# Edit .env if needed (defaults work for local dev)
```

### 2. Start all services

```bash
docker-compose up --build
```

First build takes 3–5 minutes. Subsequent starts are fast.

### 3. Seed the admin account

```bash
curl -X POST http://localhost:8000/api/auth/seed-admin
```

Returns: `{ "email": "admin@payroll.com.au", "password": "Admin1234!" }`

### 4. Open the frontend

Visit **http://localhost:3000** and log in with the seeded credentials.

---

## Running Tests

```bash
# Install test deps
pip install pytest

# Run payroll engine tests
cd tests
python -m pytest test_payroll.py -v
```

Expected: **15+ tests passing**

---

## API Documentation

Each service exposes Swagger UI:

| Service | Swagger URL |
|---------|------------|
| API Gateway | http://localhost:8000/docs |
| Employee | http://localhost:8001/docs |
| Timesheet | http://localhost:8002/docs |
| Payroll | http://localhost:8003/docs |
| Compliance | http://localhost:8004/docs |
| Payments | http://localhost:8005/docs |
| Reporting | http://localhost:8006/docs |
| Integration | http://localhost:8007/docs |

---

## Example API Workflow (cURL)

### Step 1: Login
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@payroll.com.au","password":"Admin1234!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

### Step 2: Create an Employee
```bash
curl -X POST http://localhost:8000/api/employees \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "employee_number": "E001",
    "first_name": "Sarah",
    "last_name": "Mitchell",
    "email": "sarah.mitchell@acme.com.au",
    "employment_type": "full_time",
    "pay_frequency": "fortnightly",
    "annual_salary": 95000,
    "super_fund_name": "AustralianSuper",
    "super_member_number": "12345678",
    "bank_bsb": "062-000",
    "bank_account_number": "123456789",
    "bank_account_name": "Sarah Mitchell",
    "start_date": "2024-01-01",
    "tax_free_threshold": true,
    "tfn": "123456789"
  }'
```

### Step 3: Create and Approve a Timesheet
```bash
# Create
curl -X POST http://localhost:8000/api/timesheets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "employee_id": "<EMPLOYEE_ID>",
    "period_start": "2024-01-15",
    "period_end": "2024-01-28",
    "ordinary_hours": 76,
    "overtime_hours_1_5x": 4,
    "sick_leave_hours": 0
  }'

# Submit (replace TIMESHEET_ID)
curl -X POST http://localhost:8000/api/timesheets/<TIMESHEET_ID>/submit \
  -H "Authorization: Bearer $TOKEN"

# Approve
curl -X POST http://localhost:8000/api/timesheets/<TIMESHEET_ID>/approve \
  -H "Authorization: Bearer $TOKEN"
```

### Step 4: Run Payroll (Full Orchestration)
```bash
curl -X POST http://localhost:8000/api/orchestrate/full-payroll-run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "run_name": "Fortnight 1 - Jan 2024",
    "period_start": "2024-01-15",
    "period_end": "2024-01-28",
    "pay_date": "2024-01-31",
    "pay_frequency": "fortnightly",
    "employer_abn": "12345678901",
    "employer_name": "ACME PTY LTD",
    "generate_aba": true,
    "generate_super_batch": true
  }'
```

Response includes: payroll run ID, ABA batch ID, super batch ID, STP submission ID.

### Step 5: Download ABA File
```bash
curl -O http://localhost:8000/api/payment-batches/<BATCH_ID>/aba \
  -H "Authorization: Bearer $TOKEN"
```

### Step 6: Submit to ATO (simulated)
```bash
curl -X POST http://localhost:8000/api/stp/<SUBMISSION_ID>/submit \
  -H "Authorization: Bearer $TOKEN"
```

---

## Australian Payroll Logic

### PAYG Withholding
- Based on ATO 2023-24 tax tables (Scale 1 & 2)
- Formula method: `tax = (a × weekly_earnings) − b`
- Supports: residents with/without TFT, non-residents
- Medicare levy: 2% on income above $26,000

### Superannuation
- Super Guarantee rate: **11%** (from 1 July 2023)
- Applied on Ordinary Time Earnings (OTE)
- Excludes overtime from super base
- SuperStream-compatible batch format

### Leave Types
- Annual Leave (at ordinary rate)
- Sick/Personal Leave (at ordinary rate)
- Long Service Leave (at ordinary rate)
- Unpaid Leave (excluded from calculations)
- Public Holidays (2.25× loading)

### STP Phase 2
- Income type classification (SAL, LAB, CLO)
- Disaggregated earnings reporting
- Year-to-date accumulators
- Mock ATO submission with reference number generation

### ABA File Format
- Descriptive Record (Type 0)
- Detail Records (Type 1) for each employee
- File Total Record (Type 7)
- Compatible with all major Australian banks

---

## Database Schema

Each service has its own database:

```
employee_db    → employees, users
timesheet_db   → timesheets, leave_requests
payroll_db     → payroll_runs, payslips, audit_logs
compliance_db  → stp_submissions, payg_summaries
payments_db    → payment_batches, payment_transactions, super_batches
reporting_db   → reports (metadata only)
```

---

## Security

- **JWT tokens** with configurable expiry (default: 8 hours)
- **Role-based access**: admin, payroll_officer, employee
- **Token passthrough**: gateway forwards Bearer token to all services
- **TFN masking**: Tax File Numbers masked in PAYG summaries

### Default Roles

| Role | Permissions |
|------|------------|
| admin | Full access: create/delete employees, approve, run payroll, view all |
| payroll_officer | Create employees, manage timesheets, run payroll, compliance |
| employee | View own timesheets and payslips only |

---

## Extending the Platform

### Adding a new service
1. Create `/services/my-service/main.py`
2. Add a `Dockerfile` (copy from any existing service)
3. Add to `docker-compose.yml`
4. Add route prefix to `api-gateway/main.py` SERVICES dict
5. Add nav link in `frontend/src/App.js`

### Updating tax tables
Edit `services/payroll-service/tax_engine.py`:
```python
RESIDENT_TFT_WEEKLY = [
    # (weekly_earnings_ceiling, coefficient_a, coefficient_b)
    ...  # Update with new ATO tax tables each July
]
SUPER_GUARANTEE_RATE = 0.115  # Update each year
```

### Production deployment
1. Replace `docker-compose.yml` with Kubernetes manifests
2. Use managed PostgreSQL (AWS RDS, GCP Cloud SQL)
3. Set `JWT_SECRET_KEY` to a cryptographically random 64-char string
4. Enable HTTPS via load balancer / ingress
5. Configure proper CORS origins (not `*`)
6. Encrypt TFN field with KMS before storage

---

## Project Structure

```
au-payroll/
├── docker-compose.yml
├── .env.example
├── shared/
│   ├── auth.py              # JWT utilities
│   └── models.py            # Shared Pydantic models
├── api-gateway/
│   └── main.py              # Central router
├── services/
│   ├── employee-service/
│   │   └── main.py          # Employee CRUD + auth
│   ├── timesheet-service/
│   │   └── main.py          # Hours & leave
│   ├── payroll-service/
│   │   ├── main.py          # Payroll runs & payslips
│   │   └── tax_engine.py    # AU tax calculation engine
│   ├── compliance-service/
│   │   └── main.py          # STP Phase 2 + PAYG
│   ├── payments-service/
│   │   └── main.py          # ABA files + super batches
│   ├── reporting-service/
│   │   └── main.py          # CSV reports
│   └── integration-service/
│       └── main.py          # Orchestration engine
├── frontend/
│   ├── public/index.html
│   └── src/
│       ├── App.js           # Router + auth context
│       ├── index.js
│       └── pages/
│           ├── Login.js
│           ├── Dashboard.js
│           ├── Employees.js
│           ├── Timesheets.js
│           ├── PayrollRun.js
│           ├── Payslips.js
│           ├── Compliance.js
│           └── Reports.js
├── tests/
│   └── test_payroll.py      # Payroll engine tests
└── scripts/
    └── init-dbs.sql         # PostgreSQL database init
```
