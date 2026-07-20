# Comprehensive Practice Progressive Hints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Keep students on the same Comprehensive Practice question while three wrong answers unlock progressively stronger hints, then complete the question on a later correct answer or a fourth wrong answer with the standard answer and explanation displayed.

**Architecture:** Add a small pure state-transition service for active Comprehensive Practice questions and keep its state inside ComprehensivePracticeSession.state_json. The FastAPI routes remain responsible for database validation and for writing exactly one Attempt, mastery update, style update, and phase result when a question completes. The React page consumes the server-owned state, automatically accumulates unlocked hints, and shows the next-question button only after completion.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, pytest, React, Vite, Node built-in test runner.

**Repository note:** This project directory does not contain a .git directory. The plan therefore uses verified checkpoints instead of commit commands; no step should initialize Git without the user's permission.

---

## File Structure

- Create backend/app/services/comprehensive_progress.py: pure session-state normalization and answer-transition rules.
- Create backend/tests/test_comprehensive_progress.py: fast unit tests for the pure transition rules.
- Modify backend/app/main.py: safe question serialization, active-question loading, progressive submissions, and one-time final persistence.
- Modify backend/tests/test_comprehensive_practice.py: API-level regression tests for loading, hints, completion, duplicate protection, and the existing 15-question flow.
- Modify backend/app/schemas.py: make the now-server-derived hints_used request field use a safe default factory while preserving backward compatibility.
- Create frontend/src/pages/student/comprehensivePracticeState.js: pure client state helpers.
- Create frontend/src/pages/student/comprehensivePracticeState.test.js: Node tests for hint accumulation, incomplete responses, completion, and reset.
- Modify frontend/src/pages/student/ComprehensivePractice.jsx: progressive hint UI and explicit next-question interaction.
- Modify frontend/src/styles.css: small styles for numbered hints, retry feedback, and answer/explanation blocks.
- Modify frontend/package.json: add the exact frontend unit-test command.

---

### Task 1: Build the Pure Comprehensive Question State Machine

**Files:**
- Create: backend/tests/test_comprehensive_progress.py
- Create: backend/app/services/comprehensive_progress.py

- [ ] **Step 1: Write failing transition tests**

Create backend/tests/test_comprehensive_progress.py with:

~~~python
import json

from app.services.comprehensive_progress import (
    HINT_LEVELS,
    apply_comprehensive_answer,
    create_active_question,
    dump_comprehensive_state,
    load_comprehensive_state,
)


def active_question():
    return create_active_question(
        question_id=17,
        question_number=3,
        phase="diagnosis",
    )


def test_load_state_adds_active_question_without_losing_phase_results():
    state = load_comprehensive_state(
        json.dumps(
            {
                "phase1_results": [{"question_id": 1}],
                "phase2_results": [],
                "phase3_results": [],
            }
        )
    )

    assert state["phase1_results"] == [{"question_id": 1}]
    assert state["active_question"] is None
    assert json.loads(dump_comprehensive_state(state)) == state


def test_three_wrong_answers_unlock_hints_in_order_without_completing():
    active = active_question()

    for expected_level in HINT_LEVELS:
        active, transition = apply_comprehensive_answer(
            active=active,
            answer_text="wrong",
            answer_is_correct=False,
        )
        assert transition["completed"] is False
        assert transition["outcome"] == "in_progress"
        assert transition["revealed_hint_level"] == expected_level

    assert active["attempt_count"] == 3
    assert active["wrong_attempts"] == 3
    assert active["revealed_hints"] == list(HINT_LEVELS)
    assert active["first_wrong_answer"] == "wrong"


def test_correct_after_a_wrong_answer_completes_as_incorrect():
    active, first_transition = apply_comprehensive_answer(
        active=active_question(),
        answer_text="41",
        answer_is_correct=False,
    )
    assert first_transition["completed"] is False

    active, transition = apply_comprehensive_answer(
        active=active,
        answer_text="42",
        answer_is_correct=True,
    )

    assert active["attempt_count"] == 2
    assert transition == {
        "completed": True,
        "outcome": "wrong_completed",
        "is_correct": False,
        "revealed_hint_level": None,
    }


