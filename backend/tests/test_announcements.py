from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app

client = TestClient(app)


def _login(email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 200
    return response.json()["token"]


def _create_class(teacher_token: str) -> dict:
    response = client.post(
        "/api/v1/classes",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={"name": f"Stream {uuid4().hex[:8]}", "section": "A", "subject": "Science"},
    )
    assert response.status_code == 201
    return response.json()


def _create_announcement(teacher_token: str, class_id: str) -> dict:
    response = client.post(
        f"/api/v1/classes/{class_id}/announcements",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={"title": "Welcome", "content": "Welcome to the class."},
    )
    assert response.status_code == 201
    return response.json()


def test_teacher_can_create_edit_and_delete_announcement() -> None:
    token = _login("teacher@academix.app")
    classroom = _create_class(token)
    announcement = _create_announcement(token, classroom["id"])
    headers = {"Authorization": f"Bearer {token}"}

    updated = client.put(
        f"/api/v1/announcements/{announcement['id']}",
        headers=headers,
        json={"title": "Updated", "content": "Updated classroom information."},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated"

    deleted = client.delete(f"/api/v1/announcements/{announcement['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(
        f"/api/v1/classes/{classroom['id']}/announcements",
        headers=headers,
    ).json() == []


def test_teacher_cannot_manage_another_teachers_announcement() -> None:
    owner_token = _login("teacher@academix.app")
    classroom = _create_class(owner_token)
    announcement = _create_announcement(owner_token, classroom["id"])
    other_teacher = create_access_token(
        subject="other.teacher@academix.app",
        role="teacher",
    )

    response = client.put(
        f"/api/v1/announcements/{announcement['id']}",
        headers={"Authorization": f"Bearer {other_teacher}"},
        json={"title": "Not allowed", "content": "This update must be rejected."},
    )
    assert response.status_code == 403


def test_student_can_view_announcements_only_after_joining_class() -> None:
    teacher_token = _login("teacher@academix.app")
    classroom = _create_class(teacher_token)
    announcement = _create_announcement(teacher_token, classroom["id"])
    student_token = _login("student@academix.app")
    headers = {"Authorization": f"Bearer {student_token}"}

    denied = client.get(
        f"/api/v1/classes/{classroom['id']}/announcements",
        headers=headers,
    )
    assert denied.status_code == 403

    joined = client.post(
        "/api/v1/classes/join",
        headers=headers,
        json={"class_code": classroom["class_code"]},
    )
    assert joined.status_code == 201
    response = client.get(
        f"/api/v1/classes/{classroom['id']}/announcements",
        headers=headers,
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [announcement["id"]]
    assert response.json()[0]["teacher_id"] == "teacher@academix.app"


def test_student_cannot_create_announcement() -> None:
    teacher_token = _login("teacher@academix.app")
    classroom = _create_class(teacher_token)
    response = client.post(
        f"/api/v1/classes/{classroom['id']}/announcements",
        headers={"Authorization": f"Bearer {_login('student@academix.app')}"},
        json={"title": "Unauthorized", "content": "Students cannot post."},
    )
    assert response.status_code == 403


def test_teacher_can_pin_and_unpin_announcement() -> None:
    token = _login("teacher@academix.app")
    classroom = _create_class(token)
    announcement = _create_announcement(token, classroom["id"])
    headers = {"Authorization": f"Bearer {token}"}

    pinned = client.patch(
        f"/api/v1/announcements/{announcement['id']}/pin",
        headers=headers,
        json={"is_pinned": True},
    )
    assert pinned.status_code == 200
    assert pinned.json()["is_pinned"] is True

    unpinned = client.patch(
        f"/api/v1/announcements/{announcement['id']}/pin",
        headers=headers,
        json={"is_pinned": False},
    )
    assert unpinned.status_code == 200
    assert unpinned.json()["is_pinned"] is False


def test_announcement_title_and_content_cannot_be_blank() -> None:
    token = _login("teacher@academix.app")
    classroom = _create_class(token)
    response = client.post(
        f"/api/v1/classes/{classroom['id']}/announcements",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "  ", "content": "Message"},
    )
    assert response.status_code == 422
