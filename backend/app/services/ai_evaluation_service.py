from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import lru_cache

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.database.session import SessionLocal
from app.models.ai_evaluation import (
    AIEvaluation,
    EvaluationFeedback,
    EvaluationJob,
    ExtractedAnswer,
    QuestionEvaluation,
)
from app.models.assignment import Assignment
from app.models.assignment_rubric import AssignmentRubric
from app.models.submission import Submission
from app.services.file_storage import get_file_storage

logger = logging.getLogger(__name__)
settings = get_settings()
_executor = ThreadPoolExecutor(
    max_workers=settings.ai_max_concurrent_jobs,
    thread_name_prefix="academix-evaluation",
)
_processing_limit = threading.BoundedSemaphore(settings.ai_max_concurrent_jobs)


@lru_cache(maxsize=1)
def create_pipeline():
    from academix_ai.evaluation_pipeline import EvaluationPipeline
    from evaluation.answer_evaluator import OllamaAnswerEvaluator
    from preprocessing.handwritten_ocr import TrOCRHandwritingRecognizer

    return EvaluationPipeline(
        recognizer=TrOCRHandwritingRecognizer(
            settings.ai_ocr_model,
            local_files_only=settings.ai_ocr_local_files_only,
        ),
        evaluator=OllamaAnswerEvaluator(
            base_url=settings.ai_ollama_base_url,
            model_name=settings.ai_ollama_model,
            timeout_seconds=settings.ai_model_timeout_seconds,
        ),
        max_pages=settings.ai_processing_max_pages,
        max_total_bytes=settings.ai_processing_max_bytes,
        low_confidence_threshold=settings.ai_ocr_low_confidence_threshold,
    )


def submit_evaluation_job(job_id: str) -> Future[None]:
    return _executor.submit(process_evaluation_job, job_id)


def _snapshot_job(job_id: str):
    with SessionLocal() as db:
        job = db.scalar(
            select(EvaluationJob)
            .options(selectinload(EvaluationJob.extracted_answers))
            .where(EvaluationJob.id == job_id)
        )
        if job is None or job.status != "pending":
            return None

        claimed = db.execute(
            update(EvaluationJob)
            .where(
                EvaluationJob.id == job_id,
                EvaluationJob.status == "pending",
            )
            .values(
                status="processing",
                started_at=datetime.now(UTC),
                completed_at=None,
                error_summary=None,
                attempt_count=EvaluationJob.attempt_count + 1,
                updated_at=datetime.now(UTC),
            )
        )
        if claimed.rowcount != 1:
            db.rollback()
            return None
        db.commit()

        submission = db.scalar(
            select(Submission)
            .options(selectinload(Submission.attachments))
            .where(Submission.id == job.submission_id)
        )
        if submission is None:
            job.status = "failed"
            job.error_summary = "SUBMISSION_NOT_FOUND"
            job.completed_at = datetime.now(UTC)
            job.updated_at = datetime.now(UTC)
            db.commit()
            return None
        if _to_utc(job.source_updated_at) != _to_utc(submission.updated_at):
            job.status = "failed"
            job.error_summary = "SUBMISSION_CHANGED"
            job.completed_at = datetime.now(UTC)
            job.updated_at = datetime.now(UTC)
            db.commit()
            return None
        assignment = db.get(Assignment, submission.assignment_id)
        if assignment is None:
            job.status = "failed"
            job.error_summary = "ASSIGNMENT_NOT_FOUND"
            job.completed_at = datetime.now(UTC)
            job.updated_at = datetime.now(UTC)
            db.commit()
            return None
        rubric = db.scalar(
            select(AssignmentRubric)
            .options(selectinload(AssignmentRubric.questions))
            .where(AssignmentRubric.assignment_id == assignment.id)
        )
        if not _same_optional_instant(
            job.rubric_updated_at,
            rubric.updated_at if rubric is not None else None,
        ):
            job.status = "failed"
            job.error_summary = "RUBRIC_CHANGED"
            job.completed_at = datetime.now(UTC)
            job.updated_at = datetime.now(UTC)
            db.commit()
            return None
        attachments = [
            (item.original_filename, item.storage_key)
            for item in submission.attachments
        ]
        return {
            "attempt_count": job.attempt_count,
            "submission_id": submission.id,
            "source_updated_at": submission.updated_at,
            "submission_text": submission.submission_text,
            "assignment_id": assignment.id,
            "assignment_total_marks": float(assignment.total_marks),
            "assignment_model_answer": rubric.model_answer if rubric else None,
            "teacher_instructions": rubric.teacher_instructions if rubric else None,
            "questions": list(rubric.questions) if rubric else [],
            "attachments": attachments,
        }


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _same_optional_instant(
    first: datetime | None,
    second: datetime | None,
) -> bool:
    if first is None or second is None:
        return first is second
    return _to_utc(first) == _to_utc(second)


