# Interview Guide – Bulk Certificate Generator

## A. Architecture in simple terms
A client sends ONE request with a list of people. FastAPI validates it, saves a **job** and one **certificate row per person** (status PENDING) in PostgreSQL, answers immediately with a job id, and *after* answering starts a background function. That function loops over the pending rows, asks ReportLab to draw one PDF each, saves the file path, and updates counters. The client polls the status endpoint, lists certificates, and downloads PDFs.

Layers: **routes** (HTTP) → **services** (logic) → **models** (database). Schemas (Pydantic) check input/output. Routes never draw PDFs; the generator never touches HTTP.

## B. File by file
| File | Purpose |
|---|---|
| `app/main.py` | Creates the app, registers routers, error handlers (consistent JSON, no stack traces), `/health` |
| `app/config.py` | Reads `DATABASE_URL`, `STORAGE_DIR` from env/.env |
| `app/database.py` | Engine, `SessionLocal`, `Base`, `get_db()` (one session per request, always closed) |
| `app/models/job.py`, `certificate.py` | Tables + status enums + relationship |
| `app/schemas/job.py` | Request validation (names, emails, duplicates, date) and job responses |
| `app/schemas/certificate.py`, `error.py` | Certificate response; error format |
| `app/api/routes/jobs.py` | POST job, GET status, GET certificates list |
| `app/api/routes/certificates.py` | GET download (FileResponse) |
| `app/services/job_service.py` | Create job (one transaction), fetch, build status numbers |
| `app/services/job_processor.py` | Background loop + failure isolation + final status |
| `app/services/certificate_generator.py` | ReportLab drawing of one PDF |
| `app/utils/helpers.py` | `utcnow`, `slugify`, filename builder |
| `alembic/versions/0001_*.py` | Creates the tables in PostgreSQL |
| `tests/` | `conftest.py` (SQLite + temp storage) and the test files |

## C. Database
- **generation_jobs** (1 row per request): event/title/org/date, `status`, `total_count`, `success_count`, `failure_count`, timestamps.
- **certificates** (1 row per recipient): `job_id` (FK → generation_jobs.id, ON DELETE CASCADE, indexed), name, email, `status` (PENDING/SUCCESS/FAILED), `file_path`, `error_message`, timestamps.
- One job → many certificates (`job.certificates` / `certificate.job`). IDs are UUIDs so they are hard to guess.

## D. Endpoints
1. `POST /api/v1/jobs` – validate, save job + recipients in one transaction, queue background task, return `{job_id, status, total}` with 202.
2. `GET /api/v1/jobs/{id}` – reads counters from the job row; pending = total − successful − failed; progress = finished/total × 100.
3. `GET /api/v1/jobs/{id}/certificates` – all rows of the job; `download_url` only for SUCCESS.
4. `GET /api/v1/certificates/{id}` – finds row, checks SUCCESS and that the file exists, returns `FileResponse`; else 404.

## E. Background processing
`QUEUED` (created) → `process_job` starts → `PROCESSING` (committed) → for each PENDING certificate: generate, update the row and job counters, **commit** (so the status endpoint shows live progress) → end: no failures = `COMPLETED`; some = `COMPLETED_WITH_ERRORS`; zero successes = `FAILED`. If something unexpected crashes the whole loop (e.g. DB down), the job is marked `FAILED`. The task opens its **own** DB session because the request's session is closed after the response.

## F. ReportLab
`canvas.Canvas(path, pagesize=landscape(A4))` gives a page whose origin (0,0) is bottom-left, in points. We draw two rectangles (border), then `drawCentredString(x, y, text)` for each line with chosen fonts/colours. `_fit_font_size` shrinks the font for long names. `showPage()` ends the page and `save()` writes the file. The certificate ID printed is the certificate row's UUID.

## G. Failure handling
In `_process_certificate`, only the generator call is inside `try/except Exception`. On error: delete partial file, set that row to FAILED, store the message, `failure_count += 1`. The exception stops there; the `for` loop continues with the next recipient. Each certificate is committed separately, so earlier results are never lost.

