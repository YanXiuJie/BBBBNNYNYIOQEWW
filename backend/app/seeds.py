import json

from sqlalchemy import select

from .auth import hash_password
from .models import Attempt, Chapter, Classroom, GenerationLog, MasteryRecord, Question, Subtopic, User
from .services.question_generator import generate_with_template, strip_subtopic_prefix


CHAPTERS = [
    (
        1,
        "Nombor Bulat dan Operasi",
        [
            "Kenal dan Tulis Nombor",
            "Banding dan Susun Nombor",
            "Nombor Perdana",
            "Pola Nombor",
            "Tambah",
            "Tolak",
            "Darab",
            "Bahagi",
            "Selesaikan Masalah",
        ],
    ),
    (
        2,
        "Pecahan, Perpuluhan dan Peratus",
        [
            "Darab Pecahan",
            "Bundarkan Perpuluhan",
            "Tambah dan Tolak Perpuluhan",
            "Darab Perpuluhan",
            "Bahagi Perpuluhan",
            "Tukar Nombor Bercampur dan Peratus",
            "Selesaikan Masalah",
        ],
    ),
    (
        3,
        "Wang",
        [
            "Tambah Nilai Wang",
            "Tolak Nilai Wang",
            "Darab Nilai Wang",
            "Bahagi Nilai Wang",
            "Simpan dan Labur",
            "Faedah Mudah dan Faedah Kompaun",
            "Kredit dan Hutang",
            "Selesaikan Masalah",
        ],
    ),
    (4, "Masa dan Waktu", ["Tempoh", "Tukar Unit Masa", "Tambah Masa", "Tolak Masa", "Selesaikan Masalah"]),
    (
        5,
        "Panjang, Jisim dan Isi Padu Cecair",
        [
            "Tukar Unit Panjang",
            "Tambah Unit Panjang",
            "Tolak Unit Panjang",
            "Tukar Unit Gram dan Kilogram",
            "Tukar Unit Mililiter dan Liter",
            "Selesaikan Masalah",
        ],
    ),
    (
        6,
        "Ruang",
        [
            "Poligon Sekata",
            "Ukur Sudut Pedalaman",
            "Perimeter Bentuk Gabungan",
            "Luas Bentuk Gabungan",
            "Isi Padu Bentuk Gabungan",
            "Selesaikan Masalah",
        ],
    ),
    (
        7,
        "Koordinat, Nisbah dan Kadaran",
        [
            "Jarak di antara Dua Koordinat",
            "Nisbah antara Dua Kuantiti",
            "Kadaran untuk Mencari Suatu Nilai",
            "Selesaikan Masalah",
        ],
    ),
    (8, "Pengurusan Data", ["Tafsir Carta Pai", "Mod, Julat, Median dan Min", "Selesaikan Masalah"]),
]


DIFFICULTIES = ["easy", "medium", "hard"]
QUESTION_TYPES = ["short_answer", "multiple_choice"]


def seed_demo_data(db):
    bestari = get_or_create_class(db, "Tahun 5 Bestari", "B")
    amanah = get_or_create_class(db, "Tahun 5 Amanah", "A")

    get_or_create_user(db, "cikgu", "teacher", "Cikgu Siti", None, None)
    students = [
        get_or_create_user(db, "amin", "student", "Amin Hakim", "amin.parent@example.com", bestari.id),
        get_or_create_user(db, "sara", "student", "Sara Aina", "sara.parent@example.com", bestari.id),
        get_or_create_user(db, "rayan", "student", "Rayan Danish", "rayan.parent@example.com", bestari.id),
        get_or_create_user(db, "diya", "student", "Diya Maisarah", "diya.parent@example.com", amanah.id),
        get_or_create_user(db, "rohan", "student", "Rohan Kumar", "rohan.parent@example.com", amanah.id),
    ]

    cleanup_old_template_questions(db)
    for chapter_number, chapter_title, subtopics in CHAPTERS:
        chapter = get_or_create_chapter(db, chapter_number, chapter_title)
        for subtopic_title in subtopics:
            subtopic = get_or_create_subtopic(db, chapter.id, subtopic_title)
            seed_questions_for_subtopic(db, chapter.id, subtopic)
            seed_mastery_for_subtopic(db, students, chapter.id, subtopic.id)
    cleanup_prompt_prefixes(db)
    cleanup_duplicate_generated_questions(db)
    seed_attempts(db, students)
    db.commit()


