from fractions import Fraction


def normalize_answer(value: str) -> str:
    """基础标准化：去空格、小写、去前缀"""
    cleaned = value.strip().lower().replace(" ", "")
    # 移除常见前缀
    for prefix in ["rm", "ringgit"]:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
    return cleaned.strip()


def parse_numeric(value: str) -> Fraction | None:
    """解析数值，支持分数、小数、百分比、货币"""
    cleaned = normalize_answer(value)

    try:
        # 处理百分比
        if cleaned.endswith("%"):
            return Fraction(cleaned[:-1]) / 100

        # 处理分数和整数
        return Fraction(cleaned)
    except (ValueError, ZeroDivisionError):
        return None


def get_equivalent_forms(value: str) -> set[str]:
    """生成等价形式的集合"""
    variants = {normalize_answer(value)}

    # 尝试解析为数值
    num = parse_numeric(value)
    if num is not None:
        # 添加分数形式
        if num.denominator == 1:
            variants.add(str(num.numerator))
        else:
            variants.add(f"{num.numerator}/{num.denominator}")

        # 添加小数形式（保留2位）
        decimal = float(num)
        variants.add(f"{decimal:.2f}".rstrip("0").rstrip("."))

        # 添加百分比形式（如果合理）
        if 0 <= num <= 1:
            percent = num * 100
            if percent.denominator == 1:
                variants.add(f"{percent.numerator}%")

    # 添加带货币符号的形式
    if not value.lower().startswith("rm"):
        variants.add(f"rm{normalize_answer(value)}")

    return variants


def is_equivalent_answer(student_answer: str, expected_answer: str) -> bool:
    """
    判断学生答案是否与标准答案等价。

    支持：
    - 数值等价：1/2 = 0.5 = 0.50
    - 货币格式：RM10 = RM 10 = 10
    - 百分比：0.5 = 50%
    - 大小写和空格不敏感
    """
    # 快速路径：完全相同
    if student_answer.strip().lower() == expected_answer.strip().lower():
        return True

    # 数值比较
    student_num = parse_numeric(student_answer)
    expected_num = parse_numeric(expected_answer)
    if student_num is not None and expected_num is not None:
        return student_num == expected_num

    # 等价形式集合交集
    student_forms = get_equivalent_forms(student_answer)
    expected_forms = get_equivalent_forms(expected_answer)
    if student_forms & expected_forms:
        return True

    # 最后兜底：标准化字符串比较
    return normalize_answer(student_answer) == normalize_answer(expected_answer)
