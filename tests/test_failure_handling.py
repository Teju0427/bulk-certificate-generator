import pytest

from app.services import certificate_generator


@pytest.fixture
def fail_for_bob(monkeypatch):
    original = certificate_generator.generate_certificate_pdf

    def flaky(output_path, **kwargs):
        if kwargs["recipient_name"] == "Bob Smith":
            raise RuntimeError("disk exploded")
        return original(output_path, **kwargs)

    monkeypatch.setattr(certificate_generator, "generate_certificate_pdf", flaky)


def test_one_failure_does_not_stop_the_other_certificates(client, make_payload, fail_for_bob):
    job_id = client.post("/api/v1/jobs", json=make_payload(4)).json()["job_id"]

    status = client.get(f"/api/v1/jobs/{job_id}").json()
    assert status["status"] == "COMPLETED_WITH_ERRORS"
    assert (status["total"], status["successful"], status["failed"], status["pending"]) == (4, 3, 1, 0)
    assert status["progress_percentage"] == 100


def test_failed_certificate_records_error_and_has_no_download_url(client, make_payload, fail_for_bob):
    job_id = client.post("/api/v1/jobs", json=make_payload(3)).json()["job_id"]

    certificates = {c["recipient_name"]: c for c in client.get(f"/api/v1/jobs/{job_id}/certificates").json()}
    bob = certificates["Bob Smith"]
    assert bob["status"] == "FAILED"
    assert "disk exploded" in bob["error_message"]
    assert bob["download_url"] is None
    for name in ("Alice Johnson", "Carol White"):
        assert certificates[name]["status"] == "SUCCESS"
        assert certificates[name]["error_message"] is None
        assert client.get(certificates[name]["download_url"]).status_code == 200
    assert client.get(f"/api/v1/certificates/{bob['certificate_id']}").status_code == 404


def test_job_fails_when_every_certificate_fails(client, make_payload, monkeypatch):
    def always_fail(output_path, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(certificate_generator, "generate_certificate_pdf", always_fail)
    job_id = client.post("/api/v1/jobs", json=make_payload(2)).json()["job_id"]

    status = client.get(f"/api/v1/jobs/{job_id}").json()
    assert status["status"] == "FAILED"
    assert (status["successful"], status["failed"]) == (0, 2)
