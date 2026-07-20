"""
Adaptive Question Selector Service for Comprehensive Practice Sessions

Implements a 3-phase adaptive learning strategy:
- Phase 1 (Diagnosis): Identify weak subtopics
- Phase 2 (Remedial): Target weakest areas with scaffolding
- Phase 3 (Consolidation): Balanced review with difficulty progression

Design principles:
- Data-driven difficulty adjustment based on MasteryRecord scores
- Avoidance of recently attempted questions (last 5)
- Multi-intelligence style selection with explore/exploit balance
- Simple, maintainable logic without over-engineering
"""

import json
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..models import Attempt, ComprehensivePracticeSession, GenerationLog, MasteryRecord, Question, StylePreference, Subtopic
from .hint_generator import generate_multilevel_hints
from .question_generator import generate_question_ms, generate_with_template

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Phase boundaries (1-indexed question numbers)
# CRITICAL FIX: Unified to 15 total questions (5/5/5 phases)
PHASE1_END = 5
PHASE2_END = 10
PHASE3_END = 15

# Mastery score thresholds
MASTERY_THRESHOLD_LOW = 40.0
MASTERY_THRESHOLD_HIGH = 70.0
DEFAULT_MASTERY_SCORE = 50.0

# Performance tracking
RECENT_ATTEMPTS_LIMIT = 5
STREAK_THRESHOLD_FOR_UPGRADE = 2
MISTAKES_THRESHOLD_FOR_SCAFFOLDING = 2

# Phase 1 configuration
PHASE1_WEAK_SUBTOPICS_COUNT = 3
PHASE1_DEFAULT_DIFFICULTY = "medium"  # CRITICAL FIX: English difficulty

# Phase 3 configuration
PHASE3_WEAK_FOCUS_RATIO = 0.6

# Style selection
STYLE_EXPLORATION_RATE = 0.20
AVAILABLE_PRESENTATION_STYLES = ["text_based", "visual_diagram", "real_world_story", "interactive_simulation"]

# Difficulty levels
# CRITICAL FIX: English difficulty ladder matches seeds.py
DIFFICULTY_LADDER = ["easy", "medium", "hard"]


# ============================================================================
# Sub-task 4.1: Helper Functions
# ============================================================================

def _get_mastery(student_id: int, subtopic_id: int, chapter_id: int, db: Session) -> MasteryRecord:
    """
    Get or create a MasteryRecord for a student-subtopic pair.
    New records default to score=DEFAULT_MASTERY_SCORE (neutral starting point).
    """
    mastery = db.scalar(
        select(MasteryRecord).where(
            MasteryRecord.student_id == student_id,
            MasteryRecord.subtopic_id == subtopic_id
        )
    )

    if not mastery:
        mastery = MasteryRecord(
            student_id=student_id,
            chapter_id=chapter_id,
            subtopic_id=subtopic_id,
            score=DEFAULT_MASTERY_SCORE,
            streak_correct=0,
            streak_wrong=0
        )
        db.add(mastery)
        db.flush()

    return mastery


def _get_difficulty_by_mastery(score: float) -> str:
    """
    Map mastery score to difficulty level.
    Thresholds: [0-40): easy, [40-70): medium, [70-100]: hard
    """
    if score < MASTERY_THRESHOLD_LOW:
        return "easy"
    elif score < MASTERY_THRESHOLD_HIGH:
        return "medium"
    else:
        return "hard"


def _upgrade_difficulty(current_difficulty: str) -> str:
    """Upgrade difficulty level for successful progression."""
    try:
        idx = DIFFICULTY_LADDER.index(current_difficulty)
        if idx < len(DIFFICULTY_LADDER) - 1:
            return DIFFICULTY_LADDER[idx + 1]
        return current_difficulty
    except ValueError:
        return "medium"


def _downgrade_difficulty_for_scaffolding(current_difficulty: str) -> str:
    """Downgrade difficulty level for scaffolding weak areas."""
    try:
        idx = DIFFICULTY_LADDER.index(current_difficulty)
        if idx > 0:
            return DIFFICULTY_LADDER[idx - 1]
        return current_difficulty
    except ValueError:
        return "easy"


