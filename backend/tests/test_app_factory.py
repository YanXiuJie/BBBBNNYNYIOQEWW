import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import inspect

from app.main import create_app


ROOT = Path(__file__).resolve().parents[1]


def test_importing_app_main_does_not_touch_default_database(mysql_database_url):
    env = os.environ.copy()
    env["DATABASE_URL"] = mysql_database_url
    env["PYTHONPATH"] = str(ROOT)

    result = subprocess.run(
        [sys.executable, "-c", "from app.main import create_app; print('ok')"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_create_app_creates_mysql_schema(mysql_database_url):
    app = create_app(database_url=mysql_database_url, seed=True)
    assert app.title == "Adaptive Math AI"

    engine = app.state.session_factory.kw["bind"]
    columns = {column["name"] for column in inspect(engine).get_columns("questions")}
    assert {"presentation_style", "hint_level2_ms", "hint_level3_ms"}.issubset(columns)
    attempt_columns = {column["name"] for column in inspect(engine).get_columns("attempts")}
    assert "source" in attempt_columns
    diagnostic_session_columns = {column["name"] for column in inspect(engine).get_columns("diagnostic_sessions")}
    assert {"status", "current_question_number", "total_questions", "state_json"}.issubset(diagnostic_session_columns)
