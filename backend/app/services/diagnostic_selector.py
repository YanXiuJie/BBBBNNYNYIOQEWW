import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Chapter, DiagnosticSession, Question, Subtopic

CORE_CHAPTER_IDS = [1, 2, 3, 4, 5, 7]
DEFAULT_TOTAL_QUESTIONS = 8
RECENT_DIAGNOSTIC_WINDOW = 3
DIFFICULTY_LADDER = ["easy", "medium", "hard"]


def build_diagnostic_blueprint(db: Session) -> list[dict]:
    chapter_subtopics = []
    for chapter_number in CORE_CHAPTER_IDS:
        chapter = db.scalar(select(Chapter).where(Chapter.number == chapter_number, Chapter.is_active.is_(True)))
        if not chapter:
            continue
        subtopic = db.scalar(
            select(Subtopic)
            .join(Question, Question.subtopic_id == Subtopic.id)
            .where(Subtopic.chapter_id == chapter.id, Subtopic.is_active.is_(True), Question.is_active.is_(True))
            .order_by(Subtopic.id)
            .distinct()
        )
        if subtopic:
            chapter_subtopics.append(
                {
                    "chapter_id": chapter.id,
                    "chapter_number": chapter.number,
                    "subtopic_id": subtopic.id,
                    "subtopic_title_ms": subtopic.title_ms,
                }
            )
    return chapter_subtopics


def create_diagnostic_session(student_id: int, db: Session) -> DiagnosticSession:
    blueprint = build_diagnostic_blueprint(db)
    state = {
        "chapter_blueprint": blueprint,
        "results": [],
        "asked_question_ids": [],
        "asked_subtopic_ids": [],
    }
    session = DiagnosticSession(
        student_id=student_id,
        status="in_progress",
        current_question_number=0,
        total_questions=max(DEFAULT_TOTAL_QUESTIONS, len(blueprint)),
        state_json=json.dumps(state, ensure_ascii=False),
    )
    db.add(session)
    db.flush()
    return session


def session_state(session: DiagnosticSession) -> dict:
    return json.loads(session.state_json or "{}")


def completed_diagnostic_exists(student_id: int, db: Session) -> bool:
    return bool(
        db.scalar(
            select(DiagnosticSession.id)
            .where(DiagnosticSession.student_id == student_id, DiagnosticSession.status == "completed")
            .limit(1)
        )
    )


def difficulty_after_result(previous_result: dict | None) -> str:
    if not previous_result:
        return "medium"
    if previous_result["is_correct"] and previous_result["time_seconds"] <= 45:
        return "hard" if previous_result["difficulty"] == "medium" else previous_result["difficulty"]
    if not previous_result["is_correct"] or previous_result["time_seconds"] > 90:
        return "easy" if previous_result["difficulty"] == "medium" else previous_result["difficulty"]
    return "medium"


def _ensure_blueprint_state(session: DiagnosticSession, state: dict, db: Session) -> list[dict]:
    blueprint = state.get("chapter_blueprint") or []
    if blueprint:
        return blueprint

    blueprint = build_diagnostic_blueprint(db)
    state["chapter_blueprint"] = blueprint
    session.total_questions = max(DEFAULT_TOTAL_QUESTIONS, len(blueprint))
    session.state_json = json.dumps(state, ensure_ascii=False)
    db.flush()
    return blueprint


def _fallback_difficulty(difficulty: str) -> list[str]:
    idx = DIFFICULTY_LADDER.index(difficulty) if difficulty in DIFFICULTY_LADDER else 1
    ordered = [difficulty]
    for offset in (1, -1, 2, -2):
        nxt = idx + offset
        if 0 <= nxt < len(DIFFICULTY_LADDER):
            candidate = DIFFICULTY_LADDER[nxt]
            if candidate not in ordered:
                ordered.append(candidate)
    return ordered


def select_next_diagnostic_question(session: DiagnosticSession, db: Session) -> Question | None:
    state = session_state(session)
    results = state.get("results", [])
    asked_question_ids = state.get("asked_question_ids", [])
    asked_subtopic_ids = state.get("asked_subtopic_ids", [])
    blueprint = _ensure_blueprint_state(session, state, db)

    if session.current_question_number >= session.total_questions:
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)
        return None

    previous_result = results[-1] if results else None
    target_difficulty = difficulty_after_result(previous_result)

    if session.current_question_number < len(blueprint):
        target_subtopic_id = blueprint[session.current_question_number]["subtopic_id"]
    elif asked_subtopic_ids:
        target_subtopic_id = asked_subtopic_ids[session.current_question_number % len(asked_subtopic_ids)]
    elif blueprint:
        target_subtopic_id = blueprint[session.current_question_number % len(blueprint)]["subtopic_id"]
    else:
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)
        return None

    recent_question_ids = asked_question_ids[-RECENT_DIAGNOSTIC_WINDOW:]
    for difficulty in _fallback_difficulty(target_difficulty):
        query = (
            select(Question)
            .where(
                Question.subtopic_id == target_subtopic_id,
                Question.difficulty == difficulty,
                Question.is_active.is_(True),
                Question.validation_status == "validated",
            )
            .order_by(Question.id)
        )
        candidates = db.scalars(query).all()
        if not candidates:
            continue
        for question in candidates:
            if question.id not in recent_question_ids and question.id not in asked_question_ids:
                return question
        for question in candidates:
            if question.id not in recent_question_ids:
                return question
        return candidates[0]

    return None


def record_diagnostic_progress(
    session: DiagnosticSession,
    question: Question,
    is_correct: bool,
    time_seconds: int,
    db: Session,
) -> dict:
    state = session_state(session)
    results = state.setdefault("results", [])
    asked_question_ids = state.setdefault("asked_question_ids", [])
    asked_subtopic_ids = state.setdefault("asked_subtopic_ids", [])

    results.append(
        {
            "question_id": question.id,
            "subtopic_id": question.subtopic_id,
            "chapter_id": question.chapter_id,
            "difficulty": question.difficulty,
            "is_correct": is_correct,
            "time_seconds": time_seconds,
        }
    )
    asked_question_ids.append(question.id)
    if question.subtopic_id not in asked_subtopic_ids:
        asked_subtopic_ids.append(question.subtopic_id)

    session.current_question_number += 1
    if session.current_question_number >= session.total_questions:
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)

    session.state_json = json.dumps(state, ensure_ascii=False)
    db.flush()
    return state