def _weighted_select_subtopic(weak_subtopics: list[dict]) -> int:
    """
    Weighted random selection: lower mastery scores get higher probability.
    weak_subtopics: [{"subtopic_id": int, "title_ms": str, "mastery_score": float}, ...]

    Returns: subtopic_id
    """
    if not weak_subtopics:
        raise ValueError("weak_subtopics list is empty")

    # Invert scores for weighting: lower score = higher weight
    # Use max(1, 100 - score) to ensure positive weights
    weights = [max(1.0, 100.0 - st["mastery_score"]) for st in weak_subtopics]

    chosen = random.choices(weak_subtopics, weights=weights, k=1)[0]
    return chosen["subtopic_id"]


# ============================================================================
# Sub-task 4.2: Style Selection
# ============================================================================

def _select_presentation_style(student_id: int, db: Session, exploration_rate: float = STYLE_EXPLORATION_RATE) -> str:
    """
    Multi-intelligence style selection using epsilon-greedy strategy.

    exploration_rate: probability of exploring a random style (default from constant)
    Otherwise, exploit the style with highest accuracy.

    Styles: text_based, visual_diagram, real_world_story, interactive_simulation
    """
    # Exploration: random style
    if random.random() < exploration_rate:
        return random.choice(AVAILABLE_PRESENTATION_STYLES)

    # Exploitation: choose style with highest accuracy
    preferences = db.scalars(
        select(StylePreference)
        .where(StylePreference.student_id == student_id)
        .where(StylePreference.total_attempts > 0)
    ).all()

    if not preferences:
        # No history: random choice
        return random.choice(AVAILABLE_PRESENTATION_STYLES)

    # Find best style by accuracy
    best_style = max(preferences, key=lambda p: p.accuracy)
    return best_style.presentation_style


# ============================================================================
# Sub-task 4.3: Phase Logic
# ============================================================================

def _identify_weakest_from_phase1(session: ComprehensivePracticeSession, db: Session, top_n: int = PHASE1_WEAK_SUBTOPICS_COUNT) -> list[dict]:
    """
    Analyze phase 1 results and identify the weakest subtopics.
    Returns: [{"subtopic_id": int, "title_ms": str, "mastery_score": float}, ...]
    Sorted by mastery score ascending (weakest first).
    """
    state = json.loads(session.state_json)
    phase1_results = state.get("phase1_results", [])

    if not phase1_results:
        # Fallback: select random active subtopics. Question selection can generate
        # AI/template questions when the bank has no available item.
        subtopics = db.scalars(
            select(Subtopic)
            .where(Subtopic.is_active == True)
            .limit(top_n)
        ).all()
        return [
            {
                "subtopic_id": st.id,
                "title_ms": st.title_ms,
                "mastery_score": DEFAULT_MASTERY_SCORE  # neutral default
            }
            for st in subtopics
        ]

    # Extract subtopic_ids from phase1 results
    subtopic_ids = list(set(r["subtopic_id"] for r in phase1_results))

    # Fetch current mastery scores
    mastery_records = db.scalars(
        select(MasteryRecord)
        .where(MasteryRecord.student_id == session.student_id)
        .where(MasteryRecord.subtopic_id.in_(subtopic_ids))
    ).all()

    mastery_map = {m.subtopic_id: m.score for m in mastery_records}

    # Build weak subtopics list
    weak_list = []
    for subtopic_id in subtopic_ids:
        subtopic = db.get(Subtopic, subtopic_id)
        if subtopic:
            weak_list.append({
                "subtopic_id": subtopic_id,
                "title_ms": subtopic.title_ms,
                "mastery_score": mastery_map.get(subtopic_id, DEFAULT_MASTERY_SCORE)
            })

    # Sort by score ascending (weakest first)
    weak_list.sort(key=lambda x: x["mastery_score"])

    return weak_list[:top_n]


