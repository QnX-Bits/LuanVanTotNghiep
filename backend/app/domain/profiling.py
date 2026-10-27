from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PROFILES = ("than_trong", "can_bang", "tang_truong")
PROFILE_LABELS = {
    "than_trong": {"vi": "Thận trọng", "en": "Conservative"},
    "can_bang": {"vi": "Cân bằng", "en": "Balanced"},
    "tang_truong": {"vi": "Tăng trưởng", "en": "Growth"},
}
HORIZONS = ("ngan_han", "trung_han", "dai_han")
HORIZON_LABELS = {
    "ngan_han": {"vi": "Ngắn hạn (dưới 1 năm)", "en": "Short term (under 1 year)"},
    "trung_han": {"vi": "Trung hạn (1–5 năm)", "en": "Medium term (1–5 years)"},
    "dai_han": {"vi": "Dài hạn (trên 5 năm)", "en": "Long term (over 5 years)"},
}
ACK_VERSION = "ack-v1"

TOLERANCE_TEXT = {
    "vi": [
        ["Bán ngay để tránh lỗ thêm", "Giữ nguyên, chờ phục hồi", "Mua thêm vì giá đang rẻ"],
        ["Chỉ gửi tiết kiệm hoặc mua vàng", "Đã đầu tư cổ phiếu hoặc chứng chỉ quỹ dưới 3 năm", "Từ 3 năm trở lên"],
        ["Bảo toàn vốn, chấp nhận lợi nhuận thấp", "Tăng trưởng ổn định, chấp nhận dao động vừa phải", "Tăng trưởng cao, chấp nhận dao động lớn"],
        ["Năm tốt +6 triệu, năm xấu −2 triệu", "Năm tốt +15 triệu, năm xấu −10 triệu", "Năm tốt +25 triệu, năm xấu −20 triệu"],
    ],
    "en": [
        ["Sell immediately", "Hold and wait", "Buy more because prices are lower"],
        ["Only deposits or gold", "Stocks or funds for under 3 years", "3 years or more"],
        ["Preserve capital; accept low returns", "Steady growth; accept moderate swings", "High growth; accept large swings"],
        ["Good year +VND 6m, bad year −VND 2m", "Good year +VND 15m, bad year −VND 10m", "Good year +VND 25m, bad year −VND 20m"],
    ],
}
CAPACITY_TEXT = {
    "vi": [
        ["Chưa có hoặc dưới 3 tháng", "3–6 tháng", "Trên 6 tháng"],
        ["Trên 50%", "20–50%", "Dưới 20%"],
        ["Không ổn định hoặc sắp nghỉ hưu", "Ổn định, đủ chi tiêu", "Ổn định và thường xuyên có dư"],
    ],
    "en": [
        ["None or under 3 months", "3–6 months", "Over 6 months"],
        ["Over 50%", "20–50%", "Under 20%"],
        ["Irregular or near retirement", "Stable and covers expenses", "Stable with regular surplus"],
    ],
}
ACK_TEXT = {
    "vi": "Tôi hiểu mức rủi ro này cao hơn đánh giá của hệ thống và tự chịu trách nhiệm với lựa chọn của mình.",
    "en": "I understand this risk level is higher than the system assessment and accept responsibility for my choice.",
}
WARNING_TEXT = {
    "W1": {"vi": "Bạn sẵn sàng chấp nhận rủi ro cao hơn khả năng tài chính hiện tại cho phép. Hệ thống dùng mức {capacity}.", "en": "Your risk tolerance exceeds your current financial capacity. The system uses {capacity}."},
    "W2": {"vi": "Bạn chưa có quỹ dự phòng tối thiểu 3 tháng chi tiêu. Nên giữ một khoản dự phòng riêng trước khi đầu tư; không dùng tiền chi tiêu cần thiết cho kế hoạch này.", "en": "You do not yet have an emergency fund covering at least 3 months of expenses. Keep a separate reserve before investing; do not use money needed for essential expenses."},
    "W3": {"vi": "Với thời gian dưới 1 năm, mức rủi ro tối đa là Cân bằng.", "en": "For a horizon under 1 year, the maximum risk level is Balanced."},
    "W4": {"vi": "Khoản tiền này chiếm hơn một nửa tài sản tài chính của bạn. Hãy cân nhắc kỹ trước khi chấp nhận dao động lớn.", "en": "This amount represents more than half of your financial assets. Consider carefully before accepting large swings."},
}


