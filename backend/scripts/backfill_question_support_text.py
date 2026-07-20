from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import build_engine, make_session_factory
from app.models import Question, Subtopic
from app.services.question_generator import build_support_texts, is_generic_support_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill step-by-step explanations and hints for saved questions.")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0, help="Limit processed questions. 0 means no limit.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-all", action="store_true", help="Refresh every active question, not only generic/missing rows.")
    parser.add_argument("--allow-local-fallback", action="store_true", help="Use deterministic support text if OpenAI repeatedly fails validation.")
    return parser.parse_args()


def question_needs_refresh(question: Question) -> bool:
    return any(
        [
            is_generic_support_text(question.explanation_ms),
            "Langkah 1" not in (question.explanation_ms or ""),
            is_generic_support_text(question.hint_ms),
            is_generic_support_text(question.hint_level2_ms),
            is_generic_support_text(question.hint_level3_ms),
        ]
    )


def backup_questions(rows: list[tuple[Question, str]], dry_run: bool) -> Path | None:
    if dry_run:
        return None
    backup_dir = BACKEND_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"questions_support_text_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    payload = [
        {
            "id": question.id,
            "subtopic_title": subtopic_title,
            "prompt_ms": question.prompt_ms,
            "expected_answer": question.expected_answer,
            "hint_ms": question.hint_ms,
            "hint_level2_ms": question.hint_level2_ms,
            "hint_level3_ms": question.hint_level3_ms,
            "explanation_ms": question.explanation_ms,
        }
        for question, subtopic_title in rows
    ]
    backup_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return backup_path


def build_request_items(rows: list[tuple[Question, str]]) -> list[dict]:
    return [
        {
            "id": question.id,
            "subtopic_title": subtopic_title,
            "difficulty": question.difficulty,
            "question_type": question.question_type,
            "prompt_ms": question.prompt_ms,
            "expected_answer": question.expected_answer,
            "current_hint_ms": question.hint_ms,
        }
        for question, subtopic_title in rows
    ]


def generate_support_batch(rows: list[tuple[Question, str]], api_key: str, model: str) -> dict[int, dict]:
    items = build_request_items(rows)
    prompt = (
        "Anda ialah guru Matematik Tahun 5. Lengkapkan sokongan pembelajaran untuk setiap soalan. "
        "Kekalkan id asal. Jangan ubah soalan, jawapan, jenis soalan atau pilihan jawapan. "
        "Hasilkan JSON sahaja dengan bentuk {\"items\":[...]}. Untuk setiap item, pulangkan id, hint_ms, "
        "hint_level2_ms, hint_level3_ms, explanation_ms. "
        "hint_ms ialah petunjuk awal yang khusus kepada soalan tanpa memberi jawapan akhir. "
        "hint_level2_ms lebih khusus dan sebut operasi/penukaran yang perlu digunakan. "
        "hint_level3_ms hampir mendedahkan cara kira tetapi masih meminta murid menyemak. "
        "explanation_ms mesti benar-benar step-by-step dalam Bahasa Melayu, gunakan Langkah 1, Langkah 2, "
        "Langkah 3, dan jika perlu Langkah 4, dengan nombor/unit sebenar daripada soalan dan jawapan akhir. "
        "Jangan tulis ayat generik seperti 'Soalan ini dipilih supaya kemahiran Matematik Tahun 5 sepadan dengan subtopik'. "
        f"Soalan: {json.dumps(items, ensure_ascii=False)}"
    )
    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "Return only valid JSON. No markdown."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    response.raise_for_status()
    data = json.loads(response.json()["choices"][0]["message"]["content"])
    generated_items = data.get("items", [])
    return {int(item["id"]): item for item in generated_items if "id" in item}


