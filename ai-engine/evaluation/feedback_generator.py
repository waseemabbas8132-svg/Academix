from __future__ import annotations

from academix_ai.contracts import EvaluationResult, QuestionScore


def question_feedback(score: QuestionScore) -> str:
    if score.needs_review:
        return "Teacher review is recommended before using this suggestion."
    return score.feedback.strip() or score.explanation.strip()


def overall_feedback(
    *,
    has_rubric: bool,
    warnings: tuple[str, ...],
    scores: tuple[QuestionScore, ...],
) -> str:
    if not has_rubric:
        return (
            "Text was extracted for preliminary review only. No teacher answer key or "
            "rubric was configured, so no marks were suggested."
        )
    if warnings or any(score.needs_review for score in scores):
        return (
            "Some answers need manual review. Suggested marks are provisional and must "
            "not be treated as an official grade."
        )
    return (
        "Suggested marks are based on the teacher rubric and quoted answer evidence. "
        "A teacher must review and approve them before release."
    )


def attach_overall_feedback(result: EvaluationResult) -> EvaluationResult:
    return EvaluationResult(
        questions=result.questions,
        suggested_total=result.suggested_total,
        maximum_marks=result.maximum_marks,
        confidence=result.confidence,
        explanation=result.explanation,
        feedback=overall_feedback(
            has_rubric=bool(result.questions),
            warnings=result.warnings,
            scores=result.questions,
        ),
        needs_review=result.needs_review,
        model_name=result.model_name,
        model_version=result.model_version,
        warnings=result.warnings,
        metadata=result.metadata,
    )
