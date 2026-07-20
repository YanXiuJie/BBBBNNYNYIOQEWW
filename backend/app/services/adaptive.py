from dataclasses import dataclass


@dataclass
class MasteryState:
    score: float
    streak_correct: int
    streak_wrong: int


@dataclass
class AttemptSignal:
    is_correct: bool
    difficulty: str
    time_seconds: int


def update_mastery(state: MasteryState, signal: AttemptSignal) -> MasteryState:
    """
    更新 mastery 状态，基于答题结果、难度和时间。

    改进点：
    1. time_factor 按题目难度调整预期时间
    2. 答错时扣分更温和，避免分数暴跌
    3. 难度权重更平衡
    """
    difficulty_weight = {"easy": 3, "medium": 6, "hard": 9}.get(signal.difficulty, 5)

    # 时间调整应该相对于题目难度的预期时间
    expected_time = {"easy": 30, "medium": 60, "hard": 120}.get(signal.difficulty, 60)
    time_factor = 1.0 if signal.time_seconds <= expected_time else 0.5

    if signal.is_correct:
        delta = difficulty_weight * time_factor
        score = state.score + delta
        return MasteryState(score=min(100, score), streak_correct=state.streak_correct + 1, streak_wrong=0)

    # 答错时扣分更温和，避免学生因几次错误分数暴跌
    delta = difficulty_weight * 0.5
    score = state.score - delta
    return MasteryState(score=max(0, score), streak_correct=0, streak_wrong=state.streak_wrong + 1)


def next_difficulty(state: MasteryState) -> str:
    if state.streak_wrong >= 2 or state.score < 50:
        return "easy"
    if state.score >= 80 and state.streak_correct >= 2:
        return "hard"
    return "medium"


def risk_level(score: float) -> str:
    if score < 50:
        return "high"
    if score < 70:
        return "moderate"
    return "strong"
