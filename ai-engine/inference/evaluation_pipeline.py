from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import math

from academix_ai.contracts import (
    EvaluationResult,
    ExtractedDocument,
    QuestionInput,
    QuestionScore,
)
from evaluation.answer_evaluator import OllamaAnswerEvaluator, mark_decimal, segment_answers, validate_question
from evaluation.feedback_generator import overall_feedback
from preprocessing.handwritten_ocr import (
    HandwritingRecognizer,
    TrOCRHandwritingRecognizer,
)
from preprocessing.text_extractor import extract_submission


@dataclass(frozen=True)
class EvaluationRequest:
    submission_id: str
    submission_text: str | None
    files: list[tuple[str, bytes]]
    questions: tuple[QuestionInput, ...]
    assignment_total_marks: float


class EvaluationPipeline:
    def __init__(
        self,
        *,
        recognizer: HandwritingRecognizer | None = None,
        evaluator: OllamaAnswerEvaluator | None = None,
        max_pages: int = 30,
        max_total_bytes: int = 30 * 1024 * 1024,
        low_confidence_threshold: float = 0.6,
    ) -> None:
        self.recognizer = recognizer or TrOCRHandwritingRecognizer()
        self.evaluator = evaluator or OllamaAnswerEvaluator()
        self.max_pages = max_pages
        self.max_total_bytes = max_total_bytes
        self.low_confidence_threshold = low_confidence_threshold

    def extract(self, request: EvaluationRequest) -> ExtractedDocument:
        return extract_submission(
            request.submission_text,
            request.files,
            self.recognizer,
            max_pages=self.max_pages,
            max_total_bytes=self.max_total_bytes,
            low_confidence_threshold=self.low_confidence_threshold,
        )

    def evaluate(
        self,
        request: EvaluationRequest,
        extracted: ExtractedDocument | None = None,
    ) -> EvaluationResult:
        document = extracted or self.extract(request)
        questions = request.questions
        maximum_marks = sum(question.max_marks for question in questions)
        assignment_maximum = mark_decimal(request.assignment_total_marks)
        maxima = [validate_question(question)[0] for question in questions]
        maximum_marks = float(sum(maxima, Decimal(0)))
        if len({q.question_id.casefold() for q in questions}) != len(questions):
            raise ValueError('Question IDs must be unique.')
        if sum(maxima, Decimal(0)) > assignment_maximum:
            raise ValueError('Rubric question maxima exceed the assignment total.')
        model_name = getattr(self.evaluator, "model_name", "none")
        model_version = getattr(self.evaluator, "model_version", "none")

        if not questions:
            warning = (
                "No teacher answer key or rubric is configured; marks were not generated.",
            )
            warnings = document.warnings + warning
            return EvaluationResult(
                questions=(),
                suggested_total=None,
                maximum_marks=request.assignment_total_marks,
                confidence=document.confidence or 0,
                explanation="Only document extraction was performed.",
                feedback=overall_feedback(
                    has_rubric=False,
                    warnings=warnings,
                    scores=(),
                ),
                needs_review=True,
                model_name=getattr(self.recognizer, "model_name", "none"),
                model_version=getattr(self.recognizer, "model_version", "none"),
                warnings=warnings,
                metadata={"preliminary_only": True},
            )

        segmented, segmentation_failed = segment_answers(document.text, questions)
        scores: list[QuestionScore] = []
        extraction_unreliable = document.needs_review
        no_text = not document.text.strip()
        for question in questions:
            answer = segmented.get(question.question_id)
            if extraction_unreliable or no_text or segmentation_failed or answer is None:
                reason = ('EXTRACTION_UNCERTAIN: extracted material needs checking against the original.'
                          if extraction_unreliable else
                          'NO_EXTRACTED_TEXT: missing text does not establish that the student omitted an answer.'
                          if no_text else
                          'ANSWER_UNMAPPED: a response could not be reliably associated with this question.')
                scores.append(
                    QuestionScore(
                        question_id=question.question_id,
                        suggested_marks=None,
                        max_marks=question.max_marks,
                        confidence=0,
                        explanation=reason,
                        feedback="Please identify and review this answer manually.",
                        needs_review=True,
                    )
                )
                continue
            score = self.evaluator.evaluate(question, answer)
            if score.question_id != question.question_id or mark_decimal(score.max_marks) != mark_decimal(question.max_marks):
                raise ValueError('Evaluator returned a mismatched question or maximum.')
            if (not isinstance(score.confidence, (int, float)) or not math.isfinite(score.confidence) or not 0 <= score.confidence <= 1
                    or isinstance(score.confidence, bool)):
                raise ValueError('Evaluator returned an invalid uncertainty signal.')
            if score.suggested_marks is not None and mark_decimal(score.suggested_marks) > mark_decimal(question.max_marks):
                raise ValueError('Evaluator exceeded the question maximum.')
            scores.append(score)

        score_tuple = tuple(scores)
        all_scored = all(score.suggested_marks is not None for score in score_tuple)
        suggested_total = (
            float(sum((mark_decimal(score.suggested_marks) for score in score_tuple), Decimal(0)))
            if all_scored
            else None
        )
        if suggested_total is not None and suggested_total > request.assignment_total_marks:
            suggested_total = None
            score_tuple = tuple(
                QuestionScore(
                    question_id=score.question_id,
                    suggested_marks=None,
                    max_marks=score.max_marks,
                    confidence=0,
                    explanation="Rubric maximum exceeded the assignment total.",
                    feedback="Teacher review is required before marks can be suggested.",
                    evidence=score.evidence,
                    needs_review=True,
                )
                for score in score_tuple
            )

        confidence_values = [score.confidence for score in score_tuple]
        if document.confidence is not None:
            confidence_values.append(document.confidence)
        confidence = min(confidence_values, default=0)
        warnings = list(document.warnings)
        if segmentation_failed:
            warnings.append(
                "Question headings were not detected; answers were not assigned automatically."
            )
        if any(segment.needs_review for segment in document.segments):
            warnings.append("EXTRACTION_REVIEW_REQUIRED: uncertain or incomplete text was not sent for automatic marking.")
        if no_text:
            warnings.append('NO_EXTRACTED_TEXT: no automatic zero has been assigned.')
        needs_review = (
            segmentation_failed
            or document.needs_review
            or any(score.needs_review or score.suggested_marks is None for score in score_tuple)
        )
        warnings_tuple = tuple(dict.fromkeys(warnings))
        explanation = (
            "Marks are provisional and grounded in validated answer quotations."
            if all_scored
            else "One or more answers could not be scored reliably."
        )
        return EvaluationResult(
            questions=score_tuple,
            suggested_total=suggested_total,
            maximum_marks=maximum_marks,
            confidence=confidence,
            explanation=explanation,
            feedback=overall_feedback(
                has_rubric=True,
                warnings=warnings_tuple,
                scores=score_tuple,
            ),
            needs_review=needs_review,
            model_name=model_name,
            model_version=model_version,
            warnings=warnings_tuple,
            metadata={"preliminary_only": False, "confidence_calibrated": False,
                      "extraction_abstained": extraction_unreliable or no_text},
        )