def _count_recent_mistakes(student_id: int, subtopic_id: int, db: Session, recent_limit: int = RECENT_ATTEMPTS_LIMIT) -> int:
    """
    Count incorrect attempts in the last N attempts for a subtopic.
    Used to determine if scaffolding is needed.
    """
    recent_attempts = db.scalars(
        select(Attempt)
        .where(Attempt.student_id == student_id)
        .where(Attempt.subtopic_id == subtopic_id)
        .order_by(desc(Attempt.created_at))
        .limit(recent_limit)
    ).all()

    return sum(1 for a in recent_attempts if not a.is_correct)


def _phase1_diagnosis(session: ComprehensivePracticeSession, db: Session) -> Optional[dict]:
    """
    Phase 1: Diagnosis (Questions 1-5)
    Strategy: Sample diverse subtopics, use neutral difficulty (medium)

    Returns: {"question_id": int, "subtopic_id": int, "difficulty": str, "presentation_style": str}
    """
    if session.current_question_number >= PHASE1_END:
        # Phase 1 complete: transition to phase 2
        weak_subtopics = _identify_weakest_from_phase1(session, db)
        session.weak_subtopics_json = json.dumps(weak_subtopics)
        session.phase = "remedial"
        db.flush()
        return None  # Signal phase transition

    # Select a random active subtopic. The question selector handles AI generation,
    # question-bank fallback, and template fallback.
    subtopics = db.scalars(
        select(Subtopic)
        .where(Subtopic.is_active == True)
    ).all()
    if not subtopics:
        raise ValueError("No active subtopics available for diagnosis phase")

    chosen_subtopic = random.choice(subtopics)

    # Neutral difficulty for diagnosis
    difficulty = PHASE1_DEFAULT_DIFFICULTY

    # Select presentation style
    style = _select_presentation_style(session.student_id, db)

    # Find or generate question
    question = _find_or_generate_question(
        student_id=session.student_id,
        subtopic_id=chosen_subtopic.id,
        difficulty=difficulty,
        presentation_style=style,
        db=db
    )

    if not question:
        raise ValueError(f"No question available for subtopic {chosen_subtopic.id} with difficulty {difficulty}")

    return {
        "question_id": question.id,
        "subtopic_id": chosen_subtopic.id,
        "difficulty": difficulty,
        "presentation_style": style
    }


def _phase2_remedial(session: ComprehensivePracticeSession, db: Session) -> Optional[dict]:
    """
    Phase 2: Remedial (Questions 6-10)
    Strategy: Target weakest subtopics identified in phase 1
    - If all previous questions correct: upgrade difficulty
    - If mistakes present: downgrade difficulty for scaffolding

    Returns: {"question_id": int, "subtopic_id": int, "difficulty": str, "presentation_style": str}
    """
    if session.current_question_number >= PHASE2_END:
        # Phase 2 complete: transition to phase 3
        session.phase = "consolidation"
        db.flush()
        return None  # Signal phase transition

    weak_subtopics = json.loads(session.weak_subtopics_json)
    if not weak_subtopics:
        raise ValueError("No weak subtopics identified for remedial phase")

    # Weighted selection of weak subtopic
    chosen_subtopic_id = _weighted_select_subtopic(weak_subtopics)

    # Fix 1: N+1 query - fetch subtopic first
    chosen_subtopic = db.get(Subtopic, chosen_subtopic_id)
    if not chosen_subtopic:
        raise ValueError(f"Subtopic {chosen_subtopic_id} not found")

    # Get current mastery
    mastery = _get_mastery(
        student_id=session.student_id,
        subtopic_id=chosen_subtopic_id,
        chapter_id=chosen_subtopic.chapter_id,
        db=db
    )

    # Determine difficulty based on recent performance
    base_difficulty = _get_difficulty_by_mastery(mastery.score)
    recent_mistakes = _count_recent_mistakes(session.student_id, chosen_subtopic_id, db)

    if recent_mistakes == 0 and mastery.streak_correct >= STREAK_THRESHOLD_FOR_UPGRADE:
        # Progression: upgrade difficulty
        difficulty = _upgrade_difficulty(base_difficulty)
    elif recent_mistakes >= MISTAKES_THRESHOLD_FOR_SCAFFOLDING:
        # Scaffolding: downgrade difficulty
        difficulty = _downgrade_difficulty_for_scaffolding(base_difficulty)
    else:
        # Maintain current difficulty
        difficulty = base_difficulty

    # Select presentation style
    style = _select_presentation_style(session.student_id, db)

    # Find or generate question
    question = _find_or_generate_question(
        student_id=session.student_id,
        subtopic_id=chosen_subtopic_id,
        difficulty=difficulty,
        presentation_style=style,
        db=db
    )

    if not question:
        raise ValueError(f"No question available for subtopic {chosen_subtopic_id} with difficulty {difficulty}")

    return {
        "question_id": question.id,
        "subtopic_id": chosen_subtopic_id,
        "difficulty": difficulty,
        "presentation_style": style
    }




