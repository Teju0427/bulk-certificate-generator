from uuid import UUID

from app.models import Certificate, GenerationJob


def test_create_job_returns_job_id_and_total(client, make_payload):
    response = client.post("/api/v1/jobs", json=make_payload(2))

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED"  # the response is built before background work runs
    assert body["total"] == 2
    assert body["job_id"]


def test_create_job_stores_job_and_all_recipients(client, make_payload, db):
    job_id = client.post("/api/v1/jobs", json=make_payload(3)).json()["job_id"]

    job = db.get(GenerationJob, UUID(job_id))
    assert job.event_name == "Python Workshop 2026"
    assert job.total_count == 3
    emails = {c.recipient_email for c in db.query(Certificate).filter_by(job_id=job.id)}
    assert emails == {"user0@example.com", "user1@example.com", "user2@example.com"}


def test_certificate_title_has_default(client, make_payload):
    payload = make_payload(1)
    del payload["certificate_title"]
    assert client.post("/api/v1/jobs", json=payload).status_code == 202


def test_job_stays_queued_when_background_work_does_not_run(client, make_payload, monkeypatch):
    monkeypatch.setattr("app.api.routes.jobs.process_job", lambda job_id: None)
    job_id = client.post("/api/v1/jobs", json=make_payload(2)).json()["job_id"]

    status = client.get(f"/api/v1/jobs/{job_id}").json()
    assert status["status"] == "QUEUED"
    assert status["pending"] == 2
    assert status["progress_percentage"] == 0
