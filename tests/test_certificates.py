from pathlib import Path
from uuid import UUID, uuid4


def _generate(client, make_payload, count=2):
    job_id = client.post("/api/v1/jobs", json=make_payload(count)).json()["job_id"]
    return job_id, client.get(f"/api/v1/jobs/{job_id}/certificates").json()


def test_list_certificates_returns_all_fields(client, make_payload):
    _, certificates = _generate(client, make_payload)

    assert len(certificates) == 2
    alice = next(c for c in certificates if c["recipient_name"] == "Alice Johnson")
    assert alice["recipient_email"] == "user0@example.com"
    assert alice["status"] == "SUCCESS"
    assert alice["error_message"] is None
    assert alice["download_url"] == f"/api/v1/certificates/{alice['certificate_id']}"


def test_download_returns_the_pdf_file(client, make_payload):
    _, certificates = _generate(client, make_payload)

    response = client.get(certificates[0]["download_url"])

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert ".pdf" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")


def test_unknown_certificate_returns_404(client):
    response = client.get(f"/api/v1/certificates/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_missing_file_on_disk_returns_404_not_500(client, make_payload):
    _, certificates = _generate(client, make_payload, count=1)
    from app.database import SessionLocal
    from app.models import Certificate

    with SessionLocal() as session:
        Path(session.get(Certificate, UUID(certificates[0]["certificate_id"])).file_path).unlink()

    assert client.get(certificates[0]["download_url"]).status_code == 404


def test_list_certificates_for_unknown_job_returns_404(client):
    assert client.get(f"/api/v1/jobs/{uuid4()}/certificates").status_code == 404
