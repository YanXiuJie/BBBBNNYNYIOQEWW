"""
Knowledge Tracing Service - Simplified BKT Implementation

理论基础：
Corbett, A. T., & Anderson, J. R. (1994).
"Knowledge tracing: Modeling the acquisition of procedural knowledge"
User modeling and user-adapted interaction, 4(4), 253-278.

BKT 四参数模型：
- P(L0): 初始掌握概率 (prior knowledge)
- P(T): 学习转移概率 (learning rate)
- P(G): 猜对概率 (guess probability)
- P(S): 失误概率 (slip probability)

简化实现：
- P(L0) = 0.3 (经验值)
- P(T) = 0.15 (每次正确答题的学习增益)
- P(S) = 0.1 (已掌握但失误)
- P(G) = f(difficulty) (基于题目难度)

贝叶斯更新公式：
P(Lt|obs) = P(Lt-1) * P(obs|Lt-1) / P(obs)
"""

from dataclasses import dataclass
from typing import List
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Attempt, Question, Subtopic


@dataclass
class KnowledgeState:
    """
    学生在某个知识点的掌握状态

    Attributes:
        subtopic_id: 知识点 ID
        subtopic_title_ms: 知识点名称（马来语）
        mastery_probability: 掌握概率 ∈ [0, 1]
        confidence: 估计置信度 ∈ [0, 1]，基于样本量
        attempt_count: 历史尝试次数
        last_attempt_correct: 最近一次是否正确
    """
    subtopic_id: int
    subtopic_title_ms: str
    mastery_probability: float
    confidence: float
    attempt_count: int
    last_attempt_correct: bool | None = None


# BKT 模型参数（全局常量）
P_L0 = 0.3      # 初始掌握概率（先验）
P_T = 0.15      # 学习转移概率（每次练习的学习增益）
P_S = 0.1       # 失误概率（已掌握但答错）

# 猜对概率映射（基于题目难度）
GUESS_PROBABILITY_MAP = {
    "easy": 0.3,    # 简单题猜对概率较高
    "medium": 0.2,  # 中等题
    "hard": 0.1     # 困难题猜对概率低
}

# 置信度计算参数
MIN_ATTEMPTS_FOR_HIGH_CONFIDENCE = 6  # 至少 6 次尝试才有高置信度


def estimate_mastery_probability(
    student_id: int,
    subtopic_id: int,
    db: Session
) -> KnowledgeState:
    """
    使用 BKT 模型估计学生对某个知识点的掌握概率

    算法流程：
    1. 获取学生在该知识点的所有历史答题记录（按时间排序）
    2. 初始化 P(L) = P(L0)
    3. 对每次答题，根据结果和题目难度进行贝叶斯更新
    4. 计算置信度（基于样本量）

    Args:
        student_id: 学生 ID
        subtopic_id: 知识点 ID
        db: 数据库会话

    Returns:
        KnowledgeState 对象，包含掌握概率和置信度
    """
    # 1. 获取历史答题记录
    attempts = db.scalars(
        select(Attempt)
        .where(
            Attempt.student_id == student_id,
            Attempt.subtopic_id == subtopic_id
        )
        .order_by(Attempt.created_at)  # 时间顺序很重要
    ).all()

    # 2. 获取 subtopic 信息
    subtopic = db.get(Subtopic, subtopic_id)
    subtopic_title = subtopic.title_ms if subtopic else ""

    # 3. 如果没有历史记录，返回先验概率
    if not attempts:
        return KnowledgeState(
            subtopic_id=subtopic_id,
            subtopic_title_ms=subtopic_title,
            mastery_probability=P_L0,
            confidence=0.0,
            attempt_count=0,
            last_attempt_correct=None
        )

    # 4. BKT 推理：逐步更新掌握概率
    P_L = P_L0  # 初始掌握概率

    for attempt in attempts:
        # 获取题目难度以确定 P(G)
        question = db.get(Question, attempt.question_id)
        difficulty = question.difficulty if question else "medium"
        P_G = GUESS_PROBABILITY_MAP.get(difficulty, 0.2)

        if attempt.is_correct:
            # 观察到正确答案，贝叶斯更新
            P_L = _update_after_correct(P_L, P_G)
        else:
            # 观察到错误答案，贝叶斯更新
            P_L = _update_after_wrong(P_L, P_G)

    # 5. 计算置信度
    confidence = _calculate_confidence(len(attempts))

    # 6. 记录最后一次尝试结果
    last_correct = attempts[-1].is_correct if attempts else None

    return KnowledgeState(
        subtopic_id=subtopic_id,
        subtopic_title_ms=subtopic_title,
        mastery_probability=round(P_L, 3),
        confidence=round(confidence, 2),
        attempt_count=len(attempts),
        last_attempt_correct=last_correct
    )


def _update_after_correct(P_L: float, P_G: float) -> float:
    """
    答对后的贝叶斯更新

    公式：P(L|correct) = P(L) * (1 - P(S)) / [P(L) * (1 - P(S)) + (1 - P(L)) * P(G)]

    直觉理解：
    - 如果学生已经掌握（P(L) 高），答对很正常
    - 如果学生未掌握（P(L) 低），答对可能是猜的，增益小

    学习转移：答对后有 P(T) 的概率真正学会
    P(L_new) = P(L|correct) + (1 - P(L|correct)) * P(T)
    """
    # 贝叶斯更新
    numerator = P_L * (1 - P_S)
    denominator = P_L * (1 - P_S) + (1 - P_L) * P_G

    if denominator == 0:
        P_L_updated = P_L
    else:
        P_L_updated = numerator / denominator

    # 学习转移
    P_L_final = P_L_updated + (1 - P_L_updated) * P_T

    return min(1.0, P_L_final)  # 确保不超过 1


