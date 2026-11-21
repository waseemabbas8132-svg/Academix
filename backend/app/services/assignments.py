from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.routes.auth import UserPublic
from app.models.assignment import Assignment
from app.models.classroom import AcademicClass, ClassMembership
from app.models.submission import Submission, SubmissionRevision
from app.models.uploaded_file import UploadedFile
from app.repositories.assignments import get_assignment, get_submission


def get_owned_class(db: Session, class_id: str, user: UserPublic) -> AcademicClass:
    classroom = db.get(AcademicClass, class_id)
    if classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    if classroom.teacher_id != user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage assignments in your own classes.",
        )
    return classroom


def get_teacher_assignment(
    db: Session,
    assignment_id: str,
    user: UserPublic,
) -> Assignment:
    assignment = get_assignment(db, assignment_id)
    if assignment is None or assignment.is_archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    classroom = db.get(AcademicClass, assignment.class_id)
    if classroom is None or classroom.teacher_id != user.email or assignment.teacher_id != user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage assignments in your own classes.",
        )
    return assignment


def get_student_assignment(
    db: Session,
    assignment_id: str,
    user: UserPublic,
) -> Assignment:
    assignment = get_assignment(db, assignment_id)
    if assignment is None or assignment.is_archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    if not assignment.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assignment is not available.",
        )
    membership = db.execute(
        select(ClassMembership).where(
            ClassMembership.class_id == assignment.class_id,
            ClassMembership.student_id == user.email,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in this class.",
        )
    return assignment


def get_assignment_for_user(
    db: Session,
    assignment_id: str,
    user: UserPublic,
) -> Assignment:
    if user.role == "teacher":
        return get_teacher_assignment(db, assignment_id, user)
    if user.role == "student":
        return get_student_assignment(db, assignment_id, user)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="This endpoint requires a teacher or student account.",
    )


def require_class_membership(db: Session, class_id: str, student_id: str) -> None:
    membership = db.execute(
        select(ClassMembership).where(
            ClassMembership.class_id == class_id,
            ClassMembership.student_id == student_id,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in this class.",
        )


def get_teacher_submission(
    db: Session,
    submission_id: str,
    user: UserPublic,
) -> tuple[Submission, Assignment]:
    submission = get_submission(db, submission_id)
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
    assignment = db.get(Assignment, submission.assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    classroom = db.get(AcademicClass, assignment.class_id)
    if classroom is None or classroom.teacher_id != user.email or assignment.teacher_id != user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only grade submissions in your own classes.",
        )
    return submission, assignment


def get_student_submission(
    db: Session,
    submission_id: str,
    user: UserPublic,
) -> tuple[Submission, Assignment]:
    submission = get_submission(db, submission_id)
    if submission is None or submission.student_id != user.email:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found.")
    assignment = db.get(Assignment, submission.assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    require_class_membership(db, assignment.class_id, user.email)
    return submission, assignment


def get_file_for_user(
    db: Session,
    file_id: str,
    user: UserPublic,
) -> UploadedFile:
    uploaded_file = db.get(UploadedFile, file_id)
    if uploaded_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")

    if uploaded_file.assignment_id is not None:
        assignment = db.get(Assignment, uploaded_file.assignment_id)
        if assignment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
        if user.role == "teacher":
            get_teacher_assignment(db, assignment.id, user)
        elif user.role == "student":
            get_student_assignment(db, assignment.id, user)
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File access denied.")
        return uploaded_file

    revision = db.get(SubmissionRevision, uploaded_file.submission_revision_id) if uploaded_file.submission_revision_id else None
    submission_id = revision.submission_id if revision else uploaded_file.submission_id
    submission = db.get(Submission, submission_id) if submission_id else None
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
    assignment = db.get(Assignment, submission.assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
    if user.role == "teacher":
        get_teacher_submission(db, submission.id, user)
    elif user.role == "student":
        if submission.student_id != user.email:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
        require_class_membership(db, assignment.class_id, user.email)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="File access denied.")
    return uploaded_file


def assignment_counts(db: Session, assignment: Assignment) -> dict[str, int]:
    enrolled_count = db.scalar(
        select(func.count())
        .select_from(ClassMembership)
        .where(ClassMembership.class_id == assignment.class_id)
    ) or 0
    status_counts = dict(
        db.execute(
            select(Submission.status, func.count())
            .where(Submission.assignment_id == assignment.id)
            .group_by(Submission.status)
        ).all()
    )
    submitted_count = status_counts.get("submitted", 0) + status_counts.get("returned", 0)
    graded_count = status_counts.get("graded", 0)
    pending_count = max(enrolled_count - submitted_count - graded_count, 0)
    return {
        "submitted_count": submitted_count,
        "pending_count": pending_count,
        "graded_count": graded_count,
    }


def is_late(assignment: Assignment, submitted_at: datetime) -> bool:
    due_date = assignment.due_date
    if due_date.tzinfo is None:
        due_date = due_date.replace(tzinfo=UTC)
    if submitted_at.tzinfo is None:
        submitted_at = submitted_at.replace(tzinfo=UTC)
    return submitted_at.astimezone(UTC) > due_date.astimezone(UTC)
