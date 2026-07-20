import json

from sqlalchemy import select

from app.models import ComprehensivePracticeSession


def login_token(client, username):
    response = client.post("/auth/login", json={"username": username, "password": "password123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_comprehensive_summary_tracks_diagnosis_results(client):
    token = login_token(client, "amin")
    headers = {"Authorization": f"Bearer {token}"}

    start_response = client.post("/student/comprehensive-practice/start", headers=headers)
    assert start_response.status_code == 201
    session_id = start_response.json()["session_id"]

    next_response = client.get(f"/student/comprehensive-practice/next?session_id={session_id}", headers=headers)
    assert next_response.status_code == 200
    question = next_response.json()["question"]

    submit_response = client.post(
        "/student/comprehensive-practice/submit",
        headers=headers,
        json={
            "session_id": session_id,
            "question_id": question["id"],
            "answer_text": question["expected_answer"],
            "time_seconds": 15,
            "hints_used": ["basic"],
        },
    )
    assert submit_response.status_code == 201

    summary_response = client.get(f"/student/comprehensive-practice/summary?session_id={session_id}", headers=headers)
    assert summary_response.status_code == 200
    body = summary_response.json()
    assert body["phase_breakdown"]["diagnosis"]["total"] == 1
    assert body["summary"]["total_questions"] == 1
    assert body["summary"]["total_hints_used"] == 1


def test_comprehensive_next_returns_completed_payload_after_last_question(client):
    token = login_token(client, "amin")
    headers = {"Authorization": f"Bearer {token}"}

    start_response = client.post("/student/comprehensive-practice/start", headers=headers)
    assert start_response.status_code == 201
    session_id = start_response.json()["session_id"]

    for _ in range(15):
        next_response = client.get(f"/student/comprehensive-practice/next?session_id={session_id}", headers=headers)
        assert next_response.status_code == 200
        question = next_response.json()["question"]
        submit_response = client.post(
            "/student/comprehensive-practice/submit",
            headers=headers,
            json={
                "session_id": session_id,
                "question_id": question["id"],
                "answer_text": question["expected_answer"],
                "time_seconds": 20,
                "hints_used": [],
            },
        )
        assert submit_response.status_code == 201

    completed_response = client.get(f"/student/comprehensive-practice/next?session_id={session_id}", headers=headers)
    assert completed_response.status_code == 200
    body = completed_response.json()
    assert body["completed"] is True
    assert body["question_number"] == 15

    summary_response = client.get(f"/student/comprehensive-practice/summary?session_id={session_id}", headers=headers)
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["is_completed"] is True
    assert summary["phase_breakdown"]["diagnosis"]["total"] == 5
    assert summary["phase_breakdown"]["remedial"]["total"] == 5
    assert summary["phase_breakdown"]["consolidation"]["total"] == 5
    assert summary["summary"]["total_questions"] == 15
