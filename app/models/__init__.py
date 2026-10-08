# Importing both models here makes sure SQLAlchemy and Alembic know about every table.
from app.models.certificate import Certificate, CertificateStatus
from app.models.job import GenerationJob, JobStatus

__all__ = ["Certificate", "CertificateStatus", "GenerationJob", "JobStatus"]