@dataclass(frozen=True)
class ProfileAssessment:
    answers: dict[str, Any]
    tolerance_score: int
    capacity_score: int
    tolerance_profile: str
    capacity_profile: str
    horizon: str
    horizon_cap: str
    system_profile: str
    warnings: tuple[str, ...]


def _profile_for_tolerance(score: int) -> str:
    if 4 <= score <= 6:
        return "than_trong"
    if 7 <= score <= 9:
        return "can_bang"
    if 10 <= score <= 12:
        return "tang_truong"
    raise ValueError("T score must be in [4, 12]")


def _profile_for_capacity(score: int) -> str:
    if 3 <= score <= 4:
        return "than_trong"
    if 5 <= score <= 7:
        return "can_bang"
    if 8 <= score <= 9:
        return "tang_truong"
    raise ValueError("C score must be in [3, 9]")


def assess_profile(answers: dict[str, Any]) -> ProfileAssessment:
    required = ("T1", "T2", "T3", "T4", "C1", "C2", "C3", "H")
    missing = [key for key in required if key not in answers]
    if missing:
        raise ValueError(f"Missing questionnaire answers: {', '.join(missing)}")
    scored = {key: int(answers[key]) for key in required[:7]}
    if any(value not in (1, 2, 3) for value in scored.values()):
        raise ValueError("Each scored answer must be 1, 2 or 3")
    horizon = str(answers["H"])
    if horizon not in HORIZONS:
        raise ValueError("Unknown investment horizon")

    tolerance = sum(scored[f"T{i}"] for i in range(1, 5))
    capacity = sum(scored[f"C{i}"] for i in range(1, 4))
    tp = _profile_for_tolerance(tolerance)
    cp = _profile_for_capacity(capacity)
    cap = "can_bang" if horizon == "ngan_han" else "tang_truong"
    system = min((tp, cp, cap), key=PROFILES.index)

    warnings: list[str] = []
    if PROFILES.index(tp) > PROFILES.index(cp):
        warnings.append("W1")
    if scored["C1"] == 1:
        warnings.append("W2")
    if PROFILES.index(cap) < min(PROFILES.index(tp), PROFILES.index(cp)):
        warnings.append("W3")
    if scored["C2"] == 1:
        warnings.append("W4")
    return ProfileAssessment(
        answers={**scored, "H": horizon},
        tolerance_score=tolerance,
        capacity_score=capacity,
        tolerance_profile=tp,
        capacity_profile=cp,
        horizon=horizon,
        horizon_cap=cap,
        system_profile=system,
        warnings=tuple(warnings),
    )


def allowed_choices(assessment: ProfileAssessment) -> list[dict[str, Any]]:
    system_i = PROFILES.index(assessment.system_profile)
    cap_i = PROFILES.index(assessment.horizon_cap)
    out = []
    for idx, profile in enumerate(PROFILES):
        distance = idx - system_i
        enabled = idx <= cap_i and distance <= 1
        out.append({
            "profile": profile,
            "enabled": enabled,
            "requires_ack": enabled and distance == 1,
            "choice_type": "system" if distance == 0 else ("lower" if distance < 0 else "one_level_higher"),
            "reason": None if enabled else ("above_horizon_cap" if idx > cap_i else "more_than_one_level_higher"),
        })
    return out


def validate_profile_choice(assessment: ProfileAssessment, chosen: str, acknowledged: bool = False) -> tuple[str, str | None]:
    if chosen not in PROFILES:
        raise ValueError("Unknown selected profile")
    choice = next(item for item in allowed_choices(assessment) if item["profile"] == chosen)
    if not choice["enabled"]:
        raise ValueError("Selected profile is not suitable for this assessment and horizon")
    if choice["requires_ack"] and not acknowledged:
        raise ValueError("Acknowledgement is required for a profile one level higher")
    ack_version = ACK_VERSION if choice["requires_ack"] and acknowledged else None
    return choice["choice_type"], ack_version
