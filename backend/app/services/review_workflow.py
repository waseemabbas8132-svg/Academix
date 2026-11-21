"""Manual review rules. Does not import or execute the AI pipeline."""
import hashlib
import json
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.assignment_rubric import AssignmentRubric
from app.models.submission_review import SubmissionReview


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def deadline_status(due, now=None, offset=0, submission=None):
    now = utc(now or datetime.now(UTC))
    if submission and submission.submitted_at:
        return "submitted_late" if submission.is_late else "submitted_on_time"
    due = utc(due)
    if now > due:
        return "overdue"
    local = timezone(timedelta(minutes=offset))
    return "due_today" if now.astimezone(local).date() == due.astimezone(local).date() else "upcoming"


def question_config(db, assignment):
    rubric = db.scalar(select(AssignmentRubric).options(selectinload(AssignmentRubric.questions))
                       .where(AssignmentRubric.assignment_id == assignment.id))
    questions = [dict(question_id=q.question_id, prompt=q.prompt,
                      max_marks=str(q.max_marks), criteria=q.criteria)
                 for q in rubric.questions] if rubric else [dict(
                     question_id="overall", prompt=assignment.instructions,
                     max_marks=str(assignment.total_marks), criteria=[])]
    configuration = dict(assignment_id=assignment.id, questions=questions, total_marks=str(assignment.total_marks),
                         assignment_updated_at=utc(assignment.updated_at).isoformat(),
                         rubric_updated_at=utc(rubric.updated_at).isoformat() if rubric else None)
    signature = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
    return questions, signature


def latest_review(db, submission_id):
    return db.scalar(select(SubmissionReview).where(SubmissionReview.submission_id == submission_id)
                     .order_by(SubmissionReview.version.desc()).limit(1))


def review_response(review):
    if review is None:
        return None
    return dict(id=review.id, version=review.version, state=review.state,
                source_updated_at=utc(review.source_updated_at), rubric_signature=review.rubric_signature,
                actor=review.actor, created_at=utc(review.created_at), **review.data)


def assert_current(submission, signature, source_updated_at, rubric_signature):
    if utc(submission.updated_at) != utc(source_updated_at) or signature != rubric_signature:
        raise HTTPException(409, "Submission or grading criteria changed. Reload before reviewing.")


def validated_data(payload, configuration, total_max):
    values = {q.question_id: q for q in payload.questions}
    expected = {q['question_id'] for q in configuration}
    if len(values) != len(payload.questions) or set(values) != expected:
        raise HTTPException(422, "Provide each question exactly once; unknown or duplicate questions are invalid.")
    if sum(Decimal(q['max_marks']) for q in configuration) != total_max:
        raise HTTPException(409, "Question maxima must sum to the assignment total. Update the existing rubric first.")
    questions = []
    calculated = Decimal(0)
    complete = True
    for q in configuration:
        value = values[q['question_id']]
        if value.marks is None:
            complete = False
        else:
            if value.marks > Decimal(q['max_marks']):
                raise HTTPException(422, f"Marks exceed maximum for {value.question_id}.")
            calculated += value.marks
        questions.append(dict(**q, marks=str(value.marks) if value.marks is not None else None,
                              feedback=value.feedback))
    if payload.total_override is not None:
        if not payload.override_reason.strip() or payload.total_override > total_max:
            raise HTTPException(422, "A bounded total override requires a justification.")
    if payload.state == "reviewed" and (not complete or not payload.overall_feedback.strip()):
        raise HTTPException(422, "Complete every question mark and overall feedback before marking reviewed.")
    return dict(questions=questions, overall_feedback=payload.overall_feedback,
                calculated_total=str(calculated),
                total_override=str(payload.total_override) if payload.total_override is not None else None,
                override_reason=payload.override_reason,
                total=str(payload.total_override if payload.total_override is not None else calculated),
                complete=complete)
