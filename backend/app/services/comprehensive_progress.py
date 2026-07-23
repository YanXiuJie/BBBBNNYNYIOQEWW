import json
from copy import deepcopy


HINT_LEVELS = ("basic", "intermediate", "detailed")
PHASE_RESULT_KEYS = ("phase1_results", "phase2_results", "phase3_results")


def load_comprehensive_state(raw_state: str | None) -> dict:
    try:
        parsed = json.loads(raw_state or "{}")
    except (TypeError, json.JSONDecodeError):
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    for key in PHASE_RESULT_KEYS:
        if not isinstance(parsed.get(key), list):
            parsed[key] = []
    parsed.setdefault("active_question", None)
    return parsed


def dump_comprehensive_state(state: dict) -> str:
    return json.dumps(state, ensure_ascii=False)


def create_active_question(question_id: int, question_number: int, phase: str) -> dict:
    return {
        "question_id": question_id,
        "question_number": question_number,
        "phase": phase,
        "wrong_attempts": 0,
        "attempt_count": 0,
        "first_wrong_answer": None,
        "revealed_hints": [],
        "started": True,
    }


def apply_comprehensive_answer(
    active: dict,
    answer_text: str,
    answer_is_correct: bool,
) -> tuple[dict, dict]:
    updated = deepcopy(active)
    updated["attempt_count"] = int(updated.get("attempt_count", 0)) + 1
    wrong_attempts = int(updated.get("wrong_attempts", 0))

    if answer_is_correct:
        final_is_correct = wrong_attempts == 0
        return updated, {
            "completed": True,
            "outcome": "correct" if final_is_correct else "wrong_completed",
            "is_correct": final_is_correct,
            "revealed_hint_level": None,
        }

    wrong_attempts += 1
    updated["wrong_attempts"] = wrong_attempts
    if not updated.get("first_wrong_answer"):
        updated["first_wrong_answer"] = answer_text

    if wrong_attempts >= 4:
        return updated, {
            "completed": True,
            "outcome": "wrong_completed",
            "is_correct": False,
            "revealed_hint_level": None,
        }

    revealed_hints = list(updated.get("revealed_hints", []))
    level = HINT_LEVELS[wrong_attempts - 1]
    if level not in revealed_hints:
        revealed_hints.append(level)
    updated["revealed_hints"] = revealed_hints
    return updated, {
        "completed": False,
        "outcome": "in_progress",
        "is_correct": None,
        "revealed_hint_level": level,
    }
