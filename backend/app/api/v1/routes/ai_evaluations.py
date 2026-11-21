from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.v1.routes.auth import UserPublic, require_role
from app.core.config import get_settings
from app.database.session import get_db
from app.models.ai_evaluation import (
    AIEvaluation,
    EvaluationFeedback,
    EvaluationJob,
)
from app.models.assignment import Assignment
from app.models.assignment_rubric import AssignmentRubric, RubricQuestion
from app.models.submission import Submission
from app.schemas.ai_evaluation import (
    AIEvaluationResponse,
    AssignmentRubricInput,
    AssignmentRubricResponse,
    EvaluationApprovalInput,
    EvaluationJobResponse,
    EvaluationPublicationResponse,
    EvaluationRejectInput,
    EvaluationReviewSaveInput,
)
from app.services.ai_evaluation_service import submit_evaluation_job
from app.services.assignments import get_teacher_assignment, get_teacher_submission

router = APIRouter()


def _rubric_query(assignment_id: str):
    return (
        select(AssignmentRubric)
        .options(selectinload(AssignmentRubric.questions))
        .where(AssignmentRubric.assignment_id == assignment_id)
    )


@router.get(
    "/assignments/{assignment_id}/rubric",
    response_model=AssignmentRubricResponse,
)
def get_assignment_rubric(
    assignment_id: str,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> AssignmentRubricResponse:
    get_teacher_assignment(db, assignment_id, current_user)
    rubric = db.scalar(_rubric_query(assignment_id))
    if rubric is None:
        raise HTTPException(status_code=404, detail="No answer key or rubric is configured.")
    return rubric


@router.put(
    "/assignments/{assignment_id}/rubric",
    response_model=AssignmentRubricResponse,
)
def save_assignment_rubric(
    assignment_id: str,
    payload: AssignmentRubricInput,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> AssignmentRubricResponse:
    assignment = get_teacher_assignment(db, assignment_id, current_user)
    question_marks = sum((question.max_marks for question in payload.questions), Decimal(0))
    if question_marks > assignment.total_marks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question marks cannot exceed the assignment total.",
        )

    rubric = db.scalar(_rubric_query(assignment_id))
    if rubric is None:
        rubric = AssignmentRubric(
            assignment_id=assignment_id,
            updated_by=current_user.email,
        )
        db.add(rubric)
    rubric.model_answer = payload.model_answer
    rubric.teacher_instructions = payload.teacher_instructions
    rubric.updated_by = current_user.email
    rubric.updated_at = datetime.now(UTC)
    rubric.questions = [
        RubricQuestion(
            question_id=question.question_id,
            position=index,
            prompt=question.prompt,
            max_marks=question.max_marks,
            model_answer=question.model_answer,
            acceptable_answers=question.acceptable_answers,
            criteria=[
                criterion.model_dump(mode="json")
                for criterion in question.criteria
            ],
            partial_credit_rules=question.partial_credit_rules,
        )
        for index, question in enumerate(payload.questions)
    ]
    db.commit()
    return db.scalar(_rubric_query(assignment_id))


def _job_query(job_id: str):
    return (
        select(EvaluationJob)
        .options(
            selectinload(EvaluationJob.extracted_answers),
            selectinload(EvaluationJob.evaluation).selectinload(
                AIEvaluation.question_evaluations
            ),
            selectinload(EvaluationJob.evaluation).selectinload(
                AIEvaluation.feedback_items
            ),
        )
        .where(EvaluationJob.id == job_id)
    )


def _owned_job(
    db: Session,
    job_id: str,
    current_user: UserPublic,
) -> tuple[EvaluationJob, Submission, Assignment]:
    job = db.scalar(_job_query(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Evaluation job not found.")
    submission, assignment = get_teacher_submission(db, job.submission_id, current_user)
    return job, submission, assignment


def _same_instant(first: datetime, second: datetime) -> bool:
    first_utc = first.replace(tzinfo=UTC) if first.tzinfo is None else first.astimezone(UTC)
    second_utc = second.replace(tzinfo=UTC) if second.tzinfo is None else second.astimezone(UTC)
    return first_utc == second_utc


def _same_optional_instant(
    first: datetime | None,
    second: datetime | None,
) -> bool:
    if first is None or second is None:
        return first is second
    return _same_instant(first, second)


def _owned_evaluation(
    db: Session,
    evaluation_id: str,
    current_user: UserPublic,
) -> tuple[AIEvaluation, EvaluationJob, Submission, Assignment]:
    evaluation = db.scalar(
        select(AIEvaluation)
        .options(
            selectinload(AIEvaluation.question_evaluations),
            selectinload(AIEvaluation.feedback_items),
            selectinload(AIEvaluation.job),
        )
        .where(AIEvaluation.id == evaluation_id)
    )
    if evaluation is None:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    job, submission, assignment = _owned_job(db, evaluation.job_id, current_user)
    db.refresh(submission, with_for_update=True)
    return evaluation, job, submission, assignment


def _ensure_current_evaluation(
    db: Session,
    evaluation: AIEvaluation,
    job: EvaluationJob,
    submission: Submission,
    assignment: Assignment,
    *,
    required_review_status: str,
) -> None:
    if job.status != "completed" or evaluation.review_status != required_review_status:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This evaluation is not in the required teacher review state.",
        )
    if not _same_instant(job.source_updated_at, submission.updated_at):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The submission changed after this evaluation; run a new evaluation.",
        )
    current_rubric_updated_at = db.scalar(
        select(AssignmentRubric.updated_at).where(
            AssignmentRubric.assignment_id == assignment.id
        )
    )
    if not _same_optional_instant(job.rubric_updated_at, current_rubric_updated_at):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The rubric changed after this evaluation; run a new evaluation.",
        )


