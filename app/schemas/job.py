from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.job import JobStatus

MAX_RECIPIENTS = 1000


class RecipientIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=100)
    email: EmailStr


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "event_name": "Python Workshop 2026",
                "certificate_title": "Certificate of Participation",
                "organization_name": "Aereo",
                "issue_date": "2026-10-08",
                "recipients": [
                    {"name": "Alice Johnson", "email": "alice@example.com"},
                    {"name": "Bob Smith", "email": "bob@example.com"},
                ],
            }
        },
    )

    event_name: str = Field(min_length=1, max_length=120)
    certificate_title: str = Field(default="Certificate of Participation", min_length=1, max_length=80)
    organization_name: str = Field(min_length=1, max_length=100)
    issue_date: date
    recipients: list[RecipientIn] = Field(min_length=1, max_length=MAX_RECIPIENTS)

    @model_validator(mode="after")
    def reject_duplicate_emails(self) -> "JobCreateRequest":
        seen: set[str] = set()
        duplicates: list[str] = []
        for recipient in self.recipients:
            email = str(recipient.email).lower()
            if email in seen and email not in duplicates:
                duplicates.append(email)
            seen.add(email)
        if duplicates:
            raise ValueError(f"Duplicate recipient emails: {', '.join(duplicates)}")
        return self


class JobCreateResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    total: int


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    total: int
    successful: int
    failed: int
    pending: int
    progress_percentage: int
