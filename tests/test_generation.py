from datetime import date
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader

from app.services.certificate_generator import generate_certificate_pdf


def _pdf_text(path: Path) -> str:
    return " ".join(page.extract_text() for page in PdfReader(path).pages)


def test_generator_writes_pdf_with_all_required_fields(tmp_path):
    certificate_id = uuid4()
    path = generate_certificate_pdf(
        tmp_path / "alice.pdf",
        certificate_id=certificate_id,
        recipient_name="Alice Johnson",
        event_name="Python Workshop 2026",
        certificate_title="Certificate of Participation",
        organization_name="Aereo",
        issue_date=date(2026, 10, 8),
    )

    assert path.read_bytes().startswith(b"%PDF")
    text = _pdf_text(path)
    for expected in ["AEREO", "Certificate of Participation", "Alice Johnson",
                     "Python Workshop 2026", "08 October 2026", str(certificate_id)]:
        assert expected in text


def test_job_generates_one_pdf_per_recipient(client, make_payload, temp_storage):
    job_id = client.post("/api/v1/jobs", json=make_payload(3)).json()["job_id"]

    job_dir = temp_storage / job_id
    assert sorted(p.name for p in job_dir.iterdir()) == ["alice-johnson.pdf", "bob-smith.pdf", "carol-white.pdf"]
    assert "Bob Smith" in _pdf_text(job_dir / "bob-smith.pdf")


def test_pdf_contains_unique_certificate_id_from_the_database(client, make_payload, temp_storage):
    job_id = client.post("/api/v1/jobs", json=make_payload(2)).json()["job_id"]
    certificates = client.get(f"/api/v1/jobs/{job_id}/certificates").json()

    for certificate in certificates:
        pdf = temp_storage / job_id / (certificate["recipient_name"].lower().replace(" ", "-") + ".pdf")
        assert certificate["certificate_id"] in _pdf_text(pdf)


def test_same_name_different_email_gets_separate_files(client, make_payload, temp_storage):
    payload = make_payload(2)
    payload["recipients"][1]["name"] = payload["recipients"][0]["name"]
    job_id = client.post("/api/v1/jobs", json=payload).json()["job_id"]

    assert len(list((temp_storage / job_id).iterdir())) == 2


def test_very_long_name_still_generates(tmp_path):
    path = generate_certificate_pdf(
        tmp_path / "long.pdf",
        certificate_id=uuid4(),
        recipient_name="A" * 100,
        event_name="E" * 120,
        certificate_title="T" * 80,
        organization_name="O" * 100,
        issue_date=date(2026, 10, 8),
    )
    assert path.stat().st_size > 0