def is_valid_generated_support(item: dict) -> bool:
    required_fields = ("hint_ms", "hint_level2_ms", "hint_level3_ms", "explanation_ms")
    if any(not str(item.get(field, "")).strip() for field in required_fields):
        return False
    if any(is_generic_support_text(str(item.get(field, ""))) for field in required_fields):
        return False
    explanation = str(item.get("explanation_ms", ""))
    return "Langkah 1" in explanation and "Langkah 2" in explanation and "Langkah 3" in explanation


def fallback_support(question: Question, subtopic_title: str) -> dict:
    return build_support_texts(
        subtopic_title=subtopic_title,
        prompt=question.prompt_ms,
        answer=question.expected_answer,
        hint=question.hint_ms,
        hint_level2=question.hint_level2_ms,
        hint_level3=question.hint_level3_ms,
        explanation=question.explanation_ms,
    )


def chunks(items: list[tuple[Question, str]], size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def main() -> int:
    args = parse_args()
    load_dotenv(BACKEND_DIR.parent / ".env")
    load_dotenv(BACKEND_DIR / ".env", override=True)

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    if not api_key:
        print("OPENAI_API_KEY is not set. Refusing to backfill without AI generation.")
        return 2

    engine = build_engine()
    SessionLocal = make_session_factory(engine)
    updated = 0
    skipped = 0
    failed = 0
    local_fallback = 0
    backup_path = None

    try:
        with SessionLocal() as session:
            rows = session.execute(
                select(Question, Subtopic.title_ms)
                .join(Subtopic, Question.subtopic_id == Subtopic.id)
                .where(Question.is_active.is_(True))
                .order_by(Question.id)
            ).all()
            candidate_rows = [
                (question, subtopic_title)
                for question, subtopic_title in rows
                if args.force_all or question_needs_refresh(question)
            ]
            if args.limit:
                candidate_rows = candidate_rows[: args.limit]

            backup_path = backup_questions(candidate_rows, args.dry_run)
            print(
                json.dumps(
                    {
                        "active_questions": len(rows),
                        "candidate_questions": len(candidate_rows),
                        "dry_run": args.dry_run,
                        "backup_path": str(backup_path) if backup_path else None,
                        "model": model,
                    },
                    ensure_ascii=False,
                )
            )

            for batch in chunks(candidate_rows, max(1, args.batch_size)):
                try:
                    generated_by_id = generate_support_batch(batch, api_key, model)
                except Exception as exc:
                    print(f"batch_failed ids={[question.id for question, _ in batch]} error={type(exc).__name__}: {exc}")
                    generated_by_id = {}

                for question, subtopic_title in batch:
                    generated = generated_by_id.get(question.id)
                    if not generated or not is_valid_generated_support(generated):
                        try:
                            generated = generate_support_batch([(question, subtopic_title)], api_key, model).get(question.id)
                        except Exception as exc:
                            print(f"item_retry_failed id={question.id} error={type(exc).__name__}: {exc}")
                            generated = None

                    if generated and is_valid_generated_support(generated):
                        support = generated
                    elif args.allow_local_fallback:
                        support = fallback_support(question, subtopic_title)
                        local_fallback += 1
                    else:
                        support = None

                    if not support or not is_valid_generated_support(support):
                        failed += 1
                        print(f"invalid_support id={question.id}")
                        continue

                    if args.dry_run:
                        skipped += 1
                        continue

                    question.hint_ms = str(support["hint_ms"]).strip()
                    question.hint_level2_ms = str(support["hint_level2_ms"]).strip()
                    question.hint_level3_ms = str(support["hint_level3_ms"]).strip()
                    question.explanation_ms = str(support["explanation_ms"]).strip()
                    updated += 1
                if not args.dry_run:
                    session.commit()
                print(json.dumps({"processed": updated + skipped + failed, "updated": updated, "failed": failed}, ensure_ascii=False))
    finally:
        engine.dispose()

    print(
        json.dumps(
            {
                "updated": updated,
                "dry_run_checked": skipped,
                "failed": failed,
                "local_fallback": local_fallback,
                "backup_path": str(backup_path) if backup_path else None,
            },
            ensure_ascii=False,
        )
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