def test_fourth_wrong_answer_completes_as_incorrect_without_a_fourth_hint():
    active = active_question()
    for _ in range(3):
        active, transition = apply_comprehensive_answer(
            active=active,
            answer_text="wrong",
            answer_is_correct=False,
        )
        assert transition["completed"] is False

    active, transition = apply_comprehensive_answer(
        active=active,
        answer_text="still wrong",
        answer_is_correct=False,
    )

    assert active["wrong_attempts"] == 4
    assert active["revealed_hints"] == list(HINT_LEVELS)
    assert transition == {
        "completed": True,
        "outcome": "wrong_completed",
        "is_correct": False,
        "revealed_hint_level": None,
    }


def test_first_answer_correct_completes_as_correct():
    active, transition = apply_comprehensive_answer(
        active=active_question(),
        answer_text="42",
        answer_is_correct=True,
    )

    assert active["attempt_count"] == 1
    assert active["wrong_attempts"] == 0
    assert transition == {
        "completed": True,
        "outcome": "correct",
        "is_correct": True,
        "revealed_hint_level": None,
    }
~~~

- [ ] **Step 2: Run the tests and verify RED**

Run from backend:

~~~powershell
python -m pytest tests/test_comprehensive_progress.py -v
~~~

Expected: collection fails with ModuleNotFoundError for app.services.comprehensive_progress.

- [ ] **Step 3: Implement the minimal pure state service**

Create backend/app/services/comprehensive_progress.py with:

~~~python
import json
from copy import deepcopy


HINT_LEVELS = ("basic", "intermediate", "detailed")
PHASE_RESULT_KEYS = ("phase1_results", "phase2_results", "phase3_results")


def load_comprehensive_state(raw_state: str | None) -> dict:
    try:
        parsed = json.loads(raw_state or "{}")
    except (TypeError, json.JSONDecodeError):
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    for key in PHASE_RESULT_KEYS:
        if not isinstance(parsed.get(key), list):
            parsed[key] = []
    parsed.setdefault("active_question", None)
    return parsed


def dump_comprehensive_state(state: dict) -> str:
    return json.dumps(state, ensure_ascii=False)


def create_active_question(question_id: int, question_number: int, phase: str) -> dict:
    return {
        "question_id": question_id,
        "question_number": question_number,
        "phase": phase,
        "wrong_attempts": 0,
        "attempt_count": 0,
        "first_wrong_answer": None,
        "revealed_hints": [],
        "started": True,
    }


def apply_comprehensive_answer(
    active: dict,
    answer_text: str,
    answer_is_correct: bool,
) -> tuple[dict, dict]:
    updated = deepcopy(active)
    updated["attempt_count"] = int(updated.get("attempt_count", 0)) + 1
    wrong_attempts = int(updated.get("wrong_attempts", 0))

    if answer_is_correct:
        final_is_correct = wrong_attempts == 0
        return updated, {
            "completed": True,
            "outcome": "correct" if final_is_correct else "wrong_completed",
            "is_correct": final_is_correct,
            "revealed_hint_level": None,
        }

    wrong_attempts += 1
    updated["wrong_attempts"] = wrong_attempts
    if not updated.get("first_wrong_answer"):
        updated["first_wrong_answer"] = answer_text

    if wrong_attempts >= 4:
        return updated, {
            "completed": True,
            "outcome": "wrong_completed",
            "is_correct": False,
            "revealed_hint_level": None,
        }

    revealed_hints = list(updated.get("revealed_hints", []))
    level = HINT_LEVELS[wrong_attempts - 1]
    if level not in revealed_hints:
        revealed_hints.append(level)
    updated["revealed_hints"] = revealed_hints
    return updated, {
        "completed": False,
        "outcome": "in_progress",
        "is_correct": None,
        "revealed_hint_level": level,
    }
~~~

- [ ] **Step 4: Run the tests and verify GREEN**

Run:

~~~powershell
python -m pytest tests/test_comprehensive_progress.py -v
~~~

Expected: 5 passed.

- [ ] **Step 5: Record the verified checkpoint**

Record in the execution notes: pure state tests pass; no Git commit is possible because the project has no .git directory.

---

### Task 2: Make the Next-Question Endpoint Resume One Safe Active Question

**Files:**
- Modify: backend/tests/test_comprehensive_practice.py
- Modify: backend/app/main.py