def _phase3_consolidation(session: ComprehensivePracticeSession, db: Session) -> Optional[dict]:
    """
    Phase 3: Consolidation (Questions 11-15)
    Strategy: Balanced review mixing weak and strong subtopics
    - 60% weak subtopics (from phase 1)
    - 40% random subtopics for variety
    - Difficulty tracks mastery score

    Returns: {"question_id": int, "subtopic_id": int, "difficulty": str, "presentation_style": str}
    """
    if session.current_question_number >= PHASE3_END:
        # Session complete
        session.is_completed = True
        db.flush()
        return None

    weak_subtopics = json.loads(session.weak_subtopics_json)

    # 60% focus on weak subtopics, 40% random for variety
    if random.random() < PHASE3_WEAK_FOCUS_RATIO and weak_subtopics:
        chosen_subtopic_id = _weighted_select_subtopic(weak_subtopics)
    else:
        # Random subtopic selection. The question selector handles empty banks.
        subtopics = db.scalars(
            select(Subtopic)
            .where(Subtopic.is_active == True)
        ).all()
        if not subtopics:
            raise ValueError("No active subtopics available for consolidation phase")
        chosen_subtopic_id = random.choice(subtopics).id

    # Fix 1: N+1 query - fetch subtopic first
    chosen_subtopic = db.get(Subtopic, chosen_subtopic_id)
    if not chosen_subtopic:
        raise ValueError(f"Subtopic {chosen_subtopic_id} not found")

    # Get current mastery
    mastery = _get_mastery(
        student_id=session.student_id,
        subtopic_id=chosen_subtopic_id,
        chapter_id=chosen_subtopic.chapter_id,
        db=db
    )

    # Difficulty tracks mastery score
    difficulty = _get_difficulty_by_mastery(mastery.score)

    # Select presentation style
    style = _select_presentation_style(session.student_id, db)

    # Find or generate question
    question = _find_or_generate_question(
        student_id=session.student_id,
        subtopic_id=chosen_subtopic_id,
        difficulty=difficulty,
        presentation_style=style,
        db=db
    )

    if not question:
        raise ValueError(f"No question available for subtopic {chosen_subtopic_id} with difficulty {difficulty}")

    return {
        "question_id": question.id,
        "subtopic_id": chosen_subtopic_id,
        "difficulty": difficulty,
        "presentation_style": style
    }


# ============================================================================
# Sub-task 4.4: Question Finding
# ============================================================================

def _normalize_options(question_type: str, expected_answer: str, options: list[str]) -> list[str]:
    if question_type != "multiple_choice":
        return []

    cleaned = []
    for option in [str(item).strip() for item in options if str(item).strip()]:
        if option not in cleaned:
            cleaned.append(option)
    if expected_answer not in cleaned:
        cleaned.insert(0, expected_answer)
    return cleaned


def _is_duplicate_generated_question(
    db: Session,
    subtopic_id: int,
    difficulty: str,
    question_type: str,
    prompt_ms: str,
    expected_answer: str,
) -> bool:
    return bool(
        db.scalar(
            select(Question.id)
            .where(
                Question.subtopic_id == subtopic_id,
                Question.difficulty == difficulty,
                Question.question_type == question_type,
                func.lower(Question.prompt_ms) == prompt_ms.strip().lower(),
                func.lower(Question.expected_answer) == expected_answer.strip().lower(),
            )
            .limit(1)
        )
    )


