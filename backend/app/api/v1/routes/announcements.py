from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.routes.auth import UserPublic, _current_user_from_token, require_role
from app.database.session import get_db
from app.models.announcement import Announcement
from app.repositories.announcements import (
    delete_announcement,
    list_class_announcements,
    save_announcement,
)
from app.schemas.announcement import (
    AnnouncementCreate,
    AnnouncementPin,
    AnnouncementResponse,
    AnnouncementUpdate,
)
from app.services.announcements import get_accessible_class, get_teacher_announcement

router = APIRouter()


@router.post(
    "/classes/{class_id}/announcements",
    response_model=AnnouncementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_announcement(
    class_id: str,
    payload: AnnouncementCreate,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> Announcement:
    classroom = get_accessible_class(db, class_id, current_user)
    if classroom.is_archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Announcements cannot be added to archived classes.",
        )

    announcement = Announcement(
        class_id=class_id,
        teacher_id=current_user.email,
        title=payload.title,
        content=payload.content,
    )
    return save_announcement(db, announcement)


@router.get(
    "/classes/{class_id}/announcements",
    response_model=list[AnnouncementResponse],
)
def list_announcements(
    class_id: str,
    current_user: UserPublic = Depends(_current_user_from_token),
    db: Session = Depends(get_db),
) -> list[Announcement]:
    if current_user.role not in {"teacher", "student"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint requires a teacher or student account.",
        )
    get_accessible_class(db, class_id, current_user)
    return list_class_announcements(db, class_id)


@router.put(
    "/announcements/{announcement_id}",
    response_model=AnnouncementResponse,
)
def update_announcement(
    announcement_id: str,
    payload: AnnouncementUpdate,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> Announcement:
    announcement = get_teacher_announcement(db, announcement_id, current_user)
    announcement.title = payload.title
    announcement.content = payload.content
    return save_announcement(db, announcement)


@router.delete(
    "/announcements/{announcement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_announcement(
    announcement_id: str,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> None:
    announcement = get_teacher_announcement(db, announcement_id, current_user)
    delete_announcement(db, announcement)


@router.patch(
    "/announcements/{announcement_id}/pin",
    response_model=AnnouncementResponse,
)
def set_announcement_pin(
    announcement_id: str,
    payload: AnnouncementPin,
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db),
) -> Announcement:
    announcement = get_teacher_announcement(db, announcement_id, current_user)
    announcement.is_pinned = payload.is_pinned
    return save_announcement(db, announcement)
