"""
Hint Generator Service
Generates multilevel hints for questions using AI or fallback methods.
"""

import json
import logging
import os
from sqlalchemy.orm import Session
from app.models import Question, Subtopic
from app.services.question_generator import build_support_texts, is_generic_support_text
import httpx


def generate_multilevel_hints(question: Question, db: Session) -> None:
    """
    Generate multilevel hints for a question.

    - Skips if hints already exist
    - Uses OpenAI API if available
    - Falls back to simple template-based generation

    Args:
        question: Question object to generate hints for
        db: Database session
    """
    # Skip only when both generated hints already exist and are specific enough.
    if (
        question.hint_level2_ms
        and question.hint_level3_ms
        and not is_generic_support_text(question.hint_level2_ms)
        and not is_generic_support_text(question.hint_level3_ms)
    ):
        return

    # Check if OpenAI API is available
    api_key = os.getenv("OPENAI_API_KEY")

    if api_key:
        _generate_with_openai(question, db, api_key)
    else:
        _generate_fallback_hints(question, db)


def _generate_with_openai(question: Question, db: Session, api_key: str) -> None:
    """
    Generate hints using OpenAI API.

    Args:
        question: Question object
        db: Database session
        api_key: OpenAI API key
    """
    try:
        prompt = f"""Anda adalah guru matematik Tahun 5 yang berpengalaman.

Soalan: {question.prompt_ms}
Jawapan: {question.expected_answer}
Penjelasan: {question.explanation_ms}
Petunjuk Awal: {question.hint_ms}

Sila hasilkan 2 petunjuk tambahan dalam Bahasa Melayu:

1. Petunjuk Tahap 2 (lebih spesifik dari petunjuk awal, tapi tidak terlalu dedah jawapan)
2. Petunjuk Tahap 3 (sangat spesifik, hampir mendedahkan jawapan tapi masih memerlukan pelajar berfikir)

Format output sebagai JSON:
{{
  "hint_level2_ms": "...",
  "hint_level3_ms": "..."
}}
"""

        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                "messages": [
                    {"role": "system", "content": "Anda adalah guru matematik yang membantu pelajar dengan petunjuk yang berstruktur."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        response.raise_for_status()

        hints = json.loads(response.json()["choices"][0]["message"]["content"])
        subtopic = db.get(Subtopic, question.subtopic_id)
        support_text = build_support_texts(
            subtopic_title=subtopic.title_ms if subtopic else "",
            prompt=question.prompt_ms,
            answer=question.expected_answer,
            hint=question.hint_ms,
            hint_level2=question.hint_level2_ms or hints.get("hint_level2_ms", ""),
            hint_level3=question.hint_level3_ms or hints.get("hint_level3_ms", ""),
            explanation=question.explanation_ms,
        )

        question.hint_ms = support_text["hint_ms"]
        question.explanation_ms = support_text["explanation_ms"]
        if is_generic_support_text(question.hint_level2_ms):
            question.hint_level2_ms = support_text["hint_level2_ms"]
        if is_generic_support_text(question.hint_level3_ms):
            question.hint_level3_ms = support_text["hint_level3_ms"]
        db.commit()

    except Exception as e:
        # Log the failure and fall back to simple generation
        logging.warning(f"OpenAI hint generation failed for question {question.id}: {e}")
        _generate_fallback_hints(question, db)


def _generate_fallback_hints(question: Question, db: Session) -> None:
    """
    Generate simple template-based hints when API is unavailable.

    Args:
        question: Question object
        db: Database session
    """
    subtopic = db.get(Subtopic, question.subtopic_id)
    support_text = build_support_texts(
        subtopic_title=subtopic.title_ms if subtopic else "",
        prompt=question.prompt_ms,
        answer=question.expected_answer,
        hint=question.hint_ms,
        hint_level2=question.hint_level2_ms,
        hint_level3=question.hint_level3_ms,
        explanation=question.explanation_ms,
    )

    if is_generic_support_text(question.hint_ms):
        question.hint_ms = support_text["hint_ms"]
    if is_generic_support_text(question.explanation_ms):
        question.explanation_ms = support_text["explanation_ms"]
    if is_generic_support_text(question.hint_level2_ms):
        question.hint_level2_ms = support_text["hint_level2_ms"]
    if is_generic_support_text(question.hint_level3_ms):
        question.hint_level3_ms = support_text["hint_level3_ms"]

    db.commit()


def _mask_answer(answer: str) -> str:
    """
    Mask part of the answer to create a hint.

    Args:
        answer: The correct answer

    Returns:
        Partially masked answer
    """
    if len(answer) <= 2:
        return answer[0] + "_"

    # Mask middle characters
    return answer[0] + "_" * (len(answer) - 2) + answer[-1]


def _get_operation_hint(prompt: str) -> str:
    """
    Extract operation hint from the question prompt.

    Args:
        prompt: Question prompt in Malay

    Returns:
        Operation hint string
    """
    operations = {
        "tambah": "operasi tambah",
        "tolak": "operasi tolak",
        "darab": "operasi darab",
        "bahagi": "operasi bahagi",
        "+": "operasi tambah",
        "-": "operasi tolak",
        "×": "operasi darab",
        "÷": "operasi bahagi",
        "kira": "pengiraan",
        "berapa": "pengiraan"
    }

    prompt_lower = prompt.lower()
    for keyword, hint in operations.items():
        if keyword in prompt_lower:
            return hint

    return "pengiraan yang teliti"