def get_or_create_class(db, name: str, section: str) -> Classroom:
    classroom = db.scalar(select(Classroom).where(Classroom.name == name))
    if classroom:
        classroom.is_active = True
        return classroom
    classroom = Classroom(name=name, year_level=5, section=section)
    db.add(classroom)
    db.flush()
    return classroom


def get_or_create_user(db, username: str, role: str, full_name: str, parent_email: str | None, class_id: int | None) -> User:
    user = db.scalar(select(User).where(User.username == username))
    if user:
        user.role = role
        user.full_name = full_name
        user.parent_email = parent_email
        user.class_id = class_id
        user.is_active = True
        return user
    user = User(
        username=username,
        password_hash=hash_password("password123"),
        role=role,
        full_name=full_name,
        parent_email=parent_email,
        class_id=class_id,
    )
    db.add(user)
    db.flush()
    return user


def get_or_create_chapter(db, number: int, title_ms: str) -> Chapter:
    chapter = db.scalar(select(Chapter).where(Chapter.number == number))
    if chapter:
        chapter.title_ms = title_ms
        chapter.is_active = True
        return chapter
    chapter = Chapter(number=number, title_ms=title_ms)
    db.add(chapter)
    db.flush()
    return chapter


def get_or_create_subtopic(db, chapter_id: int, title_ms: str) -> Subtopic:
    subtopic = db.scalar(select(Subtopic).where(Subtopic.chapter_id == chapter_id, Subtopic.title_ms == title_ms))
    if subtopic:
        subtopic.is_active = True
        return subtopic
    subtopic = Subtopic(chapter_id=chapter_id, title_ms=title_ms)
    db.add(subtopic)
    db.flush()
    return subtopic


def seed_questions_for_subtopic(db, chapter_id: int, subtopic: Subtopic) -> None:
    for difficulty in DIFFICULTIES:
        for question_type in QUESTION_TYPES:
            generated = generate_with_template(subtopic.title_ms, difficulty, question_type)
            options = generated["options"] if question_type == "multiple_choice" else []
            existing = db.scalar(
                select(Question).where(
                    Question.subtopic_id == subtopic.id,
                    Question.difficulty == difficulty,
                    Question.prompt_ms == generated["prompt_ms"],
                )
            )
            if existing:
                existing.question_type = question_type
                existing.options_json = json.dumps(options, ensure_ascii=False)
                existing.expected_answer = generated["expected_answer"]
                existing.hint_ms = generated["hint_ms"]
                existing.hint_level2_ms = generated.get("hint_level2_ms", "")
                existing.hint_level3_ms = generated.get("hint_level3_ms", "")
                existing.explanation_ms = generated["explanation_ms"]
                existing.is_active = True
                continue
            db.add(
                Question(
                    chapter_id=chapter_id,
                    subtopic_id=subtopic.id,
                    difficulty=difficulty,
                    prompt_ms=generated["prompt_ms"],
                    expected_answer=generated["expected_answer"],
                    question_type=question_type,
                    options_json=json.dumps(options, ensure_ascii=False),
                    hint_ms=generated["hint_ms"],
                    hint_level2_ms=generated.get("hint_level2_ms", ""),
                    hint_level3_ms=generated.get("hint_level3_ms", ""),
                    explanation_ms=generated["explanation_ms"],
                )
            )


def cleanup_old_template_questions(db) -> None:
    questions = db.scalars(select(Question).where(Question.source.in_(["seed", "template"]))).all()
    stale_questions = [question for question in questions if is_old_template_question(db, question)]
    if not stale_questions:
        return
    stale_ids = [question.id for question in stale_questions]
    stale_prompts = [question.prompt_ms for question in stale_questions]
    for attempt in db.scalars(select(Attempt).where(Attempt.question_id.in_(stale_ids))).all():
        db.delete(attempt)
    for log in db.scalars(select(GenerationLog).where(GenerationLog.prompt_ms.in_(stale_prompts))).all():
        db.delete(log)
    for question in stale_questions:
        db.delete(question)
    db.flush()


