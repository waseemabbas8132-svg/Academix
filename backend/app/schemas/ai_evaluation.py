from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RubricCriterion(BaseModel):
    description: str = Field(min_length=1, max_length=1000)
    marks: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    concepts: list[str] = Field(default_factory=list, max_length=30)


class RubricQuestionInput(BaseModel):
    question_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    prompt: str = Field(min_length=1, max_length=4000)
    max_marks: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    model_answer: str | None = Field(default=None, max_length=10000)
    acceptable_answers: list[str] = Field(default_factory=list, max_length=20)
    criteria: list[RubricCriterion] = Field(default_factory=list, max_length=30)
    partial_credit_rules: list[str] = Field(default_factory=list, max_length=30)


class AssignmentRubricInput(BaseModel):
    model_answer: str | None = Field(default=None, max_length=30000)
    teacher_instructions: str | None = Field(default=None, max_length=10000)
    questions: list[RubricQuestionInput] = Field(min_length=1, max_length=50)

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("model_answer", "teacher_instructions")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def validate_questions(self) -> "AssignmentRubricInput":
        ids = [question.question_id.casefold() for question in self.questions]
        if len(set(ids)) != len(ids):
            raise ValueError("Question IDs must be unique.")
        for question in self.questions:
            criteria_total = sum((criterion.marks for criterion in question.criteria), Decimal(0))
            if criteria_total > question.max_marks:
                raise ValueError(
                    f"Criteria marks for {question.question_id} exceed its maximum."
                )
        return self


class RubricQuestionResponse(RubricQuestionInput):
    model_config = ConfigDict(from_attributes=True)


class AssignmentRubricResponse(BaseModel):
    id: str
    assignment_id: str
    model_answer: str | None
    teacher_instructions: str | None
    questions: list[RubricQuestionResponse]
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExtractedAnswerResponse(BaseModel):
    segment_number: int
    page_number: int | None
    text: str
    source: str
    ocr_confidence: float | None
    needs_review: bool

    model_config = ConfigDict(from_attributes=True)


class QuestionEvaluationResponse(BaseModel):
    question_id: str
    suggested_marks: Decimal | None
    teacher_marks: Decimal | None
    maximum_marks: Decimal
    confidence: float
    explanation: str
    feedback: str
    evidence: list[str]
    needs_review: bool

    model_config = ConfigDict(from_attributes=True)


class EvaluationFeedbackResponse(BaseModel):
    kind: str
    message: str
    similarity_score: float | None
    other_submission_id: str | None
    details: dict[str, object]

    model_config = ConfigDict(from_attributes=True)


class AIEvaluationResponse(BaseModel):
    id: str
    suggested_total: Decimal | None
    maximum_marks: Decimal
    confidence: float
    explanation: str
    feedback: str
    model_name: str
    model_version: str
    review_status: str
    approved_marks: Decimal | None
    teacher_feedback: str | None
    approved_at: datetime | None
    question_evaluations: list[QuestionEvaluationResponse]
    feedback_items: list[EvaluationFeedbackResponse]

    model_config = ConfigDict(from_attributes=True)


class EvaluationJobResponse(BaseModel):
    id: str
    submission_id: str
    status: str
    attempt_count: int
    error_summary: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    extracted_answers: list[ExtractedAnswerResponse]
    evaluation: AIEvaluationResponse | None

    model_config = ConfigDict(from_attributes=True)


class EvaluationApprovalInput(BaseModel):
    marks_obtained: Decimal = Field(ge=0, max_digits=8, decimal_places=2)
    teacher_feedback: str = Field(min_length=1, max_length=20000)
    question_marks: dict[str, Annotated[Decimal, Field(ge=0, max_digits=8, decimal_places=2)]] = Field(default_factory=dict)
    question_feedback: dict[str, Annotated[str, Field(max_length=5000)]] = Field(
        default_factory=dict,
    )

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("teacher_feedback")
    @classmethod
    def reject_blank_feedback(cls, value: str) -> str:
        if not value:
            raise ValueError("Provide teacher feedback before approving.")
        return value

    @field_validator("question_marks")
    @classmethod
    def validate_question_marks(
        cls,
        values: dict[str, Decimal],
    ) -> dict[str, Decimal]:
        if any(value < 0 for value in values.values()):
            raise ValueError("Question marks cannot be negative.")
        return values


class EvaluationReviewSaveInput(BaseModel):
    teacher_feedback: str | None = Field(default=None, max_length=20000)
    question_marks: dict[
        str, Annotated[Decimal, Field(ge=0, max_digits=8, decimal_places=2)] | None
    ] = Field(default_factory=dict)
    question_feedback: dict[str, Annotated[str, Field(max_length=5000)]] = Field(
        default_factory=dict,
    )

    model_config = ConfigDict(str_strip_whitespace=True)


class EvaluationRejectInput(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)

    model_config = ConfigDict(str_strip_whitespace=True)


class EvaluationPublicationResponse(BaseModel):
    submission_id: str
    marks_obtained: Decimal
    total_marks: Decimal
    status: str


class EvaluationRetryResponse(BaseModel):
    job: EvaluationJobResponse
    message: str
