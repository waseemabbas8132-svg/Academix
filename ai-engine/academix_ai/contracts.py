from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TextSegment:
    text: str
    page_number: int | None
    source: str
    confidence: float | None = None
    needs_review: bool = False


@dataclass(frozen=True)
class ExtractedDocument:
    segments: tuple[TextSegment, ...]
    warnings: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        return "\n".join(segment.text for segment in self.segments if segment.text.strip())

    @property
    def confidence(self) -> float | None:
        values = [item.confidence for item in self.segments if item.confidence is not None]
        return sum(values) / len(values) if values else None

    @property
    def needs_review(self) -> bool:
        return any(item.needs_review for item in self.segments)


@dataclass(frozen=True)
class QuestionInput:
    question_id: str
    prompt: str
    max_marks: float
    model_answer: str | None = None
    acceptable_answers: tuple[str, ...] = ()
    criteria: tuple[dict[str, object], ...] = ()
    partial_credit_rules: tuple[str, ...] = ()
    assignment_model_answer: str | None = None
    teacher_instructions: str | None = None


@dataclass(frozen=True)
class QuestionScore:
    question_id: str
    suggested_marks: float | None
    max_marks: float
    confidence: float
    explanation: str
    feedback: str
    evidence: tuple[str, ...] = ()
    needs_review: bool = False


@dataclass(frozen=True)
class EvaluationResult:
    questions: tuple[QuestionScore, ...]
    suggested_total: float | None
    maximum_marks: float
    confidence: float
    explanation: str
    feedback: str
    needs_review: bool
    model_name: str
    model_version: str
    warnings: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)