def cleanup_prompt_prefixes(db) -> None:
    questions = db.scalars(select(Question)).all()
    for question in questions:
        subtopic = db.get(Subtopic, question.subtopic_id)
        if not subtopic:
            continue
        question.prompt_ms = strip_subtopic_prefix(question.prompt_ms, subtopic.title_ms)

    logs = db.scalars(select(GenerationLog)).all()
    for log in logs:
        subtopic = db.get(Subtopic, log.subtopic_id)
        if not subtopic:
            continue
        log.prompt_ms = strip_subtopic_prefix(log.prompt_ms, subtopic.title_ms)
    db.flush()


def cleanup_duplicate_generated_questions(db) -> None:
    questions = db.scalars(
        select(Question)
        .where(Question.source.in_(["seed", "template", "ai"]))
        .order_by(Question.id)
    ).all()
    if not questions:
        return

    attempted_question_ids = set(
        db.scalars(select(Attempt.question_id).where(Attempt.question_id.in_([question.id for question in questions]))).all()
    )
    grouped_questions = {}
    for question in questions:
        grouped_questions.setdefault(question_duplicate_key(question), []).append(question)

    duplicate_ids = []
    for group in grouped_questions.values():
        if len(group) <= 1:
            continue
        attempted = [question for question in group if question.id in attempted_question_ids]
        keep_id = attempted[0].id if attempted else group[-1].id
        for question in group:
            if question.id == keep_id:
                continue
            for attempt in db.scalars(select(Attempt).where(Attempt.question_id == question.id)).all():
                attempt.question_id = keep_id
            duplicate_ids.append(question.id)

    if not duplicate_ids:
        return
    for question in db.scalars(select(Question).where(Question.id.in_(duplicate_ids))).all():
        db.delete(question)
    db.flush()


def question_duplicate_key(question: Question) -> tuple[int, str, str, str, str]:
    return (
        question.subtopic_id,
        question.difficulty,
        question.question_type,
        question.prompt_ms.strip().casefold(),
        question.expected_answer.strip().casefold(),
    )


def is_old_template_question(db, question: Question) -> bool:
    prompt = question.prompt_ms
    subtopic = db.get(Subtopic, question.subtopic_id)
    subtopic_title = subtopic.title_ms.lower() if subtopic else ""
    if "Selesaikan pecahan berikut" in prompt:
        return True
    if "Tukar 0." in prompt and "kepada peratus" in prompt:
        return True
    if "Selesaikan:" in prompt and " x " in prompt and subtopic_title != "darab":
        return True
    return False


def seed_mastery_for_subtopic(db, students: list[User], chapter_id: int, subtopic_id: int) -> None:
    scores = [45, 62, 78, 88, 54]
    for student, score in zip(students, scores, strict=False):
        existing = db.scalar(select(MasteryRecord).where(MasteryRecord.student_id == student.id, MasteryRecord.subtopic_id == subtopic_id))
        if existing:
            continue
        db.add(MasteryRecord(student_id=student.id, chapter_id=chapter_id, subtopic_id=subtopic_id, score=score))


def seed_attempts(db, students: list[User]) -> None:
    if db.scalar(select(Attempt.id).limit(1)):
        return
    questions = db.scalars(select(Question).where(Question.chapter_id == 2).order_by(Question.id).limit(10)).all()
    for student_index, student in enumerate(students):
        for question_index, question in enumerate(questions[:4]):
            is_correct = (student_index + question_index) % 3 != 0
            answer = question.expected_answer if is_correct else "4/10"
            db.add(
                Attempt(
                    student_id=student.id,
                    question_id=question.id,
                    chapter_id=question.chapter_id,
                    subtopic_id=question.subtopic_id,
                    answer_text=answer,
                    is_correct=is_correct,
                    time_seconds=35 + (student_index * 8) + question_index,
                    feedback_ms="Seeded practical learning record.",
                )
            )