- [ ] **Step 1: Add failing API tests for active-question reuse and hidden support text**

In backend/tests/test_comprehensive_practice.py, extend the imports and add a database helper:

~~~python
from sqlalchemy import func, select

from app.models import (
    Attempt,
    ComprehensivePracticeSession,
    MasteryRecord,
    Question,
    StylePreference,
    User,
)


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
~~~

Add:

~~~python
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
~~~

- [ ] **Step 2: Run the single test and verify RED**

Run:

~~~powershell
python -m pytest tests/test_comprehensive_practice.py::test_comprehensive_next_reuses_active_question_and_hides_answers -v
~~~

Expected: FAIL because the second request increments the question number or selects a new question, and because the question payload exposes answer/support fields.

- [ ] **Step 3: Import the state helpers and initialize active_question**

In backend/app/main.py, add:

~~~python
from .services.comprehensive_progress import (
    create_active_question,
    dump_comprehensive_state,
    load_comprehensive_state,
)
~~~

Change the start-session state to:

~~~python
state_json=dump_comprehensive_state(
    {
        "phase1_results": [],
        "phase2_results": [],
        "phase3_results": [],
        "active_question": None,
    }
)
~~~

- [ ] **Step 4: Add safe comprehensive serialization helpers**

Add these module-level helpers near the existing serialize_question functions in backend/app/main.py:

~~~python
COMPREHENSIVE_PRIVATE_QUESTION_FIELDS = {
    "expected_answer",
    "explanation_ms",
    "hint_ms",
    "hint_level2_ms",
    "hint_level3_ms",
}


def serialize_comprehensive_question(db: Session, question: Question) -> dict:
    payload = serialize_question_with_context(db, question)
    for field in COMPREHENSIVE_PRIVATE_QUESTION_FIELDS:
        payload.pop(field, None)
    return payload


def comprehensive_hint_text(question: Question, level: str) -> str:
    candidates = {
        "basic": question.hint_ms,
        "intermediate": question.hint_level2_ms,
        "detailed": question.hint_level3_ms,
    }
    fallback = {
        "basic": f"Kenal pasti operasi utama dalam soalan: {question.prompt_ms}",
        "intermediate": f"Tulis pengiraan untuk soalan ini langkah demi langkah: {question.prompt_ms}",
        "detailed": f"Semak semula setiap langkah dan unit yang digunakan dalam: {question.prompt_ms}",
    }
    return candidates.get(level) or fallback[level]


def serialize_revealed_hints(question: Question, levels: list[str]) -> list[dict]:
    return [
        {"level": level, "text_ms": comprehensive_hint_text(question, level)}
        for level in levels
    ]
~~~

- [ ] **Step 5: Replace active-question selection inside the GET route**

In get_next_comprehensive_question, after ownership and completion validation, load state first. Reuse the active question if present; otherwise call the existing adaptive selector exactly once and store its result:

~~~python
        state = load_comprehensive_state(session.state_json)
        active = state.get("active_question")

        if active:
            question = db.get(Question, active["question_id"])
            if not question or not question.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Soalan aktif tidak ditemui.",
                )
        else:
            try:
                selection = select_next_question_for_session(session_id, db)
            except StopIteration:
                db.refresh(session)
                return {
                    "session_id": session.id,
                    "completed": True,
                    "question_number": session.current_question_number,
                    "total_questions": 15,
                }
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(exc),
                ) from exc

            question = db.get(Question, selection["question_id"])
            if not question:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Soalan tidak ditemui.",
                )
            active = create_active_question(
                question_id=question.id,
                question_number=selection["question_number"],
                phase=selection["phase"],
            )
            state["active_question"] = active
            session.state_json = dump_comprehensive_state(state)

        ensure_question_hints(question, db)
        phase_map = {
            "diagnosis": "Diagnostik",
            "remedial": "Pemulihan",
            "consolidation": "Pengukuhan",
        }
        question_number = active["question_number"]
        phase = active["phase"]
        return {
            "session_id": session.id,
            "completed": False,
            "question_number": question_number,
            "phase": phase,
            "phase_info": {
                "phase_name": phase_map.get(phase, phase),
                "question_number": question_number,
                "total_questions": 15,
                "progress_percentage": round((question_number / 15) * 100, 1),
            },
            "question": serialize_comprehensive_question(db, question),
            "attempt_count": active["attempt_count"],
            "wrong_attempts": active["wrong_attempts"],
            "revealed_hints": serialize_revealed_hints(
                question,
                list(active.get("revealed_hints", [])),
            ),
        }
