from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app

client = TestClient(app)


def _login(email: str = "teacher@academix.app", role: str | None = None) -> str:
    if role is not None:
        return create_access_token(subject=email, role=role)
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
        json={
            "name": f"Assignment {uuid4().hex[:8]}",
            "section": "A",
            "subject": "Science",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_assignment(
    teacher_token: str,
    class_id: str,
    *,
    due_date: datetime | None = None,
) -> dict:
    response = client.post(
        f"/api/v1/classes/{class_id}/assignments",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={
            "title": f"Assignment {uuid4().hex[:8]}",
            "instructions": "Complete the attached work.",
            "total_marks": "20.00",
            "due_date": (due_date or datetime.now(UTC) + timedelta(days=2)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _join_class(student_token: str, class_code: str) -> None:
    response = client.post(
        "/api/v1/classes/join",
        headers={"Authorization": f"Bearer {student_token}"},
        json={"class_code": class_code},
    )
    assert response.status_code == 201, response.text


def _publish(teacher_token: str, assignment_id: str) -> None:
    response = client.patch(
        f"/api/v1/assignments/{assignment_id}/publish",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={"is_published": True},
    )
    assert response.status_code == 200, response.text


def _submit(student_token: str, assignment_id: str, *, files: list | None = None, text: str = "My work"):
    return client.post(
        f"/api/v1/assignments/{assignment_id}/submissions",
        headers={"Authorization": f"Bearer {student_token}"},
        data={"submission_text": text},
        files=files or [],
    )


def _pdf_file(name: str = "answer.pdf", content: bytes = b"%PDF-1.7\nAcademix test\n"):
    return ("files", (name, content, "application/pdf"))


def test_teacher_creates_edits_and_only_manages_own_assignments() -> None:
    teacher_token = _login()
    classroom = _create_class(teacher_token)
    assignment = _create_assignment(teacher_token, classroom["id"])
    headers = {"Authorization": f"Bearer {teacher_token}"}

    updated = client.put(
        f"/api/v1/assignments/{assignment['id']}",
        headers=headers,
        json={
            "title": "Revised work",
            "instructions": "Submit a concise report.",
            "total_marks": "25.00",
            "due_date": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        },
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Revised work"
    assert updated.json()["total_marks"] == "25.00"

    another_teacher = _login("other.teacher@academix.app", "teacher")
    denied = client.put(
        f"/api/v1/assignments/{assignment['id']}",
        headers={"Authorization": f"Bearer {another_teacher}"},
        json={
            "title": "Unauthorized edit",
            "instructions": "Not allowed.",
            "total_marks": "20.00",
            "due_date": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert denied.status_code == 403


def test_students_only_see_published_assignments_for_joined_classes() -> None:
    teacher_token = _login()
    classroom = _create_class(teacher_token)
    assignment = _create_assignment(teacher_token, classroom["id"])
    student_token = _login("student@academix.app")
    _join_class(student_token, classroom["class_code"])
    headers = {"Authorization": f"Bearer {student_token}"}

    assert client.get("/api/v1/student/assignments", headers=headers).json() == []
    _publish(teacher_token, assignment["id"])
    visible = client.get("/api/v1/student/assignments", headers=headers)
    assert visible.status_code == 200
    assert [item["id"] for item in visible.json()] == [assignment["id"]]

    another_student = _login("another.student@academix.app", "student")
    denied = client.get(
        f"/api/v1/assignments/{assignment['id']}",
        headers={"Authorization": f"Bearer {another_student}"},
    )
    assert denied.status_code == 403


def test_submission_upserts_once_supports_multiple_files_and_flags_late_work() -> None:
    teacher_token = _login()
    classroom = _create_class(teacher_token)
    assignment = _create_assignment(
        teacher_token,
        classroom["id"],
        due_date=datetime.now(UTC) - timedelta(minutes=1),
    )
    _publish(teacher_token, assignment["id"])
    student_one = _login("student@academix.app")
    student_two = _login("another.student@academix.app", "student")
    _join_class(student_one, classroom["class_code"])
    _join_class(student_two, classroom["class_code"])

    first = _submit(
        student_one,
        assignment["id"],
        files=[_pdf_file(), ("files", ("notes.png", b"\x89PNG\r\n\x1a\nimage", "image/png"))],
    )
    assert first.status_code == 201, first.text
    first_body = first.json()
    assert first_body["is_late"] is True
    assert len(first_body["attachments"]) == 2

    updated = _submit(
        student_one,
        assignment["id"],
        files=[_pdf_file("revision.pdf")],
        text="Updated work",
    )
    assert updated.status_code == 201
    assert updated.json()["id"] == first_body["id"]
    assert updated.json()["submission_text"] == "Updated work"
    assert len(updated.json()["attachments"]) == 1
    assert len(updated.json()["revisions"][0]["attachments"]) == 2
    assert len(updated.json()["revisions"]) == 1
    assert updated.json()["revisions"][0]["submission_text"] == "My work"

    second = _submit(student_two, assignment["id"])
    assert second.status_code == 201
    assert second.json()["id"] != first_body["id"]

    teacher_submissions = client.get(
        f"/api/v1/assignments/{assignment['id']}/submissions",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert teacher_submissions.status_code == 200
    assert len(teacher_submissions.json()) == 2


def test_draft_return_and_resubmission_preserve_attempt_history() -> None:
    teacher_token = _login()
    classroom = _create_class(teacher_token)
    assignment = _create_assignment(teacher_token, classroom["id"])
    _publish(teacher_token, assignment["id"])
    student_token = _login("student@academix.app")
    _join_class(student_token, classroom["class_code"])
    student_headers = {"Authorization": f"Bearer {student_token}"}

    draft = client.post(
        f"/api/v1/assignments/{assignment['id']}/submissions",
        headers=student_headers,
        data={"submission_text": "Early draft", "is_draft": "true"},
    )
    assert draft.status_code == 201
    assert draft.json()["status"] == "draft"

    submitted = _submit(student_token, assignment["id"], text="First attempt")
    assert submitted.status_code == 201
    submission_id = submitted.json()["id"]
    returned = client.post(
        f"/api/v1/submissions/{submission_id}/grade",
        headers={"Authorization": f"Bearer {teacher_token}"},
        json={"teacher_feedback": "Please add one supporting example."},
    )
    assert returned.status_code == 200
    assert returned.json()["status"] == "returned"

    revised = _submit(student_token, assignment["id"], text="Revised attempt")
    assert revised.status_code == 201
    assert revised.json()["id"] == submission_id
    assert revised.json()["status"] == "submitted"
    assert revised.json()["revisions"][0]["submission_text"] == "First attempt"
    assert revised.json()["revisions"][0]["teacher_feedback"] == (
        "Please add one supporting example."
    )


def test_failed_submission_upload_does_not_commit_submission() -> None:
    teacher_token = _login()
    classroom = _create_class(teacher_token)
    assignment = _create_assignment(teacher_token, classroom["id"])
    _publish(teacher_token, assignment["id"])
    student_token = _login("student@academix.app")
    _join_class(student_token, classroom["class_code"])
    headers = {"Authorization": f"Bearer {student_token}"}

    failed = client.post(
        f"/api/v1/assignments/{assignment['id']}/submissions",
        headers=headers,
        data={"submission_text": "Must not persist"},
        files=[_pdf_file(content=b"not a PDF")],
    )
    assert failed.status_code == 415

    submissions = client.get(
        "/api/v1/student/submissions",
        params={"assignment_id": assignment["id"]},
        headers=headers,
    )
    assert submissions.status_code == 200
    assert submissions.json() == []


def test_teacher_grading_checks_marks_and_student_sees_feedback() -> None:
    teacher_token = _login()
    classroom = _create_class(teacher_token)
    assignment = _create_assignment(teacher_token, classroom["id"])
    _publish(teacher_token, assignment["id"])
    student_token = _login("student@academix.app")
    _join_class(student_token, classroom["class_code"])
    submission = _submit(student_token, assignment["id"]).json()
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

    invalid_grade = client.post(
        f"/api/v1/submissions/{submission['id']}/grade",
        headers=teacher_headers,
        json={"marks_obtained": "21", "teacher_feedback": "Good effort."},
    )
    assert invalid_grade.status_code == 400

    graded = client.post(
        f"/api/v1/submissions/{submission['id']}/grade",
        headers=teacher_headers,
        json={"marks_obtained": "18.5", "teacher_feedback": "Clear explanation."},
    )
    assert graded.status_code == 200
    assert graded.json()["status"] == "graded"
    assert graded.json()["graded_at"] is not None

    student_headers = {"Authorization": f"Bearer {student_token}"}
    details = client.get(
        f"/api/v1/student/submissions/{submission['id']}",
        headers=student_headers,
    )
    assert details.status_code == 200
    assert details.json()["teacher_feedback"] == "Clear explanation."
    assert details.json()["marks_obtained"] == "18.50"

    locked = _submit(student_token, assignment["id"], text="Changed after grading")
    assert locked.status_code == 409


def test_assignment_files_validate_content_and_enforce_download_access() -> None:
    teacher_token = _login()
    classroom = _create_class(teacher_token)
    assignment = _create_assignment(teacher_token, classroom["id"])
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

    invalid = client.post(
        f"/api/v1/assignments/{assignment['id']}/attachments",
        headers=teacher_headers,
        files=[_pdf_file("malware.exe")],
    )
    assert invalid.status_code == 415

    mismatched = client.post(
        f"/api/v1/assignments/{assignment['id']}/attachments",
        headers=teacher_headers,
        files=[("files", ("wrong.pdf", b"\x89PNG\r\n\x1a\nimage", "application/pdf"))],
    )
    assert mismatched.status_code == 415

    oversized = client.post(
        f"/api/v1/assignments/{assignment['id']}/attachments",
        headers=teacher_headers,
        files=[_pdf_file(content=b"%PDF-" + b"x" * (1024 * 1024))],
    )
    assert oversized.status_code == 413

    uploaded = client.post(
        f"/api/v1/assignments/{assignment['id']}/attachments",
        headers=teacher_headers,
        files=[_pdf_file("../../assignment.pdf")],
    )
    assert uploaded.status_code == 201, uploaded.text
    file_record = uploaded.json()[0]
    assert file_record["filename"] == "assignment.pdf"
    teacher_download = client.get(file_record["download_url"], headers=teacher_headers)
    assert teacher_download.status_code == 200
    assert teacher_download.content.startswith(b"%PDF-")

    student_token = _login("student@academix.app")
    nonmember_download = client.get(
        file_record["download_url"],
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert nonmember_download.status_code == 404

    _join_class(student_token, classroom["class_code"])
    _publish(teacher_token, assignment["id"])
    student_download = client.get(
        file_record["download_url"],
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert student_download.status_code == 200


def test_students_cannot_read_other_students_submission_files() -> None:
    teacher_token = _login()
    classroom = _create_class(teacher_token)
    assignment = _create_assignment(teacher_token, classroom["id"])
    _publish(teacher_token, assignment["id"])
    student_one = _login("student@academix.app")
    student_two = _login("another.student@academix.app", "student")
    _join_class(student_one, classroom["class_code"])
    _join_class(student_two, classroom["class_code"])
    submission = _submit(
        student_one,
        assignment["id"],
        files=[_pdf_file()],
    ).json()

    response = client.get(
        submission["attachments"][0]["download_url"],
        headers={"Authorization": f"Bearer {student_two}"},
    )
    assert response.status_code == 404


def test_student_cannot_access_drafts_and_teacher_cannot_submit() -> None:
    teacher_token = _login()
    classroom = _create_class(teacher_token)
    assignment = _create_assignment(teacher_token, classroom["id"])
    student_token = _login("student@academix.app")
    _join_class(student_token, classroom["class_code"])

    denied_assignment = client.get(
        f"/api/v1/assignments/{assignment['id']}",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert denied_assignment.status_code == 404

    teacher_submission = _submit(teacher_token, assignment["id"])
    assert teacher_submission.status_code == 403

    draft = client.post(
        f"/api/v1/assignments/{assignment['id']}/submissions",
        headers={"Authorization": f"Bearer {student_token}"},
        data={"is_draft": "true"},
    )
    assert draft.status_code == 404


def test_teacher_can_archive_assignment_without_erasing_submission_history() -> None:
    teacher_token = _login()
    classroom = _create_class(teacher_token)
    assignment = _create_assignment(teacher_token, classroom["id"])
    _publish(teacher_token, assignment["id"])
    student_token = _login("student@academix.app")
    _join_class(student_token, classroom["class_code"])
    submission = _submit(student_token, assignment["id"]).json()

    deleted = client.delete(
        f"/api/v1/assignments/{assignment['id']}",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert deleted.status_code == 204
    student_submissions = client.get(
        "/api/v1/student/submissions",
        headers={"Authorization": f"Bearer {student_token}"},
    )
    assert any(item["id"] == submission["id"] for item in student_submissions.json())
