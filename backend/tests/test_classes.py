from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_teacher_creates_class() -> None:
    teacher_login = client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@academix.app", "password": "password123"},
    )
    token = teacher_login.json()["token"]

    response = client.post(
        "/api/v1/classes",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Biology 101",
            "section": "A",
            "subject": "Biology",
            "room": "Lab 2",
            "description": "Introductory biology course.",
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Biology 101"
    assert response.json()["teacher_id"] == "teacher@academix.app"
    assert response.json()["class_code"]


def test_teacher_lists_only_their_classes() -> None:
    teacher_login = client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@academix.app", "password": "password123"},
    )
    token = teacher_login.json()["token"]

    client.post(
        "/api/v1/classes",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Physics 202",
            "section": "B",
            "subject": "Physics",
        },
    )

    response = client.get("/api/v1/classes", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert len(response.json()) >= 1
    assert all(item["teacher_id"] == "teacher@academix.app" for item in response.json())


def test_teacher_cannot_modify_another_teachers_class() -> None:
    teacher_login = client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@academix.app", "password": "password123"},
    )
    token = teacher_login.json()["token"]
    class_response = client.post(
        "/api/v1/classes",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "History 1", "section": "C", "subject": "History"},
    )
    class_id = class_response.json()["id"]

    student_login = client.post(
        "/api/v1/auth/login",
        json={"email": "student@academix.app", "password": "password123"},
    )
    student_token = student_login.json()["token"]

    response = client.patch(
        f"/api/v1/classes/{class_id}",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"name": "Student edited class"},
    )

    assert response.status_code == 403


def test_student_joins_with_valid_code() -> None:
    teacher_login = client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@academix.app", "password": "password123"},
    )
    class_response = client.post(
        "/api/v1/classes",
        headers={"Authorization": f"Bearer {teacher_login.json()['token']}"},
        json={"name": "Chemistry 101", "section": "D", "subject": "Chemistry"},
    )
    class_code = class_response.json()["class_code"]

    student_login = client.post(
        "/api/v1/auth/login",
        json={"email": "student@academix.app", "password": "password123"},
    )
    response = client.post(
        "/api/v1/classes/join",
        headers={"Authorization": f"Bearer {student_login.json()['token']}"},
        json={"class_code": class_code},
    )

    assert response.status_code == 201
    assert response.json()["student_id"] == "student@academix.app"


def test_invalid_class_code_is_rejected() -> None:
    student_login = client.post(
        "/api/v1/auth/login",
        json={"email": "student@academix.app", "password": "password123"},
    )
    response = client.post(
        "/api/v1/classes/join",
        headers={"Authorization": f"Bearer {student_login.json()['token']}"},
        json={"class_code": "INVALID00"},
    )

    assert response.status_code == 404


def test_duplicate_enrollment_is_rejected() -> None:
    teacher_login = client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@academix.app", "password": "password123"},
    )
    class_response = client.post(
        "/api/v1/classes",
        headers={"Authorization": f"Bearer {teacher_login.json()['token']}"},
        json={"name": "Math 110", "section": "E", "subject": "Math"},
    )
    class_code = class_response.json()["class_code"]

    student_login = client.post(
        "/api/v1/auth/login",
        json={"email": "student@academix.app", "password": "password123"},
    )
    student_token = student_login.json()["token"]
    client.post(
        "/api/v1/classes/join",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"class_code": class_code},
    )

    response = client.post(
        "/api/v1/classes/join",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"class_code": class_code},
    )

    assert response.status_code == 400


def test_student_cannot_create_classes() -> None:
    student_login = client.post(
        "/api/v1/auth/login",
        json={"email": "student@academix.app", "password": "password123"},
    )
    response = client.post(
        "/api/v1/classes",
        headers={"Authorization": f"Bearer {student_login.json()['token']}"},
        json={"name": "Unauthorized", "section": "A", "subject": "Math"},
    )

    assert response.status_code == 403


def test_teacher_cannot_join_classes_as_student() -> None:
    teacher_login = client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@academix.app", "password": "password123"},
    )
    class_response = client.post(
        "/api/v1/classes",
        headers={"Authorization": f"Bearer {teacher_login.json()['token']}"},
        json={"name": "Art 301", "section": "F", "subject": "Art"},
    )
    response = client.post(
        "/api/v1/classes/join",
        headers={"Authorization": f"Bearer {teacher_login.json()['token']}"},
        json={"class_code": class_response.json()["class_code"]},
    )

    assert response.status_code == 403


def test_archived_class_cannot_be_joined() -> None:
    teacher_login = client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@academix.app", "password": "password123"},
    )
    token = teacher_login.json()["token"]
    class_response = client.post(
        "/api/v1/classes",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Archived Course", "section": "Z", "subject": "History"},
    )
    class_id = class_response.json()["id"]
    delete_response = client.delete(f"/api/v1/classes/{class_id}", headers={"Authorization": f"Bearer {token}"})
    assert delete_response.status_code == 204

    student_login = client.post(
        "/api/v1/auth/login",
        json={"email": "student@academix.app", "password": "password123"},
    )
    response = client.post(
        "/api/v1/classes/join",
        headers={"Authorization": f"Bearer {student_login.json()['token']}"},
        json={"class_code": class_response.json()["class_code"]},
    )

    assert response.status_code == 400


def test_student_can_leave_a_class() -> None:
    teacher_login = client.post(
        "/api/v1/auth/login",
        json={"email": "teacher@academix.app", "password": "password123"},
    )
    class_response = client.post(
        "/api/v1/classes",
        headers={"Authorization": f"Bearer {teacher_login.json()['token']}"},
        json={"name": "Leave Test", "section": "G", "subject": "Math"},
    )
    class_code = class_response.json()["class_code"]

    student_login = client.post(
        "/api/v1/auth/login",
        json={"email": "student@academix.app", "password": "password123"},
    )
    student_token = student_login.json()["token"]
    client.post(
        "/api/v1/classes/join",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"class_code": class_code},
    )

    response = client.delete(
        f"/api/v1/classes/{class_response.json()['id']}/leave",
        headers={"Authorization": f"Bearer {student_token}"},
    )

    assert response.status_code == 204
