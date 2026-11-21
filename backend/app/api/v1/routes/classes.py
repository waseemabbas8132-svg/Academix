import secrets
import string
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.routes.auth import UserPublic, _current_user_from_token, require_role
from app.database.session import get_db
from app.models.classroom import AcademicClass, ClassMembership

router = APIRouter()


class ClassCreateRequest(BaseModel):
    name: str
    section: str
    subject: str
    room: str | None = None
    description: str | None = None

    model_config = ConfigDict(str_strip_whitespace=True)

    def validate(self) -> None:
        if not self.name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Class name is required.")
        if not self.section.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Section is required.")
        if not self.subject.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject is required.")


class ClassUpdateRequest(BaseModel):
    name: str | None = None
    section: str | None = None
    subject: str | None = None
    room: str | None = None
    description: str | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class ClassJoinRequest(BaseModel):
    class_code: str


class ClassStudentSummary(BaseModel):
    student_id: str
    name: str
    joined_at: datetime


class AcademicClassResponse(BaseModel):
    id: str
    name: str
    section: str
    subject: str
    room: str | None = None
    description: str | None = None
    class_code: str
    teacher_id: str
    created_at: datetime
    updated_at: datetime
    is_archived: bool


class ClassMembershipResponse(BaseModel):
    class_id: str
    student_id: str
    joined_at: datetime


def _generate_class_code(db: Session) -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(8))
        exists = db.execute(select(AcademicClass).where(AcademicClass.class_code == code)).scalar_one_or_none()
        if exists is None:
            return code


def _serialize_class(item: AcademicClass) -> AcademicClassResponse:
    return AcademicClassResponse(
        id=item.id,
        name=item.name,
        section=item.section,
        subject=item.subject,
        room=item.room,
        description=item.description,
        class_code=item.class_code,
        teacher_id=item.teacher_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
        is_archived=item.is_archived,
    )