def _append_question_feedback(
    evaluation: AIEvaluation,
    feedback: dict[str, str],
) -> None:
    saved_at = datetime.now(UTC)
    evaluation.feedback_items.extend(
        EvaluationFeedback(
            kind="teacher_question_feedback",
            message=value,
            details={"question_id": question_id},
            created_at=saved_at + timedelta(microseconds=index),
        )
        for index, (question_id, value) in enumerate(feedback.items())
    )


@router.put(
    "/evaluations/{evaluation_id}/review",
    response_model=AIEvaluationResponse,
)
def save_evaluation_review(
    evaluation_id: str,
    payload: EvaluationReviewSaveInput,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> AIEvaluationResponse:
    evaluation, job, submission, assignment = _owned_evaluation(
        db, evaluation_id, current_user
    )
    _ensure_current_evaluation(
        db,
        evaluation,
        job,
        submission,
        assignment,
        required_review_status="pending",
    )

    question_evaluations = {
        question.question_id: question
        for question in evaluation.question_evaluations
    }
    supplied_ids = set(payload.question_marks) | set(payload.question_feedback)
    if supplied_ids - set(question_evaluations):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Review changes include an unknown question.",
        )

    for question_id, marks in payload.question_marks.items():
        question = question_evaluations[question_id]
        if marks is not None and (
            not marks.is_finite() or marks < 0 or marks > question.maximum_marks
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Marks for {question_id} must be finite and within its maximum.",
            )
        question.teacher_marks = marks

    saved_total = sum(
        (
            question.teacher_marks
            for question in question_evaluations.values()
            if question.teacher_marks is not None
        ),
        Decimal(0),
    )
    if saved_total > assignment.total_marks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Saved question marks cannot exceed the assignment total.",
        )

    if payload.teacher_feedback is not None:
        evaluation.teacher_feedback = payload.teacher_feedback or None

    _append_question_feedback(evaluation, payload.question_feedback)
    db.commit()
    db.refresh(evaluation)
    return evaluation