~~~

Remove the old hint_config response because it exposes all three hints before they are earned.

- [ ] **Step 6: Run the focused tests**

Run:

~~~powershell
python -m pytest tests/test_comprehensive_progress.py tests/test_comprehensive_practice.py::test_comprehensive_next_reuses_active_question_and_hides_answers -v
~~~

Expected: all selected tests pass.

- [ ] **Step 7: Record the verified checkpoint**

Record: repeated GET requests return the same safe question and do not increment progress.

---

### Task 3: Implement Progressive Submission and One-Time Completion

**Files:**
- Modify: backend/tests/test_comprehensive_practice.py
- Modify: backend/app/main.py
- Modify: backend/app/schemas.py

- [ ] **Step 1: Add failing API tests for the three hints**

Add this helper to backend/tests/test_comprehensive_practice.py:

~~~python
def start_question(client):
    token = login_token(client, "amin")
    headers = {"Authorization": f"Bearer {token}"}
    session_id = client.post(
        "/student/comprehensive-practice/start",
        headers=headers,
    ).json()["session_id"]
    question = client.get(
        f"/student/comprehensive-practice/next?session_id={session_id}",
        headers=headers,
    ).json()["question"]
    return headers, session_id, question
~~~

Add:

~~~python
def test_first_three_wrong_answers_unlock_hints_without_formal_attempt(client):
    headers, session_id, question = start_question(client)
    student_id = student_id_for(client)
    question_record = database_result(
        client,
        lambda db: db.get(Question, question["id"]),
    )
    initial_mastery_score = mastery_score_for(
        client,
        student_id,
        question["subtopic_id"],
    )
    initial_style_attempts = style_attempts_for(
        client,
        student_id,
        question_record.presentation_style,
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
        question_record.presentation_style,
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
~~~

- [ ] **Step 2: Add failing completion and duplicate-protection tests**

Add:

~~~python
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
        lambda db: list(
            db.scalars(
                select(Attempt).where(
                    Attempt.question_id == question["id"],
                    Attempt.answer_text == "wrong-1",
                )
            ).all()
        ),
    )
    assert len(attempts) == 1
    assert attempts[0].is_correct is False

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
            .where(Attempt.question_id == question["id"])
            .order_by(Attempt.id.desc())
        ),
    )
    assert attempt.answer_text == "wrong-first"
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
~~~

- [ ] **Step 3: Run the new tests and verify RED**

Run:

~~~powershell
python -m pytest tests/test_comprehensive_practice.py -k "first_three_wrong or fourth_wrong or correct_after_wrong or first_correct" -v
~~~

Expected: failures because the current route finalizes every submission and does not return progressive response fields.

- [ ] **Step 4: Use a safe default for the legacy request field**

In backend/app/schemas.py change the request model to:

~~~python
class ComprehensiveSubmitRequest(BaseModel):
    session_id: int
    question_id: int
    answer_text: str = Field(min_length=1)
    time_seconds: int = Field(ge=1, le=1800)
    hints_used: list[str] = Field(default_factory=list)
~~~

The server will ignore payload.hints_used and derive it from active-question state.

- [ ] **Step 5: Import the transition helper**

Extend the comprehensive_progress import in backend/app/main.py:

~~~python
from .services.comprehensive_progress import (
    apply_comprehensive_answer,
    create_active_question,
    dump_comprehensive_state,
    load_comprehensive_state,
)
~~~

- [ ] **Step 6: Replace the comprehensive submit route with the state-driven flow**

Keep the current route signature and ownership checks, then use this body after loading the session:

