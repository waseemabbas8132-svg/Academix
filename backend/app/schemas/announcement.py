from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("title", "content")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class AnnouncementUpdate(AnnouncementCreate):
    pass


class AnnouncementPin(BaseModel):
    is_pinned: bool


class AnnouncementResponse(BaseModel):
    id: str
    class_id: str
    teacher_id: str
    title: str
    content: str
    is_pinned: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