def _update_after_wrong(P_L: float, P_G: float) -> float:
    """
    答错后的贝叶斯更新

    公式：P(L|wrong) = P(L) * P(S) / [P(L) * P(S) + (1 - P(L)) * (1 - P(G))]

    直觉理解：
    - 如果学生已经掌握，答错可能是失误（小概率）
    - 如果学生未掌握，答错是预期结果，P(L) 下降
    """
    numerator = P_L * P_S
    denominator = P_L * P_S + (1 - P_L) * (1 - P_G)

    if denominator == 0:
        return max(0.0, P_L * 0.5)  # 惩罚性降低
    else:
        return max(0.0, numerator / denominator)


def _calculate_confidence(attempt_count: int) -> float:
    """
    计算估计的置信度

    策略：
    - 0 次尝试：置信度 0
    - 1-5 次尝试：线性增长 0.0 → 0.5
    - 6+ 次尝试：线性增长 0.5 → 1.0
    - 12+ 次尝试：置信度 1.0（饱和）

    Returns:
        confidence ∈ [0, 1]
    """
    if attempt_count == 0:
        return 0.0
    elif attempt_count < MIN_ATTEMPTS_FOR_HIGH_CONFIDENCE:
        # 0.5 / 6 ≈ 0.083 per attempt
        return min(0.5, attempt_count / MIN_ATTEMPTS_FOR_HIGH_CONFIDENCE * 0.5)
    else:
        # 0.5 + (attempts - 6) * 0.083
        excess = attempt_count - MIN_ATTEMPTS_FOR_HIGH_CONFIDENCE
        return min(1.0, 0.5 + excess / MIN_ATTEMPTS_FOR_HIGH_CONFIDENCE * 0.5)


def get_student_knowledge_map(
    student_id: int,
    db: Session,
    chapter_id: int | None = None
) -> List[KnowledgeState]:
    """
    获取学生的完整知识地图

    用于：
    - 学生端：展示自己的知识掌握全景
    - 教师端：分析学生的强项和弱项

    Args:
        student_id: 学生 ID
        db: 数据库会话
        chapter_id: 可选，只获取特定章节的知识点

    Returns:
        所有知识点的掌握状态列表，按掌握概率升序排序
    """
    # 获取所有活跃的 subtopics
    query = select(Subtopic).where(Subtopic.is_active == True)
    if chapter_id:
        query = query.where(Subtopic.chapter_id == chapter_id)

    subtopics = db.scalars(query.order_by(Subtopic.id)).all()

    # 为每个 subtopic 估计掌握概率
    knowledge_map = []
    for subtopic in subtopics:
        state = estimate_mastery_probability(student_id, subtopic.id, db)
        knowledge_map.append(state)

    # 按掌握概率排序（最弱的在前）
    knowledge_map.sort(key=lambda x: (x.mastery_probability, -x.confidence))

    return knowledge_map


def predict_next_attempt_success(
    student_id: int,
    subtopic_id: int,
    difficulty: str,
    db: Session
) -> float:
    """
    预测学生下一次在该知识点特定难度下的答对概率

    公式：P(correct) = P(L) * (1 - P(S)) + (1 - P(L)) * P(G)

    直觉理解：
    - 如果已掌握（P(L) 高）：大概率答对，小概率失误
    - 如果未掌握（P(L) 低）：小概率猜对

    用途：
    - 教师决策："给这个学生出 hard 题合适吗？"
    - 自适应算法："预测成功率 > 0.8，可以升级难度"

    Args:
        student_id: 学生 ID
        subtopic_id: 知识点 ID
        difficulty: 题目难度 (easy/medium/hard)
        db: 数据库会话

    Returns:
        答对概率 ∈ [0, 1]
    """
    state = estimate_mastery_probability(student_id, subtopic_id, db)
    P_L = state.mastery_probability
    P_G = GUESS_PROBABILITY_MAP.get(difficulty, 0.2)

    # P(correct) = P(L) * (1 - P(S)) + (1 - P(L)) * P(G)
    P_correct = P_L * (1 - P_S) + (1 - P_L) * P_G

    return round(P_correct, 3)


def get_weakest_subtopics(
    student_id: int,
    db: Session,
    top_n: int = 5,
    min_confidence: float = 0.3
) -> List[KnowledgeState]:
    """
    获取学生最弱的 N 个知识点（用于推荐练习）

    策略：
    - 只返回有足够样本的知识点（confidence >= min_confidence）
    - 按掌握概率升序排序

    Args:
        student_id: 学生 ID
        db: 数据库会话
        top_n: 返回前 N 个最弱的
        min_confidence: 最低置信度阈值

    Returns:
        最弱的知识点列表
    """
    knowledge_map = get_student_knowledge_map(student_id, db)

    # 过滤：只要有足够样本的
    reliable = [state for state in knowledge_map if state.confidence >= min_confidence]

    # 返回最弱的 top_n 个
    return reliable[:top_n]
