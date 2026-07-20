def classify_risk(score: float) -> str:
    if score < 50:
        return "high"
    if score < 70:
        return "moderate"
    return "strong"


def average(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0
