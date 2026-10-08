from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Certificate, CertificateStatus
from app.schemas.error import ErrorResponse

router = APIRouter(prefix="/certificates", tags=["Certificates"])


@router.get(
    "/{certificate_id}",
    response_class=FileResponse,
    responses={404: {"model": ErrorResponse, "description": "Certificate not found or not generated"}},
    summary="Download a generated certificate (PDF)",
)
def download_certificate(certificate_id: UUID, db: Session = Depends(get_db)) -> FileResponse:
    certificate = db.get(Certificate, certificate_id)
    if certificate is None:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if certificate.status != CertificateStatus.SUCCESS.value or not certificate.file_path:
        raise HTTPException(status_code=404, detail="Certificate has not been generated")

    path = Path(certificate.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Certificate file is missing")
    return FileResponse(path, media_type="application/pdf", filename=path.name)
