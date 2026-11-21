import logging
from datetime import UTC, datetime
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.v1.routes.auth import (
    DEMO_USERS,
    UserPublic,
    _current_user_from_token,
    require_role,
)
from app.database.session import get_db
from app.models.assignment import Assignment
from app.models.assignment_rubric import AssignmentRubric
from app.models.classroom import AcademicClass, ClassMembership
from app.models.submission import Submission, SubmissionRevision
from app.models.uploaded_file import UploadedFile
from app.repositories.assignments import (
    get_student_submission as find_student_submission,
    list_assignment_submissions,
    list_class_assignments,
    list_student_submissions,
)
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentPublish,
    AssignmentResponse,
    AssignmentUpdate,
    FileAttachmentResponse,
    GradeRequest,
    SubmissionResponse,
    StudentAssignmentRubricResponse,
    StudentRubricCriterion,
    StudentRubricQuestion,
)
from app.services.assignments import (
    assignment_counts,
    get_assignment_for_user,
    get_file_for_user,
    get_owned_class,
    get_student_assignment,
    get_student_submission,
    get_teacher_assignment,
    get_teacher_submission,
    is_late,
    require_class_membership,
)
from app.services.file_storage import (
    FileStorage,
    UploadRejected,
    get_file_storage,
)
from app.services.review_workflow import deadline_status

logger = logging.getLogger(__name__)
router = APIRouter()


def _file_response(file: UploadedFile) -> FileAttachmentResponse:
    return FileAttachmentResponse(
        id=file.id,
        filename=file.original_filename,
        content_type=file.content_type,
        size_bytes=file.size_bytes,
        download_url=f"/api/v1/files/{file.id}",
    )


def _assignment_response(
    db: Session,
    assignment: Assignment,
    *,
    include_counts: bool,
) -> AssignmentResponse:
    counts = assignment_counts(db, assignment) if include_counts else {}
    return AssignmentResponse(
        id=assignment.id,
        class_id=assignment.class_id,
        teacher_id=assignment.teacher_id,
        title=assignment.title,
        instructions=assignment.instructions,
        total_marks=assignment.total_marks,
        due_date=assignment.due_date,
        is_published=assignment.is_published,
        is_archived=assignment.is_archived,
        created_at=assignment.created_at,
        updated_at=assignment.updated_at,
        attachments=[_file_response(file) for file in assignment.attachments],
        deadline_status=deadline_status(assignment.due_date),
        server_now=datetime.now(UTC),
        **counts,
    )


def _submission_response(
    submission: Submission,
    assignment: Assignment,
    *,
    include_student_name: bool = False,
) -> SubmissionResponse:
    student_name = (
        next(
            (
                user["name"]
                for email, user in DEMO_USERS.items()
                if user["id"] == submission.student_id
                or email == submission.student_id
            ),
            None,
        )
        if include_student_name
        else None
    )
    return SubmissionResponse(
        id=submission.id,
        assignment_id=submission.assignment_id,
        student_id=submission.student_id,
        student_name=student_name,
        submission_text=submission.submission_text,
        status=submission.status,
        is_late=submission.is_late,
        submitted_at=submission.submitted_at,
        updated_at=submission.updated_at,
        marks_obtained=submission.marks_obtained,
        teacher_feedback=submission.teacher_feedback,
        graded_at=submission.graded_at,
        attachments=[_file_response(file) for file in submission.attachments],
        revisions=[dict(
            revision_number=r.revision_number, submission_text=r.submission_text,
            status=r.status, is_late=r.is_late, submitted_at=r.submitted_at,
            marks_obtained=r.marks_obtained, teacher_feedback=r.teacher_feedback,
            graded_at=r.graded_at, created_at=r.created_at,
            attachments=[_file_response(f) for f in r.attachments],
        ) for r in submission.revisions],
        assignment_title=assignment.title,
        total_marks=assignment.total_marks,
        due_date=assignment.due_date,
    )


