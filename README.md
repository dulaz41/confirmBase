# ConfirmBase Waitlist Backend API

A high-performance, secure, and privacy-focused waitlist backend API built with **Python 3.12+**, **FastAPI**, **SQLAlchemy 2.x**, and **PostgreSQL** for **ConfirmBase** ("Only see the houses worth inspecting").

The backend powers the ConfirmBase landing page to collect, normalize, and securely store early access requests from both **tenants** (budget, timeframe, red flags, taste, areas) and **agents/landlords** (role, listings volume, areas). Contact information is deduplicated via normalized WhatsApp phone numbers and email addresses, with full CSV export and automated backup capabilities.

---

## 1. Table of Contents

- [Architecture & Design](#2-architecture--design)
- [Technology Stack](#3-technology-stack)
- [Project Structure](#4-project-structure)
- [Environment Variables](#5-environment-variables)
- [Local Development Setup](#6-local-development-setup)
- [Database Migrations](#7-database-migrations)
- [Running Automated Tests](#8-running-automated-tests)
- [Running with Docker & Docker Compose](#9-running-with-docker--docker-compose)
- [API Reference](#10-api-reference)
  - [Public Endpoints](#public-endpoints)
  - [Health & Readiness Probes](#health--readiness-probes)
  - [Protected Admin Endpoints](#protected-admin-endpoints)
- [CSV Export & Formula Injection Defense](#11-csv-export--formula-injection-defense)
- [Automated 24-Hour Backup System](#12-automated-24-hour-backup-system)
  - [PostgreSQL Backups](#postgresql-database-backup)
  - [CSV Snapshots](#csv-snapshot-backup)
  - [Retention & Encryption](#retention-policy--encryption)
  - [Restore Procedure](#backup-restore-procedure)
- [Transactional Confirmation Emails](#13-transactional-confirmation-emails)
  - [Provider Options & Switching](#provider-options--how-to-switch)
  - [HTML & Plain-Text Templates](#email-templates)
  - [Non-Blocking Background Dispatch](#asynchronous-background-dispatch)
- [Security & Rate Limiting](#14-security--rate-limiting)
- [Data Minimization & Privacy](#15-data-minimization--privacy)
- [Production Deployment Checklist](#16-production-deployment-checklist)

---

## 2. Architecture & Design

The backend establishes PostgreSQL as the single, authoritative source of truth. The application layer enforces strict payload validation, whitespace trimming, case-insensitivity, and concurrency safety.

```text
                  ┌─────────────────┐
                  │ Frontend / User │
                  └────────┬────────┘
                           │ POST /api/v1/waitlist
                           ▼
                  ┌─────────────────┐
                  │ FastAPI Backend │
                  │ ─────────────── │
                  │ • Rate Limiter  │
                  │ • Size Guard    │
                  │ • Normalizer    │
                  │ • Security Hdr  │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │   PostgreSQL    │
                  │ Source of Truth │
                  │ (Unique Index)  │
                  └────────┬────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
      Protected CSV Export       Automated Backups
      (Formula-Sanitized)        (DB Dump + CSV)
              │                         │
              ▼                         ▼
      Email Marketing           Local / S3 Storage
```

### Concurrency & Duplicate Prevention

Duplicate checks in application logic alone are vulnerable to race conditions under concurrent submissions. To guarantee idempotency, a database-level `UNIQUE` constraint is enforced on `email_normalized`. If two identical requests occur concurrently, PostgreSQL rejects the second insertion, and the backend safely catches the constraint violation to return a standard success response without duplicating data.

---

## 3. Technology Stack

- **Runtime:** Python 3.12+
- **Web Framework:** [FastAPI](https://fastapi.tiangolo.com/) (Asynchronous ASGI)
- **Data Validation & Settings:** [Pydantic v2](https://docs.pydantic.dev/) and `pydantic-settings`
- **Database ORM:** [SQLAlchemy 2.x](https://docs.sqlalchemy.org/) (AsyncIO with `asyncpg`, synchronous driver support with `psycopg2-binary`)
- **Database Migrations:** [Alembic](https://alembic.sqlalchemy.org/)
- **Database:** [PostgreSQL 16](https://www.postgresql.org/)
- **Production Server:** Gunicorn with Uvicorn workers (`uvicorn.workers.UvicornWorker`)
- **Scheduler:** APScheduler (in-process 24h cron runner)
- **Encryption:** `cryptography` (Fernet symmetric encryption for backups)
- **Containerization:** Docker multi-stage build & Docker Compose

---

## 4. Project Structure

```text
waitlist-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # Application entry point, middlewares & lifespan
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py              # Dependency injection (Auth, Rate Limit, DB)
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── health.py        # /health and /ready probes
│   │       ├── waitlist.py      # Public waitlist registration
│   │       └── admin.py         # Admin export, stats, and delete
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # Pydantic BaseSettings environment config
│   │   ├── logging.py           # Structured JSON logging & audit logger
│   │   ├── middleware.py        # Security headers, size limiter, access logging
│   │   ├── rate_limit.py        # In-memory sliding window rate limiter
│   │   └── security.py          # Timing-safe constant-time Bearer token validator
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py          # Async engine, sessionmaker, and health checks
│   │   └── models.py            # SQLAlchemy 2.0 WaitlistEntry model
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── admin.py             # Admin response models
│   │   └── waitlist.py          # Pydantic v2 registration schemas
│   └── services/
│       ├── __init__.py
│       ├── backup_service.py    # Automated pg_dump, CSV snapshot & retention
│       ├── csv_service.py       # Safe CSV streaming & formula injection filter
│       └── waitlist_service.py  # Waitlist registration and duplicate handling
├── alembic/
│   ├── env.py                   # Alembic environment linked to app settings
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_waitlist.py # Initial migration for waitlist_entries
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # In-memory async SQLite fixtures and overrides
│   ├── test_backup.py           # Backup, retention, encryption & restore tests
│   ├── test_export.py           # CSV format & formula injection tests
│   ├── test_security.py         # Auth, headers, rate limit & size guard tests
│   └── test_waitlist.py         # Registration, duplicate & validation tests
├── scripts/
│   ├── backup.py                # Standalone backup execution script
│   ├── restore.py               # Database restore & integrity check utility
│   └── restore_backup.sh        # Shell restore runner
├── backups/
│   ├── .gitkeep
│   ├── csv/
│   └── postgres/
├── Dockerfile                   # Multi-stage non-root container configuration
├── docker-compose.yml           # Compose setup with PostgreSQL and healthchecks
├── requirements.txt             # Pinned production requirements
├── pyproject.toml               # Project metadata and test configuration
├── alembic.ini                  # Alembic migration configuration
├── .env.example                 # Environment template
├── .gitignore
└── README.md
```

---

## 5. Environment Variables

Create your local `.env` by copying `.env.example`:

```bash
cp .env.example .env
```

| Variable | Description | Default | Production Note |
|---|---|---|---|
| `APP_ENV` | Application environment (`development`, `production`, `testing`) | `development` | Set to `production` |
| `DEBUG` | Enable verbose debug logging | `false` | Must be `false` in production |
| `APP_PORT` | HTTP port to bind | `8000` | Typically `8000` behind reverse proxy |
| `DATABASE_URL` | Async PostgreSQL connection string | `postgresql+asyncpg://...` | Point to production DB |
| `SYNC_DATABASE_URL` | Sync PostgreSQL connection string (for Alembic & CLI) | `postgresql://...` | Point to production DB |
| `CORS_ALLOWED_ORIGINS` | Comma-separated list of permitted origins | `http://localhost:3000` | Wildcards (`*`) forbidden in production |
| `ADMIN_API_KEY` | Secret token for admin endpoints (`Authorization: Bearer <KEY>`) | Random string | Must be strong, minimum 16 chars |
| `WAITLIST_RATE_LIMIT` | Allowed requests per window for waitlist registrations | `10` | Tune based on expected traffic |
| `WAITLIST_RATE_WINDOW_SECONDS` | Sliding window in seconds for waitlist rate limiter | `60` | Default 60s |
| `ADMIN_RATE_LIMIT` | Allowed requests per window for admin operations | `30` | Default 30 |
| `ADMIN_RATE_WINDOW_SECONDS` | Sliding window in seconds for admin rate limiter | `60` | Default 60s |
| `MAX_REQUEST_BODY_SIZE_BYTES` | Maximum incoming payload size in bytes | `10240` (10KB) | Prevents DoS payload attacks |
| `BACKUP_SCHEDULE_HOUR_UTC` | UTC hour for 24-hour backup run | `2` | Runs at 02:00 UTC |
| `BACKUP_SCHEDULE_MINUTE_UTC` | UTC minute for 24-hour backup run | `0` | Runs at 02:00 UTC |
| `BACKUP_DIRECTORY` | Local filesystem path for backups | `backups` | Persistent volume in Docker |
| `BACKUP_RETENTION_DAYS` | Number of days to retain backups | `30` | Older files purged, newest preserved |
| `BACKUP_STORAGE` | Storage mode: `local` or `s3` | `local` | Set `s3` for off-site backup |
| `BACKUP_ENCRYPTION_KEY` | Optional 32-byte Fernet key for backup encryption | `""` | Keep separate from backups |

To generate a Fernet key for `BACKUP_ENCRYPTION_KEY`:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 6. Local Development Setup

### Prerequisites
- Python 3.10+ (Python 3.12 recommended)
- PostgreSQL (or use Docker Compose)

### 1. Clone & create virtual environment
```bash
git clone <repo-url> waitlist-backend
cd waitlist-backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate
```

### 2. Install dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your local PostgreSQL credentials
```

### 4. Run database migrations
```bash
alembic upgrade head
```

### 5. Start development server
```bash
uvicorn app.main:app --reload --port 8000
```
Open [http://localhost:8000/docs](http://localhost:8000/docs) to explore the interactive API documentation.

---

## 7. Database Migrations

Alembic manages all schema revisions. Never run direct `CREATE TABLE` commands in production.

- **Apply all pending migrations:**
  ```bash
  alembic upgrade head
  ```
- **Revert last migration:**
  ```bash
  alembic downgrade -1
  ```
- **Create a new migration after editing models:**
  ```bash
  alembic revision --autogenerate -m "describe_changes"
  ```

---

## 8. Running Automated Tests

The test suite runs using `pytest` and `httpx.AsyncClient` with an isolated in-memory SQLite database, requiring no external PostgreSQL instance:

```bash
pytest -v
```

The automated tests verify:
1. **Registration:** Valid email acceptance, syntax errors, empty strings, whitespace trimming, case-insensitive duplicates, and extra input rejection.
2. **Security:** Missing/invalid admin tokens, timing attack mitigation, security headers, rate limit thresholds (429), and size limit rejections (413).
3. **CSV Export:** Correct headers, UTF-8 output, spreadsheet formula injection neutralization (`=`, `+`, `-`, `@`), and administrative deletion.
4. **Backups:** Timestamped CSV generation, retention cleanup safety (never deleting the newest backup), Fernet encryption/decryption, and test database restore.

---

## 9. Running with Docker & Docker Compose

Docker Compose provisions both the PostgreSQL database and the FastAPI application in isolated, bridged containers.

### Quick Start with Docker Compose
```bash
# Build and start services in the background
docker compose up -d --build

# View logs
docker compose logs -f backend

# Verify health status
docker compose ps
```

The database container is connected via an internal Docker network and **not exposed to the public internet**. Only port `8000` is bound to the host.

---

## 10. API Reference & Swagger UI

Interactive Swagger documentation is available at **`/docs`** (and ReDoc at **`/redoc`**).
The Swagger documentation is organized into clean visual groups:
* **Tenant**: `POST /api/v1/waitlist/tenant` (budget, timeframe, red flags, taste)
* **Agent**: `POST /api/v1/waitlist/agent` (role, listings volume, areas)
* **Admin**: `GET /api/v1/admin/waitlist/export`, `GET /api/v1/admin/waitlist/stats`, `DELETE /api/v1/admin/waitlist/{id}`
* **Waitlist (Unified)**: `POST /api/v1/waitlist` (dynamic frontend forms)
* **Health**: `GET /health`, `GET /ready`

### Tenant Endpoints

#### Register as Tenant
```http
POST /api/v1/waitlist/tenant
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "Chidi Okonkwo",
  "phone": "08031234567",
  "email": "chidi@example.com",
  "areas": "Arab road, Chikakore, FO1",
  "budget": "₦500,000 – ₦1,000,000",
  "timing": "Within a month",
  "redflags": "Landlord in the Compound, Bad access road, No steady water",
  "taste": "A quiet street, tiled floors, space for a small garden"
}
```

### Agent Endpoints

#### Register as Agent / Landlord
```http
POST /api/v1/waitlist/agent
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "Grace Bello",
  "phone": "08099887766",
  "email": "grace@agency.ng",
  "role": "Agent",
  "areas": "Kubwa, Arab road",
  "listings": "4–10"
}
```

### Unified Waitlist Endpoint (Frontend Forms)

#### Join Waitlist (Dynamic Type)
```http
POST /api/v1/waitlist
Content-Type: application/json
```
Accepts either tenant or agent payload with `"type": "tenant"` or `"type": "agent"`.

- **200 OK** (Duplicate registration - idempotent):
  ```json
  {
    "success": true,
    "message": "This WhatsApp number is already on the waitlist."
  }
  ```

- **422 Unprocessable Entity** (Malformed or missing email):
  ```json
  {
    "success": false,
    "message": "Validation error: invalid request payload or fields.",
    "details": ["body -> email: value is not a valid email address"]
  }
  ```

- **429 Too Many Requests** (Rate limit exceeded):
  ```json
  {
    "success": false,
    "message": "Too many requests. Please try again later."
  }
  ```
  *Headers include `Retry-After: <seconds>`.*

---

### Health & Readiness Probes

#### Liveness Probe
```http
GET /health
```
Returns `{"status": "ok"}` with HTTP 200. Does not expose credentials, paths, or internals.

#### Readiness Probe
```http
GET /ready
```
Verifies active PostgreSQL database connectivity. Returns `200 OK` when ready, or `503 Service Unavailable` if the database is disconnected.

---

### Protected Admin Endpoints

All admin endpoints require authentication via Bearer token:
```http
Authorization: Bearer <ADMIN_API_KEY>
```

#### Export Waitlist CSV
```http
GET /api/v1/admin/waitlist/export
```
Streams a UTF-8 encoded CSV file containing `email,created_at` with formula-injection defenses applied.

#### Waitlist Statistics
```http
GET /api/v1/admin/waitlist/stats
```
**Response:**
```json
{
  "total_entries": 42,
  "latest_signup_at": "2026-10-07T00:15:00Z"
}
```

#### Delete Waitlist Record
```http
DELETE /api/v1/admin/waitlist/{id}
```
**Response:**
```json
{
  "success": true,
  "message": "Waitlist record deleted successfully.",
  "deleted_id": "c138d407-c466-455b-8f8f-16e788c0374e"
}
```

---

## 11. CSV Export & Formula Injection Defense

When exported CSV files are opened in spreadsheet software (Microsoft Excel, LibreOffice Calc, Google Sheets), cells starting with formula characters can execute arbitrary system commands via Dynamic Data Exchange (DDE).

The export service automatically applies sanitization according to OWASP guidelines:
- If a cell begins with `=`, `+`, `-`, `@`, `\t`, or `\r`, a single quote (`'`) is prepended.
- For example: `=cmd|' /C calc'!A0` is exported as `'=cmd|' /C calc'!A0`.
- Safe email addresses such as `alice@example.com` remain unchanged.
- Output uses RFC 4180 escaping and UTF-8 encoding.

---

## 12. Automated 24-Hour Backup System

The backend features an automated backup system running every 24 hours (configured by default for 02:00 UTC).

### PostgreSQL Database Backup
- Created via `pg_dump` with gzip compression (`.sql.gz`).
- Stored with UTC timestamps: `backups/postgres/waitlist_db_YYYY-MM-DD_HHMMSS.sql.gz`.

### CSV Snapshot Backup
- Complete email list exported to timestamped CSV file: `backups/csv/waitlist_YYYY-MM-DD_HHMMSS.csv`.

### Retention Policy & Encryption
- Automated retention purges backups older than `BACKUP_RETENTION_DAYS`.
- **Safety guarantee:** The newest valid backup is **never** deleted, ensuring a viable restore point is always retained.
- Optional symmetric encryption via Fernet (`BACKUP_ENCRYPTION_KEY`) produces `.enc` encrypted archives. Encryption keys are loaded from environment variables and never stored in the backup directory.

### Manual Backup Execution
You can trigger backups manually at any time:
```bash
# Full backup cycle (DB + CSV)
python scripts/backup.py

# CSV snapshot only
python scripts/backup.py --csv-only

# Database dump only
python scripts/backup.py --db-only
```

### Backup Restore Procedure

To restore and verify a backup archive:
```bash
# Restore PostgreSQL dump
python scripts/restore.py --backup-file backups/postgres/waitlist_db_2026-10-07_020000.sql.gz

# Or using the shell wrapper:
./scripts/restore_backup.sh backups/postgres/waitlist_db_2026-10-07_020000.sql.gz
```
The restore script will:
1. Decrypt the archive if encrypted (`.enc`).
2. Decompress the gzip stream.
3. Execute SQL restoration into the target database.
4. Execute verification queries (`SELECT count(*) FROM waitlist_entries`) to confirm data integrity.

---

## 13. Transactional Confirmation Emails

When a user successfully joins the waitlist, the backend can automatically dispatch a confirmation email congratulating them on securing their spot.

### Provider Options & How to Switch

The email architecture uses a pluggable adapter pattern. You can switch between providers at any time **without changing any code**, simply by updating the `EMAIL_PROVIDER` variable in your `.env`:

```env
# Choose: console | smtp | resend | sendgrid
EMAIL_PROVIDER=resend
```

#### 1. Console / Mock Provider (`EMAIL_PROVIDER=console`)
- **Use case:** Local development and testing.
- **Behavior:** Renders the email and logs it to the application logger without sending actual emails or requiring external credentials.

#### 2. Standard SMTP (`EMAIL_PROVIDER=smtp`)
- **Use case:** Works with any standard SMTP server (AWS SES SMTP, Postmark, Brevo, Mailgun, SendGrid SMTP, Gmail, custom corporate relay).
- **Configuration:**
  ```env
  EMAIL_PROVIDER=smtp
  SMTP_HOST=email-smtp.us-east-1.amazonaws.com
  SMTP_PORT=587
  SMTP_USER=your_smtp_username
  SMTP_PASSWORD=your_smtp_password
  SMTP_TLS=true
  SMTP_SSL=false
  ```

#### 3. Resend HTTP API (`EMAIL_PROVIDER=resend`)
- **Use case:** Modern developer-friendly email delivery via Resend.
- **Configuration:**
  ```env
  EMAIL_PROVIDER=resend
  RESEND_API_KEY=re_123456789abcdef
  EMAIL_FROM_ADDRESS=noreply@yourdomain.com
  EMAIL_FROM_NAME="Waitlist Team"
  ```

#### 4. Twilio SendGrid API (`EMAIL_PROVIDER=sendgrid`)
- **Use case:** High-volume delivery via SendGrid v3 Mail Send API.
- **Configuration:**
  ```env
  EMAIL_PROVIDER=sendgrid
  SENDGRID_API_KEY=SG.123456789abcdef
  EMAIL_FROM_ADDRESS=noreply@yourdomain.com
  EMAIL_FROM_NAME="Waitlist Team"
  ```

### Email Templates
- **HTML Version:** Responsive, modern design with a branded gradient header, congratulations message, clear bullet points of what to expect, and an unobtrusive unsubscribe/privacy note.
- **Plain-Text Version:** Formatted text fallback ensuring accessibility across all email clients.
- **Customization:** Customize sender name, product name, and company footer using `PRODUCT_NAME`, `COMPANY_NAME`, `EMAIL_FROM_NAME`, and `EMAIL_SUBJECT`.

### Asynchronous Background Dispatch
- Confirmation emails are queued using FastAPI's `BackgroundTasks`.
- The user's `POST /api/v1/waitlist` request completes in milliseconds ($<50\text{ms}$) without waiting for external SMTP or HTTP network calls.
- **Duplicate Protection:** Emails are **only** sent when a new record is created (`201 Created`). If an existing user resubmits their address, no duplicate email is triggered.
- **Error Isolation:** If an email provider encounters a temporary API error or outage, the error is logged without failing the user's registration.

---

## 14. Security & Rate Limiting

- **HTTP Security Headers:**
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains` (enabled in production)
- **Rate Limiting:** Sliding-window rate limiter per client IP. Returns `429 Too Many Requests` with a standard `Retry-After` header.
- **Request Body Size Guard:** Requests larger than 10KB (`MAX_REQUEST_BODY_SIZE_BYTES`) are terminated with `413 Payload Too Large`.
- **Constant-Time Auth:** Admin API keys are evaluated using `secrets.compare_digest` to prevent timing attacks.
- **CORS Protection:** Configurable per environment. Wildcard `*` origins are strictly forbidden in production mode.
- **Parameterized Queries:** All database interactions utilize SQLAlchemy 2.0 ORM expressions, preventing SQL injection.

---

## 15. Data Minimization & Privacy

- **What data is collected:** Only the user's email address and registration timestamp.
- **Why it is collected:** Solely to notify interested users about product availability and launches.
- **What is NOT collected:** Names, phone numbers, passwords, billing details, device fingerprints, or tracking cookies.
- **Data Deletion:** Records can be deleted upon user request via `DELETE /api/v1/admin/waitlist/{id}`.
- **Logging Privacy:** Raw user emails, request bodies, and authentication headers are never written to application logs.

---

## 16. Production Deployment Checklist

1. [ ] **Reverse Proxy:** Terminate TLS/HTTPS at Nginx, Caddy, Cloudflare, or AWS ALB.
2. [ ] **Environment Configuration:**
   - Set `APP_ENV=production`
   - Set `DEBUG=false`
   - Set a strong `ADMIN_API_KEY` (minimum 32 random characters)
   - Restrict `CORS_ALLOWED_ORIGINS` to your verified production domain(s)
   - Configure `EMAIL_PROVIDER` and credentials (`resend`, `sendgrid`, or `smtp`)
3. [ ] **Database Access:** Restrict PostgreSQL port 5432 to internal private network access only.
4. [ ] **Backups:** Mount `/app/backups` to a persistent volume or configure off-site S3 synchronization.
5. [ ] **Run Migrations:** Execute `alembic upgrade head` during deployment startup.
"# confirmBase" 