~~~python
        state = load_comprehensive_state(session.state_json)
        active = state.get("active_question")
        if not active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Soalan ini telah selesai atau belum dimulakan.",
            )
        if active["question_id"] != payload.question_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Soalan yang dihantar bukan soalan aktif.",
            )

        question = db.get(Question, payload.question_id)
        if not question or not question.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Soalan tidak ditemui.",
            )

        answer_matches = is_equivalent_answer(
            payload.answer_text,
            question.expected_answer,
        )
        updated_active, transition = apply_comprehensive_answer(
            active=active,
            answer_text=payload.answer_text,
            answer_is_correct=answer_matches,
        )
        state["active_question"] = updated_active

        if not transition["completed"]:
            session.state_json = dump_comprehensive_state(state)
            level = transition["revealed_hint_level"]
            db.flush()
            return {
                "completed": False,
                "outcome": "in_progress",
                "is_correct": None,
                "attempt_number": updated_active["attempt_count"],
                "wrong_attempts": updated_active["wrong_attempts"],
                "feedback_ms": "Belum tepat. Cuba lagi dengan petunjuk ini.",
                "revealed_hint": {
                    "level": level,
                    "text_ms": comprehensive_hint_text(question, level),
                },
            }

        final_is_correct = transition["is_correct"]
        subtopic = db.get(Subtopic, question.subtopic_id)
        if not subtopic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subtopik tidak ditemui.",
            )

        mastery = get_or_create_mastery(db, user.id, subtopic)
        updated_mastery = update_mastery(
            MasteryState(
                mastery.score,
                mastery.streak_correct,
                mastery.streak_wrong,
            ),
            AttemptSignal(
                is_correct=final_is_correct,
                difficulty=question.difficulty,
                time_seconds=payload.time_seconds,
            ),
        )
        mastery.score = updated_mastery.score
        mastery.streak_correct = updated_mastery.streak_correct
        mastery.streak_wrong = updated_mastery.streak_wrong

        update_style_preference(
            student_id=user.id,
            presentation_style=question.presentation_style,
            is_correct=final_is_correct,
            time_seconds=payload.time_seconds,
            db=db,
        )

        outcome = transition["outcome"]
        feedback = "Betul." if outcome == "correct" else "Salah tetapi selesai."
        recorded_answer = (
            payload.answer_text
            if final_is_correct
            else updated_active.get("first_wrong_answer") or payload.answer_text
        )
        db.add(
            Attempt(
                student_id=user.id,
                question_id=question.id,
                chapter_id=question.chapter_id,
                subtopic_id=question.subtopic_id,
                answer_text=recorded_answer,
                is_correct=final_is_correct,
                time_seconds=payload.time_seconds,
                feedback_ms=feedback,
            )
        )

        phase_key = {
            "diagnosis": "phase1_results",
            "remedial": "phase2_results",
            "consolidation": "phase3_results",
        }.get(updated_active["phase"])
        if not phase_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fasa sesi tidak sah.",
            )

        hints_used = list(updated_active.get("revealed_hints", []))
        state[phase_key].append(
            {
                "question_id": question.id,
                "subtopic_id": question.subtopic_id,
                "difficulty": question.difficulty,
                "is_correct": final_is_correct,
                "outcome": outcome,
                "attempt_count": updated_active["attempt_count"],
                "wrong_attempts": updated_active["wrong_attempts"],
                "hints_used": hints_used,
                "time_seconds": payload.time_seconds,
            }
        )
        state["active_question"] = None
        session.state_json = dump_comprehensive_state(state)
        db.flush()
        db.refresh(mastery)

        return {
            "completed": True,
            "outcome": outcome,
            "is_correct": final_is_correct,
            "attempt_number": updated_active["attempt_count"],
            "wrong_attempts": updated_active["wrong_attempts"],
            "feedback_ms": feedback,
            "correct_answer": question.expected_answer,
            "explanation_ms": question.explanation_ms,
            "hints_used": hints_used,
            "mastery_updated": {
                "subtopic_id": subtopic.id,
                "subtopic_title_ms": subtopic.title_ms,
                "score": round(mastery.score, 2),
                "streak_correct": mastery.streak_correct,
                "streak_wrong": mastery.streak_wrong,
            },
        }
~~~

Delete the old always-finalize logic so no duplicate Attempt or mastery update remains.

- [ ] **Step 7: Update existing correct-answer tests for the private payload**

In both existing tests in backend/tests/test_comprehensive_practice.py, replace:

~~~python
"answer_text": question["expected_answer"],
~~~

