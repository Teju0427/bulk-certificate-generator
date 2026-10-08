from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Certificate, CertificateStatus
from app.schemas.certificate import CertificateOut
from app.schemas.error import ErrorResponse
from app.schemas.job import JobCreateRequest, JobCreateResponse, JobStatusResponse
from app.services import job_service
from app.services.job_processor import process_job

router = APIRouter(prefix="/jobs", tags=["Jobs"])

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Job not found"}}


def _to_certificate_out(certificate: Certificate) -> CertificateOut:
    is_success = certificate.status == CertificateStatus.SUCCESS.value
    return CertificateOut(
        certificate_id=certificate.id,
        recipient_name=certificate.recipient_name,
        recipient_email=certificate.recipient_email,
        status=certificate.status,
        error_message=certificate.error_message,
        download_url=f"/api/v1/certificates/{certificate.id}" if is_success else None,
    )


@router.post(
    "",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a bulk certificate generation job",
    description="Stores the job and all recipients, returns immediately, and generates the PDFs in the background.",
)
def create_generation_job(
    payload: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JobCreateResponse:
    job = job_service.create_job(db, payload)
    background_tasks.add_task(process_job, job.id)  # runs after the response is sent
    return JobCreateResponse(job_id=job.id, status=job.status, total=job.total_count)


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    responses=NOT_FOUND,
    summary="Get job status and progress",
)
def get_job_status(job_id: UUID, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_service.build_status(job)


@router.get(
    "/{job_id}/certificates",
    response_model=list[CertificateOut],
    responses=NOT_FOUND,
    summary="List all certificates of a job",
)
def list_job_certificates(job_id: UUID, db: Session = Depends(get_db)) -> list[CertificateOut]:
    if job_service.get_job(db, job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return [_to_certificate_out(c) for c in job_service.list_certificates(db, job_id)]