async def _store_uploads(
    db: Session,
    storage: FileStorage,
    uploads: list[UploadFile],
    *,
    assignment_id: str | None = None,
    submission_id: str | None = None,
    commit: bool = True,
) -> list[UploadedFile]:
    if len(uploads) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A maximum of 10 files can be uploaded at once.",
        )

    stored_keys: list[str] = []
    records: list[UploadedFile] = []
    try:
        for upload in uploads:
            blob = await storage.store(upload)
            stored_keys.append(blob.storage_key)
            record = UploadedFile(
                assignment_id=assignment_id,
                submission_id=submission_id,
                storage_key=blob.storage_key,
                original_filename=blob.original_filename,
                content_type=blob.content_type,
                size_bytes=blob.size_bytes,
            )
            db.add(record)
            records.append(record)
        db.flush()
        if commit:
            db.commit()
            for record in records:
                db.refresh(record)
        return records
    except UploadRejected as error:
        db.rollback()
        _delete_stored_files(storage, stored_keys)
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except Exception:
        db.rollback()
        _delete_stored_files(storage, stored_keys)
        raise


def _delete_stored_files(storage: FileStorage, storage_keys: list[str]) -> None:
    for key in storage_keys:
        try:
            storage.delete(key)
        except OSError:
            logger.exception("Could not remove staged upload %s after transaction failure.", key)


@router.post(
    "/classes/{class_id}/assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    class_id: str,
    payload: AssignmentCreate,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> AssignmentResponse:
    classroom = get_owned_class(db, class_id, current_user)
    if classroom.is_archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignments cannot be added to archived classes.",
        )

    assignment = Assignment(
        class_id=class_id,
        teacher_id=current_user.email,
        title=payload.title,
        instructions=payload.instructions,
        total_marks=payload.total_marks,
        due_date=payload.due_date,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return _assignment_response(db, assignment, include_counts=True)


@router.get(
    "/classes/{class_id}/assignments",
    response_model=list[AssignmentResponse],
)
def list_class_assignment_records(
    class_id: str,
    current_user: UserPublic = Depends(_current_user_from_token),
    db: Session = Depends(get_db),
) -> list[AssignmentResponse]:
    if current_user.role == "teacher":
        get_owned_class(db, class_id, current_user)
        assignments = list_class_assignments(db, class_id)
        return [
            _assignment_response(db, assignment, include_counts=True)
            for assignment in assignments
        ]
    if current_user.role == "student":
        require_class_membership(db, class_id, current_user.email)
        assignments = list(
            db.execute(
                select(Assignment)
                .options(selectinload(Assignment.attachments))
                .where(
                    Assignment.class_id == class_id,
                    Assignment.is_published.is_(True),
                    Assignment.is_archived.is_(False),
                )
                .order_by(Assignment.due_date.asc())
            )
            .scalars()
            .all()
        )
        return [
            _assignment_response(db, assignment, include_counts=False)
            for assignment in assignments
        ]
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="This endpoint requires a teacher or student account.",
    )


@router.get("/assignments/{assignment_id}", response_model=AssignmentResponse)
def get_assignment_details(
    assignment_id: str,
    current_user: UserPublic = Depends(_current_user_from_token),
    db: Session = Depends(get_db),
) -> AssignmentResponse:
    assignment = get_assignment_for_user(db, assignment_id, current_user)
    return _assignment_response(
        db,
        assignment,
        include_counts=current_user.role == "teacher",
    )


@router.get(
    "/student/assignments/{assignment_id}/rubric",
    response_model=StudentAssignmentRubricResponse,
)
def get_student_assignment_rubric(
    assignment_id: str,
    current_user: UserPublic = Depends(require_role("student")),
    db: Session = Depends(get_db),
) -> StudentAssignmentRubricResponse:
    assignment = get_student_assignment(db, assignment_id, current_user)
    rubric = db.scalar(
        select(AssignmentRubric)
        .options(selectinload(AssignmentRubric.questions))
        .where(AssignmentRubric.assignment_id == assignment.id)
    )
    if rubric is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No student-visible rubric is configured.",
        )
    return StudentAssignmentRubricResponse(
        assignment_id=assignment.id,
        questions=[
            StudentRubricQuestion(
                question_id=question.question_id,
                prompt=question.prompt,
                max_marks=question.max_marks,
                partial_credit_rules=question.partial_credit_rules,
                criteria=[
                    StudentRubricCriterion(
                        description=str(criterion["description"]),
                        marks=criterion["marks"],
                    )
                    for criterion in question.criteria
                ],
            )
            for question in rubric.questions
        ],
    )