@router.post(
    "/submissions/{submission_id}/evaluations",
    response_model=EvaluationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_evaluation(
    submission_id: str,
    force: bool = Query(default=False),
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> EvaluationJobResponse:
    submission, assignment = get_teacher_submission(db, submission_id, current_user)
    if submission.status == "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Draft submissions cannot be evaluated.",
        )

    current_rubric_updated_at = db.scalar(
        select(AssignmentRubric.updated_at).where(
            AssignmentRubric.assignment_id == assignment.id
        )
    )
    latest = db.scalar(
        select(EvaluationJob)
        .options(
            selectinload(EvaluationJob.extracted_answers),
            selectinload(EvaluationJob.evaluation).selectinload(
                AIEvaluation.question_evaluations
            ),
            selectinload(EvaluationJob.evaluation).selectinload(
                AIEvaluation.feedback_items
            ),
        )
        .where(EvaluationJob.submission_id == submission_id)
        .order_by(EvaluationJob.created_at.desc())
        .limit(1)
    )
    if (
        latest is not None
        and latest.status in {"pending", "processing"}
        and _same_instant(latest.source_updated_at, submission.updated_at)
        and _same_optional_instant(
            latest.rubric_updated_at,
            current_rubric_updated_at,
        )
    ):
        if latest.status == "pending":
            submit_evaluation_job(latest.id)
        return latest
    if latest is not None and latest.status in {"pending", "processing"}:
        if latest.status == "processing":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A previous evaluation is still processing. Retry after it finishes.",
            )
        latest.status = "failed"
        latest.error_summary = "SOURCE_CHANGED"
        latest.completed_at = datetime.now(UTC)
        latest.updated_at = datetime.now(UTC)
        db.commit()
    if (
        latest is not None
        and latest.status == "completed"
        and not force
        and _same_instant(latest.source_updated_at, submission.updated_at)
        and _same_optional_instant(
            latest.rubric_updated_at,
            current_rubric_updated_at,
        )
    ):
        return latest

    settings = get_settings()
    active_jobs = db.scalar(
        select(func.count())
        .select_from(EvaluationJob)
        .where(EvaluationJob.status.in_(("pending", "processing")))
    ) or 0
    if active_jobs >= settings.ai_max_active_jobs:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI evaluation capacity is full. Try again later.",
        )

    job = EvaluationJob(
        submission_id=submission.id,
        requested_by=current_user.email,
        source_updated_at=submission.updated_at,
        rubric_updated_at=current_rubric_updated_at,
        status="pending",
        attempt_count=0,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        active = db.scalar(
            select(EvaluationJob)
            .options(
                selectinload(EvaluationJob.extracted_answers),
                selectinload(EvaluationJob.evaluation).selectinload(
                    AIEvaluation.question_evaluations
                ),
                selectinload(EvaluationJob.evaluation).selectinload(
                    AIEvaluation.feedback_items
                ),
            )
            .where(
                EvaluationJob.submission_id == submission_id,
                EvaluationJob.status.in_(("pending", "processing")),
            )
            .order_by(EvaluationJob.created_at.desc())
            .limit(1)
        )
        if active is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An evaluation job could not be created.",
            )
        return active

    db.refresh(job)
    submit_evaluation_job(job.id)
    return db.scalar(_job_query(job.id))


@router.get(
    "/submissions/{submission_id}/evaluations",
    response_model=EvaluationJobResponse,
)
def get_latest_evaluation(
    submission_id: str,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> EvaluationJobResponse:
    get_teacher_submission(db, submission_id, current_user)
    job_id = db.scalar(
        select(EvaluationJob.id)
        .where(EvaluationJob.submission_id == submission_id)
        .order_by(EvaluationJob.created_at.desc())
        .limit(1)
    )
    if job_id is None:
        raise HTTPException(status_code=404, detail="No evaluation has been requested.")
    job = db.scalar(_job_query(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Evaluation job not found.")
    return job


@router.get(
    "/evaluation-jobs/{job_id}",
    response_model=EvaluationJobResponse,
)
def get_evaluation_job(
    job_id: str,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> EvaluationJobResponse:
    job, _, _ = _owned_job(db, job_id, current_user)
    return job


@router.post(
    "/evaluation-jobs/{job_id}/retry",
    response_model=EvaluationJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_evaluation_job(
    job_id: str,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> EvaluationJobResponse:
    job, submission, assignment = _owned_job(db, job_id, current_user)
    db.refresh(job, with_for_update=True)
    settings = get_settings()
    stale_before = datetime.now(UTC) - timedelta(
        minutes=settings.ai_stale_job_timeout_minutes
    )
    if job.status == "processing":
        updated_at = (
            job.updated_at.replace(tzinfo=UTC)
            if job.updated_at.tzinfo is None
            else job.updated_at.astimezone(UTC)
        )
        if updated_at < stale_before:
            job.status = "failed"
            job.error_summary = "WORKER_TIMEOUT"
    if job.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed or timed-out jobs can be retried.",
        )
    if job.attempt_count >= settings.ai_max_job_attempts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The maximum number of attempts has been reached.",
        )

    job.status = "pending"
    job.error_summary = None
    job.started_at = None
    job.completed_at = None
    job.source_updated_at = submission.updated_at
    job.rubric_updated_at = db.scalar(
        select(AssignmentRubric.updated_at).where(
            AssignmentRubric.assignment_id == assignment.id
        )
    )
    job.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(job)
    submit_evaluation_job(job.id)
    return db.scalar(_job_query(job.id))


@router.post(
    "/evaluations/{evaluation_id}/approve",
    response_model=AIEvaluationResponse,
)
def approve_evaluation(
    evaluation_id: str,
    payload: EvaluationApprovalInput,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> AIEvaluationResponse:
    evaluation, job, submission, assignment = _owned_evaluation(
        db, evaluation_id, current_user
    )
    _ensure_current_evaluation(
        db,
        evaluation,
        job,
        submission,
        assignment,
        required_review_status="pending",
    )
    if not evaluation.question_evaluations or (evaluation.suggested_total is None and not payload.question_marks):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A rubric-based suggestion or complete teacher-entered question marks are required.",
        )
    if payload.marks_obtained > assignment.total_marks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Approved marks cannot exceed the assignment total.",
        )

    question_evaluations = {
        question.question_id: question
        for question in evaluation.question_evaluations
    }
    if set(payload.question_feedback) - set(question_evaluations):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Review changes include an unknown question.",
        )
    if payload.question_marks:
        if set(payload.question_marks) != set(question_evaluations):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provide final marks for every rubric question.",
            )
        question_total = Decimal(0)
        for question_id, marks in payload.question_marks.items():
            question = question_evaluations[question_id]
            if marks > question.maximum_marks:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Marks for {question_id} exceed its maximum.",
                )
            question.teacher_marks = marks
            question_total += marks
        if question_total != payload.marks_obtained:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Question marks must sum to the approved total.",
            )
    else:
        if payload.marks_obtained != evaluation.suggested_total:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Provide edited question marks when changing the suggested total.",
            )
        for question in question_evaluations.values():
            if question.suggested_marks is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Unscored questions require teacher-entered question marks.",
                )
            question.teacher_marks = question.suggested_marks

    now = datetime.now(UTC)
    evaluation.review_status = "approved"
    evaluation.approved_by = current_user.email
    evaluation.approved_at = now
    evaluation.approved_marks = payload.marks_obtained
    evaluation.teacher_feedback = payload.teacher_feedback
    _append_question_feedback(evaluation, payload.question_feedback)
    db.commit()
    db.refresh(evaluation)
    return evaluation


