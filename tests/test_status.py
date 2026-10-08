from uuid import UUID, uuid4

from app.models import GenerationJob


def test_completed_job_reports_full_progress(client, make_payload):
    job_id = client.post("/api/v1/jobs", json=make_payload(3)).json()["job_id"]

    body = client.get(f"/api/v1/jobs/{job_id}").json()
    assert body == {
        "job_id": job_id,
        "status": "COMPLETED",
        "total": 3,
        "successful": 3,
        "failed": 0,
        "pending": 0,
        "progress_percentage": 100,
    }


def test_progress_is_calculated_from_finished_certificates(client, make_payload, db, monkeypatch):
    monkeypatch.setattr("app.api.routes.jobs.process_job", lambda job_id: None)
    job_id = client.post("/api/v1/jobs", json=make_payload(4)).json()["job_id"]

    # Pretend the worker is half way: 2 succeeded, 1 failed, 1 still pending.
    job = db.get(GenerationJob, UUID(job_id))
    job.status, job.success_count, job.failure_count = "PROCESSING", 2, 1
    db.commit()

    body = client.get(f"/api/v1/jobs/{job_id}").json()
    assert (body["status"], body["successful"], body["failed"], body["pending"]) == ("PROCESSING", 2, 1, 1)
    assert body["progress_percentage"] == 75


def test_unknown_job_returns_404_in_standard_error_format(client):
    response = client.get(f"/api/v1/jobs/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "NOT_FOUND", "message": "Job not found"}}


def test_malformed_job_id_returns_422(client):
    response = client.get("/api/v1/jobs/not-a-uuid")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
