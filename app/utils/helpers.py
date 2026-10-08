"""Small helper functions shared across the app."""
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def slugify(text: str) -> str:
    """'Alice Johnson' -> 'alice-johnson'. Only [a-z0-9-] survive, so it is safe in a path."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "certificate"


def build_pdf_path(directory: Path, recipient_name: str, certificate_id: UUID) -> Path:
    """alice-johnson.pdf; if that name is taken (two Alices) add part of the certificate id."""
    slug = slugify(recipient_name)
    path = directory / f"{slug}.pdf"
    if path.exists():
        path = directory / f"{slug}-{str(certificate_id)[:8]}.pdf"
    return path
