import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import create_app
from app.database import Base
from app.models import User, Chapter, Subtopic, Question

MYSQL_ADMIN_URL = os.getenv(
    "MYSQL_ADMIN_URL",
    "mysql+pymysql://root:admin123@127.0.0.1:3306/mysql?charset=utf8mb4",
)
MYSQL_TEST_DB_PREFIX = os.getenv("MYSQL_TEST_DB_PREFIX", "adaptive_math_ai_test")


def _admin_engine():
    return create_engine(MYSQL_ADMIN_URL, pool_pre_ping=True, isolation_level="AUTOCOMMIT")


def _create_mysql_database(database_name: str) -> None:
    engine = _admin_engine()
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql(
                f"CREATE DATABASE IF NOT EXISTS `{database_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        engine.dispose()


def _drop_mysql_database(database_name: str) -> None:
    engine = _admin_engine()
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql(f"DROP DATABASE IF EXISTS `{database_name}`")
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def mysql_database_name():
    database_name = f"{MYSQL_TEST_DB_PREFIX}_{uuid.uuid4().hex}"
    _create_mysql_database(database_name)
    yield database_name
    _drop_mysql_database(database_name)


@pytest.fixture(scope="session")
def mysql_database_url(mysql_database_name):
    return f"mysql+pymysql://root:admin123@127.0.0.1:3306/{mysql_database_name}?charset=utf8mb4"


def _reset_mysql_schema(database_url: str) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def mysql_app(mysql_database_url):
    _reset_mysql_schema(mysql_database_url)
    return create_app(database_url=mysql_database_url, seed=True)


@pytest.fixture()
def client(mysql_app):
    with TestClient(mysql_app) as test_client:
        yield test_client


@pytest.fixture()
def db(mysql_database_url):
    """Provide a clean MySQL test database session"""
    _reset_mysql_schema(mysql_database_url)
    engine = create_engine(mysql_database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def student_user(db):
    """Create a test student user"""
    user = User(
        username="test_student",
        full_name="Test Student",
        role="student",
        password_hash="dummy_hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def sample_question(db):
    """Create a test question with chapter and subtopic"""
    chapter = Chapter(
        number=1,
        title_ms="Nombor Bulat dan Operasi",
        is_active=True
    )
    db.add(chapter)
    db.commit()
    db.refresh(chapter)

    subtopic = Subtopic(
        chapter_id=chapter.id,
        title_ms="Tambah dan Tolak",
        activity_type="lesson",
        is_active=True
    )
    db.add(subtopic)
    db.commit()
    db.refresh(subtopic)

    question = Question(
        chapter_id=chapter.id,
        subtopic_id=subtopic.id,
        difficulty="medium",
        prompt_ms="Kira 25 + 37",
        expected_answer="62",
        question_type="short_answer",
        options_json="[]",
        explanation_ms="25 + 37 = 62",
        hint_ms="Cuba tambah digit satu per satu",
        presentation_style="text_based",
        hint_level2_ms="",
        hint_level3_ms="",
        source="seed",
        validation_status="validated",
        is_active=True
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question
