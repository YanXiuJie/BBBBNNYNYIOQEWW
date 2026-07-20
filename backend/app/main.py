from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from .auth import decode_token, hash_password, issue_token, verify_password
from .database import Base, build_engine, make_session_factory, session_scope
from .models import Attempt, Chapter, Classroom, ComprehensivePracticeSession, DiagnosticSession, GenerationLog, MasteryRecord, Question, Subtopic, User
from .schemas import (
    AttemptRequest,
    ChapterRequest,
    ClassRequest,
    ComprehensiveSubmitRequest,
    DiagnosticAnswerSubmitRequest,
    DiagnosticStartResponse,
    DiagnosticSubmissionRequest,
    GenerateQuestionRequest,
    LoginRequest,
    QuestionRequest,
    StudentRequest,
    SubtopicRequest,
)
from .seeds import seed_demo_data
from .services.adaptive import AttemptSignal, MasteryState, next_difficulty, risk_level, update_mastery
from .services.adaptive_selector import select_next_question_for_session
from .services.analytics import average
from .services.answer_checker import is_equivalent_answer
from .services.diagnostic_selector import (
    completed_diagnostic_exists,
    create_diagnostic_session,
    record_diagnostic_progress,
    select_next_diagnostic_question,
    session_state as diagnostic_session_state,
)
from .services.hint_generator import generate_multilevel_hints
from .services.question_generator import generate_question_ms, generate_with_template
from .services.style_preference import update_style_preference

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR.parent / ".env")
load_dotenv(BACKEND_DIR / ".env", override=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def create_app(database_url: str | None = None, seed: bool = True) -> FastAPI:
    app = FastAPI(title="Adaptive Math AI")
    engine = build_engine(database_url)
    session_factory = make_session_factory(engine)
    Base.metadata.create_all(engine)
    _ensure_sqlite_question_columns(engine)
    _ensure_attempt_source_column(engine)
    if seed:
        with session_factory() as session:
            seed_demo_data(session)

    app.state.session_factory = session_factory

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_db():
        with session_scope(app.state.session_factory) as session:
            yield session

    def current_user(db: Session = Depends(get_db), authorization: str | None = Header(default=None)) -> User:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token diperlukan.")
        token = authorization.removeprefix("Bearer ").strip()

        # 使用 JWT 解码替代内存字典
        user_id = decode_token(token)
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token tidak sah atau telah tamat tempoh.")

        user = db.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Pengguna tidak ditemui.")
        return user

    def require_role(user: User, role: str) -> None:
        if user.role != role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses tidak dibenarkan.")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/auth/login")
    def login(payload: LoginRequest, db: Session = Depends(get_db)):
        logger.info(f"Login attempt: username={payload.username}")
        user = db.scalar(select(User).where(User.username == payload.username, User.is_active.is_(True)))
        if not user or not verify_password(payload.password, user.password_hash):
            logger.warning(f"Login failed: username={payload.username}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Log masuk gagal.")
        token = issue_token(user.id)
        logger.info(f"Login successful: user_id={user.id}, role={user.role}, username={user.username}")
        return {"access_token": token, "token_type": "bearer", "user": serialize_user(user)}

    @app.get("/syllabus")
    def syllabus(db: Session = Depends(get_db)):
        chapters = db.scalars(select(Chapter).where(Chapter.is_active.is_(True)).order_by(Chapter.number)).all()
        subtopics = db.scalars(select(Subtopic).where(Subtopic.is_active.is_(True)).order_by(Subtopic.id)).all()
        by_chapter = {}
        for subtopic in subtopics:
            by_chapter.setdefault(subtopic.chapter_id, []).append(serialize_subtopic(subtopic))
        return {
            "chapters": [
                {**serialize_chapter(chapter), "subtopics": by_chapter.get(chapter.id, [])}
                for chapter in chapters
            ]
        }

    @app.get("/student/dashboard")
    def student_dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "student")
        progress = build_student_progress(db, user.id)
        weak = [item for chapter in progress["chapters"] for item in chapter["subtopics"] if item["score"] < 70]
        recommended = weak[0] if weak else first_active_subtopic(db)
        return {
            "student": serialize_user(user),
            "diagnostic_completed": completed_diagnostic_exists(user.id, db),
            "recommended_subtopic": recommended,
            "weak_subtopics": weak[:4],
        }

    @app.get("/student/diagnostic")
    def student_diagnostic(db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "student")
        subtopics = db.scalars(
            select(Subtopic).where(Subtopic.chapter_id == 2, Subtopic.is_active.is_(True)).order_by(Subtopic.id)
        ).all()
        questions = [question for subtopic in subtopics if (question := find_question(db, subtopic.id, "medium"))]
        return {"questions": [serialize_question_with_context(db, question) for question in questions]}

    @app.post("/student/diagnostic/start", status_code=status.HTTP_201_CREATED, response_model=DiagnosticStartResponse)
    def start_diagnostic_session(db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "student")
        session = create_diagnostic_session(user.id, db)
        db.commit()
        db.refresh(session)
        state = diagnostic_session_state(session)
        chapters = []
        for item in state.get("chapter_blueprint", []):
            chapter = db.get(Chapter, item["chapter_id"])
            if chapter:
                chapters.append({"id": chapter.id, "number": chapter.number, "title_ms": chapter.title_ms})
        return {
            "session_id": session.id,
            "status": session.status,
            "total_questions": session.total_questions,
            "chapters": chapters,
        }

    @app.get("/student/diagnostic/next")
    def next_diagnostic_question(
        session_id: int = Query(...),
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
    ):
        require_role(user, "student")
        session = db.get(DiagnosticSession, session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesi diagnostik tidak ditemui.")
        if session.student_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses sesi tidak dibenarkan.")
        if session.status == "completed":
            return {"session_id": session.id, "completed": True, "question_number": session.current_question_number}

        question = select_next_diagnostic_question(session, db)
        db.commit()
        if question is None:
            return {"session_id": session.id, "completed": True, "question_number": session.current_question_number}

        return {
            "session_id": session.id,
            "completed": False,
            "question_number": session.current_question_number + 1,
            "total_questions": session.total_questions,
            "question": serialize_question_with_context(db, question),
        }

    @app.post("/student/diagnostic/submit", status_code=status.HTTP_201_CREATED)
    def submit_diagnostic_answer(
        payload: DiagnosticAnswerSubmitRequest,
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
    ):
        require_role(user, "student")
        session = db.get(DiagnosticSession, payload.session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesi diagnostik tidak ditemui.")
        if session.student_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses sesi tidak dibenarkan.")
        if session.status == "completed":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sesi diagnostik telah selesai.")

        payload_like_attempt = AttemptRequest(
            question_id=payload.question_id,
            answer_text=payload.answer_text,
            time_seconds=payload.time_seconds,
        )
        result = record_attempt(db, user, payload_like_attempt, source="diagnostic")
        question = db.get(Question, payload.question_id)
        record_diagnostic_progress(
            session=session,
            question=question,
            is_correct=result["is_correct"],
            time_seconds=payload.time_seconds,
            db=db,
        )
        db.commit()
        db.refresh(session)
        return {
            "session_id": session.id,
            "status": session.status,
            "attempt": result,
            "completed": session.status == "completed",
        }

    @app.get("/student/diagnostic/summary")
    def diagnostic_summary(
        session_id: int = Query(...),
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
    ):
        require_role(user, "student")
        session = db.get(DiagnosticSession, session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sesi diagnostik tidak ditemui.")
        if session.student_id != user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses sesi tidak dibenarkan.")

        state = diagnostic_session_state(session)
        results = state.get("results", [])
        if not results:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tiada hasil diagnostik.")

        correct_count = sum(1 for item in results if item["is_correct"])
        chapter_breakdown = {}
        for item in results:
            chapter = db.get(Chapter, item["chapter_id"])
            if not chapter:
                continue
            bucket = chapter_breakdown.setdefault(
                chapter.id,
                {"chapter_id": chapter.id, "title_ms": chapter.title_ms, "total": 0, "correct": 0},
            )
            bucket["total"] += 1
            if item["is_correct"]:
                bucket["correct"] += 1

        return {
            "session_id": session.id,
            "status": session.status,
            "summary": {
                "total_questions": len(results),
                "correct_count": correct_count,
                "accuracy": round((correct_count / len(results)) * 100, 1) if results else 0,
            },
            "chapter_breakdown": list(chapter_breakdown.values()),
            "results": results,
        }

    @app.post("/student/diagnostic", status_code=status.HTTP_201_CREATED)
    def submit_diagnostic(
        payload: DiagnosticSubmissionRequest,
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
    ):
        require_role(user, "student")
        results = [record_attempt(db, user, answer) for answer in payload.answers]
        return {
            "summary": {"correct_count": sum(1 for result in results if result["is_correct"]), "total_questions": len(results)},
            "results": results,
        }

    @app.get("/student/topics")
    def student_topics(db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "student")
        return build_student_progress(db, user.id)

    @app.get("/student/next-question")
    def next_question(
        subtopic_id: int = Query(...),
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
    ):
        require_role(user, "student")
        subtopic = get_subtopic_or_404(db, subtopic_id)
        mastery = get_or_create_mastery(db, user.id, subtopic)
        difficulty = next_difficulty(MasteryState(mastery.score, mastery.streak_correct, mastery.streak_wrong))
        question = generate_and_save_question(db, user.id, subtopic, difficulty) or find_question(db, subtopic.id, difficulty, user.id)
        if not question:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tiada soalan tersedia untuk subtopik ini.")
        ensure_question_hints(question, db)
        return {
            "recommended_difficulty": difficulty,
            "mastery": serialize_mastery(mastery),
            "question": serialize_question_with_context(db, question),
        }

    @app.post("/student/attempts", status_code=status.HTTP_201_CREATED)
    def submit_attempt(payload: AttemptRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "student")
        logger.info(f"Attempt submitted: student_id={user.id}, question_id={payload.question_id}")
        result = record_attempt(db, user, payload)
        logger.info(f"Attempt recorded: student_id={user.id}, is_correct={result['is_correct']}, mastery_score={result['mastery']['score']}")
        return result

    @app.get("/student/progress")
    def student_progress(db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "student")
        return build_student_progress(db, user.id)

    @app.get("/student/mistakes")
    def student_mistakes(
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100),
        sort_by: str = Query("created_at"),
        sort_dir: str = Query("desc"),
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
    ):
        require_role(user, "student")
        sort_column = attempt_sort_column(sort_by)
        order = sort_column.desc() if sort_dir.lower() == "desc" else sort_column.asc()
        filters = [Attempt.student_id == user.id, Attempt.is_correct.is_(False)]
        total = db.scalar(select(func.count(Attempt.id)).where(*filters))
        attempts = db.scalars(
            select(Attempt)
            .where(*filters)
            .order_by(order, Attempt.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return {
            "mistakes": [serialize_attempt(db, attempt) for attempt in attempts],
            "pagination": pagination_payload(page, page_size, total or 0),
            "sort": {"sort_by": sort_by, "sort_dir": sort_dir.lower()},
        }

    @app.get("/teacher/classes")
    def teacher_classes(db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        classes = db.scalars(select(Classroom).order_by(Classroom.id)).all()
        return {"classes": [serialize_classroom(item) for item in classes]}

    @app.post("/teacher/classes", status_code=status.HTTP_201_CREATED)
    def create_classroom(payload: ClassRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        classroom = Classroom(**payload.model_dump())
        db.add(classroom)
        db.commit()
        db.refresh(classroom)
        return serialize_classroom(classroom)

    @app.get("/teacher/chapters")
    def teacher_chapters(db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        chapters = db.scalars(select(Chapter).order_by(Chapter.number)).all()
        return {"chapters": [serialize_chapter(chapter) for chapter in chapters]}

    @app.post("/teacher/chapters", status_code=status.HTTP_201_CREATED)
    def create_chapter(payload: ChapterRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        chapter = Chapter(number=payload.number, title_ms=payload.title_ms)
        db.add(chapter)
        db.commit()
        db.refresh(chapter)
        return serialize_chapter(chapter)

    @app.put("/teacher/chapters/{chapter_id}")
    def update_chapter(chapter_id: int, payload: ChapterRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        chapter = get_chapter_or_404(db, chapter_id)
        chapter.number = payload.number
        chapter.title_ms = payload.title_ms
        db.commit()
        db.refresh(chapter)
        return serialize_chapter(chapter)

    @app.delete("/teacher/chapters/{chapter_id}")
    def delete_chapter(chapter_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        chapter = get_chapter_or_404(db, chapter_id)
        chapter.is_active = False
        subtopics = db.scalars(select(Subtopic).where(Subtopic.chapter_id == chapter.id)).all()
        for subtopic in subtopics:
            subtopic.is_active = False
        db.commit()
        db.refresh(chapter)
        return serialize_chapter(chapter)

    @app.post("/teacher/subtopics", status_code=status.HTTP_201_CREATED)
    def create_subtopic(payload: SubtopicRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        get_chapter_or_404(db, payload.chapter_id)
        subtopic = Subtopic(chapter_id=payload.chapter_id, title_ms=payload.title_ms, activity_type=payload.activity_type)
        db.add(subtopic)
        db.commit()
        db.refresh(subtopic)
        return serialize_subtopic(subtopic)

    @app.put("/teacher/subtopics/{subtopic_id}")
    def update_subtopic(subtopic_id: int, payload: SubtopicRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        get_chapter_or_404(db, payload.chapter_id)
        subtopic = get_subtopic_or_404(db, subtopic_id)
        subtopic.chapter_id = payload.chapter_id
        subtopic.title_ms = payload.title_ms
        subtopic.activity_type = payload.activity_type
        db.commit()
        db.refresh(subtopic)
        return serialize_subtopic(subtopic)

    @app.delete("/teacher/subtopics/{subtopic_id}")
    def delete_subtopic(subtopic_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        subtopic = get_subtopic_or_404(db, subtopic_id)
        subtopic.is_active = False
        db.commit()
        db.refresh(subtopic)
        return serialize_subtopic(subtopic)

    @app.put("/teacher/classes/{class_id}")
    def update_classroom(class_id: int, payload: ClassRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        classroom = get_classroom_or_404(db, class_id)
        classroom.name = payload.name
        classroom.year_level = payload.year_level
        classroom.section = payload.section
        db.commit()
        db.refresh(classroom)
        return serialize_classroom(classroom)

    @app.delete("/teacher/classes/{class_id}")
    def delete_classroom(class_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        classroom = get_classroom_or_404(db, class_id)
        classroom.is_active = False
        db.commit()
        db.refresh(classroom)
        return serialize_classroom(classroom)

    @app.get("/teacher/students")
    def teacher_students(
        class_id: int | None = None,
        risk: str | None = None,
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
    ):
        require_role(user, "teacher")
        query = select(User).where(User.role == "student")
        if class_id:
            query = query.where(User.class_id == class_id)
        students = db.scalars(query.order_by(User.full_name)).all()
        payload = [serialize_student_summary(db, student) for student in students]
        if risk:
            payload = [student for student in payload if student["risk_level"] == risk]
        return {"students": payload}

    @app.post("/teacher/students", status_code=status.HTTP_201_CREATED)
    def create_student(payload: StudentRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        classroom = get_classroom_or_404(db, payload.class_id)
        if not classroom.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kelas tidak aktif.")
        student = User(
            username=payload.username,
            password_hash=hash_password(payload.password),
            role="student",
            full_name=payload.full_name,
            parent_email=payload.parent_email,
            class_id=payload.class_id,
        )
        db.add(student)
        db.commit()
        db.refresh(student)
        return serialize_user(student)

    @app.put("/teacher/students/{student_id}")
    def update_student(student_id: int, payload: StudentRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        classroom = get_classroom_or_404(db, payload.class_id)
        if not classroom.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kelas tidak aktif.")
        student = get_student_or_404(db, student_id)
        student.username = payload.username
        student.full_name = payload.full_name
        student.parent_email = payload.parent_email
        student.class_id = payload.class_id
        if payload.password:
            student.password_hash = hash_password(payload.password)
        db.commit()
        db.refresh(student)
        return serialize_user(student)

    @app.delete("/teacher/students/{student_id}")
    def delete_student(student_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        student = get_student_or_404(db, student_id)
        student.is_active = False
        db.commit()
        db.refresh(student)
        return serialize_user(student)

    @app.get("/teacher/students/{student_id}")
    def teacher_student_detail(student_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        student = get_student_or_404(db, student_id)
        return build_student_detail(db, student)

    @app.get("/teacher/questions")
    def teacher_questions(
        page: int = Query(1, ge=1),
        page_size: int = Query(10, ge=1, le=100),
        sort_by: str = Query("created_at"),
        sort_dir: str = Query("desc"),
        difficulty: str | None = None,
        subtopic_id: int | None = None,
        question_type: str | None = None,
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
    ):
        require_role(user, "teacher")
        filters = []
        if difficulty and difficulty != "all":
            filters.append(Question.difficulty == difficulty)
        if subtopic_id:
            filters.append(Question.subtopic_id == subtopic_id)
        if question_type and question_type != "all":
            filters.append(Question.question_type == question_type)
        sort_column = question_sort_column(sort_by)
        order = sort_column.desc() if sort_dir.lower() == "desc" else sort_column.asc()
        total = db.scalar(select(func.count(Question.id)).where(*filters))
        questions = db.scalars(
            select(Question)
            .where(*filters)
            .order_by(order, Question.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return {
            "questions": [serialize_question_with_context(db, question) for question in questions],
            "pagination": pagination_payload(page, page_size, total or 0),
            "sort": {"sort_by": sort_by, "sort_dir": sort_dir.lower()},
        }

    @app.post("/teacher/questions", status_code=status.HTTP_201_CREATED)
    def create_question(payload: QuestionRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        question = Question(**question_payload_to_model(payload), source="manual", validation_status="validated")
        db.add(question)
        db.commit()
        db.refresh(question)
        return {"question": serialize_question_with_context(db, question)}

    @app.put("/teacher/questions/{question_id}")
    def update_question(question_id: int, payload: QuestionRequest, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        question = get_question_or_404(db, question_id)
        for key, value in question_payload_to_model(payload).items():
            setattr(question, key, value)
        db.commit()
        db.refresh(question)
        return {"question": serialize_question_with_context(db, question)}

    @app.delete("/teacher/questions/{question_id}")
    def delete_question(question_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        question = get_question_or_404(db, question_id)
        question.is_active = False
        db.commit()
        db.refresh(question)
        return {"question": serialize_question_with_context(db, question)}

    @app.post("/teacher/questions/generate", status_code=status.HTTP_201_CREATED)
    def generate_question_endpoint(
        payload: GenerateQuestionRequest,
        db: Session = Depends(get_db),
        user: User = Depends(current_user),
    ):
        require_role(user, "teacher")
        subtopic = get_subtopic_or_404(db, payload.subtopic_id)
        question = generate_and_save_question(
            db,
            user.id,
            subtopic,
            payload.difficulty,
            payload.question_type,
            allow_template_fallback=True,
        )
        if not question:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Gagal menjana soalan baharu.")
        return {"question": serialize_question_with_context(db, question)}

    @app.get("/teacher/generation-logs")
    def generation_logs(db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        logs = db.scalars(select(GenerationLog).order_by(GenerationLog.created_at.desc())).all()
        return {"logs": [serialize_generation_log(log) for log in logs]}

    @app.get("/teacher/analytics/classes/{class_id}")
    def class_analytics(class_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        students = db.scalars(select(User).where(User.class_id == class_id, User.role == "student").order_by(User.full_name)).all()
        summaries = [serialize_student_summary(db, student) for student in students]
        mastery_scores = [item["mastery_average"] for item in summaries if item["mastery_average"] > 0]
        attempts = db.scalars(select(Attempt).where(Attempt.student_id.in_([student.id for student in students] or [0]))).all()
        weak_subtopics = build_weak_subtopics(db, class_id)
        return {
            "class_id": class_id,
            "summary": {
                "student_count": len(students),
                "average_mastery": average(mastery_scores),
                "at_risk_count": sum(1 for item in summaries if item["risk_level"] == "high"),
                "average_accuracy": average([1 if attempt.is_correct else 0 for attempt in attempts]) * 100 if attempts else 0,
            },
            "students": summaries,
            "weak_subtopics": weak_subtopics,
        }

    @app.get("/teacher/analytics/students/{student_id}")
    def student_analytics(student_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
        require_role(user, "teacher")
        student = get_student_or_404(db, student_id)
        return build_student_detail(db, student)

    @app.post("/student/comprehensive-practice/start", status_code=status.HTTP_201_CREATED)
    def start_comprehensive_practice(
        db: Session = Depends(get_db),
        user: User = Depends(current_user)
    ):
        require_role(user, "student")

        if not completed_diagnostic_exists(user.id, db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selesaikan ujian diagnostik dahulu sebelum memulakan latihan menyeluruh.",
            )

        mastery_rows = db.scalars(
            select(MasteryRecord)
            .join(Subtopic, MasteryRecord.subtopic_id == Subtopic.id)
            .join(Question, Subtopic.id == Question.subtopic_id)
            .where(
                MasteryRecord.student_id == user.id,
                MasteryRecord.score < 70,
                Question.is_active == True
            )
            .distinct()
            .order_by(MasteryRecord.score)
        ).all()

        # Prepare weak subtopics snapshot
        weak_subtopics = []
        for mastery in mastery_rows:
            subtopic = db.get(Subtopic, mastery.subtopic_id)
            if subtopic and subtopic.is_active:
                weak_subtopics.append({
                    "subtopic_id": subtopic.id,
                    "title_ms": subtopic.title_ms,
                    "mastery_score": round(mastery.score, 2)
                })

        # Create session
        session = ComprehensivePracticeSession(
            student_id=user.id,
            current_question_number=0,
            phase="diagnosis",
            weak_subtopics_json=json.dumps(weak_subtopics, ensure_ascii=False),
            state_json=json.dumps({
                "phase1_results": [],
                "phase2_results": [],
                "phase3_results": []
            }, ensure_ascii=False)
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        return {
            "session_id": session.id,
            "total_questions": 15,
            "weak_subtopics": weak_subtopics,
            "message": "Sesi latihan menyeluruh dimulakan. 15 soalan akan disesuaikan dengan tahap anda."
        }

    @app.get("/student/comprehensive-practice/next")
    def get_next_comprehensive_question(
        session_id: int = Query(...),
        db: Session = Depends(get_db),
        user: User = Depends(current_user)
    ):
        require_role(user, "student")

        # Validate session
        session = db.get(ComprehensivePracticeSession, session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesi tidak ditemui."
            )

        if session.student_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Anda tidak mempunyai akses ke sesi ini."
            )

        if session.is_completed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sesi telah selesai."
            )

        # Use adaptive selector to get next question
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
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        # Fetch question
        question = db.get(Question, selection["question_id"])
        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Soalan tidak ditemui."
            )

        # Generate hints if not present
        ensure_question_hints(question, db)

        # Build phase info
        phase_map = {
            "diagnosis": "Diagnostik",
            "remedial": "Pemulihan",
            "consolidation": "Pengukuhan"
        }

        phase_info = {
            "phase_name": phase_map.get(session.phase, session.phase),
            "question_number": selection["question_number"],
            "total_questions": 15,
            "progress_percentage": round((selection["question_number"] / 15) * 100, 1)
        }

        # Build hint config
        hint_config = {
            "hint_level1_ms": question.hint_ms or "",
            "hint_level2_ms": question.hint_level2_ms or "",
            "hint_level3_ms": question.hint_level3_ms or "",
            "max_hints": 3
        }

        return {
            "session_id": session.id,
            "question_number": selection["question_number"],
            "phase": session.phase,
            "phase_info": phase_info,
            "question": serialize_question_with_context(db, question),
            "hint_config": hint_config
        }

    @app.post("/student/comprehensive-practice/submit", status_code=status.HTTP_201_CREATED)
    def submit_comprehensive_answer(
        payload: ComprehensiveSubmitRequest,
        db: Session = Depends(get_db),
        user: User = Depends(current_user)
    ):
        require_role(user, "student")

        # Validate session
        session = db.get(ComprehensivePracticeSession, payload.session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesi tidak ditemui."
            )

        if session.student_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Anda tidak mempunyai akses ke sesi ini."
            )

        # Validate question
        question = db.get(Question, payload.question_id)
        if not question or not question.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Soalan tidak ditemui."
            )

        # Check answer
        is_correct = is_equivalent_answer(payload.answer_text, question.expected_answer)

        # Update mastery
        subtopic = db.get(Subtopic, question.subtopic_id)
        if not subtopic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subtopik tidak ditemui."
            )

        mastery = get_or_create_mastery(db, user.id, subtopic)
        updated = update_mastery(
            MasteryState(mastery.score, mastery.streak_correct, mastery.streak_wrong),
            AttemptSignal(is_correct=is_correct, difficulty=question.difficulty, time_seconds=payload.time_seconds)
        )
        mastery.score = updated.score
        mastery.streak_correct = updated.streak_correct
        mastery.streak_wrong = updated.streak_wrong

        # Update style preference
        update_style_preference(
            student_id=user.id,
            presentation_style=question.presentation_style,
            is_correct=is_correct,
            time_seconds=payload.time_seconds,
            db=db
        )

        # Record attempt
        feedback = build_feedback_ms(is_correct, question)
        attempt = Attempt(
            student_id=user.id,
            question_id=question.id,
            chapter_id=question.chapter_id,
            subtopic_id=question.subtopic_id,
            answer_text=payload.answer_text,
            is_correct=is_correct,
            time_seconds=payload.time_seconds,
            feedback_ms=feedback
        )
        db.add(attempt)

        # Update session state
        state = json.loads(session.state_json)
        phase_key = {
            "diagnosis": "phase1_results",
            "remedial": "phase2_results",
            "consolidation": "phase3_results",
        }.get(session.phase)
        if not phase_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fasa sesi tidak sah.",
            )
        if phase_key not in state:
            state[phase_key] = []

        state[phase_key].append({
            "question_id": question.id,
            "subtopic_id": question.subtopic_id,
            "difficulty": question.difficulty,
            "is_correct": is_correct,
            "hints_used": payload.hints_used,
            "time_seconds": payload.time_seconds
        })
        session.state_json = json.dumps(state, ensure_ascii=False)

        db.commit()
        db.refresh(mastery)

        return {
            "is_correct": is_correct,
            "feedback_ms": feedback,
            "mastery_updated": {
                "subtopic_id": subtopic.id,
                "subtopic_title_ms": subtopic.title_ms,
                "score": round(mastery.score, 2),
                "streak_correct": mastery.streak_correct,
                "streak_wrong": mastery.streak_wrong
            }
        }

    @app.get("/student/comprehensive-practice/summary")
    def get_comprehensive_summary(
        session_id: int = Query(...),
        db: Session = Depends(get_db),
        user: User = Depends(current_user)
    ):
        require_role(user, "student")

        # Validate session
        session = db.get(ComprehensivePracticeSession, session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesi tidak ditemui."
            )

        if session.student_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Anda tidak mempunyai akses ke sesi ini."
            )

        # Parse session state
        state = json.loads(session.state_json)
        all_results = (
            state.get("phase1_results", []) +
            state.get("phase2_results", []) +
            state.get("phase3_results", [])
        )

        if not all_results:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tiada hasil untuk sesi ini."
            )

        # Calculate statistics
        total_questions = len(all_results)
        correct_count = sum(1 for r in all_results if r["is_correct"])
        total_time = sum(r["time_seconds"] for r in all_results)
        total_hints = sum(len(r.get("hints_used", [])) for r in all_results)
        phase_results = {
            "diagnosis": state.get("phase1_results", []),
            "remedial": state.get("phase2_results", []),
            "consolidation": state.get("phase3_results", []),
        }

        def summarize_phase(rows: list[dict]) -> dict:
            total = len(rows)
            correct = sum(1 for row in rows if row["is_correct"])
            incorrect = total - correct
            total_time_seconds = sum(row["time_seconds"] for row in rows)
            total_hints_used = sum(len(row.get("hints_used", [])) for row in rows)
            return {
                "total": total,
                "correct": correct,
                "incorrect": incorrect,
                "accuracy": round((correct / total) * 100, 1) if total else 0,
                "avg_time": round(total_time_seconds / total, 1) if total else 0,
                "hints_used": total_hints_used,
            }

        subtopic_stats = {}
        for result in all_results:
            subtopic_id = result["subtopic_id"]
            stats = subtopic_stats.setdefault(subtopic_id, {"total": 0, "correct": 0})
            stats["total"] += 1
            if result["is_correct"]:
                stats["correct"] += 1

        # Fetch current mastery scores
        weak_subtopics_before = json.loads(session.weak_subtopics_json)
        mastery_updates = []
        for weak_st in weak_subtopics_before:
            subtopic_id = weak_st["subtopic_id"]
            mastery = db.scalar(
                select(MasteryRecord).where(
                    MasteryRecord.student_id == user.id,
                    MasteryRecord.subtopic_id == subtopic_id
                )
            )
            subtopic = db.get(Subtopic, subtopic_id)
            if mastery and subtopic:
                mastery_updates.append({
                    "subtopic_id": subtopic_id,
                    "title_ms": subtopic.title_ms,
                    "score_before": weak_st["mastery_score"],
                    "score_after": round(mastery.score, 2),
                    "improvement": round(mastery.score - weak_st["mastery_score"], 2)
                })

        overall_metrics = {
            "accuracy": round((correct_count / total_questions) * 100, 1) if total_questions > 0 else 0,
            "avg_time_seconds": round(total_time / total_questions, 1) if total_questions > 0 else 0,
            "total_hints_used": total_hints,
            "total_questions": total_questions,
        }
        mastery_changes = []
        weak_points = []
        for weak_st in weak_subtopics_before:
            stats = subtopic_stats.get(weak_st["subtopic_id"], {"total": 0, "correct": 0})
            score_after = next(
                (
                    update["score_after"]
                    for update in mastery_updates
                    if update["subtopic_id"] == weak_st["subtopic_id"]
                ),
                weak_st["mastery_score"],
            )
            mastery_changes.append(
                {
                    "subtopic_name": weak_st["title_ms"],
                    "before": weak_st["mastery_score"],
                    "after": score_after,
                }
            )
            if stats["total"] > 0:
                weak_points.append(
                    {
                        "subtopic_name": weak_st["title_ms"],
                        "accuracy": round((stats["correct"] / stats["total"]) * 100, 1),
                    }
                )

        return {
            "session_id": session.id,
            "is_completed": session.is_completed,
            "summary": {
                "total_questions": total_questions,
                "correct_count": correct_count,
                "accuracy": round((correct_count / total_questions) * 100, 1) if total_questions > 0 else 0,
                "total_time_seconds": total_time,
                "average_time_seconds": round(total_time / total_questions, 1) if total_questions > 0 else 0,
                "total_hints_used": total_hints
            },
            "overall_metrics": overall_metrics,
            "mastery_updates": mastery_updates,
            "mastery_changes": mastery_changes,
            "weak_points": weak_points,
            "next_steps": "Fokus pada subtopik dengan ketepatan terendah dan ulang sesi latihan menyeluruh selepas itu.",
            "phase_breakdown": {
                phase: summarize_phase(rows)
                for phase, rows in phase_results.items()
            }
        }

    @app.get("/student/knowledge-map")
    def student_knowledge_map(
        chapter_id: int | None = None,
        db: Session = Depends(get_db),
        user: User = Depends(current_user)
    ):
        """
        学生端：获取自己的知识掌握地图

        返回所有知识点的掌握概率，用于可视化：
        - 雷达图（多维度能力）
        - 热力图（知识点矩阵）
        - 列表（详细数据）
        """
        require_role(user, "student")
        from .services.knowledge_tracing import get_student_knowledge_map

        knowledge_map = get_student_knowledge_map(user.id, db, chapter_id)

        return {
            "knowledge_map": [
                {
                    "subtopic_id": state.subtopic_id,
                    "subtopic_title_ms": state.subtopic_title_ms,
                    "mastery_probability": state.mastery_probability,
                    "confidence": state.confidence,
                    "attempt_count": state.attempt_count,
                    "last_attempt_correct": state.last_attempt_correct,
                    "status": _kt_status_label(state.mastery_probability),
                    "status_ms": _kt_status_label_ms(state.mastery_probability)
                }
                for state in knowledge_map
            ],
            "summary": {
                "total_subtopics": len(knowledge_map),
                "attempted_count": sum(1 for s in knowledge_map if s.attempt_count > 0),
                "mastered_count": sum(1 for s in knowledge_map if s.mastery_probability >= 0.9),
                "struggling_count": sum(1 for s in knowledge_map if s.mastery_probability < 0.4 and s.confidence > 0.3),
                "average_mastery": average([s.mastery_probability for s in knowledge_map if s.attempt_count > 0])
            }
        }

    @app.get("/teacher/students/{student_id}/knowledge-prediction")
    def student_knowledge_prediction(
        student_id: int,
        subtopic_id: int = Query(...),
        difficulty: str = Query("medium"),
        db: Session = Depends(get_db),
        user: User = Depends(current_user)
    ):
        """
        教师端：预测学生在特定题目上的表现

        用于辅助教学决策：
        - "这个学生准备好做 hard 题了吗？"
        - "应该继续练习还是可以进入下一个主题？"
        """
        require_role(user, "teacher")
        from .services.knowledge_tracing import (
            estimate_mastery_probability,
            predict_next_attempt_success
        )

        student = get_student_or_404(db, student_id)
        subtopic = get_subtopic_or_404(db, subtopic_id)

        # 当前掌握状态
        state = estimate_mastery_probability(student_id, subtopic_id, db)

        # 预测不同难度的答对概率
        predictions = {}
        for diff in ["easy", "medium", "hard"]:
            predictions[diff] = predict_next_attempt_success(
                student_id, subtopic_id, diff, db
            )

        # 生成建议
        current_prob = predictions[difficulty]
        if current_prob > 0.8:
            recommendation = "建议升级难度"
            recommendation_ms = "Cadangkan tingkatkan kesukaran"
        elif current_prob < 0.4:
            recommendation = "建议降低难度或提供辅导"
            recommendation_ms = "Cadangkan kurangkan kesukaran atau beri bimbingan"
        else:
            recommendation = "当前难度合适"
            recommendation_ms = "Kesukaran semasa sesuai"

        return {
            "student": serialize_user(student),
            "subtopic": serialize_subtopic(subtopic),
            "current_state": {
                "mastery_probability": state.mastery_probability,
                "confidence": state.confidence,
                "attempt_count": state.attempt_count,
                "last_attempt_correct": state.last_attempt_correct
            },
            "predictions": {
                "easy": predictions["easy"],
                "medium": predictions["medium"],
                "hard": predictions["hard"],
                "requested_difficulty": difficulty,
                "predicted_success_probability": current_prob
            },
            "recommendation": recommendation,
            "recommendation_ms": recommendation_ms
        }

    return app


def _kt_status_label(probability: float) -> str:
    """Knowledge Tracing 状态标签（英文）"""
    if probability < 0.4:
        return "struggling"
    elif probability < 0.7:
        return "developing"
    elif probability < 0.9:
        return "proficient"
    else:
        return "mastered"

def _kt_status_label_ms(probability: float) -> str:
    """Knowledge Tracing 状态标签（马来语）"""
    if probability < 0.4:
        return "Memerlukan Bantuan"
    elif probability < 0.7:
        return "Dalam Pembangunan"
    elif probability < 0.9:
        return "Mahir"
    else:
        return "Dikuasai"


def pagination_payload(page: int, page_size: int, total: int) -> dict:
    total_pages = max(1, (total + page_size - 1) // page_size)
    return {"page": page, "page_size": page_size, "total": total, "total_pages": total_pages}


def question_sort_column(sort_by: str):
    return {
        "id": Question.id,
        "created_at": Question.created_at,
        "difficulty": Question.difficulty,
        "source": Question.source,
        "subtopic_id": Question.subtopic_id,
        "question_type": Question.question_type,
    }.get(sort_by, Question.created_at)


def attempt_sort_column(sort_by: str):
    return {
        "id": Attempt.id,
        "created_at": Attempt.created_at,
        "time_seconds": Attempt.time_seconds,
        "subtopic_id": Attempt.subtopic_id,
    }.get(sort_by, Attempt.created_at)


def get_classroom_or_404(db: Session, class_id: int) -> Classroom:
    classroom = db.get(Classroom, class_id)
    if not classroom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kelas tidak ditemui.")
    return classroom


def get_chapter_or_404(db: Session, chapter_id: int) -> Chapter:
    chapter = db.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bab tidak ditemui.")
    return chapter


def get_student_or_404(db: Session, student_id: int) -> User:
    student = db.get(User, student_id)
    if not student or student.role != "student":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Murid tidak ditemui.")
    return student


def get_subtopic_or_404(db: Session, subtopic_id: int) -> Subtopic:
    subtopic = db.get(Subtopic, subtopic_id)
    if not subtopic or not subtopic.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subtopik tidak ditemui.")
    return subtopic


def get_question_or_404(db: Session, question_id: int) -> Question:
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Soalan tidak ditemui.")
    return question


def get_or_create_mastery(db: Session, student_id: int, subtopic: Subtopic) -> MasteryRecord:
    mastery = db.scalar(select(MasteryRecord).where(MasteryRecord.student_id == student_id, MasteryRecord.subtopic_id == subtopic.id))
    if mastery:
        return mastery
    mastery = MasteryRecord(student_id=student_id, chapter_id=subtopic.chapter_id, subtopic_id=subtopic.id, score=50)
    db.add(mastery)
    db.commit()
    db.refresh(mastery)
    return mastery


def find_question(db: Session, subtopic_id: int, difficulty: str, student_id: int | None = None) -> Question | None:
    candidates = db.scalars(
        select(Question)
        .where(
            Question.subtopic_id == subtopic_id,
            Question.difficulty == difficulty,
            Question.is_active.is_(True),
            Question.validation_status == "validated",
        )
        .order_by(Question.id)
    ).all()
    attempted_ids = set()
    if student_id:
        attempted_ids = set(
            db.scalars(
                select(Attempt.question_id)
                .where(Attempt.student_id == student_id, Attempt.subtopic_id == subtopic_id)
            ).all()
        )

    bank_candidates = [question for question in candidates if question.source != "template"]
    for question in bank_candidates:
        if question.id not in attempted_ids:
            return question

    subtopic = db.get(Subtopic, subtopic_id)
    if subtopic:
        template_question = create_template_question(db, subtopic, difficulty)
        if template_question:
            return template_question

    return bank_candidates[0] if bank_candidates else (candidates[0] if candidates else None)


def create_template_question(db: Session, subtopic: Subtopic, difficulty: str, question_type: str = "short_answer") -> Question | None:
    generated = generate_with_template(subtopic.title_ms, difficulty, question_type)
    if not generated:
        return None

    existing = db.scalar(
        select(Question)
        .where(
            Question.subtopic_id == subtopic.id,
            Question.difficulty == difficulty,
            Question.question_type == generated.get("question_type", question_type),
            func.lower(Question.prompt_ms) == generated["prompt_ms"].strip().lower(),
            func.lower(Question.expected_answer) == generated["expected_answer"].strip().lower(),
            Question.is_active.is_(True),
        )
        .limit(1)
    )
    if existing:
        generate_multilevel_hints(existing, db)
        db.refresh(existing)
        return existing

    options = normalize_options(generated.get("question_type", question_type), generated["expected_answer"], generated.pop("options", []))
    generated["question_type"] = generated.get("question_type") or question_type
    generated["options_json"] = json.dumps(options, ensure_ascii=False)
    question = Question(chapter_id=subtopic.chapter_id, subtopic_id=subtopic.id, **generated)
    db.add(question)
    db.commit()
    db.refresh(question)
    generate_multilevel_hints(question, db)
    db.refresh(question)
    return question


def ensure_question_hints(question: Question, db: Session) -> None:
    if question.hint_level2_ms and question.hint_level3_ms:
        return
    generate_multilevel_hints(question, db)
    db.refresh(question)


def generate_and_save_question(
    db: Session,
    teacher_id: int,
    subtopic: Subtopic,
    difficulty: str,
    question_type: str = "short_answer",
    allow_template_fallback: bool = False,
) -> Question | None:
    """
    尝试生成并保存题目，最多尝试3次 LLM 调用。
    如果生成的题目重复，继续尝试（最多检查 24 个候选）。
    """
    logger.info(f"Generating question: subtopic_id={subtopic.id}, difficulty={difficulty}, type={question_type}")
    llm_attempts = 0
    duplicate_checks = 0
    max_llm_attempts = 5
    max_duplicate_checks = 24

    while llm_attempts < max_llm_attempts and duplicate_checks < max_duplicate_checks:
        # 尝试生成题目
        try:
            generated = generate_question_ms(subtopic.title_ms, difficulty, question_type)
        except Exception as e:
            logger.warning(f"LLM generation failed (attempt {llm_attempts + 1}/{max_llm_attempts}): {e}")
            llm_attempts += 1
            continue  # LLM 调用失败，重试

        if not generated:
            logger.warning(f"Generation returned None (attempt {llm_attempts + 1}/{max_llm_attempts})")
            llm_attempts += 1
            continue  # 生成失败，重试

        generated_source = generated.get("source")
        if generated_source != "ai":
            if allow_template_fallback and generated_source == "template":
                logger.warning(
                    "Generation used template fallback for teacher request (attempt %s/%s)",
                    llm_attempts + 1,
                    max_llm_attempts,
                )
            else:
                logger.warning(
                    "Generation returned non-LLM source %r (attempt %s/%s); retrying",
                    generated_source,
                    llm_attempts + 1,
                    max_llm_attempts,
                )
                llm_attempts += 1
                continue
        duplicate_checks += 1
        generated["question_type"] = generated.get("question_type") or question_type

        # 检查是否重复
        if is_duplicate_generated_question(
            db,
            subtopic.id,
            difficulty,
            generated["question_type"],
            generated["prompt_ms"],
            generated["expected_answer"],
        ):
            continue  # 重复了，继续生成下一个

        # 保存题目
        options = normalize_options(generated["question_type"], generated["expected_answer"], generated.pop("options", []))
        generated["options_json"] = json.dumps(options, ensure_ascii=False)
        question = Question(chapter_id=subtopic.chapter_id, subtopic_id=subtopic.id, **generated)
        db.add(question)
        db.flush()
        db.add(
            GenerationLog(
                teacher_id=teacher_id,
                chapter_id=subtopic.chapter_id,
                subtopic_id=subtopic.id,
                difficulty=difficulty,
                prompt_ms=question.prompt_ms,
                validation_status=question.validation_status,
            )
        )
        db.commit()
        db.refresh(question)
        generate_multilevel_hints(question, db)
        db.refresh(question)
        logger.info(f"Question generated successfully: id={question.id}, prompt={question.prompt_ms[:50]}...")
        return question

    # 所有尝试都失败
    if allow_template_fallback:
        fallback_question = create_template_question(db, subtopic, difficulty, question_type)
        if fallback_question:
            logger.warning("Teacher generation returned saved template fallback question: id=%s", fallback_question.id)
            return fallback_question

    logger.error(f"Failed to generate question after {llm_attempts} LLM attempts and {duplicate_checks} duplicate checks")
    return None


def is_duplicate_generated_question(
    db: Session,
    subtopic_id: int,
    difficulty: str,
    question_type: str,
    prompt_ms: str,
    expected_answer: str,
) -> bool:
    return bool(
        db.scalar(
            select(Question.id)
            .where(
                Question.subtopic_id == subtopic_id,
                Question.difficulty == difficulty,
                Question.question_type == question_type,
                func.lower(Question.prompt_ms) == prompt_ms.strip().lower(),
                func.lower(Question.expected_answer) == expected_answer.strip().lower(),
            )
            .limit(1)
        )
    )


def record_attempt(db: Session, user: User, payload: AttemptRequest, source: str = "practice"):
    question = get_question_or_404(db, payload.question_id)
    if not question.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Soalan tidak aktif.")
    subtopic = get_subtopic_or_404(db, question.subtopic_id)
    is_correct = is_equivalent_answer(payload.answer_text, question.expected_answer)
    mastery = get_or_create_mastery(db, user.id, subtopic)
    updated = update_mastery(
        MasteryState(mastery.score, mastery.streak_correct, mastery.streak_wrong),
        AttemptSignal(is_correct=is_correct, difficulty=question.difficulty, time_seconds=payload.time_seconds),
    )
    mastery.score = updated.score
    mastery.streak_correct = updated.streak_correct
    mastery.streak_wrong = updated.streak_wrong
    feedback = build_feedback_ms(is_correct, question)
    attempt = Attempt(
        student_id=user.id,
        question_id=question.id,
        chapter_id=question.chapter_id,
        subtopic_id=question.subtopic_id,
        answer_text=payload.answer_text,
        is_correct=is_correct,
        time_seconds=payload.time_seconds,
        feedback_ms=feedback,
        source=source,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    db.refresh(mastery)
    return {
        "id": attempt.id,
        "is_correct": is_correct,
        "feedback_ms": feedback,
        "mastery": serialize_mastery(mastery),
        "source": source,
        "question": serialize_question_with_context(db, question),
    }


def build_feedback_ms(is_correct: bool, question: Question) -> str:
    if is_correct:
        return f"Betul. {question.explanation_ms}"
    return f"Belum tepat. Jawapan yang betul ialah {question.expected_answer}. {question.explanation_ms}"


def build_student_progress(db: Session, student_id: int):
    chapters = db.scalars(select(Chapter).where(Chapter.is_active.is_(True)).order_by(Chapter.number)).all()
    mastery_rows = db.scalars(select(MasteryRecord).where(MasteryRecord.student_id == student_id)).all()
    mastery_by_subtopic = {row.subtopic_id: row for row in mastery_rows}
    attempts = db.scalars(select(Attempt).where(Attempt.student_id == student_id)).all()
    attempt_count_by_subtopic = {}
    correct_count = 0
    for attempt in attempts:
        attempt_count_by_subtopic[attempt.subtopic_id] = attempt_count_by_subtopic.get(attempt.subtopic_id, 0) + 1
        correct_count += 1 if attempt.is_correct else 0
    payload = []
    for chapter in chapters:
        subtopics = db.scalars(select(Subtopic).where(Subtopic.chapter_id == chapter.id, Subtopic.is_active.is_(True)).order_by(Subtopic.id)).all()
        serialized_subtopics = []
        for subtopic in subtopics:
            mastery = mastery_by_subtopic.get(subtopic.id)
            score = round(mastery.score, 2) if mastery else 50
            serialized_subtopics.append(
                {
                    **serialize_subtopic(subtopic),
                    "score": score,
                    "risk_level": risk_level(score),
                    "attempt_count": attempt_count_by_subtopic.get(subtopic.id, 0),
                }
            )
        payload.append({**serialize_chapter(chapter), "subtopics": serialized_subtopics})
    return {
        "chapters": payload,
        "summary": {
            "attempt_count": len(attempts),
            "accuracy": round((correct_count / len(attempts)) * 100, 2) if attempts else 0,
            "average_mastery": average([row.score for row in mastery_rows]),
        },
    }


def build_student_detail(db: Session, student: User):
    progress = build_student_progress(db, student.id)
    attempts = db.scalars(select(Attempt).where(Attempt.student_id == student.id).order_by(Attempt.created_at.desc()).limit(10)).all()
    weak = [item for chapter in progress["chapters"] for item in chapter["subtopics"] if item["score"] < 70]
    return {
        "student": serialize_user(student),
        "progress": progress,
        "recent_attempts": [serialize_attempt(db, attempt) for attempt in attempts],
        "mistake_patterns": build_mistake_patterns(db, student.id),
        "recommended_path": weak[:3],
    }


def build_mistake_patterns(db: Session, student_id: int):
    rows = db.execute(
        select(Subtopic.title_ms, func.count(Attempt.id))
        .join(Attempt, Attempt.subtopic_id == Subtopic.id)
        .where(Attempt.student_id == student_id, Attempt.is_correct.is_(False))
        .group_by(Subtopic.title_ms)
    ).all()
    return [{"subtopic_title_ms": title, "wrong_count": count} for title, count in rows]


def build_weak_subtopics(db: Session, class_id: int):
    students = db.scalars(select(User).where(User.class_id == class_id, User.role == "student")).all()
    student_ids = [student.id for student in students]
    if not student_ids:
        return []
    rows = db.execute(
        select(Subtopic.id, Subtopic.title_ms, func.avg(MasteryRecord.score))
        .join(MasteryRecord, MasteryRecord.subtopic_id == Subtopic.id)
        .where(MasteryRecord.student_id.in_(student_ids))
        .group_by(Subtopic.id, Subtopic.title_ms)
        .order_by(func.avg(MasteryRecord.score))
        .limit(5)
    ).all()
    return [{"subtopic_id": subtopic_id, "title_ms": title, "average_mastery": round(score or 0, 2)} for subtopic_id, title, score in rows]


def has_attempts(db: Session, student_id: int) -> bool:
    return db.scalar(select(func.count(Attempt.id)).where(Attempt.student_id == student_id)) > 0


def first_active_subtopic(db: Session):
    subtopic = db.scalar(select(Subtopic).where(Subtopic.chapter_id == 2, Subtopic.is_active.is_(True)).order_by(Subtopic.id))
    return serialize_subtopic(subtopic) if subtopic else None


def question_payload_to_model(payload: QuestionRequest) -> dict:
    data = payload.model_dump()
    options = normalize_options(data["question_type"], data["expected_answer"], data.pop("options", []))
    data["options_json"] = json.dumps(options, ensure_ascii=False)
    return data


def normalize_options(question_type: str, expected_answer: str, options: list[str]) -> list[str]:
    if question_type != "multiple_choice":
        return []
    cleaned = []
    for option in [str(item).strip() for item in options if str(item).strip()]:
        if option not in cleaned:
            cleaned.append(option)
    if expected_answer not in cleaned:
        cleaned.insert(0, expected_answer)
    return cleaned


def parse_options(options_json: str | None) -> list[str]:
    if not options_json:
        return []
    try:
        parsed = json.loads(options_json)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        return []
    return []


def serialize_user(user: User):
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name,
        "parent_email": user.parent_email,
        "class_id": user.class_id,
        "is_active": user.is_active,
    }


def serialize_classroom(classroom: Classroom):
    return {
        "id": classroom.id,
        "name": classroom.name,
        "year_level": classroom.year_level,
        "section": classroom.section,
        "is_active": classroom.is_active,
    }


def serialize_chapter(chapter: Chapter):
    return {"id": chapter.id, "number": chapter.number, "title_ms": chapter.title_ms, "is_active": chapter.is_active}


def serialize_subtopic(subtopic: Subtopic):
    return {
        "id": subtopic.id,
        "chapter_id": subtopic.chapter_id,
        "title_ms": subtopic.title_ms,
        "activity_type": subtopic.activity_type,
        "is_active": subtopic.is_active,
    }


def serialize_question(question: Question):
    return {
        "id": question.id,
        "chapter_id": question.chapter_id,
        "subtopic_id": question.subtopic_id,
        "difficulty": question.difficulty,
        "question_type": question.question_type,
        "prompt_ms": question.prompt_ms,
        "expected_answer": question.expected_answer,
        "options": parse_options(question.options_json),
        "explanation_ms": question.explanation_ms,
        "hint_ms": question.hint_ms,
        "hint_level2_ms": question.hint_level2_ms,
        "hint_level3_ms": question.hint_level3_ms,
        "source": question.source,
        "validation_status": question.validation_status,
        "is_active": question.is_active,
        "created_at": iso_datetime(question.created_at),
    }


def serialize_question_with_context(db: Session, question: Question):
    chapter = db.get(Chapter, question.chapter_id)
    subtopic = db.get(Subtopic, question.subtopic_id)
    return {
        **serialize_question(question),
        "chapter": serialize_chapter(chapter) if chapter else None,
        "subtopic": serialize_subtopic(subtopic) if subtopic else None,
    }


def serialize_mastery(mastery: MasteryRecord):
    return {
        "score": round(mastery.score, 2),
        "streak_correct": mastery.streak_correct,
        "streak_wrong": mastery.streak_wrong,
        "risk_level": risk_level(mastery.score),
    }


def serialize_attempt(db: Session, attempt: Attempt):
    question = db.get(Question, attempt.question_id)
    return {
        "id": attempt.id,
        "student_id": attempt.student_id,
        "question": serialize_question_with_context(db, question) if question else None,
        "answer_text": attempt.answer_text,
        "is_correct": attempt.is_correct,
        "time_seconds": attempt.time_seconds,
        "feedback_ms": attempt.feedback_ms,
        "created_at": iso_datetime(attempt.created_at),
    }


def serialize_student_summary(db: Session, student: User):
    mastery_rows = db.scalars(select(MasteryRecord).where(MasteryRecord.student_id == student.id)).all()
    attempts = db.scalars(select(Attempt).where(Attempt.student_id == student.id)).all()
    mastery_average = average([row.score for row in mastery_rows]) if mastery_rows else 0
    accuracy = round((sum(1 for attempt in attempts if attempt.is_correct) / len(attempts)) * 100, 2) if attempts else 0
    return {
        **serialize_user(student),
        "mastery_average": mastery_average,
        "accuracy": accuracy,
        "attempt_count": len(attempts),
        "risk_level": risk_level(mastery_average if mastery_average else 50),
    }


def serialize_generation_log(log: GenerationLog):
    return {
        "id": log.id,
        "teacher_id": log.teacher_id,
        "chapter_id": log.chapter_id,
        "subtopic_id": log.subtopic_id,
        "difficulty": log.difficulty,
        "prompt_ms": log.prompt_ms,
        "validation_status": log.validation_status,
        "created_at": log.created_at.isoformat(),
    }


def iso_datetime(value) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value) if value else ""


def _ensure_sqlite_question_columns(engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    existing_columns = {column["name"] for column in inspect(engine).get_columns("questions")}
    required_columns = {
        "presentation_style": "VARCHAR(30) NOT NULL DEFAULT 'text_based'",
        "hint_level2_ms": "TEXT NOT NULL DEFAULT ''",
        "hint_level3_ms": "TEXT NOT NULL DEFAULT ''",
    }

    with engine.begin() as connection:
        for column_name, ddl in required_columns.items():
            if column_name in existing_columns:
                continue
            connection.exec_driver_sql(f"ALTER TABLE questions ADD COLUMN {column_name} {ddl}")


def _ensure_attempt_source_column(engine) -> None:
    existing_columns = {column["name"] for column in inspect(engine).get_columns("attempts")}
    if "source" in existing_columns:
        return

    ddl = "VARCHAR(30) NOT NULL DEFAULT 'practice'"
    with engine.begin() as connection:
        connection.exec_driver_sql(f"ALTER TABLE attempts ADD COLUMN source {ddl}")


app = create_app(seed=False)


@app.on_event("startup")
def seed_default_app() -> None:
    with app.state.session_factory() as session:
        if should_seed_default_app(session):
            seed_demo_data(session)


def should_seed_default_app(session: Session) -> bool:
    mode = os.getenv("SEED_DEMO_DATA", "auto").strip().lower()
    if mode in {"0", "false", "no", "off", "skip"}:
        return False
    if mode in {"1", "true", "yes", "force", "always"}:
        return True
    has_teacher = bool(session.scalar(select(User.id).where(User.username == "cikgu").limit(1)))
    has_chapters = bool(session.scalar(select(Chapter.id).limit(1)))
    return not (has_teacher and has_chapters)
