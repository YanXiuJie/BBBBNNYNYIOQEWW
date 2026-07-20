from app.services.adaptive import AttemptSignal, MasteryState, next_difficulty, risk_level, update_mastery


def test_mastery_increases_after_correct_medium_answer():
    updated = update_mastery(
        MasteryState(score=50, streak_correct=0, streak_wrong=0),
        AttemptSignal(is_correct=True, difficulty="medium", time_seconds=40),
    )
    assert updated.score > 50
    assert updated.streak_correct == 1
    assert updated.streak_wrong == 0


def test_mastery_decreases_after_wrong_answer():
    updated = update_mastery(
        MasteryState(score=50, streak_correct=0, streak_wrong=0),
        AttemptSignal(is_correct=False, difficulty="medium", time_seconds=70),
    )
    assert updated.score < 50
    assert updated.streak_correct == 0
    assert updated.streak_wrong == 1


def test_next_difficulty_uses_mastery_score_and_streaks():
    assert next_difficulty(MasteryState(score=40, streak_correct=0, streak_wrong=2)) == "easy"
    assert next_difficulty(MasteryState(score=65, streak_correct=1, streak_wrong=0)) == "medium"
    assert next_difficulty(MasteryState(score=85, streak_correct=3, streak_wrong=0)) == "hard"


def test_risk_level_thresholds():
    assert risk_level(49) == "high"
    assert risk_level(69) == "moderate"
    assert risk_level(70) == "strong"
