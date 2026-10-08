"""Database operations for jobs (create, read, build status numbers)."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Certificate, CertificateStatus, GenerationJob, JobStatus
from app.schemas.job import JobCreateRequest, JobStatusResponse


def create_job(db: Session, payload: JobCreateRequest) -> GenerationJob:
    """Store the job and all its recipients in ONE transaction (all or nothing)."""
    job = GenerationJob(
        event_name=payload.event_name,
        certificate_title=payload.certificate_title,
        organization_name=payload.organization_name,
        issue_date=payload.issue_date,
        status=JobStatus.QUEUED.value,
        total_count=len(payload.recipients),
        certificates=[
            Certificate(
                recipient_name=recipient.name,
                recipient_email=str(recipient.email),
                status=CertificateStatus.PENDING.value,
            )
            for recipient in payload.recipients
        ],
    )
    db.add(job)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return job


def get_job(db: Session, job_id: UUID) -> GenerationJob | None:
    return db.get(GenerationJob, job_id)


def list_certificates(db: Session, job_id: UUID) -> list[Certificate]:
    stmt = select(Certificate).where(Certificate.job_id == job_id).order_by(Certificate.created_at)
    return list(db.scalars(stmt).all())


def build_status(job: GenerationJob) -> JobStatusResponse:
    """pending = total - successful - failed; progress counts finished certificates."""
    finished = job.success_count + job.failure_count
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        total=job.total_count,
        successful=job.success_count,
        failed=job.failure_count,
        pending=job.total_count - finished,
        progress_percentage=round(finished / job.total_count * 100),
    )