@router.put("/assignments/{assignment_id}", response_model=AssignmentResponse)
def update_assignment(
    assignment_id: str,
    payload: AssignmentUpdate,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> AssignmentResponse:
    assignment = get_teacher_assignment(db, assignment_id, current_user)
    highest_grade = db.scalar(
        select(Submission.marks_obtained)
        .where(
            Submission.assignment_id == assignment_id,
            Submission.marks_obtained.is_not(None),
        )
        .order_by(Submission.marks_obtained.desc())
        .limit(1)
    )
    if highest_grade is not None and payload.total_marks < highest_grade:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Total marks cannot be lower than marks already awarded.",
        )

    assignment.title = payload.title
    assignment.instructions = payload.instructions
    assignment.total_marks = payload.total_marks
    assignment.due_date = payload.due_date
    db.commit()
    db.refresh(assignment)
    return _assignment_response(db, assignment, include_counts=True)


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_assignment(
    assignment_id: str,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> None:
    assignment = get_teacher_assignment(db, assignment_id, current_user)
    assignment.is_archived = True
    assignment.is_published = False
    db.commit()


@router.patch("/assignments/{assignment_id}/publish", response_model=AssignmentResponse)
def set_assignment_published(
    assignment_id: str,
    payload: AssignmentPublish,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> AssignmentResponse:
    assignment = get_teacher_assignment(db, assignment_id, current_user)
    classroom = db.get(AcademicClass, assignment.class_id)
    if payload.is_published and (classroom is None or classroom.is_archived):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignments in archived classes cannot be published.",
        )
    assignment.is_published = payload.is_published
    db.commit()
    db.refresh(assignment)
    return _assignment_response(db, assignment, include_counts=True)


@router.get(
    "/assignments/{assignment_id}/submissions",
    response_model=list[SubmissionResponse],
)
def list_assignment_submissions_for_teacher(
    assignment_id: str,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> list[SubmissionResponse]:
    assignment = get_teacher_assignment(db, assignment_id, current_user)
    submissions = list_assignment_submissions(db, assignment_id)
    return [
        _submission_response(
            submission,
            assignment,
            include_student_name=True,
        )
        for submission in submissions
    ]


@router.post(
    "/submissions/{submission_id}/grade",
    response_model=SubmissionResponse,
)
def grade_submission(
    submission_id: str,
    payload: GradeRequest,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> SubmissionResponse:
    db.execute(select(Submission.id).where(Submission.id == submission_id).with_for_update())
    submission, assignment = get_teacher_submission(db, submission_id, current_user)
    if submission.status == "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Draft submissions cannot be graded.",
        )
    if payload.marks_obtained is not None and payload.marks_obtained > assignment.total_marks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Marks cannot exceed the assignment total.",
        )
    submission.marks_obtained = payload.marks_obtained
    submission.teacher_feedback = payload.teacher_feedback
    # Preserve a precise version for stale AI-approval checks, including SQLite
    # whose server-side CURRENT_TIMESTAMP can have only second precision.
    submission.updated_at = datetime.now(UTC)
    if payload.marks_obtained is None:
        submission.status = "returned"
        submission.graded_at = None
    else:
        submission.status = "graded"
        submission.graded_at = datetime.now(UTC)
    db.commit()
    db.refresh(submission)
    return _submission_response(
        submission,
        assignment,
        include_student_name=True,
    )


@router.get(
    "/student/assignments",
    response_model=list[AssignmentResponse],
)
def list_student_assignments(
    current_user: UserPublic = Depends(require_role("student")),
    db: Session = Depends(get_db),
) -> list[AssignmentResponse]:
    assignments = list(
        db.execute(
            select(Assignment)
            .join(ClassMembership, ClassMembership.class_id == Assignment.class_id)
            .options(selectinload(Assignment.attachments))
            .where(
                ClassMembership.student_id == current_user.email,
                Assignment.is_published.is_(True),
                Assignment.is_archived.is_(False),
                AcademicClass.is_archived.is_(False),
            )
            .join(AcademicClass, AcademicClass.id == Assignment.class_id)
            .order_by(Assignment.due_date.asc())
        )
        .scalars()
        .all()
    )
    return [
        _assignment_response(db, assignment, include_counts=False)
        for assignment in assignments
    ]


@router.post(
    "/assignments/{assignment_id}/submissions",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_or_update_submission(
    assignment_id: str,
    submission_text: str | None = Form(default=None, max_length=50000),
    is_draft: bool = Form(default=False),
    files: list[UploadFile] = File(default=[]),
    current_user: UserPublic = Depends(require_role("student")),
    db: Session = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
) -> SubmissionResponse:
    assignment = get_student_assignment(db, assignment_id, current_user)
    cleaned_text = submission_text.strip() if submission_text else None
    if not is_draft and not cleaned_text and not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add text or at least one file before submitting.",
        )

    db.execute(select(Submission.id).where(Submission.assignment_id == assignment_id,
        Submission.student_id == current_user.email).with_for_update())
    submission = find_student_submission(db, assignment_id, current_user.email)
    if submission is not None and submission.status == "graded":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A graded submission cannot be changed.",
        )

    submitted_at = None if is_draft else datetime.now(UTC)
    if submission is None:
        submission = Submission(
            assignment_id=assignment_id,
            student_id=current_user.email,
        )
    elif submission.status in {"submitted", "returned"}:
        revision = SubmissionRevision(
                submission_id=submission.id,
                revision_number=len(submission.revisions) + 1,
                submission_text=submission.submission_text,
                status=submission.status,
                is_late=submission.is_late,
                submitted_at=submission.submitted_at,
                marks_obtained=submission.marks_obtained,
                teacher_feedback=submission.teacher_feedback,
                graded_at=submission.graded_at,
        )
        db.add(revision)
        db.flush()
        # Move ownership metadata only. Stored original bytes never change.
        for attached in list(submission.attachments):
            attached.submission = None
            attached.revision = revision
    submission.submission_text = cleaned_text
    submission.updated_at = datetime.now(UTC)
    submission.status = "draft" if is_draft else "submitted"
    submission.submitted_at = submitted_at
    submission.is_late = bool(submitted_at and is_late(assignment, submitted_at))
    submission.marks_obtained = None
    submission.teacher_feedback = None
    submission.graded_at = None
    db.add(submission)
    stored_files: list[UploadedFile] = []
    try:
        db.flush()
        stored_files = await _store_uploads(
            db,
            storage,
            files,
            submission_id=submission.id,
            commit=False,
        )
        db.commit()
        db.refresh(submission)
    except IntegrityError as error:
        db.rollback()
        _delete_stored_files(
            storage,
            [uploaded_file.storage_key for uploaded_file in stored_files],
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A submission already exists or was updated. Refresh and try again.",
        ) from error
    except Exception:
        db.rollback()
        _delete_stored_files(
            storage,
            [uploaded_file.storage_key for uploaded_file in stored_files],
        )
        raise
    return _submission_response(submission, assignment)


