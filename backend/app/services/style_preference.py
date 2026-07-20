from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import StylePreference


def update_style_preference(
    student_id: int,
    presentation_style: str,
    is_correct: bool,
    time_seconds: float,
    db: Session
) -> None:
    """
    Update student performance statistics for a specific presentation style.
    Creates a new record if it doesn't exist.

    Note: Caller is responsible for db.commit() to maintain transaction boundaries.
    """
    pref = db.scalar(
        select(StylePreference).where(
            StylePreference.student_id == student_id,
            StylePreference.presentation_style == presentation_style
        )
    )

    if not pref:
        pref = StylePreference(
            student_id=student_id,
            presentation_style=presentation_style,
            total_attempts=0,
            correct_count=0,
            total_time_seconds=0,
            accuracy=0.0,
            avg_time_seconds=0.0
        )
        db.add(pref)
        db.flush()  # Flush to database so subsequent calls can find this record

    # Update statistics
    pref.total_attempts += 1
    if is_correct:
        pref.correct_count += 1
    pref.total_time_seconds += time_seconds

    # Recalculate derived fields
    assert pref.total_attempts > 0, "total_attempts must be positive before division"
    pref.accuracy = (pref.correct_count / pref.total_attempts) * 100.0
    pref.avg_time_seconds = pref.total_time_seconds / pref.total_attempts


def get_style_preference_summary(student_id: int, db: Session) -> dict:
    """
    Get summary of student's performance across all presentation styles.
    Returns: {"text_based": {"accuracy": 75.0, "avg_time": 45.2}, ...}
    """
    preferences = db.scalars(
        select(StylePreference).where(StylePreference.student_id == student_id)
    ).all()

    summary = {}
    for pref in preferences:
        summary[pref.presentation_style] = {
            "total_attempts": pref.total_attempts,
            "accuracy": pref.accuracy,
            "avg_time_seconds": pref.avg_time_seconds
        }

    return summary
