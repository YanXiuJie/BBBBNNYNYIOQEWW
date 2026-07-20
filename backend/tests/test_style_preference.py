import pytest
from app.services.style_preference import update_style_preference, get_style_preference_summary
from app.models import StylePreference, User


def test_update_style_preference_creates_new_record(db, student_user):
    """Test creating a new style preference record"""
    update_style_preference(
        student_id=student_user.id,
        presentation_style="text_based",
        is_correct=True,
        time_seconds=45.0,
        db=db
    )
    db.commit()

    pref = db.query(StylePreference).filter_by(
        student_id=student_user.id,
        presentation_style="text_based"
    ).first()

    assert pref is not None
    assert pref.total_attempts == 1
    assert pref.correct_count == 1
    assert pref.accuracy == 100.0
    assert pref.avg_time_seconds == 45.0


def test_update_style_preference_updates_existing(db, student_user):
    """Test updating an existing style preference record"""
    # First attempt
    update_style_preference(student_user.id, "visual_spatial", True, 30.0, db)
    # Second attempt
    update_style_preference(student_user.id, "visual_spatial", False, 60.0, db)
    db.commit()

    pref = db.query(StylePreference).filter_by(
        student_id=student_user.id,
        presentation_style="visual_spatial"
    ).first()

    assert pref.total_attempts == 2
    assert pref.correct_count == 1
    assert pref.accuracy == 50.0
    assert pref.avg_time_seconds == 45.0


def test_get_style_preference_summary_empty(db, student_user):
    """Test getting summary when no preferences exist"""
    summary = get_style_preference_summary(student_user.id, db)
    assert summary == {}


def test_get_style_preference_summary_multiple_styles(db, student_user):
    """Test getting summary with multiple presentation styles"""
    # Create multiple style preferences
    update_style_preference(student_user.id, "text_based", True, 40.0, db)
    update_style_preference(student_user.id, "text_based", True, 50.0, db)
    update_style_preference(student_user.id, "visual_spatial", True, 30.0, db)
    update_style_preference(student_user.id, "visual_spatial", False, 60.0, db)
    db.commit()

    summary = get_style_preference_summary(student_user.id, db)

    assert "text_based" in summary
    assert "visual_spatial" in summary

    assert summary["text_based"]["total_attempts"] == 2
    assert summary["text_based"]["accuracy"] == 100.0
    assert summary["text_based"]["avg_time_seconds"] == 45.0

    assert summary["visual_spatial"]["total_attempts"] == 2
    assert summary["visual_spatial"]["accuracy"] == 50.0
    assert summary["visual_spatial"]["avg_time_seconds"] == 45.0