@router.get("/student/submissions", response_model=list[SubmissionResponse])
def list_my_submissions(
    assignment_id: str | None = None,
    current_user: UserPublic = Depends(require_role("student")),
    db: Session = Depends(get_db),
) -> list[SubmissionResponse]:
    submissions = list_student_submissions(db, current_user.email, assignment_id)
    return [
        _submission_response(submission, submission.assignment)
        for submission in submissions
    ]


@router.get(
    "/student/submissions/{submission_id}",
    response_model=SubmissionResponse,
)
def get_my_submission(
    submission_id: str,
    current_user: UserPublic = Depends(require_role("student")),
    db: Session = Depends(get_db),
) -> SubmissionResponse:
    submission, assignment = get_student_submission(db, submission_id, current_user)
    return _submission_response(submission, assignment)


@router.post(
    "/assignments/{assignment_id}/attachments",
    response_model=list[FileAttachmentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_assignment_attachments(
    assignment_id: str,
    files: list[UploadFile] = File(...),
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
) -> list[FileAttachmentResponse]:
    get_teacher_assignment(db, assignment_id, current_user)
    stored = await _store_uploads(
        db,
        storage,
        files,
        assignment_id=assignment_id,
    )
    return [_file_response(file) for file in stored]


@router.get("/files/{file_id}")
def download_file(
    file_id: str,
    current_user: UserPublic = Depends(_current_user_from_token),
    db: Session = Depends(get_db),
    storage: FileStorage = Depends(get_file_storage),
) -> FileResponse:
    uploaded_file = get_file_for_user(db, file_id, current_user)
    try:
        path: Path = storage.resolve(uploaded_file.storage_key)
    except FileNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.") from error
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found.")
    return FileResponse(
        path=path,
        media_type=uploaded_file.content_type,
        filename=uploaded_file.original_filename,
        content_disposition_type="attachment",
    )
