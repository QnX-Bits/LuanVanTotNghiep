from __future__ import annotations

from typing import Any

from .allocation import ADVISOR_METHOD_LABEL, ASSET_CLASSES, ASSET_LABELS
from .profiling import PROFILE_LABELS, HORIZON_LABELS


def why_sentences(
    assessment: Any,
    chosen_profile: str,
    weights: dict[str, float],
    amount: int,
    annualised_return: float,
    deposit_annualised_return: float,
    locale: str = "vi",
) -> list[str]:
    locale = "en" if locale == "en" else "vi"
    ranked = sorted(ASSET_CLASSES, key=lambda key: (-float(weights[key]), ASSET_CLASSES.index(key)))[:2]
    band = {"than_trong": "10–30%", "can_bang": "40–60%", "tang_truong": "70–90%"}[chosen_profile]
    if locale == "vi":
        sentences = [
            f"Hồ sơ chịu đựng rủi ro {PROFILE_LABELS[assessment.tolerance_profile]['vi']} ({assessment.tolerance_score}/12), khả năng tài chính {PROFILE_LABELS[assessment.capacity_profile]['vi']} ({assessment.capacity_score}/9); hệ thống dùng mức {PROFILE_LABELS[assessment.system_profile]['vi']}.",
            f"Thời gian {HORIZON_LABELS[assessment.horizon]['vi'].lower()} quyết định lịch tái cân bằng và kỳ hạn của phần tiền gửi trong nghiên cứu.",
            f"Dải tài sản rủi ro của profile {PROFILE_LABELS[chosen_profile]['vi']} là {band}; tỷ trọng được đọc từ phiên bản nghiên cứu hiện hành.",
            f"Hai lớp lớn nhất là {ASSET_LABELS[ranked[0]]['vi']} ({weights[ranked[0]]:.2%}) và {ASSET_LABELS[ranked[1]]['vi']} ({weights[ranked[1]]:.2%}).",
            f"{ADVISOR_METHOD_LABEL} được chọn theo cơ sở lý thuyết (cân bằng đóng góp rủi ro, Maillard, Roncalli & Teïletche, 2010), không phải vì có Sharpe backtest cao nhất.",
        ]
        if annualised_return < deposit_annualised_return:
            sentences[-1] += f" Trong giai đoạn kiểm tra, lợi nhuận năm hóa {annualised_return:.2%} thấp hơn tiền gửi 12 tháng {deposit_annualised_return:.2%}."
        else:
            sentences[-1] += f" Trong giai đoạn kiểm tra, lợi nhuận năm hóa của danh mục là {annualised_return:.2%}, so với tiền gửi 12 tháng {deposit_annualised_return:.2%}."
    else:
        sentences = [
            f"Risk tolerance is {PROFILE_LABELS[assessment.tolerance_profile]['en']} ({assessment.tolerance_score}/12); financial capacity is {PROFILE_LABELS[assessment.capacity_profile]['en']} ({assessment.capacity_score}/9). The system uses {PROFILE_LABELS[assessment.system_profile]['en']}.",
            f"The {HORIZON_LABELS[assessment.horizon]['en'].lower()} horizon sets the rebalancing schedule and the deposit tenor used in the study.",
            f"The {PROFILE_LABELS[chosen_profile]['en']} risk-asset band is {band}; weights come from the active research version.",
            f"The two largest classes are {ASSET_LABELS[ranked[0]]['en']} ({weights[ranked[0]]:.2%}) and {ASSET_LABELS[ranked[1]]['en']} ({weights[ranked[1]]:.2%}).",
            f"{ADVISOR_METHOD_LABEL} is selected on theoretical grounds (equal risk contributions, Maillard, Roncalli & Teïletche, 2010), not because it has the highest backtest Sharpe ratio.",
        ]
        if annualised_return < deposit_annualised_return:
            sentences[-1] += f" Over the test period, annualised return was {annualised_return:.2%}, below 12-month deposits at {deposit_annualised_return:.2%}."
        else:
            sentences[-1] += f" Over the test period, the portfolio returned {annualised_return:.2%} annualised versus {deposit_annualised_return:.2%} for 12-month deposits."
    return sentences
