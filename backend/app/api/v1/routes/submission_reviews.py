from datetime import UTC, datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.routes.auth import UserPublic, _current_user_from_token, require_role
from app.database.session import get_db
from app.models.submission import Submission
from app.models.submission_review import SubmissionReview
from app.models.assignment import Assignment
from app.models.assignment_rubric import AssignmentRubric
from app.models.classroom import ClassMembership
from app.schemas.submission_review import ReviewAction, ReviewSave
from app.services.assignments import get_teacher_assignment, get_teacher_submission, get_student_submission
from app.services.review_workflow import (assert_current, latest_review, question_config,
                                        review_response, validated_data, utc)

router = APIRouter()


@router.get('/submissions/{submission_id}')
def get_teacher_work(submission_id: str, user: UserPublic = Depends(require_role('teacher')),
                     db: Session = Depends(get_db)):
    from app.api.v1.routes.assignments import _submission_response
    submission, assignment = get_teacher_submission(db,submission_id,user)
    return _submission_response(
        submission,
        assignment,
        include_student_name=True,
    )


def context(db, submission_id, user):
    # PostgreSQL serializes review actions, legacy grading and student revisions on
    # this same source row. Unique history versions also reject colliding saves.
    db.execute(select(Submission.id).where(Submission.id == submission_id).with_for_update())
    submission, assignment = get_teacher_submission(db, submission_id, user)
    if submission.status == 'draft':
        raise HTTPException(409, 'Student drafts cannot be reviewed.')
    db.execute(select(Assignment.id).where(Assignment.id==assignment.id).with_for_update())
    db.execute(select(AssignmentRubric.id).where(AssignmentRubric.assignment_id==assignment.id).with_for_update())
    questions, signature = question_config(db, assignment)
    return submission, assignment, questions, signature, latest_review(db, submission_id)


def check_version(latest, version):
    if (latest.version if latest else 0) != version:
        raise HTTPException(409, 'A newer review exists. Reload before saving.')


def commit(db, review):
    db.add(review)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, 'Concurrent review update. Reload before saving.') from error
    db.refresh(review)
    return review_response(review)


@router.get('/submissions/{submission_id}/review')
def get_review(submission_id: str, user: UserPublic = Depends(require_role('teacher')),
               db: Session = Depends(get_db)):
    submission, assignment = get_teacher_submission(db, submission_id, user)
    questions, signature = question_config(db, assignment)
    latest = latest_review(db, submission_id)
    return dict(submission_id=submission.id, source_updated_at=utc(submission.updated_at),
                source_text=submission.submission_text,
                source_files=[dict(id=f.id,filename=f.original_filename,content_type=f.content_type,
                    size_bytes=f.size_bytes,download_url=f'/api/v1/files/{f.id}') for f in submission.attachments],
                rubric_signature=signature, questions=questions, total_marks=assignment.total_marks,
                source_revision=len(submission.revisions) + 1, official_marks=submission.marks_obtained,
                official_feedback=submission.teacher_feedback, official_status=submission.status,
                latest=review_response(latest),
                stale=bool(latest and (utc(latest.source_updated_at) != utc(submission.updated_at)
                                      or latest.rubric_signature != signature)))


