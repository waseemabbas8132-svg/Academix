from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.assignment import Assignment
from app.models.classroom import ClassMembership
from app.models.submission import Submission
from app.models.uploaded_file import UploadedFile


def get_assignment(db: Session, assignment_id: str) -> Assignment | None:
    return db.execute(
        select(Assignment)
        .options(selectinload(Assignment.attachments))
        .where(Assignment.id == assignment_id)
    ).scalar_one_or_none()


def list_class_assignments(db: Session, class_id: str) -> list[Assignment]:
    return list(
        db.execute(
            select(Assignment)
            .options(selectinload(Assignment.attachments))
            .where(Assignment.class_id == class_id)
            .where(Assignment.is_archived.is_(False))
            .order_by(Assignment.due_date.asc(), Assignment.created_at.desc())
        )
        .scalars()
        .all()
    )


def list_submission_files(db: Session, submission_id: str) -> list[UploadedFile]:
    return list(
        db.execute(
            select(UploadedFile)
            .where(UploadedFile.submission_id == submission_id)
            .order_by(UploadedFile.created_at.asc())
        )
        .scalars()
        .all()
    )


def list_assignment_submissions(db: Session, assignment_id: str) -> list[Submission]:
    return list(
        db.execute(
            select(Submission)
            .options(
                selectinload(Submission.attachments),
                selectinload(Submission.revisions),
            )
            .where(Submission.assignment_id == assignment_id)
            .order_by(Submission.submitted_at.asc().nulls_first(), Submission.created_at.asc())
        )
        .scalars()
        .all()
    )


def get_student_submission(
    db: Session,
    assignment_id: str,
    student_id: str,
) -> Submission | None:
    return db.execute(
        select(Submission)
        .options(selectinload(Submission.attachments), selectinload(Submission.revisions))
        .where(
            Submission.assignment_id == assignment_id,
            Submission.student_id == student_id,
        )
    ).scalar_one_or_none()


def get_submission(db: Session, submission_id: str) -> Submission | None:
    return db.execute(
        select(Submission)
        .options(selectinload(Submission.attachments), selectinload(Submission.revisions))
        .where(Submission.id == submission_id)
    ).scalar_one_or_none()


def list_student_submissions(
    db: Session,
    student_id: str,
    assignment_id: str | None = None,
) -> list[Submission]:
    statement = (
        select(Submission)
        .join(Assignment, Assignment.id == Submission.assignment_id)
        .join(ClassMembership, ClassMembership.class_id == Assignment.class_id)
        .options(
            selectinload(Submission.attachments),
            selectinload(Submission.revisions),
            selectinload(Submission.assignment),
        )
        .where(
            Submission.student_id == student_id,
            ClassMembership.student_id == student_id,
        )
        .order_by(Submission.updated_at.desc())
    )
    if assignment_id is not None:
        statement = statement.where(Submission.assignment_id == assignment_id)
    return list(
        db.execute(statement).scalars().all()
    )
