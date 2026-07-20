import json

from sqlalchemy import select

from app.models import Attempt, Chapter, ComprehensivePracticeSession, GenerationLog, Question, Subtopic
from app.services import adaptive_selector
from app.services.adaptive_selector import select_next_question_for_session


def test_select_next_question_uses_template_when_bank_questions_are_all_attempted(db, student_user, sample_question, monkeypatch):
    second_question = Question(
        chapter_id=sample_question.chapter_id,
        subtopic_id=sample_question.subtopic_id,
        difficulty=sample_question.difficulty,
        prompt_ms="Kira 26 + 37",
        expected_answer="63",
        question_type="short_answer",
        options_json="[]",
        explanation_ms="Soalan latihan kedua.",
        hint_ms="Tambah dua nombor itu.",
        presentation_style="text_based",
        hint_level2_ms="",
        hint_level3_ms="",
        source="seed",
        validation_status="validated",
        is_active=True,
    )
    db.add(second_question)
    db.commit()
    db.refresh(second_question)

    db.add_all(
        [
            Attempt(
                student_id=student_user.id,
                question_id=sample_question.id,
                chapter_id=sample_question.chapter_id,
                subtopic_id=sample_question.subtopic_id,
                answer_text=sample_question.expected_answer,
                is_correct=True,
                time_seconds=20,
                feedback_ms="ok",
            ),
            Attempt(
                student_id=student_user.id,
                question_id=second_question.id,
                chapter_id=second_question.chapter_id,
                subtopic_id=second_question.subtopic_id,
                answer_text=second_question.expected_answer,
                is_correct=True,
                time_seconds=20,
                feedback_ms="ok",
            ),
        ]
    )

    session = ComprehensivePracticeSession(
        student_id=student_user.id,
        current_question_number=10,
        phase="consolidation",
        is_completed=False,
        weak_subtopics_json=json.dumps(
            [
                {
                    "subtopic_id": sample_question.subtopic_id,
                    "title_ms": "Tambah dan Tolak",
                    "mastery_score": 51.0,
                }
            ]
        ),
        state_json=json.dumps({"phase1_results": [], "phase2_results": [], "phase3_results": []}),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    monkeypatch.setattr(adaptive_selector, "_select_presentation_style", lambda student_id, db, exploration_rate=0.2: "text_based")
    monkeypatch.setattr(adaptive_selector.random, "random", lambda: 0.0)
    monkeypatch.setattr(adaptive_selector, "generate_question_ms", lambda *args, **kwargs: None, raising=False)

    selection = select_next_question_for_session(session.id, db)

    selected_question = db.get(Question, selection["question_id"])
    assert selected_question.source == "template"
    assert selection["question_id"] not in {sample_question.id, second_question.id}
    assert selection["subtopic_id"] == sample_question.subtopic_id
    assert selection["question_number"] == 11


def test_find_or_generate_question_creates_llm_question_when_bank_is_empty(db, student_user, monkeypatch):
    chapter = Chapter(number=99, title_ms="Ujian LLM", is_active=True)
    db.add(chapter)
    db.commit()
    db.refresh(chapter)

    subtopic = Subtopic(
        chapter_id=chapter.id,
        title_ms="Topik baharu tanpa bank soalan",
        activity_type="lesson",
        is_active=True,
    )
    db.add(subtopic)
    db.commit()
    db.refresh(subtopic)

    def fake_generate_question_ms(subtopic_title, difficulty, question_type="short_answer"):
        assert subtopic_title == subtopic.title_ms
        assert difficulty == "medium"
        assert question_type == "short_answer"
        return {
            "difficulty": difficulty,
            "prompt_ms": "Apakah nilai 12 + 8?",
            "expected_answer": "20",
            "question_type": question_type,
            "options": [],
            "explanation_ms": "12 + 8 = 20.",
            "hint_ms": "Tambah 8 kepada 12.",
            "presentation_style": "text_based",
            "hint_level2_ms": "",
            "hint_level3_ms": "",
            "source": "ai",
            "validation_status": "validated",
            "is_active": True,
        }

    monkeypatch.setattr(adaptive_selector, "generate_question_ms", fake_generate_question_ms, raising=False)

    question = adaptive_selector._find_or_generate_question(
        student_id=student_user.id,
        subtopic_id=subtopic.id,
        difficulty="medium",
        presentation_style="text_based",
        db=db,
    )

    assert question is not None
    assert question.source == "ai"
    assert question.subtopic_id == subtopic.id
    assert question.options_json == "[]"
    assert db.scalar(select(Question).where(Question.id == question.id)) is not None

    log = db.scalar(select(GenerationLog).where(GenerationLog.subtopic_id == subtopic.id))
    assert log is not None
    assert log.teacher_id == student_user.id
    assert log.prompt_ms == question.prompt_ms
