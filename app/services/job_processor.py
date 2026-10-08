"""Background worker: QUEUED -> PROCESSING -> COMPLETED / COMPLETED_WITH_ERRORS / FAILED."""
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Certificate, CertificateStatus, GenerationJob, JobStatus
from app.services import certificate_generator
from app.utils.helpers import build_pdf_path, utcnow

logger = logging.getLogger(__name__)


def process_job(job_id: UUID) -> None:
    """Entry point used by FastAPI BackgroundTasks. Owns its own DB session."""
    db = SessionLocal()
    try:
        _run_job(db, job_id)
    except Exception:
        logger.exception("Job %s crashed", job_id)
        db.rollback()
        _mark_job_failed(db, job_id)
    finally:
        db.close()


def _run_job(db: Session, job_id: UUID) -> None:
    job = db.get(GenerationJob, job_id)
    if job is None:
        logger.warning("Job %s not found, nothing to do", job_id)
        return

    job.status = JobStatus.PROCESSING.value
    db.commit()

    pending = db.scalars(
        select(Certificate)
        .where(Certificate.job_id == job.id, Certificate.status == CertificateStatus.PENDING.value)
        .order_by(Certificate.created_at)
    ).all()
    for certificate in pending:
        _process_certificate(db, job, certificate)

    job.status = _final_status(job).value
    job.completed_at = utcnow()
    db.commit()


def _process_certificate(db: Session, job: GenerationJob, certificate: Certificate) -> None:
    """Generate one PDF. A failure is recorded on this certificate only."""
    output_dir = settings.storage_dir / str(job.id)
    output_path = build_pdf_path(output_dir, certificate.recipient_name, certificate.id)
    try:
        certificate_generator.generate_certificate_pdf(
            output_path,
            certificate_id=certificate.id,
            recipient_name=certificate.recipient_name,
            event_name=job.event_name,
            certificate_title=job.certificate_title,
            organization_name=job.organization_name,
            issue_date=job.issue_date,
        )
    except Exception as exc:  # isolate the failure: record it and move on
        logger.warning("Certificate %s failed: %s", certificate.id, exc)
        output_path.unlink(missing_ok=True)  # remove a half-written file
        certificate.status = CertificateStatus.FAILED.value
        certificate.error_message = str(exc)[:500] or exc.__class__.__name__
        job.failure_count += 1
    else:
        certificate.status = CertificateStatus.SUCCESS.value
        certificate.file_path = str(output_path)
        job.success_count += 1
    certificate.completed_at = utcnow()
    db.commit()  # commit per certificate so the status API shows live progress


def _final_status(job: GenerationJob) -> JobStatus:
    if job.failure_count == 0:
        return JobStatus.COMPLETED
    if job.success_count == 0:
        return JobStatus.FAILED  # nothing worked at all
    return JobStatus.COMPLETED_WITH_ERRORS


def _mark_job_failed(db: Session, job_id: UUID) -> None:
    try:
        job = db.get(GenerationJob, job_id)
        if job is not None:
            job.status = JobStatus.FAILED.value
            job.completed_at = utcnow()
            db.commit()
    except Exception:
        logger.exception("Could not mark job %s as FAILED", job_id)
        db.rollback()
