from typing import Literal
from decimal import Decimal
from pydantic import AwareDatetime, BaseModel, Field


class QuestionMark(BaseModel):
    question_id: str = Field(min_length=1, max_length=64)
    marks: Decimal | None = Field(default=None, ge=0, max_digits=8, decimal_places=2)
    feedback: str = Field(default="", max_length=5000)


class ReviewSave(BaseModel):
    expected_version: int = Field(ge=0)
    source_updated_at: AwareDatetime
    rubric_signature: str = Field(min_length=64, max_length=64)
    state: Literal['draft', 'reviewed'] = 'draft'
    questions: list[QuestionMark] = Field(max_length=100)
    overall_feedback: str = Field(default="", max_length=20000)
    total_override: Decimal | None = Field(default=None, ge=0, max_digits=8, decimal_places=2)
    override_reason: str = Field(default="", max_length=5000)


class ReviewAction(BaseModel):
    expected_version: int = Field(ge=0)
    source_updated_at: AwareDatetime
    rubric_signature: str = Field(min_length=64, max_length=64)
    reason: str = Field(default="", max_length=20000)
