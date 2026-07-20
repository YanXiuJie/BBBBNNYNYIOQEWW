from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Classroom(Base):
    __tablename__ = "classes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    year_level: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    section: Mapped[str] = mapped_column(String(20), default="A", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    class_id: Mapped[int | None] = mapped_column(ForeignKey("classes.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    title_ms: Mapped[str] = mapped_column(String(180), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Subtopic(Base):
    __tablename__ = "subtopics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), nullable=False)
    title_ms: Mapped[str] = mapped_column(String(180), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(40), default="lesson", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), nullable=False)
    subtopic_id: Mapped[int] = mapped_column(ForeignKey("subtopics.id"), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    prompt_ms: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str] = mapped_column(String(120), nullable=False)
    question_type: Mapped[str] = mapped_column(String(30), default="short_answer", nullable=False)
    options_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    explanation_ms: Mapped[str] = mapped_column(Text, nullable=False)
    hint_ms: Mapped[str] = mapped_column(Text, default="", nullable=False)
    presentation_style: Mapped[str] = mapped_column(String(30), default="text_based", nullable=False)
    hint_level2_ms: Mapped[str] = mapped_column(Text, default="", nullable=False)
    hint_level3_ms: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="seed", nullable=False)
    validation_status: Mapped[str] = mapped_column(String(30), default="validated", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        Index("idx_attempts_student", "student_id"),
        Index("idx_attempts_subtopic", "subtopic_id"),
        Index("idx_attempts_student_subtopic", "student_id", "subtopic_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), nullable=False)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), nullable=False)
    subtopic_id: Mapped[int] = mapped_column(ForeignKey("subtopics.id"), nullable=False)
    answer_text: Mapped[str] = mapped_column(String(240), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    feedback_ms: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="practice", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class DiagnosticSession(Base):
    __tablename__ = "diagnostic_sessions"
    __table_args__ = (
        Index("idx_diagnostic_student_status", "student_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    current_question_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    state_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class MasteryRecord(Base):
    __tablename__ = "mastery_records"
    __table_args__ = (
        UniqueConstraint("student_id", "subtopic_id"),
        Index("idx_mastery_student", "student_id"),
        Index("idx_mastery_subtopic", "subtopic_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), nullable=False)
    subtopic_id: Mapped[int] = mapped_column(ForeignKey("subtopics.id"), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    streak_correct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak_wrong: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class GenerationLog(Base):
    __tablename__ = "generation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), nullable=False)
    subtopic_id: Mapped[int] = mapped_column(ForeignKey("subtopics.id"), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    prompt_ms: Mapped[str] = mapped_column(Text, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ComprehensivePracticeSession(Base):
    __tablename__ = "comprehensive_practice_sessions"
    __table_args__ = (
        Index("idx_student_session", "student_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    current_question_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    phase: Mapped[str] = mapped_column(String(20), default="diagnosis", nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # JSON schema: [{"subtopic_id": int, "title_ms": str, "mastery_score": float}]
    weak_subtopics_json: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON schema: {"phase1_results": [...], "phase2_results": [...], "phase3_results": [...]}
    state_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class StylePreference(Base):
    __tablename__ = "style_preferences"
    __table_args__ = (
        UniqueConstraint("student_id", "presentation_style"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    presentation_style: Mapped[str] = mapped_column(String(30), nullable=False)
    total_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_time_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Derived field: updated by business logic from correct_count/total_attempts
    accuracy: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Derived field: updated by business logic from total_time_seconds/total_attempts
    avg_time_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
