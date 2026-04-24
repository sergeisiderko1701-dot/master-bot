from dataclasses import dataclass

from validators import is_valid_ua_phone


MIN_PROBLEM_LEN = 10
RECENT_ORDERS_HARD_LIMIT = 2


@dataclass
class AntiFakeDecision:
    is_suspect: bool
    score: int
    reasons: list[str]


def normalize_problem_for_compare(problem: str) -> str:
    text = " ".join(str(problem or "").strip().lower().split())
    return text[:300]


def evaluate_order_antifake(
    *,
    problem: str,
    phone: str,
    recent_orders_count: int,
    duplicate_problem: bool,
    has_media: bool,
) -> AntiFakeDecision:
    reasons: list[str] = []
    score = 0

    normalized_problem = normalize_problem_for_compare(problem)

    if len(normalized_problem) < MIN_PROBLEM_LEN:
        score += 2
        reasons.append("Опис проблеми коротший за 10 символів")

    if not is_valid_ua_phone(phone):
        score += 2
        reasons.append("Телефон схожий на некоректний")

    if recent_orders_count >= RECENT_ORDERS_HARD_LIMIT:
        score += 2
        reasons.append("Користувач створив кілька заявок за короткий час")

    if duplicate_problem:
        score += 1
        reasons.append("Схожий текст заявки вже був раніше")

    if not has_media and len(normalized_problem) < 20:
        score += 1
        reasons.append("Дуже слабкий опис без фото/відео")

    return AntiFakeDecision(
        is_suspect=score >= 2,
        score=score,
        reasons=reasons,
    )