@router.post(
    "/evaluations/{evaluation_id}/publish",
    response_model=EvaluationPublicationResponse,
)
def publish_evaluation_grade(
    evaluation_id: str,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> EvaluationPublicationResponse:
    evaluation, job, submission, assignment = _owned_evaluation(
        db, evaluation_id, current_user
    )
    if (
        evaluation.review_status == "approved"
        and evaluation.approved_marks is not None
        and evaluation.teacher_feedback
        and submission.status == "graded"
        and submission.marks_obtained == evaluation.approved_marks
        and submission.teacher_feedback == evaluation.teacher_feedback
    ):
        return EvaluationPublicationResponse(
            submission_id=submission.id,
            marks_obtained=submission.marks_obtained,
            total_marks=assignment.total_marks,
            status="graded",
        )
    _ensure_current_evaluation(
        db,
        evaluation,
        job,
        submission,
        assignment,
        required_review_status="approved",
    )
    if evaluation.approved_marks is None or not evaluation.teacher_feedback:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The evaluation must be approved with marks and feedback before publication.",
        )
    if submission.status == "graded":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An official grade already exists. Review it before publishing another grade.",
        )

    submission.marks_obtained = evaluation.approved_marks
    submission.teacher_feedback = evaluation.teacher_feedback
    submission.status = "graded"
    submission.graded_at = datetime.now(UTC)
    submission.updated_at = submission.graded_at
    db.commit()
    return EvaluationPublicationResponse(
        submission_id=submission.id,
        marks_obtained=evaluation.approved_marks,
        total_marks=assignment.total_marks,
        status=submission.status,
    )


@router.post(
    "/evaluations/{evaluation_id}/reject",
    response_model=AIEvaluationResponse,
)
def reject_evaluation(
    evaluation_id: str,
    payload: EvaluationRejectInput,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> AIEvaluationResponse:
    evaluation = db.scalar(
        select(AIEvaluation)
        .options(
            selectinload(AIEvaluation.question_evaluations),
            selectinload(AIEvaluation.feedback_items),
            selectinload(AIEvaluation.job),
        )
        .where(AIEvaluation.id == evaluation_id)
    )
    if evaluation is None:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    job, _, _ = _owned_job(db, evaluation.job_id, current_user)
    if job.status != "completed" or evaluation.review_status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This evaluation is not awaiting teacher review.",
        )
    evaluation.review_status = "rejected"
    db.add(
        EvaluationFeedback(
            evaluation_id=evaluation.id,
            kind="teacher_rejection",
            message=payload.reason,
            details={"reviewer": current_user.email},
        )
    )
    db.commit()
    db.refresh(evaluation)
    return evaluation
