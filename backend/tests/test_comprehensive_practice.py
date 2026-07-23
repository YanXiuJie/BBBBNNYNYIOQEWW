import json

import pytest
from sqlalchemy import func, select

from app.models import (
    Attempt,
    ComprehensivePracticeSession,
    DiagnosticSession,
    MasteryRecord,
    Question,
    StylePreference,
    User,
)


@pytest.fixture(autouse=True)
def prepare_comprehensive_student(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with client.app.state.session_factory() as db:
        student_id = db.scalar(select(User.id).where(User.username == "amin"))
        db.add(
            DiagnosticSession(
                student_id=student_id,
                status="completed",
                current_question_number=8,
                total_questions=8,
                state_json="{}",
            )
        )
        db.commit()


def login_token(client, username):
    response = client.post("/auth/login", json={"username": username, "password": "password123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def database_result(client, callback):
    with client.app.state.session_factory() as db:
        return callback(db)


def expected_answer_for(client, question_id):
    return database_result(client, lambda db: db.get(Question, question_id).expected_answer)


def student_id_for(client, username="amin"):
    return database_result(
        client,
        lambda db: db.scalar(select(User.id).where(User.username == username)),
    )


def mastery_score_for(client, student_id, subtopic_id):
    return database_result(
        client,
        lambda db: db.scalar(
            select(MasteryRecord.score).where(
                MasteryRecord.student_id == student_id,
                MasteryRecord.subtopic_id == subtopic_id,
            )
        ),
    )


def style_attempts_for(client, student_id, presentation_style):
    return database_result(
        client,
        lambda db: db.scalar(
            select(StylePreference.total_attempts).where(
                StylePreference.student_id == student_id,
                StylePreference.presentation_style == presentation_style,
            )
        ),
    )


def start_question(client):
    token = login_token(client, "amin")
    headers = {"Authorization": f"Bearer {token}"}
    start_response = client.post("/student/comprehensive-practice/start", headers=headers)
    assert start_response.status_code == 201
    session_id = start_response.json()["session_id"]
    next_response = client.get(
        f"/student/comprehensive-practice/next?session_id={session_id}",
        headers=headers,
    )
    assert next_response.status_code == 200
    return headers, session_id, next_response.json()["question"]


def test_comprehensive_next_reuses_active_question_and_hides_answers(client):
    token = login_token(client, "amin")
    headers = {"Authorization": f"Bearer {token}"}
    session_id = client.post(
        "/student/comprehensive-practice/start",
        headers=headers,
    ).json()["session_id"]

    first = client.get(
        f"/student/comprehensive-practice/next?session_id={session_id}",
        headers=headers,
    )
    second = client.get(
        f"/student/comprehensive-practice/next?session_id={session_id}",
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_body = first.json()
    second_body = second.json()
    assert second_body["question"]["id"] == first_body["question"]["id"]
    assert second_body["question_number"] == first_body["question_number"] == 1
    assert second_body["attempt_count"] == 0
    assert second_body["wrong_attempts"] == 0
    assert second_body["revealed_hints"] == []

    hidden_fields = {
        "expected_answer",
        "explanation_ms",
        "hint_ms",
        "hint_level2_ms",
        "hint_level3_ms",
    }
    assert hidden_fields.isdisjoint(first_body["question"])

    session_state = database_result(
        client,
        lambda db: json.loads(db.get(ComprehensivePracticeSession, session_id).state_json),
    )
    assert session_state["active_question"]["question_id"] == first_body["question"]["id"]


def test_first_three_wrong_answers_unlock_hints_without_formal_attempt(client):
    headers, session_id, question = start_question(client)
    student_id = student_id_for(client)
    presentation_style = database_result(
        client,
        lambda db: db.get(Question, question["id"]).presentation_style,
    )
    initial_mastery_score = mastery_score_for(
        client,
        student_id,
        question["subtopic_id"],
    )
    initial_style_attempts = style_attempts_for(
        client,
        student_id,
        presentation_style,
    )
    initial_attempt_count = database_result(
        client,
        lambda db: db.scalar(
            select(func.count(Attempt.id)).where(Attempt.question_id == question["id"])
        ),
    )

    for attempt_number, expected_level in enumerate(
        ["basic", "intermediate", "detailed"],
        start=1,
    ):
        response = client.post(
            "/student/comprehensive-practice/submit",
            headers=headers,
            json={
                "session_id": session_id,
                "question_id": question["id"],
                "answer_text": f"wrong-{attempt_number}",
                "time_seconds": attempt_number * 10,
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["completed"] is False
        assert body["outcome"] == "in_progress"
        assert body["attempt_number"] == attempt_number
        assert body["wrong_attempts"] == attempt_number
        assert body["revealed_hint"]["level"] == expected_level
        assert body["revealed_hint"]["text_ms"]

    final_attempt_count = database_result(
        client,
        lambda db: db.scalar(
            select(func.count(Attempt.id)).where(Attempt.question_id == question["id"])
        ),
    )
    assert final_attempt_count == initial_attempt_count
    assert mastery_score_for(
        client,
        student_id,
        question["subtopic_id"],
    ) == initial_mastery_score
    assert style_attempts_for(
        client,
        student_id,
        presentation_style,
    ) == initial_style_attempts

    state = database_result(
        client,
        lambda db: json.loads(db.get(ComprehensivePracticeSession, session_id).state_json),
    )
    assert state["phase1_results"] == []
    assert state["active_question"]["revealed_hints"] == [
        "basic",
        "intermediate",
        "detailed",
    ]


def test_fourth_wrong_answer_completes_once_and_reveals_answer(client):
    headers, session_id, question = start_question(client)

    last_response = None
    for attempt_number in range(1, 5):
        last_response = client.post(
            "/student/comprehensive-practice/submit",
            headers=headers,
            json={
                "session_id": session_id,
                "question_id": question["id"],
                "answer_text": f"wrong-{attempt_number}",
                "time_seconds": attempt_number * 10,
            },
        )

    assert last_response.status_code == 201
    body = last_response.json()
    assert body["completed"] is True
    assert body["outcome"] == "wrong_completed"
    assert body["is_correct"] is False
    assert body["correct_answer"] == expected_answer_for(client, question["id"])
    assert body["explanation_ms"]
    assert body["attempt_number"] == 4
    assert body["wrong_attempts"] == 4
    assert body["hints_used"] == ["basic", "intermediate", "detailed"]

    attempts = database_result(
        client,
        lambda db: [
            {
                "answer_text": attempt.answer_text,
                "is_correct": attempt.is_correct,
            }
            for attempt in db.scalars(
                select(Attempt).where(
                    Attempt.question_id == question["id"],
                    Attempt.answer_text == "wrong-1",
                )
            ).all()
        ],
    )
    assert attempts == [{"answer_text": "wrong-1", "is_correct": False}]

    duplicate = client.post(
        "/student/comprehensive-practice/submit",
        headers=headers,
        json={
            "session_id": session_id,
            "question_id": question["id"],
            "answer_text": "wrong-again",
            "time_seconds": 50,
        },
    )
    assert duplicate.status_code == 409


def test_correct_after_wrong_completes_as_wrong_completed(client):
    headers, session_id, question = start_question(client)
    client.post(
        "/student/comprehensive-practice/submit",
        headers=headers,
        json={
            "session_id": session_id,
            "question_id": question["id"],
            "answer_text": "wrong-first",
            "time_seconds": 10,
        },
    )

    response = client.post(
        "/student/comprehensive-practice/submit",
        headers=headers,
        json={
            "session_id": session_id,
            "question_id": question["id"],
            "answer_text": expected_answer_for(client, question["id"]),
            "time_seconds": 20,
        },
    )

    body = response.json()
    assert response.status_code == 201
    assert body["completed"] is True
    assert body["outcome"] == "wrong_completed"
    assert body["is_correct"] is False
    attempt = database_result(
        client,
        lambda db: db.scalar(
            select(Attempt)
            .where(
                Attempt.question_id == question["id"],
                Attempt.answer_text == "wrong-first",
            )
            .order_by(Attempt.id.desc())
        ),
    )
    assert attempt.is_correct is False


def test_first_correct_answer_completes_as_correct_and_reveals_explanation(client):
    headers, session_id, question = start_question(client)
    response = client.post(
        "/student/comprehensive-practice/submit",
        headers=headers,
        json={
            "session_id": session_id,
            "question_id": question["id"],
            "answer_text": expected_answer_for(client, question["id"]),
            "time_seconds": 12,
        },
    )

    body = response.json()
    assert response.status_code == 201
    assert body["completed"] is True
    assert body["outcome"] == "correct"
    assert body["is_correct"] is True
    assert body["correct_answer"] == expected_answer_for(client, question["id"])
    assert body["explanation_ms"]
    assert body["attempt_number"] == 1
    assert body["wrong_attempts"] == 0


def test_comprehensive_summary_tracks_diagnosis_results(client):
    headers, session_id, question = start_question(client)

    wrong_response = client.post(
        "/student/comprehensive-practice/submit",
        headers=headers,
        json={
            "session_id": session_id,
            "question_id": question["id"],
            "answer_text": "wrong-summary",
            "time_seconds": 10,
        },
    )
    assert wrong_response.status_code == 201

    submit_response = client.post(
        "/student/comprehensive-practice/submit",
        headers=headers,
        json={
            "session_id": session_id,
            "question_id": question["id"],
            "answer_text": expected_answer_for(client, question["id"]),
            "time_seconds": 15,
        },
    )
    assert submit_response.status_code == 201

    summary_response = client.get(
        f"/student/comprehensive-practice/summary?session_id={session_id}",
        headers=headers,
    )
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
        next_response = client.get(
            f"/student/comprehensive-practice/next?session_id={session_id}",
            headers=headers,
        )
        assert next_response.status_code == 200
        question = next_response.json()["question"]
        submit_response = client.post(
            "/student/comprehensive-practice/submit",
            headers=headers,
            json={
                "session_id": session_id,
                "question_id": question["id"],
                "answer_text": expected_answer_for(client, question["id"]),
                "time_seconds": 20,
            },
        )
        assert submit_response.status_code == 201

    completed_response = client.get(
        f"/student/comprehensive-practice/next?session_id={session_id}",
        headers=headers,
    )
    assert completed_response.status_code == 200
    body = completed_response.json()
    assert body["completed"] is True
    assert body["question_number"] == 15

    summary_response = client.get(
        f"/student/comprehensive-practice/summary?session_id={session_id}",
        headers=headers,
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["is_completed"] is True
    assert summary["phase_breakdown"]["diagnosis"]["total"] == 5
    assert summary["phase_breakdown"]["remedial"]["total"] == 5
    assert summary["phase_breakdown"]["consolidation"]["total"] == 5
    assert summary["summary"]["total_questions"] == 15
