from sqlalchemy import select

from app.main import create_app
from app.models import Attempt, Question, Subtopic, User
from app.seeds import seed_demo_data


def test_seed_cleanup_strips_subtopic_prefix_and_removes_unattempted_duplicates(mysql_database_url):
    app = create_app(database_url=mysql_database_url, seed=True)

    with app.state.session_factory() as db:
        subtopic = db.scalar(select(Subtopic).where(Subtopic.title_ms == "Tukar Unit Masa"))
        db.add_all(
            [
                Question(
                    chapter_id=subtopic.chapter_id,
                    subtopic_id=subtopic.id,
                    difficulty="medium",
                    prompt_ms="Tukar Unit Masa: 4 hari bersamaan berapa jam?",
                    expected_answer="96",
                    question_type="multiple_choice",
                    options_json='["96", "98", "94", "100"]',
                    hint_ms="1 hari = 24 jam.",
                    explanation_ms="Demo old duplicate.",
                    source="template",
                    validation_status="validated",
                ),
                Question(
                    chapter_id=subtopic.chapter_id,
                    subtopic_id=subtopic.id,
                    difficulty="medium",
                    prompt_ms="Tukar Unit Masa: 4 hari bersamaan berapa jam?",
                    expected_answer="96",
                    question_type="multiple_choice",
                    options_json='["96", "97", "95", "98"]',
                    hint_ms="1 hari = 24 jam.",
                    explanation_ms="Demo old duplicate.",
                    source="template",
                    validation_status="validated",
                ),
            ]
        )
        db.commit()
        subtopic_id = subtopic.id

    with app.state.session_factory() as db:
        seed_demo_data(db)

    with app.state.session_factory() as db:
        repeated_questions = db.scalars(
            select(Question).where(
                Question.subtopic_id == subtopic_id,
                Question.difficulty == "medium",
                Question.question_type == "multiple_choice",
                Question.prompt_ms == "4 hari bersamaan berapa jam?",
                Question.expected_answer == "96",
                Question.source == "template",
            )
        ).all()
        prompts = db.scalars(select(Question.prompt_ms).where(Question.subtopic_id == subtopic_id)).all()

    assert len(repeated_questions) == 1
    assert all(not prompt.startswith("Tukar Unit Masa:") for prompt in prompts)


def test_seed_cleanup_prefers_duplicate_question_with_attempt_history(mysql_database_url):
    app = create_app(database_url=mysql_database_url, seed=True)

    with app.state.session_factory() as db:
        subtopic = db.scalar(select(Subtopic).where(Subtopic.title_ms == "Tukar Unit Masa"))
        student = db.scalar(select(User).where(User.username == "amin"))
        attempted_question = Question(
            chapter_id=subtopic.chapter_id,
            subtopic_id=subtopic.id,
            difficulty="medium",
            prompt_ms="5 hari bersamaan berapa jam?",
            expected_answer="120",
            question_type="multiple_choice",
            options_json='["120", "122", "118", "124"]',
            hint_ms="1 hari = 24 jam.",
            explanation_ms="Demo attempted duplicate.",
            source="template",
            validation_status="validated",
        )
        db.add(attempted_question)
        db.flush()
        db.add(
            Attempt(
                student_id=student.id,
                question_id=attempted_question.id,
                chapter_id=attempted_question.chapter_id,
                subtopic_id=attempted_question.subtopic_id,
                answer_text="120",
                is_correct=True,
                time_seconds=30,
                feedback_ms="Demo answer.",
            )
        )
        db.add(
            Question(
                chapter_id=subtopic.chapter_id,
                subtopic_id=subtopic.id,
                difficulty="medium",
                prompt_ms="5 hari bersamaan berapa jam?",
                expected_answer="120",
                question_type="multiple_choice",
                options_json='["120", "121", "119", "122"]',
                hint_ms="1 hari = 24 jam.",
                explanation_ms="Demo unattempted duplicate.",
                source="template",
                validation_status="validated",
            )
        )
        db.commit()
        subtopic_id = subtopic.id
        attempted_question_id = attempted_question.id

    with app.state.session_factory() as db:
        seed_demo_data(db)

    with app.state.session_factory() as db:
        repeated_questions = db.scalars(
            select(Question).where(
                Question.subtopic_id == subtopic_id,
                Question.difficulty == "medium",
                Question.question_type == "multiple_choice",
                Question.prompt_ms == "5 hari bersamaan berapa jam?",
                Question.expected_answer == "120",
                Question.source == "template",
            )
        ).all()

    assert [question.id for question in repeated_questions] == [attempted_question_id]


def test_seed_cleanup_merges_attempts_when_duplicate_questions_both_have_history(mysql_database_url):
    app = create_app(database_url=mysql_database_url, seed=True)

    with app.state.session_factory() as db:
        subtopic = db.scalar(select(Subtopic).where(Subtopic.title_ms == "Tukar Unit Masa"))
        student = db.scalar(select(User).where(User.username == "amin"))
        duplicate_questions = []
        for seconds in [30, 40]:
            question = Question(
                chapter_id=subtopic.chapter_id,
                subtopic_id=subtopic.id,
                difficulty="medium",
                prompt_ms="6 hari bersamaan berapa jam?",
                expected_answer="144",
                question_type="multiple_choice",
                options_json='["144", "146", "142", "148"]',
                hint_ms="1 hari = 24 jam.",
                explanation_ms="Demo attempted duplicate.",
                source="template",
                validation_status="validated",
            )
            db.add(question)
            db.flush()
            duplicate_questions.append(question)
            db.add(
                Attempt(
                    student_id=student.id,
                    question_id=question.id,
                    chapter_id=question.chapter_id,
                    subtopic_id=question.subtopic_id,
                    answer_text="144",
                    is_correct=True,
                    time_seconds=seconds,
                    feedback_ms="Demo answer.",
                )
            )
        db.commit()
        subtopic_id = subtopic.id
        keep_question_id = duplicate_questions[0].id

    with app.state.session_factory() as db:
        seed_demo_data(db)

    with app.state.session_factory() as db:
        repeated_questions = db.scalars(
            select(Question).where(
                Question.subtopic_id == subtopic_id,
                Question.difficulty == "medium",
                Question.question_type == "multiple_choice",
                Question.prompt_ms == "6 hari bersamaan berapa jam?",
                Question.expected_answer == "144",
                Question.source == "template",
            )
        ).all()
        attempt_question_ids = db.scalars(
            select(Attempt.question_id).where(Attempt.question_id == keep_question_id)
        ).all()

    assert [question.id for question in repeated_questions] == [keep_question_id]
    assert len(attempt_question_ids) == 2
