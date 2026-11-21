from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.routes.auth import UserPublic
from app.models.announcement import Announcement
from app.models.classroom import AcademicClass, ClassMembership
from app.repositories.announcements import get_announcement


def get_accessible_class(db: Session, class_id: str, user: UserPublic) -> AcademicClass:
    classroom = db.get(AcademicClass, class_id)
    if classroom is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found.")

    if user.role == "teacher" and classroom.teacher_id == user.email:
        return classroom
    if user.role == "student":
        membership = db.execute(
            select(ClassMembership).where(
                ClassMembership.class_id == class_id,
                ClassMembership.student_id == user.email,
            )
        ).scalar_one_or_none()
        if membership is not None:
            return classroom

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this class stream.",
    )


def get_teacher_announcement(
    db: Session,
    announcement_id: str,
    user: UserPublic,
) -> Announcement:
    announcement = get_announcement(db, announcement_id)
    if announcement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found.")

    classroom = db.get(AcademicClass, announcement.class_id)
    if (
        classroom is None
        or classroom.teacher_id != user.email
        or announcement.teacher_id != user.email
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage announcements in your own classes.",
        )
    return announcement
