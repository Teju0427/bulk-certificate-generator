from uuid import UUID

from pydantic import BaseModel

from app.models.certificate import CertificateStatus


class CertificateOut(BaseModel):
    certificate_id: UUID
    recipient_name: str
    recipient_email: str
    status: CertificateStatus
    error_message: str | None = None
    download_url: str | None = None  # only set when status is SUCCESS