with:

~~~python
"answer_text": expected_answer_for(client, question["id"]),
~~~

The rest of those tests should remain unchanged.

- [ ] **Step 8: Run all comprehensive tests and fix only failures caused by the new contract**

Run:

~~~powershell
python -m pytest tests/test_comprehensive_progress.py tests/test_comprehensive_practice.py -v
~~~

Expected: all tests pass, including the 15-question 5/5/5 phase test.

- [ ] **Step 9: Run related backend regressions**

Run:

~~~powershell
python -m pytest tests/test_answer_checker.py tests/test_adaptive_selector.py tests/test_hint_generator.py -v
~~~

Expected: all tests pass.

- [ ] **Step 10: Record the verified checkpoint**

Record: three hints progress without formal scoring; all completion paths persist one final result; duplicate submissions return HTTP 409.

---

### Task 4: Add Tested Frontend Interaction State

**Files:**
- Modify: frontend/package.json
- Create: frontend/src/pages/student/comprehensivePracticeState.test.js
- Create: frontend/src/pages/student/comprehensivePracticeState.js

- [ ] **Step 1: Add the frontend test command and failing tests**

Add this script to frontend/package.json:

~~~json
"test": "node --test src/pages/student/comprehensivePracticeState.test.js"
~~~

Create frontend/src/pages/student/comprehensivePracticeState.test.js:

~~~javascript
import test from "node:test";
import assert from "node:assert/strict";

import {
  applySubmissionResponse,
  createQuestionInteraction,
} from "./comprehensivePracticeState.js";


test("creates an empty interaction for a new question", () => {
  assert.deepEqual(createQuestionInteraction(), {
    answer: "",
    feedback: null,
    result: null,
    revealedHints: [],
  });
});


test("an incomplete response clears the answer and appends one hint", () => {
  const next = applySubmissionResponse(
    {
      answer: "41",
      feedback: null,
      result: null,
      revealedHints: [],
    },
    {
      completed: false,
      feedback_ms: "Belum tepat.",
      revealed_hint: { level: "basic", text_ms: "Hint 1" },
    },
  );

  assert.deepEqual(next, {
    answer: "",
    feedback: "Belum tepat.",
    result: null,
    revealedHints: [{ level: "basic", text_ms: "Hint 1" }],
  });
});


test("repeated hint levels are not duplicated", () => {
  const next = applySubmissionResponse(
    {
      answer: "40",
      feedback: "Belum tepat.",
      result: null,
      revealedHints: [{ level: "basic", text_ms: "Hint 1" }],
    },
    {
      completed: false,
      feedback_ms: "Cuba lagi.",
      revealed_hint: { level: "basic", text_ms: "Hint 1" },
    },
  );

  assert.equal(next.revealedHints.length, 1);
});


test("a completed response preserves hints and stores the result", () => {
  const response = {
    completed: true,
    outcome: "wrong_completed",
    correct_answer: "42",
    explanation_ms: "40 + 2 = 42",
  };
  const next = applySubmissionResponse(
    {
      answer: "42",
      feedback: "Belum tepat.",
      result: null,
      revealedHints: [{ level: "basic", text_ms: "Hint 1" }],
    },
    response,
  );

  assert.equal(next.answer, "42");
  assert.equal(next.feedback, null);
  assert.equal(next.result, response);
  assert.equal(next.revealedHints.length, 1);
});
~~~

- [ ] **Step 2: Run the frontend tests and verify RED**

Run from frontend:

~~~powershell
npm test
~~~

Expected: FAIL with ERR_MODULE_NOT_FOUND for comprehensivePracticeState.js.

- [ ] **Step 3: Implement the pure frontend state helpers**

Create frontend/src/pages/student/comprehensivePracticeState.js:

~~~javascript
export function createQuestionInteraction() {
  return {
    answer: "",
    feedback: null,
    result: null,
    revealedHints: [],
  };
}


export function applySubmissionResponse(interaction, response) {
  if (response.completed) {
    return {
      ...interaction,
      feedback: null,
      result: response,
    };
  }

  const nextHints = [...interaction.revealedHints];
  const revealedHint = response.revealed_hint;
  if (
    revealedHint &&
    !nextHints.some((hint) => hint.level === revealedHint.level)
  ) {
    nextHints.push(revealedHint);
  }

  return {
    ...interaction,
    answer: "",
    feedback: response.feedback_ms,
    result: null,
    revealedHints: nextHints,
  };
}
~~~