@router.post("/classes", response_model=AcademicClassResponse, status_code=status.HTTP_201_CREATED)
def create_class(
    payload: ClassCreateRequest,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> AcademicClassResponse:
    payload.validate()
    class_code = _generate_class_code(db)
    classroom = AcademicClass(
        name=payload.name.strip(),
        section=payload.section.strip(),
        subject=payload.subject.strip(),
        room=payload.room.strip() if payload.room else None,
        description=payload.description.strip() if payload.description else None,
        class_code=class_code,
        teacher_id=current_user.email,
    )
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return _serialize_class(classroom)


@router.get("/classes", response_model=list[AcademicClassResponse])
def list_classes(
    current_user: UserPublic = Depends(_current_user_from_token),
    db: Session = Depends(get_db),
) -> list[AcademicClassResponse]:
    if current_user.role == "teacher":
        rows = (
            db.execute(
                select(AcademicClass)
                .where(AcademicClass.teacher_id == current_user.email)
                .where(AcademicClass.is_archived.is_(False))
                .order_by(AcademicClass.created_at.desc())
            )
            .scalars()
            .all()
        )
        return [_serialize_class(item) for item in rows]

    rows = (
        db.execute(
            select(AcademicClass)
            .join(ClassMembership, ClassMembership.class_id == AcademicClass.id)
            .where(ClassMembership.student_id == current_user.email)
            .where(AcademicClass.is_archived.is_(False))
            .order_by(AcademicClass.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_serialize_class(item) for item in rows]


@router.get("/classes/{class_id}", response_model=AcademicClassResponse)
def get_class_details(
    class_id: str,
    current_user: UserPublic = Depends(_current_user_from_token),
    db: Session = Depends(get_db),
) -> AcademicClassResponse:
    classroom = db.get(AcademicClass, class_id)
    if classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    if current_user.role == "teacher":
        if classroom.teacher_id != current_user.email:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this class.")
    else:
        membership = db.execute(
            select(ClassMembership).where(
                ClassMembership.class_id == class_id,
                ClassMembership.student_id == current_user.email,
            )
        ).scalar_one_or_none()
        if membership is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not enrolled in this class.")
    return _serialize_class(classroom)


@router.patch("/classes/{class_id}", response_model=AcademicClassResponse)
def update_class(
    class_id: str,
    payload: ClassUpdateRequest,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> AcademicClassResponse:
    classroom = db.get(AcademicClass, class_id)
    if classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    if classroom.teacher_id != current_user.email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update your own classes.")
    if classroom.is_archived:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Archived classes cannot be edited.")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Class name cannot be empty.")
        classroom.name = name
    if payload.section is not None:
        section = payload.section.strip()
        if not section:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Section cannot be empty.")
        classroom.section = section
    if payload.subject is not None:
        subject = payload.subject.strip()
        if not subject:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Subject cannot be empty.")
        classroom.subject = subject
    if payload.room is not None:
        classroom.room = payload.room.strip() if payload.room.strip() else None
    if payload.description is not None:
        classroom.description = payload.description.strip() or None

    db.commit()
    db.refresh(classroom)
    return _serialize_class(classroom)


@router.delete("/classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_class(
    class_id: str,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> None:
    classroom = db.get(AcademicClass, class_id)
    if classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    if classroom.teacher_id != current_user.email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only archive your own classes.")
    classroom.is_archived = True
    db.commit()


@router.get("/classes/{class_id}/students", response_model=list[ClassStudentSummary])
def list_class_students(
    class_id: str,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> list[ClassStudentSummary]:
    classroom = db.get(AcademicClass, class_id)
    if classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    if classroom.teacher_id != current_user.email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only view your own class roster.")

    memberships = (
        db.execute(
            select(ClassMembership)
            .where(ClassMembership.class_id == class_id)
            .order_by(ClassMembership.joined_at.desc())
        )
        .scalars()
        .all()
    )
    return [
        ClassStudentSummary(
            student_id=membership.student_id,
            name=membership.student_id.split("@")[0].title(),
            joined_at=membership.joined_at,
        )
        for membership in memberships
    ]


@router.delete("/classes/{class_id}/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_student_from_class(
    class_id: str,
    student_id: str,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> None:
    classroom = db.get(AcademicClass, class_id)
    if classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    if classroom.teacher_id != current_user.email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only manage your own classes.")

    membership = db.execute(
        select(ClassMembership).where(
            ClassMembership.class_id == class_id,
            ClassMembership.student_id == student_id,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student is not enrolled in this class.")
    db.delete(membership)
    db.commit()


@router.post("/classes/join", response_model=ClassMembershipResponse, status_code=status.HTTP_201_CREATED)
def join_class(
    payload: ClassJoinRequest,
    current_user: UserPublic = Depends(require_role("student")),
    db: Session = Depends(get_db),
) -> ClassMembershipResponse:
    classroom = db.execute(
        select(AcademicClass).where(AcademicClass.class_code == payload.class_code.strip().upper())
    ).scalar_one_or_none()
    if classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class code is invalid.")
    if classroom.is_archived:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This class has been archived.")
    existing_membership = db.execute(
        select(ClassMembership).where(
            ClassMembership.class_id == classroom.id,
            ClassMembership.student_id == current_user.email,
        )
    ).scalar_one_or_none()
    if existing_membership is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You are already enrolled in this class.")

    membership = ClassMembership(class_id=classroom.id, student_id=current_user.email)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return ClassMembershipResponse(
        class_id=membership.class_id,
        student_id=membership.student_id,
        joined_at=membership.joined_at,
    )


@router.delete("/classes/{class_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_class(
    class_id: str,
    current_user: UserPublic = Depends(require_role("student")),
    db: Session = Depends(get_db),
) -> None:
    membership = db.execute(
        select(ClassMembership).where(
            ClassMembership.class_id == class_id,
            ClassMembership.student_id == current_user.email,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not enrolled in this class.")
    db.delete(membership)
    db.commit()


@router.get("/classes/{class_id}/details", response_model=AcademicClassResponse)
def get_student_class_details(
    class_id: str,
    current_user: UserPublic = Depends(require_role("student")),
    db: Session = Depends(get_db),
) -> AcademicClassResponse:
    membership = db.execute(
        select(ClassMembership).where(
            ClassMembership.class_id == class_id,
            ClassMembership.student_id == current_user.email,
        )
    ).scalar_one_or_none()
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not enrolled in this class.")
    classroom = db.get(AcademicClass, class_id)
    if classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")
    return _serialize_class(classroom)