@router.get('/submissions/{submission_id}/review/history')
def history(submission_id: str, offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
            user: UserPublic = Depends(require_role('teacher')), db: Session = Depends(get_db)):
    get_teacher_submission(db, submission_id, user)
    query = select(SubmissionReview).where(SubmissionReview.submission_id == submission_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    records = db.scalars(query.order_by(SubmissionReview.version.desc()).offset(offset).limit(limit)).all()
    return dict(total=total, offset=offset, limit=limit, items=[review_response(r) for r in records])


@router.put('/submissions/{submission_id}/review')
def save(submission_id: str, payload: ReviewSave, user: UserPublic = Depends(require_role('teacher')),
         db: Session = Depends(get_db)):
    submission, assignment, questions, signature, latest = context(db, submission_id, user)
    check_version(latest, payload.expected_version)
    assert_current(submission, signature, payload.source_updated_at, payload.rubric_signature)
    data = validated_data(payload, questions, assignment.total_marks)
    data['source_revision'] = len(submission.revisions) + 1
    return commit(db, SubmissionReview(submission_id=submission.id, version=payload.expected_version + 1,
                  assignment_version=assignment.updated_at,
                  rubric_version=db.scalar(select(AssignmentRubric.updated_at).where(AssignmentRubric.assignment_id==assignment.id)),
                  source_updated_at=submission.updated_at, rubric_signature=signature,
                  actor=user.email, state=payload.state, data=data))


def action(submission_id, payload, user, db, release):
    submission, assignment, questions, signature, latest = context(db, submission_id, user)
    check_version(latest, payload.expected_version)
    assert_current(submission, signature, payload.source_updated_at, payload.rubric_signature)
    now = datetime.now(UTC)
    if release:
        if not latest or latest.state != 'reviewed':
            raise HTTPException(409, 'Save a complete reviewed version before releasing.')
        assert_current(submission, signature, latest.source_updated_at, latest.rubric_signature)
        data = dict(latest.data)
        submission.marks_obtained = Decimal(data['total'])
        submission.teacher_feedback = data['overall_feedback']
        submission.status = 'graded'
        submission.graded_at = now
    else:
        if not payload.reason.strip():
            raise HTTPException(422, 'A revision request needs a clear reason.')
        if latest and latest.state == 'returned' and utc(latest.source_updated_at) == utc(submission.updated_at):
            raise HTTPException(409, 'This revision request is already active.')
        data = dict(reason=payload.reason.strip(), source_revision=len(submission.revisions) + 1)
        submission.status = 'returned'
        submission.teacher_feedback = payload.reason.strip()
        # Keep any previously released grade until a new attempt is submitted.
    submission.updated_at = now
    return commit(db, SubmissionReview(submission_id=submission.id, version=payload.expected_version + 1,
                  assignment_version=assignment.updated_at,
                  rubric_version=db.scalar(select(AssignmentRubric.updated_at).where(AssignmentRubric.assignment_id==assignment.id)),
                  source_updated_at=now, rubric_signature=signature, actor=user.email,
                  state='released' if release else 'returned', data=data))


@router.post('/submissions/{submission_id}/review/release')
def release(submission_id: str, payload: ReviewAction, user: UserPublic = Depends(require_role('teacher')),
            db: Session = Depends(get_db)):
    return action(submission_id, payload, user, db, True)


@router.post('/submissions/{submission_id}/review/return')
def return_work(submission_id: str, payload: ReviewAction, user: UserPublic = Depends(require_role('teacher')),
                db: Session = Depends(get_db)):
    return action(submission_id, payload, user, db, False)


@router.get('/submissions/{submission_id}/released-review')
def released_review(submission_id: str, user: UserPublic = Depends(_current_user_from_token),
                    db: Session = Depends(get_db)):
    if user.role == 'teacher':
        submission, _ = get_teacher_submission(db, submission_id, user)
    elif user.role == 'student':
        submission, _ = get_student_submission(db, submission_id, user)
    else:
        raise HTTPException(403, 'Grade access denied.')
    record = db.scalar(select(SubmissionReview).where(
        SubmissionReview.submission_id == submission_id, SubmissionReview.state == 'released',
        SubmissionReview.source_updated_at == submission.updated_at).limit(1))
    if not record or submission.status != 'graded':
        return None
    # Return only released educational content; no private history/override reason.
    return dict(questions=[{key:q[key] for key in ('question_id','prompt','max_marks','marks','feedback')}
                          for q in record.data['questions']], total=record.data['total'],
                feedback=record.data['overall_feedback'], released_at=utc(record.created_at))


@router.get('/assignments/{assignment_id}/review-roster')
def roster(assignment_id: str, state: str = Query('all', pattern='^(all|submitted|not_submitted|late|under_review|draft|reviewed|returned|graded|released)$'),
           offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100),
           user: UserPublic = Depends(require_role('teacher')), db: Session = Depends(get_db)):
    assignment = get_teacher_assignment(db, assignment_id, user)
    latest_ids = select(SubmissionReview.submission_id, func.max(SubmissionReview.version).label('version')).group_by(SubmissionReview.submission_id).subquery()
    q = select(ClassMembership.student_id, Submission, SubmissionReview).select_from(ClassMembership).outerjoin(Submission,
        (Submission.student_id == ClassMembership.student_id) & (Submission.assignment_id == assignment_id))
    q = q.outerjoin(latest_ids, latest_ids.c.submission_id == Submission.id).outerjoin(SubmissionReview,
        (SubmissionReview.submission_id == Submission.id) & (SubmissionReview.version == latest_ids.c.version))
    q = q.where(ClassMembership.class_id == assignment.class_id)
    _, signature = question_config(db,assignment)
    current = (SubmissionReview.source_updated_at == Submission.updated_at) & (SubmissionReview.rubric_signature==signature)
    filters = dict(submitted=Submission.status == 'submitted', not_submitted=(Submission.id.is_(None) | (Submission.status == 'draft')),
        late=Submission.is_late.is_(True), draft=(Submission.status == 'draft') | (current & (SubmissionReview.state == 'draft')),
        under_review=current & SubmissionReview.state.in_(['draft','reviewed']), reviewed=current & (SubmissionReview.state == 'reviewed'),
        returned=Submission.status == 'returned', graded=Submission.status == 'graded', released=Submission.status == 'graded')
    if state != 'all': q = q.where(filters[state])
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.execute(q.order_by(ClassMembership.student_id).offset(offset).limit(limit)).all()
    return dict(total=total, offset=offset, limit=limit, items=[dict(student_id=student,
        submission_id=s.id if s else None, status=s.status if s else 'not_submitted', is_late=s.is_late if s else False,
        review_state=r.state if r and utc(r.source_updated_at)==utc(s.updated_at) and r.rubric_signature==signature else None,
        marks_obtained=s.marks_obtained if s else None) for student,s,r in rows])