- [ ] **Step 4: Run the frontend tests and verify GREEN**

Run:

~~~powershell
npm test
~~~

Expected: 4 tests pass.

- [ ] **Step 5: Record the verified checkpoint**

Record: client state correctly accumulates hints, clears retry answers, and preserves the final result.

---

### Task 5: Update the Comprehensive Practice React Page

**Files:**
- Modify: frontend/src/pages/student/ComprehensivePractice.jsx
- Modify: frontend/src/styles.css

- [ ] **Step 1: Import the tested interaction helpers and replace old hint state**

In ComprehensivePractice.jsx add:

~~~javascript
import {
  applySubmissionResponse,
  createQuestionInteraction,
} from "./comprehensivePracticeState";
~~~

Replace result, answer, hintsUsed, and expandedHintLevel state with:

~~~javascript
const [interaction, setInteraction] = useState(createQuestionInteraction);
const [isSubmitting, setIsSubmitting] = useState(false);
~~~

Read these values after the state declarations:

~~~javascript
const {
  answer,
  feedback: attemptFeedback,
  result,
  revealedHints,
} = interaction;
~~~

- [ ] **Step 2: Reset interaction state only after the next question loads successfully**

Replace loadNextQuestion with this version so a failed network request leaves the completed question, answer, and hints visible:

~~~javascript
async function loadNextQuestion(sid) {
  setError("");
  try {
    const nextData = await api.getNextComprehensiveQuestion(sid);
    if (nextData.completed) {
      setData(null);
      setShowSummary(true);
      return;
    }
    setData(nextData);
    setQuestionNumber(nextData.question_number);
    setInteraction({
      answer: "",
      feedback: null,
      result: null,
      revealedHints: nextData.revealed_hints || [],
    });
    setElapsedSeconds(0);
    setStartedAt(Date.now());
  } catch (err) {
    setError(err.message);
  }
}
~~~

- [ ] **Step 3: Replace submit with retry-aware behavior**

Use:

~~~javascript
async function submit(event) {
  event.preventDefault();
  if (!data?.question || !sessionId || isSubmitting || result) return;
  setError("");
  setIsSubmitting(true);
  const secondsSpent = Math.max(
    1,
    elapsedSeconds ||
      (startedAt ? Math.floor((Date.now() - startedAt) / 1000) : 1),
  );
  try {
    const submitResult = await api.submitComprehensiveAnswer({
      session_id: sessionId,
      question_id: data.question.id,
      answer_text: answer,
      time_seconds: secondsSpent,
    });
    setInteraction((current) =>
      applySubmissionResponse(current, submitResult),
    );
  } catch (err) {
    setError(err.message);
  } finally {
    setIsSubmitting(false);
  }
}
~~~

Update answer controls with:

~~~javascript
onChange={(event) =>
  setInteraction((current) => ({
    ...current,
    answer: event.target.value,
  }))
}
~~~

For multiple-choice buttons use:

~~~javascript
onClick={() =>
  setInteraction((current) => ({
    ...current,
    answer: option,
  }))
}
~~~

- [ ] **Step 4: Replace manual hints with automatically revealed hints**

Remove toggleHint and the old data.hint_config mapping. Render:

~~~jsx
{revealedHints.length > 0 && (
  <div className="hints-section" aria-live="polite">
    {revealedHints.map((hint, index) => (
      <div key={hint.level} className="hint-item progressive-hint">
        <strong>Petunjuk {index + 1}</strong>
        <p className="hint-box">{hint.text_ms}</p>
      </div>
    ))}
  </div>
)}

{attemptFeedback && !result && (
  <p className="retry-feedback" role="status">
    {attemptFeedback}
  </p>
)}
~~~

- [ ] **Step 5: Keep the form active for retries and lock it only at completion**

Use result and isSubmitting for disabled states:

~~~jsx
disabled={Boolean(result) || isSubmitting}
~~~

Use this submit button:

~~~jsx
<button
  className="primary-button"
  disabled={!answer.trim() || Boolean(result) || isSubmitting}
