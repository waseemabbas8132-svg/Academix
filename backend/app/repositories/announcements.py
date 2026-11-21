from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.announcement import Announcement


def get_announcement(db: Session, announcement_id: str) -> Announcement | None:
    return db.get(Announcement, announcement_id)


def list_class_announcements(db: Session, class_id: str) -> list[Announcement]:
    return list(
        db.execute(
            select(Announcement)
            .where(Announcement.class_id == class_id)
            .order_by(Announcement.created_at.desc(), Announcement.id.desc())
        )
        .scalars()
        .all()
    )


def save_announcement(db: Session, announcement: Announcement) -> Announcement:
    db.add(announcement)
    db.commit()
    db.refresh(announcement)
    return announcement


def delete_announcement(db: Session, announcement: Announcement) -> None:
    db.delete(announcement)
    db.commit()
