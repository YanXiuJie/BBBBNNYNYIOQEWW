import json

from sqlalchemy import select

from app.models import DiagnosticSession, User
from app.seeds import seed_demo_data
from app.services.diagnostic_selector import build_diagnostic_blueprint, select_next_diagnostic_question


def test_diagnostic_blueprint_uses_seeded_core_chapters(db):
    seed_demo_data(db)
    blueprint = build_diagnostic_blueprint(db)

    assert len(blueprint) >= 6
    chapter_numbers = {item["chapter_number"] for item in blueprint}
    assert {1, 2, 3, 4, 5, 7}.issubset(chapter_numbers)


def test_diagnostic_selector_recovers_empty_blueprint_state(db):
    seed_demo_data(db)
    student = db.scalar(select(User).where(User.username == "amin"))
    session = DiagnosticSession(
        student_id=student.id,
        status="in_progress",
        current_question_number=0,
        total_questions=8,
        state_json=json.dumps(
            {
                "chapter_blueprint": [],
                "results": [],
                "asked_question_ids": [],
                "asked_subtopic_ids": [],
            },
            ensure_ascii=False,
        ),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    question = select_next_diagnostic_question(session, db)
    db.refresh(session)
    state = json.loads(session.state_json)

    assert question is not None
    assert len(state["chapter_blueprint"]) >= 6
    assert session.total_questions >= 8
