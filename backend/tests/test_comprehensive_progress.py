import json

from app.services.comprehensive_progress import (
    HINT_LEVELS,
    apply_comprehensive_answer,
    create_active_question,
    dump_comprehensive_state,
    load_comprehensive_state,
)


def active_question():
    return create_active_question(
        question_id=17,
        question_number=3,
        phase="diagnosis",
    )


def test_load_state_adds_active_question_without_losing_phase_results():
    state = load_comprehensive_state(
        json.dumps(
            {
                "phase1_results": [{"question_id": 1}],
                "phase2_results": [],
                "phase3_results": [],
            }
        )
    )

    assert state["phase1_results"] == [{"question_id": 1}]
    assert state["active_question"] is None
    assert json.loads(dump_comprehensive_state(state)) == state


def test_three_wrong_answers_unlock_hints_in_order_without_completing():
    active = active_question()

    for expected_level in HINT_LEVELS:
        active, transition = apply_comprehensive_answer(
            active=active,
            answer_text="wrong",
            answer_is_correct=False,
        )
        assert transition["completed"] is False
        assert transition["outcome"] == "in_progress"
        assert transition["revealed_hint_level"] == expected_level

    assert active["attempt_count"] == 3
    assert active["wrong_attempts"] == 3
    assert active["revealed_hints"] == list(HINT_LEVELS)
    assert active["first_wrong_answer"] == "wrong"


def test_correct_after_a_wrong_answer_completes_as_incorrect():
    active, first_transition = apply_comprehensive_answer(
        active=active_question(),
        answer_text="41",
        answer_is_correct=False,
    )
    assert first_transition["completed"] is False

    active, transition = apply_comprehensive_answer(
        active=active,
        answer_text="42",
        answer_is_correct=True,
    )

    assert active["attempt_count"] == 2
    assert transition == {
        "completed": True,
        "outcome": "wrong_completed",
        "is_correct": False,
        "revealed_hint_level": None,
    }


def test_fourth_wrong_answer_completes_as_incorrect_without_a_fourth_hint():
    active = active_question()
    for _ in range(3):
        active, transition = apply_comprehensive_answer(
            active=active,
            answer_text="wrong",
            answer_is_correct=False,
        )
        assert transition["completed"] is False

    active, transition = apply_comprehensive_answer(
        active=active,
        answer_text="still wrong",
        answer_is_correct=False,
    )

    assert active["wrong_attempts"] == 4
    assert active["revealed_hints"] == list(HINT_LEVELS)
    assert transition == {
        "completed": True,
        "outcome": "wrong_completed",
        "is_correct": False,
        "revealed_hint_level": None,
    }


def test_first_answer_correct_completes_as_correct():
    active, transition = apply_comprehensive_answer(
        active=active_question(),
        answer_text="42",
        answer_is_correct=True,
    )

    assert active["attempt_count"] == 1
    assert active["wrong_attempts"] == 0
    assert transition == {
        "completed": True,
        "outcome": "correct",
        "is_correct": True,
        "revealed_hint_level": None,
    }