def _generate_and_save_question_for_comprehensive(
    student_id: int,
    subtopic: Subtopic,
    difficulty: str,
    presentation_style: str,
    db: Session,
    question_type: str = "short_answer",
) -> Optional[Question]:
    max_attempts = 5

    for attempt_number in range(1, max_attempts + 1):
        try:
            generated = generate_question_ms(subtopic.title_ms, difficulty, question_type)
        except Exception as exc:
            logger.warning("Comprehensive practice generation failed on attempt %s: %s", attempt_number, exc)
            continue

        if not generated:
            continue

        if generated.get("source") != "ai":
            logger.warning(
                "Comprehensive practice generation returned non-LLM source %r; falling back to question bank",
                generated.get("source"),
            )
            return None

        generated["question_type"] = generated.get("question_type") or question_type
        generated["difficulty"] = generated.get("difficulty") or difficulty
        generated["presentation_style"] = generated.get("presentation_style") or presentation_style

        if _is_duplicate_generated_question(
            db,
            subtopic.id,
            difficulty,
            generated["question_type"],
            generated["prompt_ms"],
            generated["expected_answer"],
        ):
            continue

        options = _normalize_options(generated["question_type"], generated["expected_answer"], generated.pop("options", []))
        generated["options_json"] = json.dumps(options, ensure_ascii=False)

        question = Question(
            chapter_id=subtopic.chapter_id,
            subtopic_id=subtopic.id,
            **generated,
        )
        db.add(question)
        db.flush()
        db.add(
            GenerationLog(
                teacher_id=student_id,
                chapter_id=subtopic.chapter_id,
                subtopic_id=subtopic.id,
                difficulty=difficulty,
                prompt_ms=question.prompt_ms,
                validation_status=question.validation_status,
            )
        )
        db.commit()
        db.refresh(question)
        return question

    return None