def _failure_summary(error: Exception) -> str:
    from evaluation.answer_evaluator import EvaluationUnavailable
    from preprocessing.handwritten_ocr import OCRUnavailable
    from preprocessing.text_extractor import DocumentRejected

    if isinstance(error, OCRUnavailable):
        return "OCR_MODEL_UNAVAILABLE"
    if isinstance(error, EvaluationUnavailable):
        return "LOCAL_EVALUATION_MODEL_UNAVAILABLE"
    if isinstance(error, DocumentRejected):
        return str(error)[:500]
    return "PROCESSING_FAILED"


def _compare_with_peers(
    db: Session,
    *,
    assignment_id: str,
    submission_id: str,
    current_text: str,
) -> list[EvaluationFeedback]:
    from evaluation.similarity_checker import compare_answers

    rows = db.execute(
        select(
            EvaluationJob.submission_id,
            ExtractedAnswer.text,
        )
        .join(Submission, Submission.id == EvaluationJob.submission_id)
        .join(ExtractedAnswer, ExtractedAnswer.job_id == EvaluationJob.id)
        .where(
            Submission.assignment_id == assignment_id,
            EvaluationJob.submission_id != submission_id,
            EvaluationJob.status == "completed",
        )
        .order_by(EvaluationJob.completed_at.desc())
        .limit(settings.ai_similarity_max_segments)
    ).all()
    peer_texts: dict[str, list[str]] = {}
    for peer_id, text in rows:
        if peer_id not in peer_texts and len(peer_texts) >= settings.ai_similarity_max_peers:
            continue
        peer_texts.setdefault(peer_id, []).append(text)
    peers = [
        (peer_id, "\n".join(parts)[:20000])
        for peer_id, parts in peer_texts.items()
    ]

    findings = compare_answers(
        submission_id,
        current_text[:20000],
        peers,
        max_tokens=settings.ai_similarity_max_tokens,
    )
    return [
        EvaluationFeedback(
            kind="similarity_signal",
            message=(
                "Potentially similar wording was found in another submission. "
                "This is an investigation signal, not proof of misconduct."
            ),
            similarity_score=match.score,
            other_submission_id=match.other_submission_id,
            details={"matching_segments": list(match.matching_segments)},
        )
        for match in findings
    ]