## H. 20 interview questions
1. **Why background processing?** Many PDFs are slow; the client gets an answer instantly and polls. No extra infrastructure.
2. **Limitation of BackgroundTasks?** Runs in the same process; lost if the server restarts; no retries/scaling. For production I'd use a queue (Celery/RQ).
3. **Why PostgreSQL?** Relational data, FKs, transactions, concurrent writes.
4. **How is a failure isolated?** try/except per certificate + commit per certificate.
5. **Why 202 not 201?** Work is accepted but not finished.
6. **Why UUIDs?** Not guessable/sequential, safe to expose in URLs.
7. **How do you validate input?** Pydantic: lengths, `EmailStr`, `date`, list min length, a model validator for duplicate emails.
8. **Why a separate DB session in the task?** Request session is closed after the response.
9. **What does `get_db` do?** Yields a session and closes it in `finally`.
10. **How does progress work?** Counters on the job row; pending = total − success − failed.
11. **Why commit per certificate?** Live progress and no lost work on a crash.
12. **How do you avoid path traversal?** Filenames are slugified to `[a-z0-9-]`; user text never forms a path directly.
13. **Two people with the same name?** Second file gets `-<first 8 of id>` suffix.
14. **What does Alembic do?** Versioned schema migrations instead of `create_all`.
15. **How do you test without PostgreSQL?** SQLite via env var before imports; `Uuid` type works on both.
16. **How do you test failures?** Monkeypatch the generator to raise for one name.
17. **How are errors made consistent?** Exception handlers for HTTP, validation and unexpected errors return `{"error": {...}}`; 500 hides internals.
18. **What if the file was deleted from disk?** Download returns 404, not 500.
19. **How would you scale?** Queue + workers, object storage (S3), pagination, rate limits.
20. **Race conditions?** One task per job updates its counters; for many workers use atomic `UPDATE … SET count = count + 1`.
21. **Why `expire_on_commit=False`?** Objects stay readable after commit without re-querying.
22. **Why store file_path, not the PDF?** Keeps the DB small; files are served from disk.

## I. 10 modification exercises
1. **Expiry date** – add `expiry_date: date | None` to `JobCreateRequest` (schemas/job.py), `GenerationJob` (models/job.py), `job_service.create_job`, a new Alembic migration, and draw it in `certificate_generator.py`.
2. **Phone number** – `RecipientIn.phone` (schema), `Certificate.phone` (model), pass it in `create_job`, migration, add to `CertificateOut` and `_to_certificate_out`.
3. **Retry failed certificates** – new route in `routes/jobs.py` `POST /jobs/{id}/retry`: set FAILED certs back to PENDING, subtract from `failure_count`, set job QUEUED, `background_tasks.add_task(process_job, id)` (the processor already only picks PENDING rows).
4. **Pagination** – add `limit`/`offset` query params to `list_job_certificates`, pass to `job_service.list_certificates` (`.limit().offset()`).
5. **Filtering** – add `status: CertificateStatus | None` param; add `.where(Certificate.status == status)` in `list_certificates`.
6. **Change filename** – edit `build_pdf_path` in `utils/helpers.py` (e.g. include email or certificate id).
7. **New field (e.g. course duration)** – same path as #1: schema → model → migration → `create_job` → `_process_certificate` argument → generator.
8. **Authentication** – API-key dependency in a new `app/auth.py` using `Header("X-API-Key")` compared with an env setting; add `dependencies=[Depends(verify_key)]` to both routers in `main.py`.
9. **Make generation synchronous** – in `create_generation_job` replace `background_tasks.add_task(...)` with `process_job(job.id)` (status will already be final in the response).
10. **Change certificate design/colours** – constants (`NAVY`, `GOLD`) and y-positions in `certificate_generator.py` only; nothing else changes.
