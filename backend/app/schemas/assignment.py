from datetime import datetime
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class AssignmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    instructions: str = Field(min_length=1, max_length=20000)
    total_marks: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    due_date: AwareDatetime

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("title", "instructions")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class AssignmentUpdate(AssignmentCreate):
    pass


class AssignmentPublish(BaseModel):
    is_published: bool


class FileAttachmentResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    download_url: str


class SubmissionRevisionResponse(BaseModel):
    revision_number: int
    submission_text: str | None
    status: str
    is_late: bool
    submitted_at: datetime | None
    marks_obtained: Decimal | None
    teacher_feedback: str | None
    graded_at: datetime | None
    created_at: datetime
    attachments: list[FileAttachmentResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AssignmentResponse(BaseModel):
    id: str
    class_id: str
    teacher_id: str
    title: str
    instructions: str
    total_marks: Decimal
    due_date: datetime
    is_published: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    attachments: list[FileAttachmentResponse] = Field(default_factory=list)
    submitted_count: int = 0
    pending_count: int = 0
    graded_count: int = 0
    deadline_status: str = "unknown"
    server_now: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class StudentRubricCriterion(BaseModel):
    description: str
    marks: Decimal


class StudentRubricQuestion(BaseModel):
    question_id: str
    prompt: str
    max_marks: Decimal
    criteria: list[StudentRubricCriterion] = Field(default_factory=list)
    partial_credit_rules: list[str] = Field(default_factory=list)


class StudentAssignmentRubricResponse(BaseModel):
    assignment_id: str
    questions: list[StudentRubricQuestion]


class SubmissionCreate(BaseModel):
    submission_text: str | None = Field(default=None, max_length=50000)
    is_draft: bool = False

    model_config = ConfigDict(str_strip_whitespace=True)


class GradeRequest(BaseModel):
    marks_obtained: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=8,
        decimal_places=2,
    )
    teacher_feedback: str | None = Field(default=None, max_length=20000)

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="after")
    def require_grade_or_feedback(self) -> "GradeRequest":
        if self.marks_obtained is None and not self.teacher_feedback:
            raise ValueError("Provide marks, feedback, or both.")
        return self


class SubmissionResponse(BaseModel):
    id: str
    assignment_id: str
    student_id: str
    student_name: str | None = None
    submission_text: str | None
    status: str
    is_late: bool
    submitted_at: datetime | None
    updated_at: datetime
    marks_obtained: Decimal | None
    teacher_feedback: str | None
    graded_at: datetime | None
    attachments: list[FileAttachmentResponse] = Field(default_factory=list)
    revisions: list[SubmissionRevisionResponse] = Field(default_factory=list)
    assignment_title: str | None = None
    total_marks: Decimal | None = None
    due_date: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