def _generate_template_question_for_comprehensive(
    subtopic: Subtopic,
    difficulty: str,
    presentation_style: str,
    db: Session,
    question_type: str = "short_answer",
) -> Optional[Question]:
    generated = generate_with_template(subtopic.title_ms, difficulty, question_type)
    if not generated:
        return None

    existing = db.scalar(
        select(Question)
        .where(
            Question.subtopic_id == subtopic.id,
            Question.difficulty == difficulty,
            Question.question_type == generated.get("question_type", question_type),
            func.lower(Question.prompt_ms) == generated["prompt_ms"].strip().lower(),
            func.lower(Question.expected_answer) == generated["expected_answer"].strip().lower(),
            Question.is_active == True,
        )
        .limit(1)
    )
    if existing:
        generate_multilevel_hints(existing, db)
        db.refresh(existing)
        return existing

    options = _normalize_options(generated.get("question_type", question_type), generated["expected_answer"], generated.pop("options", []))
    generated["question_type"] = generated.get("question_type") or question_type
    generated["presentation_style"] = generated.get("presentation_style") or presentation_style
    generated["options_json"] = json.dumps(options, ensure_ascii=False)
    question = Question(
        chapter_id=subtopic.chapter_id,
        subtopic_id=subtopic.id,
        **generated,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    generate_multilevel_hints(question, db)
    db.refresh(question)
    return question


def _find_or_generate_question(
    student_id: int,
    subtopic_id: int,
    difficulty: str,
    presentation_style: str,
    db: Session,
    avoid_recent_n: int = RECENT_ATTEMPTS_LIMIT
) -> Optional[Question]:
    """
    Generate a fresh LLM question first, then fall back to the existing question bank.

    Selection order:
    1. New LLM-generated question saved to DB
    2. Same subtopic + difficulty + style, excluding recent questions
    3. Same subtopic + difficulty, excluding recent questions
    4. Same subtopic + difficulty + style, allowing repeats if pool is exhausted
    5. Same subtopic + difficulty, allowing repeats if pool is exhausted

    Args:
        avoid_recent_n: number of recent attempts to avoid (default from constant)
    """
    subtopic = db.get(Subtopic, subtopic_id)
    if subtopic:
        generated_question = _generate_and_save_question_for_comprehensive(
            student_id=student_id,
            subtopic=subtopic,
            difficulty=difficulty,
            presentation_style=presentation_style,
            db=db,
        )
        if generated_question:
            return generated_question

    attempted_question_ids = set(
        db.scalars(
            select(Attempt.question_id)
            .where(Attempt.student_id == student_id)
            .where(Attempt.subtopic_id == subtopic_id)
        ).all()
    )

    recent_attempts = db.scalars(
        select(Attempt)
        .where(Attempt.student_id == student_id)
        .where(Attempt.subtopic_id == subtopic_id)
        .order_by(desc(Attempt.created_at))
        .limit(avoid_recent_n)
    ).all()
    recent_question_ids = [a.question_id for a in recent_attempts]

    query_variants = [
        (True, True),
        (False, True),
        (True, False),
        (False, False),
    ]

    for use_style, exclude_recent in query_variants:
        query = (
            select(Question)
            .where(Question.subtopic_id == subtopic_id)
            .where(Question.difficulty == difficulty)
            .where(Question.is_active == True)
            .where(Question.validation_status == "validated")
            .where(Question.source != "template")
        )

        if use_style:
            query = query.where(Question.presentation_style == presentation_style)

        if exclude_recent and recent_question_ids:
            query = query.where(Question.id.not_in(recent_question_ids))

        candidates = db.scalars(query).all()
        unattempted = [question for question in candidates if question.id not in attempted_question_ids]
        if unattempted:
            return random.choice(unattempted)

    if subtopic:
        template_question = _generate_template_question_for_comprehensive(
            subtopic=subtopic,
            difficulty=difficulty,
            presentation_style=presentation_style,
            db=db,
        )
        if template_question:
            return template_question

    repeated_bank = db.scalars(
        select(Question)
        .where(Question.subtopic_id == subtopic_id)
        .where(Question.difficulty == difficulty)
        .where(Question.is_active == True)
        .where(Question.validation_status == "validated")
        .where(Question.source != "template")
    ).all()
    if repeated_bank:
        return random.choice(repeated_bank)

    return None


# ============================================================================
# Sub-task 4.5: Main Function
# ============================================================================

def select_next_question_for_session(session_id: int, db: Session) -> dict:
    """
    Main entry point for adaptive question selection in comprehensive practice.

    Args:
        session_id: ComprehensivePracticeSession ID
        db: SQLAlchemy session

    Returns:
        {
            "question_id": int,
            "subtopic_id": int,
            "difficulty": str,
            "presentation_style": str,
            "question_number": int,
            "phase": str
        }

    Raises:
        ValueError: if session not found or no questions available
    """
    session = db.get(ComprehensivePracticeSession, session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")

    if session.is_completed:
        raise ValueError(f"Session {session_id} is already completed")

    # Route to appropriate phase handler
    phase_handlers = {
        "diagnosis": _phase1_diagnosis,
        "remedial": _phase2_remedial,
        "consolidation": _phase3_consolidation
    }

    # Fix 2: Replace recursion with while loop
    while True:
        if session.is_completed:
            raise StopIteration

        handler = phase_handlers.get(session.phase)
        if not handler:
            raise ValueError(f"Unknown phase: {session.phase}")

        result = handler(session, db)

        # Handle phase transitions
        if result is None:
            # Phase transition occurred, continue loop with new phase
            db.flush()
            continue

        # Question found, increment question number and return
        session.current_question_number += 1
        db.flush()

        # Build response
        return {
            "question_id": result["question_id"],
            "subtopic_id": result["subtopic_id"],
            "difficulty": result["difficulty"],
            "presentation_style": result["presentation_style"],
            "question_number": session.current_question_number,
            "phase": session.phase
        }