def process_evaluation_job(job_id: str) -> None:
    with _processing_limit:
        snapshot = None
        try:
            snapshot = _snapshot_job(job_id)
            if snapshot is None:
                return

            storage = get_file_storage()
            files = [
                (filename, storage.resolve(storage_key).read_bytes())
                for filename, storage_key in snapshot["attachments"]
            ]

            from academix_ai.contracts import QuestionInput
            from inference.evaluation_pipeline import EvaluationRequest

            questions = tuple(
                QuestionInput(
                    question_id=question.question_id,
                    prompt=question.prompt,
                    max_marks=float(question.max_marks),
                    model_answer=question.model_answer,
                    acceptable_answers=tuple(question.acceptable_answers or ()),
                    criteria=tuple(question.criteria or ()),
                    partial_credit_rules=tuple(question.partial_credit_rules or ()),
                    assignment_model_answer=snapshot["assignment_model_answer"],
                    teacher_instructions=snapshot["teacher_instructions"],
                )
                for question in snapshot["questions"]
            )
            request = EvaluationRequest(
                submission_id=snapshot["submission_id"],
                submission_text=snapshot["submission_text"],
                files=files,
                questions=questions,
                assignment_total_marks=snapshot["assignment_total_marks"],
            )
            pipeline = create_pipeline()
            extracted = pipeline.extract(request)
            result = pipeline.evaluate(request, extracted)

            with SessionLocal() as db:
                job = db.get(EvaluationJob, job_id, with_for_update=True)
                if (job is None or job.status != "processing"
                        or job.attempt_count != snapshot['attempt_count']):
                    return
                current_submission = db.get(Submission, snapshot["submission_id"])
                if (
                    current_submission is None
                    or _to_utc(current_submission.updated_at)
                    != _to_utc(snapshot["source_updated_at"])
                ):
                    job.status = "failed"
                    job.error_summary = "SUBMISSION_CHANGED"
                    job.completed_at = datetime.now(UTC)
                    job.updated_at = datetime.now(UTC)
                    db.commit()
                    return
                current_rubric_updated_at = db.scalar(
                    select(AssignmentRubric.updated_at).where(
                        AssignmentRubric.assignment_id == snapshot["assignment_id"]
                    )
                )
                if not _same_optional_instant(
                    job.rubric_updated_at,
                    current_rubric_updated_at,
                ):
                    job.status = "failed"
                    job.error_summary = "RUBRIC_CHANGED"
                    job.completed_at = datetime.now(UTC)
                    job.updated_at = datetime.now(UTC)
                    db.commit()
                    return
                evaluation = AIEvaluation(
                    job_id=job_id,
                    suggested_total=(
                        Decimal(str(result.suggested_total))
                        if result.suggested_total is not None
                        else None
                    ),
                    maximum_marks=Decimal(str(result.maximum_marks)),
                    confidence=result.confidence,
                    explanation=result.explanation[:10000],
                    feedback=result.feedback[:10000],
                    model_name=result.model_name[:255],
                    model_version=result.model_version[:255],
                    review_status="pending",
                )
                db.add(evaluation)
                db.flush()
                db.add_all(
                    ExtractedAnswer(
                        job_id=job_id,
                        segment_number=index,
                        page_number=segment.page_number,
                        text=segment.text,
                        source=segment.source,
                        ocr_confidence=segment.confidence,
                        needs_review=segment.needs_review,
                    )
                    for index, segment in enumerate(extracted.segments)
                )
                db.add_all(
                    QuestionEvaluation(
                        evaluation_id=evaluation.id,
                        question_id=score.question_id,
                        suggested_marks=(
                            Decimal(str(score.suggested_marks))
                            if score.suggested_marks is not None
                            else None
                        ),
                        maximum_marks=Decimal(str(score.max_marks)),
                        confidence=score.confidence,
                        explanation=score.explanation[:10000],
                        feedback=score.feedback[:10000],
                        evidence=list(score.evidence),
                        needs_review=score.needs_review,
                    )
                    for score in result.questions
                )
                db.add_all(
                    EvaluationFeedback(
                        evaluation_id=evaluation.id,
                        kind="processing_warning",
                        message=warning[:2000],
                        details={},
                    )
                    for warning in result.warnings
                )
                peer_feedback = _compare_with_peers(
                    db,
                    assignment_id=snapshot["assignment_id"],
                    submission_id=snapshot["submission_id"],
                    current_text=extracted.text,
                )
                for finding in peer_feedback:
                    finding.evaluation_id = evaluation.id
                db.add_all(peer_feedback)
                job.status = "completed"
                job.completed_at = datetime.now(UTC)
                job.updated_at = datetime.now(UTC)
                db.commit()
        except Exception as error:
            logger.exception("AI evaluation job %s failed.", job_id)
            with SessionLocal() as db:
                job = db.get(EvaluationJob, job_id, with_for_update=True)
                if (job is not None and job.status == "processing" and snapshot is not None
                        and job.attempt_count == snapshot['attempt_count']):
                    job.status = "failed"
                    job.error_summary = _failure_summary(error)
                    job.completed_at = datetime.now(UTC)
                    job.updated_at = datetime.now(UTC)
                    db.commit()


def recover_pending_evaluation_jobs() -> None:
    """Requeue persisted pending work and fail jobs stranded by a process exit."""
    stale_before = datetime.now(UTC) - timedelta(
        minutes=settings.ai_stale_job_timeout_minutes
    )
    with SessionLocal() as db:
        stale = list(
            db.scalars(
                select(EvaluationJob).where(
                    EvaluationJob.status == "processing",
                    EvaluationJob.updated_at < stale_before,
                )
            ).all()
        )
        for job in stale:
            job.status = "failed"
            job.error_summary = "WORKER_RESTARTED"
            job.completed_at = datetime.now(UTC)
        pending = list(
            db.scalars(
                select(EvaluationJob.id).where(EvaluationJob.status == "pending")
            ).all()
        )
        db.commit()
    for job_id in pending:
        submit_evaluation_job(job_id)


def create_job_snapshot(
    db: Session,
    *,
    submission: Submission,
    teacher_email: str,
) -> EvaluationJob:
    assignment = db.get(Assignment, submission.assignment_id)
    if assignment is None:
        raise ValueError("Submission assignment no longer exists.")
    rubric_updated_at = db.scalar(
        select(AssignmentRubric.updated_at).where(
            AssignmentRubric.assignment_id == assignment.id
        )
    )
    job = EvaluationJob(
        submission_id=submission.id,
        requested_by=teacher_email,
        source_updated_at=submission.updated_at,
        rubric_updated_at=rubric_updated_at,
        status="pending",
        attempt_count=0,
    )
    db.add(job)
    return job