>
  {isSubmitting ? "Menyemak..." : "Hantar"}
</button>
~~~

- [ ] **Step 6: Render the final answer, explanation, metrics, and explicit next button**

Replace the current result card with:

~~~jsx
{result && (
  <div
    className={
      result.outcome === "correct"
        ? "card success-card"
        : "card danger-card"
    }
  >
    <h3>
      {result.outcome === "correct"
        ? "Betul"
        : "Salah tetapi selesai"}
    </h3>
    <p>{result.feedback_ms}</p>
    <div className="answer-review">
      <p>
        <strong>Jawapan betul:</strong> {result.correct_answer}
      </p>
      <p>
        <strong>Penjelasan:</strong> {result.explanation_ms}
      </p>
    </div>
    <p>
      Cubaan: {result.attempt_number} | Petunjuk digunakan:{" "}
      {result.hints_used.length}
    </p>
    <button className="primary-button" onClick={continueSession}>
      Soalan Seterusnya
    </button>
  </div>
)}
~~~

Do not call continueSession from submit. The button is the only completion path that loads a new question.

- [ ] **Step 7: Keep errors on the current page and reset state on an explicit restart**

Delete the early return:

~~~javascript
if (error) return <p className="error-text">{error}</p>;
~~~

Render this inside both the start-session section and the active-question section:

~~~jsx
{error && <p className="error-text" role="alert">{error}</p>}
~~~

In PracticeSummary onRestart, replace the old setResult call and reset all interaction-specific state:

~~~javascript
onRestart={() => {
  setSessionId(null);
  setShowSummary(false);
  setData(null);
  setInteraction(createQuestionInteraction());
  setError("");
}}
~~~

- [ ] **Step 8: Add focused styles**

Add to frontend/src/styles.css:

~~~css
.progressive-hint {
  border-left: 3px solid var(--primary);
  padding-left: 12px;
}

.retry-feedback {
  margin: 0;
  color: var(--danger);
  font-weight: 700;
}

.answer-review {
  display: grid;
  gap: 8px;
  padding: 14px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.04);
}

.answer-review p {
  margin: 0;
}
~~~

- [ ] **Step 9: Run frontend tests**

Run:

~~~powershell
npm test
~~~

Expected: 4 tests pass.

- [ ] **Step 10: Build the production frontend**

Run:

~~~powershell
npm run build
~~~

Expected: Vite exits with code 0 and writes frontend/dist.

- [ ] **Step 11: Record the verified checkpoint**

Record: the UI hides unearned hints, allows retries, displays every completed answer and explanation, and loads a new question only from the button.

---

### Task 6: Full Regression Verification

**Files:**
- No new files unless verification exposes a defect in the files already listed.

- [ ] **Step 1: Run the complete backend suite**

Run from backend:

~~~powershell
python -m pytest tests -v
~~~

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend tests and build together**

Run from frontend:

~~~powershell
npm test
npm run build
~~~

Expected: all Node tests pass and Vite exits with code 0.

- [ ] **Step 3: Perform a local API smoke flow**

With the backend running, use the student account to verify one question through these observable states:

1. Initial question contains no standard answer, explanation, or unlocked hint.
2. Wrong answer 1 shows Petunjuk 1 and leaves the form enabled.
3. Wrong answer 2 shows Petunjuk 1 and Petunjuk 2.
4. Wrong answer 3 shows all three hints.
5. Wrong answer 4 shows Salah tetapi selesai, the correct answer, and explanation.
6. The question remains visible until Soalan Seterusnya is clicked.

Repeat with a first-attempt correct answer and verify Betul plus the standard answer and explanation.

- [ ] **Step 4: Inspect persistence after smoke verification**

Query through the application's SQLAlchemy session or a read-only database client and confirm:

- One completed question created one Attempt row.
- A four-wrong sequence did not create four Attempt rows.
- The phase result contains attempt_count, wrong_attempts, outcome, hints_used, and one final is_correct value.
- The session current_question_number increased once for that question.

- [ ] **Step 5: Apply verification-before-completion**

Before reporting success, invoke superpowers:verification-before-completion and repeat any command it requires. Report exact pass counts and build result. Do not claim completion from code inspection alone.
