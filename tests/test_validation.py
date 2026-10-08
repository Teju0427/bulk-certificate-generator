import pytest

from app.models import GenerationJob


def _bad(payload: dict, **changes) -> dict:
    return {**payload, **changes}


@pytest.mark.parametrize(
    "mutate, expected_field",
    [
        (lambda p: _bad(p, recipients=[]), "recipients"),
        (lambda p: _bad(p, recipients=[{"email": "a@example.com"}]), "recipients.0.name"),
        (lambda p: _bad(p, recipients=[{"name": "A", "email": "a@example.com"}]), "recipients.0.name"),
        (lambda p: _bad(p, recipients=[{"name": "   ", "email": "a@example.com"}]), "recipients.0.name"),
        (lambda p: _bad(p, recipients=[{"name": "x" * 101, "email": "a@example.com"}]), "recipients.0.name"),
        (lambda p: _bad(p, recipients=[{"name": "Alice", "email": "not-an-email"}]), "recipients.0.email"),
        (lambda p: {k: v for k, v in p.items() if k != "event_name"}, "event_name"),
        (lambda p: {k: v for k, v in p.items() if k != "organization_name"}, "organization_name"),
        (lambda p: _bad(p, organization_name=""), "organization_name"),
        (lambda p: _bad(p, issue_date="2026-13-45"), "issue_date"),
        (lambda p: _bad(p, issue_date="not a date"), "issue_date"),
    ],
)
def test_invalid_request_is_rejected(client, make_payload, db, mutate, expected_field):
    response = client.post("/api/v1/jobs", json=mutate(make_payload(1)))

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert expected_field in [d["field"] for d in error["details"]]
    assert db.query(GenerationJob).count() == 0  # nothing stored for a rejected request


def test_duplicate_emails_are_rejected_case_insensitively(client, make_payload):
    payload = make_payload(2)
    payload["recipients"][1]["email"] = payload["recipients"][0]["email"].upper()

    response = client.post("/api/v1/jobs", json=payload)

    assert response.status_code == 422
    assert "Duplicate" in response.json()["error"]["details"][0]["message"]


def test_same_name_with_different_email_is_allowed(client, make_payload):
    payload = make_payload(2)
    payload["recipients"][1]["name"] = payload["recipients"][0]["name"]
    assert client.post("/api/v1/jobs", json=payload).status_code == 202


def test_name_whitespace_is_trimmed(client, make_payload):
    payload = make_payload(1)
    payload["recipients"][0]["name"] = "  Alice Johnson  "
    job_id = client.post("/api/v1/jobs", json=payload).json()["job_id"]
    certificates = client.get(f"/api/v1/jobs/{job_id}/certificates").json()
    assert certificates[0]["recipient_name"] == "Alice Johnson"
