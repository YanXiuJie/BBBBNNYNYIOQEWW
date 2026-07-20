import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


DEFAULT_DATABASE_URL = "mysql+pymysql://root:admin123@127.0.0.1:3306/adaptive_math_ai?charset=utf8mb4"


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def _ensure_mysql_database_exists(url: str) -> None:
    parsed_url = make_url(url)
    if parsed_url.get_backend_name() != "mysql" or not parsed_url.database:
        return

    admin_url = parsed_url.set(database="mysql")
    admin_engine = create_engine(admin_url, pool_pre_ping=True, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(
                f"CREATE DATABASE IF NOT EXISTS `{parsed_url.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        admin_engine.dispose()


def build_engine(database_url: str | None = None):
    url = database_url or get_database_url()
    parsed_url = make_url(url)
    if parsed_url.get_backend_name() == "mysql":
        _ensure_mysql_database_exists(url)

    connect_args = {"check_same_thread": False} if parsed_url.get_backend_name() == "sqlite" else {}
    return create_engine(url, connect_args=connect_args, pool_pre_ping=parsed_url.get_backend_name() == "mysql")


def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def session_scope(session_factory):
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
