from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    passcode: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=32)


class ProfileRequest(BaseModel):
    answers: dict[str, int | str]
    locale: str | None = None
    chosen_profile: str | None = None
    acknowledged: bool = False
    amount_vnd: int | None = Field(default=None, ge=1_000_000, le=100_000_000_000)


class ArticleRequest(BaseModel):
    kind: str
    title: dict[str, str]
    summary: dict[str, str]
    body: dict[str, str]
    tags: list[str] = []
    source_name: str | None = None
    source_url: str | None = None
    source_published_at: str | None = None


class RunRequest(BaseModel):
    # δ (hệ số ngại rủi ro) của Markowitz/BL: 1,5 / 2,5 / 4. Thay cho "sàn vol tiền gửi" đã bỏ (QC 9).
    delta: float = Field(default=2.5, ge=1.0, le=5.0)
    # None = vector phí theo lớp (mặc định); có giá trị = phí đồng nhất cho mọi lớp
    transaction_cost: float | None = Field(default=None, ge=0, le=0.005)
    note: str = Field(default="", max_length=1000)


class ExecutionRulesRequest(BaseModel):
    rules: dict
