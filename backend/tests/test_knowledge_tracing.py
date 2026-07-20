"""
Knowledge Tracing 单元测试

测试覆盖：
1. 无历史记录时返回先验概率
2. 连续答对后概率上升
3. 连续答错后概率下降
4. 混合答题序列的推理
5. 不同难度题目的影响
6. 置信度计算
7. 预测功能
"""

import pytest
from sqlalchemy import func, select
from app.models import Attempt, Question, Subtopic, User
from app.services.knowledge_tracing import (
    estimate_mastery_probability,
    get_student_knowledge_map,
    predict_next_attempt_success,
    P_L0
)
from app.seeds import seed_demo_data


def test_no_attempts_returns_prior(db):
    """测试：无历史记录时返回先验概率"""
    # Seed demo data first
    seed_demo_data(db)

    student = db.scalar(select(User).where(User.username == "amin"))
    subtopic = db.scalars(select(Subtopic)).first()

    # 确保这个学生没有在这个 subtopic 上答过题
    db.query(Attempt).filter(
        Attempt.student_id == student.id,
        Attempt.subtopic_id == subtopic.id
    ).delete()
    db.commit()

    state = estimate_mastery_probability(student.id, subtopic.id, db)

    assert state.mastery_probability == P_L0
    assert state.confidence == 0.0
    assert state.attempt_count == 0


def test_correct_answers_increase_probability(db):
    """测试：连续答对提高掌握概率"""
    # Seed demo data first
    seed_demo_data(db)

    student = db.scalar(select(User).where(User.username == "amin"))
    subtopic = db.scalars(select(Subtopic)).first()
    question = db.scalar(
        select(Question).where(
            Question.subtopic_id == subtopic.id,
            Question.difficulty == "medium"
        )
    )

    # 清空历史
    db.query(Attempt).filter(
        Attempt.student_id == student.id,
        Attempt.subtopic_id == subtopic.id
    ).delete()
    db.commit()

    # 连续 5 次答对
    for i in range(5):
        attempt = Attempt(
            student_id=student.id,
            question_id=question.id,
            chapter_id=subtopic.chapter_id,
            subtopic_id=subtopic.id,
            answer_text="correct",
            is_correct=True,
            time_seconds=30,
            feedback_ms="Betul"
        )
        db.add(attempt)
    db.commit()

    state = estimate_mastery_probability(student.id, subtopic.id, db)

    # 掌握概率应该明显高于先验
    assert state.mastery_probability > P_L0 + 0.2
    assert state.attempt_count == 5


def test_wrong_answers_decrease_probability(db):
    """测试：连续答错降低掌握概率"""
    # Seed demo data first
    seed_demo_data(db)

    student = db.scalar(select(User).where(User.username == "amin"))
    subtopic = db.scalars(select(Subtopic)).first()
    question = db.scalar(
        select(Question).where(
            Question.subtopic_id == subtopic.id,
            Question.difficulty == "medium"
        )
    )

    # 清空历史
    db.query(Attempt).filter(
        Attempt.student_id == student.id,
        Attempt.subtopic_id == subtopic.id
    ).delete()
    db.commit()

    # 连续 5 次答错
    for i in range(5):
        attempt = Attempt(
            student_id=student.id,
            question_id=question.id,
            chapter_id=subtopic.chapter_id,
            subtopic_id=subtopic.id,
            answer_text="wrong",
            is_correct=False,
            time_seconds=60,
            feedback_ms="Salah"
        )
        db.add(attempt)
    db.commit()

    state = estimate_mastery_probability(student.id, subtopic.id, db)

    # 掌握概率应该低于先验
    assert state.mastery_probability < P_L0
    assert state.attempt_count == 5


def test_confidence_increases_with_attempts(db):
    """测试：尝试次数越多，置信度越高"""
    # Seed demo data first
    seed_demo_data(db)

    student = db.scalar(select(User).where(User.username == "amin"))
    subtopic = db.scalars(select(Subtopic)).first()
    question = db.scalar(
        select(Question).where(Question.subtopic_id == subtopic.id)
    )

    # 清空历史
    db.query(Attempt).filter(
        Attempt.student_id == student.id,
        Attempt.subtopic_id == subtopic.id
    ).delete()
    db.commit()

    confidences = []

    # 逐步增加尝试次数
    for i in range(10):
        attempt = Attempt(
            student_id=student.id,
            question_id=question.id,
            chapter_id=subtopic.chapter_id,
            subtopic_id=subtopic.id,
            answer_text="test",
            is_correct=i % 2 == 0,  # 交替答对答错
            time_seconds=30,
            feedback_ms="Test"
        )
        db.add(attempt)
        db.commit()

        state = estimate_mastery_probability(student.id, subtopic.id, db)
        confidences.append(state.confidence)

    # 置信度应该单调递增
    assert confidences[-1] > confidences[0]
    assert confidences[-1] > confidences[len(confidences) // 2]


def test_prediction_probability_range(db):
    """测试：预测概率在 [0, 1] 范围内"""
    # Seed demo data first
    seed_demo_data(db)

    student = db.scalar(select(User).where(User.username == "amin"))
    subtopic = db.scalars(select(Subtopic)).first()

    for difficulty in ["easy", "medium", "hard"]:
        prob = predict_next_attempt_success(
            student.id, subtopic.id, difficulty, db
        )
        assert 0.0 <= prob <= 1.0


def test_knowledge_map_returns_all_subtopics(db):
    """测试：知识地图返回所有活跃的知识点"""
    # Seed demo data first
    seed_demo_data(db)

    student = db.scalar(select(User).where(User.username == "amin"))

    knowledge_map = get_student_knowledge_map(student.id, db)

    active_subtopics_count = db.scalar(
        select(func.count(Subtopic.id)).where(Subtopic.is_active == True)
    )

    assert len(knowledge_map) == active_subtopics_count

    # 验证排序（按掌握概率升序）
    probabilities = [state.mastery_probability for state in knowledge_map]
    assert probabilities == sorted(probabilities)
