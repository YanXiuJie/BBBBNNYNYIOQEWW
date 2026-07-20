from sqlalchemy import select

from app.models import Attempt, User


def login_token(client, username):
    response = client.post("/auth/login", json={"username": username, "password": "password123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def create_fresh_student(client, username: str):
    teacher_token = login_token(client, "cikgu")
    response = client.post(
        "/teacher/students",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "username": username,
            "password": "password123",
            "full_name": "Fresh Diagnostic Student",
            "parent_email": f"{username}@example.com",
            "class_id": 1,
        },
    )
    assert response.status_code == 201
    return login_token(client, username)


def test_diagnostic_requires_completed_session_for_dashboard_status(client):
    token = create_fresh_student(client, "fresh_diagnostic_student")
    headers = {"Authorization": f"Bearer {token}"}

    dashboard_before = client.get("/student/dashboard", headers=headers)
    assert dashboard_before.status_code == 200
    assert dashboard_before.json()["diagnostic_completed"] is False

    start_response = client.post("/student/diagnostic/start", headers=headers)
    assert start_response.status_code == 201
    session_id = start_response.json()["session_id"]

    next_response = client.get(f"/student/diagnostic/next?session_id={session_id}", headers=headers)
    assert next_response.status_code == 200
    question = next_response.json()["question"]

    submit_response = client.post(
        "/student/diagnostic/submit",
        headers=headers,
        json={
            "session_id": session_id,
            "question_id": question["id"],
            "answer_text": question["expected_answer"],
            "time_seconds": 12,
        },
    )
    assert submit_response.status_code == 201

    dashboard_during = client.get("/student/dashboard", headers=headers)
    assert dashboard_during.status_code == 200
    assert dashboard_during.json()["diagnostic_completed"] is False


def test_diagnostic_session_completes_and_tags_attempts(client):
    username = "fresh_diagnostic_complete"
    token = create_fresh_student(client, username)
    headers = {"Authorization": f"Bearer {token}"}

    start_response = client.post("/student/diagnostic/start", headers=headers)
    assert start_response.status_code == 201
    body = start_response.json()
    session_id = body["session_id"]
    assert body["status"] == "in_progress"

    answered = 0
    while True:
        next_response = client.get(f"/student/diagnostic/next?session_id={session_id}", headers=headers)
        assert next_response.status_code == 200
        next_body = next_response.json()
        if next_body.get("completed") is True:
            break

        question = next_body["question"]
        submit_response = client.post(
            "/student/diagnostic/submit",
            headers=headers,
            json={
                "session_id": session_id,
                "question_id": question["id"],
                "answer_text": question["expected_answer"],
                "time_seconds": 18,
            },
        )
        assert submit_response.status_code == 201
        answered += 1
        assert submit_response.json()["attempt"]["source"] == "diagnostic"

    assert answered >= 8

    summary_response = client.get(f"/student/diagnostic/summary?session_id={session_id}", headers=headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["status"] == "completed"
    assert summary["summary"]["total_questions"] == answered
    assert summary["summary"]["correct_count"] == answered

    dashboard_after = client.get("/student/dashboard", headers=headers)
    assert dashboard_after.status_code == 200
    assert dashboard_after.json()["diagnostic_completed"] is True

    with client.app.state.session_factory() as session:
        student = session.scalar(select(User).where(User.username == username))
        attempt_sources = session.scalars(
            select(Attempt.source).where(Attempt.student_id == student.id, Attempt.source == "diagnostic")
        ).all()
    assert len(attempt_sources) == answered
