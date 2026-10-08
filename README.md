# Bulk Certificate Generator API

## Project Overview
Creating certificates one by one is slow. This API accepts **one request containing many recipients**, generates a PDF certificate for each from a single predefined template, tracks progress, and lets clients list and download the results.

Stack: Python 3.11+, FastAPI, PostgreSQL, SQLAlchemy 2.x, Pydantic, Alembic, ReportLab, Pytest, Docker Compose.

## Architecture
```
Client
  ↓  POST /api/v1/jobs
FastAPI (validation, routes)
  ↓  stores job + recipients
PostgreSQL
  ↓  BackgroundTasks starts after the response is sent
Background Job Processor (services/job_processor.py)
  ↓  one call per recipient
ReportLab (services/certificate_generator.py)
  ↓
Generated PDF Storage  storage/certificates/{job_id}/alice-johnson.pdf
```

## Setup (local)
```bash
git clone <your-repo-url> && cd bulk-certificate-generator
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # edit DATABASE_URL / password
# start PostgreSQL (or: docker compose up -d db) and create the database from .env
alembic upgrade head            # create tables
uvicorn app.main:app --reload   # http://localhost:8000
```
Swagger UI: `/docs` · ReDoc: `/redoc`

## Setup (Docker Compose)
```bash
cp .env.example .env            # set POSTGRES_PASSWORD
docker compose up --build       # starts PostgreSQL, runs migrations, starts the API on :8000
```
PDFs are kept in the `certificates` Docker volume.

## API Endpoints
All errors look like `{"error": {"code": "NOT_FOUND", "message": "Job not found"}}`.

### POST /api/v1/jobs — create a job (202 Accepted)
```bash
curl -X POST localhost:8000/api/v1/jobs -H "Content-Type: application/json" -d '{
  "event_name": "Python Workshop 2026",
  "certificate_title": "Certificate of Participation",
  "organization_name": "Aereo",
  "issue_date": "2026-10-08",
  "recipients": [
    {"name": "Alice Johnson", "email": "alice@example.com"},
    {"name": "Bob Smith", "email": "bob@example.com"}]}'
```
Response: `{"job_id": "…", "status": "QUEUED", "total": 2}`
Validation failure → `422` with `error.code = "VALIDATION_ERROR"` and a `details` list (field + message).
Rules: 1–1000 recipients, name 2–100 chars, valid email, no duplicate emails (case-insensitive), valid date, event/organization required.

### GET /api/v1/jobs/{job_id} — status
```json
{"job_id": "…", "status": "PROCESSING", "total": 100, "successful": 65,
 "failed": 2, "pending": 33, "progress_percentage": 67}
```
`404` if the job does not exist.

### GET /api/v1/jobs/{job_id}/certificates — list
```json
[{"certificate_id": "…", "recipient_name": "Alice Johnson", "recipient_email": "alice@example.com",
  "status": "SUCCESS", "error_message": null, "download_url": "/api/v1/certificates/…"}]
```
Failed items have `status: "FAILED"`, an `error_message` and `download_url: null`.

### GET /api/v1/certificates/{certificate_id} — download
Returns the PDF (`application/pdf`). `404` if unknown, not generated, or the file is missing.

## Example Workflow
```bash
curl -X POST …/api/v1/jobs …            # 1. returns {"job_id": "abc", ...}
curl …/api/v1/jobs/abc                  # 2. poll until status is COMPLETED
curl …/api/v1/jobs/abc/certificates     # 3. get certificate ids + download URLs
curl -OJ …/api/v1/certificates/<id>     # 4. download one PDF
```

## Design Decisions
- **Background processing:** generating hundreds of PDFs would make the HTTP request slow or time out. FastAPI `BackgroundTasks` returns the response immediately and does the work afterwards, with no extra infrastructure (no Redis/Celery). Trade-off: if the server restarts mid-job, the job is not resumed.
- **Failure isolation:** each certificate is generated inside its own `try/except` and committed on its own. A failure marks only that certificate `FAILED` (with the error message) and the loop continues. Final job status: all ok → `COMPLETED`; some failed → `COMPLETED_WITH_ERRORS`; none succeeded → `FAILED`.
- **PostgreSQL:** relational data (job → many certificates), foreign keys, transactions (job + recipients are saved atomically), and safe concurrent access.
- **File storage:** PDFs are written to `storage/certificates/{job_id}/{name-slug}.pdf`; the database stores only the path. Names are slugified (path-safe); same-name collisions get a short id suffix.
- **Known limitation:** the built-in PDF fonts support Latin characters only.

## Testing
```bash
pytest -v
```
Tests use a temporary SQLite database and temp storage; production uses PostgreSQL.
