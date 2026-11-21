from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.api.v1.routes import ai_evaluations
from app.core.security import create_access_token
from app.database.base import Base
from app.main import app
from app.models.ai_evaluation import AIEvaluation, EvaluationJob, QuestionEvaluation
from app.models.assignment import Assignment
from app.models.submission import Submission
from app.services import ai_evaluation_service
from conftest import TestSessionLocal, test_engine

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_ai_evaluation_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)


def _token(email: str = "teacher@academix.app", role: str | None = None) -> str:
    return create_access_token(subject=email, role=role) if role else client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    ).json()["token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_submission() -> tuple[str, str, str]:
    teacher_token = _token()
    classroom_response = client.post(
        "/api/v1/classes",
        headers=_headers(teacher_token),
        json={"name": f"AI class {uuid4().hex[:8]}", "section": "A", "subject": "Science"},
    )
    assert classroom_response.status_code == 201
    classroom = classroom_response.json()
    assignment_response = client.post(
        f"/api/v1/classes/{classroom['id']}/assignments",
        headers=_headers(teacher_token),
        json={
            "title": f"AI assignment {uuid4().hex[:8]}",
            "instructions": "Explain the answer.",
            "total_marks": "10",
            "due_date": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert assignment_response.status_code == 201
    assignment = assignment_response.json()
    published = client.patch(
        f"/api/v1/assignments/{assignment['id']}/publish",
        headers=_headers(teacher_token),
        json={"is_published": True},
    )
    assert published.status_code == 200
    student_token = _token("student@academix.app")
    joined = client.post(
        "/api/v1/classes/join",
        headers=_headers(student_token),
        json={"class_code": classroom["class_code"]},
    )
    assert joined.status_code == 201
    submitted = client.post(
        f"/api/v1/assignments/{assignment['id']}/submissions",
        headers=_headers(student_token),
        data={"submission_text": "The answer is supported by evidence."},
    )
    assert submitted.status_code == 201
    return teacher_token, student_token, submitted.json()["id"]


def test_rubric_is_teacher_owned_and_not_visible_to_students() -> None:
    teacher_token, student_token, submission_id = _create_submission()
    with TestSessionLocal() as db:
        submission = db.get(Submission, submission_id)
        assert submission is not None
        assignment_id = submission.assignment_id

    teacher_submissions = client.get(
        f"/api/v1/assignments/{assignment_id}/submissions",
        headers=_headers(teacher_token),
    )
    assert teacher_submissions.status_code == 200
    assert teacher_submissions.json()[0]["student_name"] == "Demo Student"
    student_submission = client.get(
        f"/api/v1/student/submissions/{submission_id}",
        headers=_headers(student_token),
    )
    assert student_submission.status_code == 200
    assert student_submission.json()["student_name"] is None

    rubric_input = {
        "model_answer": "Teacher-only answer key.",
        "teacher_instructions": "Award partial credit.",
        "questions": [
            {
                "question_id": "q1",
                "prompt": "Explain the concept.",
                "max_marks": "10",
                "model_answer": "A model explanation.",
                "acceptable_answers": [],
                "criteria": [
                    {
                        "description": "Explains the key concept",
                        "marks": "5",
                        "keywords": ["private-keyword"],
                        "concepts": ["private-concept"],
                    }
                ],
                "partial_credit_rules": ["Award partial credit for a correct definition."],
            }
        ],
    }
    saved = client.put(
        f"/api/v1/assignments/{assignment_id}/rubric",
        headers=_headers(teacher_token),
        json=rubric_input,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["model_answer"] == "Teacher-only answer key."

    another_teacher = _token("other.teacher@academix.app", "teacher")
    denied = client.get(
        f"/api/v1/assignments/{assignment_id}/rubric",
        headers=_headers(another_teacher),
    )
    assert denied.status_code == 403
    student_request = client.get(
        f"/api/v1/assignments/{assignment_id}/rubric",
        headers=_headers(student_token),
    )
    assert student_request.status_code == 403
    student_rubric = client.get(
        f"/api/v1/student/assignments/{assignment_id}/rubric",
        headers=_headers(student_token),
    )
    assert student_rubric.status_code == 200
    student_question = student_rubric.json()["questions"][0]
    assert student_question["prompt"] == "Explain the concept."
    assert student_question["criteria"] == [
        {"description": "Explains the key concept", "marks": "5"}
    ]
    assert student_question["partial_credit_rules"] == [
        "Award partial credit for a correct definition."
    ]
    assert "model_answer" not in student_question
    assert "acceptable_answers" not in student_question
    assert "keywords" not in student_question["criteria"][0]
    assert "teacher_instructions" not in student_rubric.json()

    nonmember_token = _token("another.student@academix.app", "student")
    nonmember_rubric = client.get(
        f"/api/v1/student/assignments/{assignment_id}/rubric",
        headers=_headers(nonmember_token),
    )
    assert nonmember_rubric.status_code == 403

    latest = client.get(
        f"/api/v1/submissions/{submission_id}/evaluations",
        headers=_headers(student_token),
    )
    assert latest.status_code == 403


def test_evaluation_request_is_deduplicated_and_teacher_only(monkeypatch) -> None:
    teacher_token, student_token, submission_id = _create_submission()
    monkeypatch.setattr(ai_evaluations, "submit_evaluation_job", lambda _: None)

    first = client.post(
        f"/api/v1/submissions/{submission_id}/evaluations",
        headers=_headers(teacher_token),
        json={},
    )
    assert first.status_code == 202, first.text
    second = client.post(
        f"/api/v1/submissions/{submission_id}/evaluations",
        headers=_headers(teacher_token),
        json={},
    )
    assert second.status_code == 202, second.text
    assert second.json()["id"] == first.json()["id"]

    student_request = client.post(
        f"/api/v1/submissions/{submission_id}/evaluations",
        headers=_headers(student_token),
        json={},
    )
    assert student_request.status_code == 403
    latest = client.get(
        f"/api/v1/submissions/{submission_id}/evaluations",
        headers=_headers(teacher_token),
    )
    assert latest.status_code == 200
    assert latest.json()["id"] == first.json()["id"]


def test_approval_is_provisional_until_teacher_publishes_official_grade() -> None:
    teacher_token, student_token, submission_id = _create_submission()
    with TestSessionLocal() as db:
        submission = db.get(Submission, submission_id)
        assert submission is not None
        assignment = db.get(Assignment, submission.assignment_id)
        assert assignment is not None
        job = EvaluationJob(
            submission_id=submission.id,
            requested_by="teacher@academix.app",
            source_updated_at=submission.updated_at,
            status="completed",
            attempt_count=1,
            completed_at=datetime.now(UTC),
        )
        db.add(job)
        db.flush()
        evaluation = AIEvaluation(
            job_id=job.id,
            suggested_total=Decimal("8"),
            maximum_marks=Decimal("10"),
            confidence=0.8,
            explanation="A suggestion only.",
            feedback="Review before release.",
            model_name="test-model",
            model_version="test-version",
            review_status="pending",
        )
        db.add(evaluation)
        db.flush()
        db.add(
            QuestionEvaluation(
                evaluation_id=evaluation.id,
                question_id="q1",
                suggested_marks=Decimal("8"),
                maximum_marks=Decimal("10"),
                confidence=0.8,
                explanation="Evidence was found.",
                feedback="Good explanation.",
                evidence=["supported by evidence"],
                needs_review=False,
            )
        )
        db.commit()
        evaluation_id = evaluation.id

    teacher_dashboard = client.get(
        "/api/v1/teacher/dashboard",
        headers=_headers(teacher_token),
    )
    assert teacher_dashboard.status_code == 200, teacher_dashboard.text
    assert teacher_dashboard.json()["statistics"]["pending_ai_evaluations"] == 1
    assert teacher_dashboard.json()["statistics"]["ai_evaluated_submissions"] == 1
    student_dashboard = client.get(
        "/api/v1/student/dashboard",
        headers=_headers(student_token),
    )
    assert student_dashboard.status_code == 200
    assert "pending_ai_evaluations" not in student_dashboard.json()["statistics"]

    before = client.get(
        f"/api/v1/student/submissions/{submission_id}",
        headers=_headers(student_token),
    )
    assert before.status_code == 200
    assert before.json()["marks_obtained"] is None
    assert "evaluation" not in before.json()

    saved = client.put(
        f"/api/v1/evaluations/{evaluation_id}/review",
        headers=_headers(teacher_token),
        json={
            "teacher_feedback": "Draft teacher feedback.",
            "question_marks": {"q1": "7"},
            "question_feedback": {"q1": "Add one more example."},
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["review_status"] == "pending"
    assert saved.json()["question_evaluations"][0]["teacher_marks"] == "7.00"
    assert any(
        item["kind"] == "teacher_question_feedback"
        and item["message"] == "Add one more example."
        for item in saved.json()["feedback_items"]
    )

    still_private = client.get(
        f"/api/v1/student/submissions/{submission_id}",
        headers=_headers(student_token),
    )
    assert still_private.json()["marks_obtained"] is None

    approved = client.post(
        f"/api/v1/evaluations/{evaluation_id}/approve",
        headers=_headers(teacher_token),
        json={
            "marks_obtained": "8",
            "teacher_feedback": "Reviewed and approved.",
            "question_marks": {"q1": "8"},
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["review_status"] == "approved"
    assert approved.json()["approved_marks"] == "8.00"
    approved_dashboard = client.get(
        "/api/v1/teacher/dashboard",
        headers=_headers(teacher_token),
    )
    assert approved_dashboard.json()["statistics"]["pending_ai_evaluations"] == 0
    assert approved_dashboard.json()["statistics"]["ai_evaluated_submissions"] == 1

    before_publication = client.get(
        f"/api/v1/student/submissions/{submission_id}",
        headers=_headers(student_token),
    )
    assert before_publication.status_code == 200
    assert before_publication.json()["marks_obtained"] is None
    assert "evaluation" not in before_publication.json()

    published = client.post(
        f"/api/v1/evaluations/{evaluation_id}/publish",
        headers=_headers(teacher_token),
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "graded"
    assert published.json()["marks_obtained"] == "8.00"
    repeated_publication = client.post(
        f"/api/v1/evaluations/{evaluation_id}/publish",
        headers=_headers(teacher_token),
    )
    assert repeated_publication.status_code == 200
    assert repeated_publication.json() == published.json()

    after_publication = client.get(
        f"/api/v1/student/submissions/{submission_id}",
        headers=_headers(student_token),
    )
    assert after_publication.status_code == 200
    assert after_publication.json()["marks_obtained"] == "8.00"
    assert after_publication.json()["teacher_feedback"] == "Reviewed and approved."
    assert "evaluation" not in after_publication.json()


def test_saved_ai_question_marks_are_assignment_and_question_bounded() -> None:
    teacher_token, _, submission_id = _create_submission()
    with TestSessionLocal() as db:
        submission = db.get(Submission, submission_id)
        assert submission is not None
        job = EvaluationJob(
            submission_id=submission_id,
            requested_by="teacher@academix.app",
            source_updated_at=submission.updated_at,
            status="completed",
            attempt_count=1,
        )
        db.add(job)
        db.flush()
        evaluation = AIEvaluation(
            job_id=job.id,
            suggested_total=Decimal("8"),
            maximum_marks=Decimal("10"),
            confidence=0.8,
            explanation="A suggestion only.",
            feedback="Review before release.",
            model_name="test-model",
            model_version="test-version",
            review_status="pending",
        )
        db.add(evaluation)
        db.flush()
        db.add(
            QuestionEvaluation(
                evaluation_id=evaluation.id,
                question_id="q1",
                suggested_marks=Decimal("8"),
                maximum_marks=Decimal("10"),
                confidence=0.8,
                explanation="Evidence was found.",
                feedback="Good explanation.",
                evidence=["supported by evidence"],
                needs_review=False,
            )
        )
        db.commit()
        evaluation_id = evaluation.id

    too_high = client.put(
        f"/api/v1/evaluations/{evaluation_id}/review",
        headers=_headers(teacher_token),
        json={"question_marks": {"q1": "11"}},
    )
    assert too_high.status_code == 422

    unknown_question = client.put(
        f"/api/v1/evaluations/{evaluation_id}/review",
        headers=_headers(teacher_token),
        json={"question_feedback": {"q2": "Unknown question."}},
    )
    assert unknown_question.status_code == 422


def test_teacher_cannot_approve_another_teachers_evaluation() -> None:
    teacher_token, _, submission_id = _create_submission()
    with TestSessionLocal() as db:
        submission = db.get(Submission, submission_id)
        assert submission is not None
        job = EvaluationJob(
            submission_id=submission.id,
            requested_by="teacher@academix.app",
            source_updated_at=submission.updated_at,
            status="completed",
            attempt_count=1,
        )
        db.add(job)
        db.flush()
        evaluation = AIEvaluation(
            job_id=job.id,
            suggested_total=Decimal("8"),
            maximum_marks=Decimal("10"),
            confidence=0.8,
            explanation="Suggestion.",
            feedback="Review.",
            model_name="test-model",
            model_version="test-version",
            review_status="pending",
        )
        db.add(evaluation)
        db.flush()
        db.add(
            QuestionEvaluation(
                evaluation_id=evaluation.id,
                question_id="q1",
                suggested_marks=Decimal("8"),
                maximum_marks=Decimal("10"),
                confidence=0.8,
                explanation="Evidence.",
                feedback="Review.",
                evidence=[],
                needs_review=False,
            )
        )
        db.commit()
        evaluation_id = evaluation.id

    other_teacher = _token("other.teacher@academix.app", "teacher")
    response = client.post(
        f"/api/v1/evaluations/{evaluation_id}/approve",
        headers=_headers(other_teacher),
        json={
            "marks_obtained": "8",
            "teacher_feedback": "Approved.",
            "question_marks": {"q1": "8"},
        },
    )
    assert response.status_code == 403


def test_worker_persists_extraction_and_provisional_question_results(monkeypatch) -> None:
    from academix_ai.contracts import (
        EvaluationResult,
        ExtractedDocument,
        QuestionScore,
        TextSegment,
    )
    from inference.evaluation_pipeline import EvaluationRequest

    teacher_token, _, submission_id = _create_submission()
    with TestSessionLocal() as db:
        submission = db.get(Submission, submission_id)
        assert submission is not None
        assignment_id = submission.assignment_id
    rubric = client.put(
        f"/api/v1/assignments/{assignment_id}/rubric",
        headers=_headers(teacher_token),
        json={
            "questions": [
                {
                    "question_id": "q1",
                    "prompt": "Explain the concept.",
                    "max_marks": "10",
                    "model_answer": "Supported explanation.",
                }
            ]
        },
    )
    assert rubric.status_code == 200
    with TestSessionLocal() as db:
        submission = db.get(Submission, submission_id)
        assert submission is not None
        job = EvaluationJob(
            submission_id=submission.id,
            requested_by="teacher@academix.app",
            source_updated_at=submission.updated_at,
            rubric_updated_at=datetime.fromisoformat(rubric.json()["updated_at"]),
            status="pending",
            attempt_count=0,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id

    class _Pipeline:
        def extract(self, request: EvaluationRequest) -> ExtractedDocument:
            assert request.questions[0].question_id == "q1"
            return ExtractedDocument(
                (TextSegment("Supported explanation.", 1, "typed_submission"),)
            )

        def evaluate(
            self,
            request: EvaluationRequest,
            extracted: ExtractedDocument,
        ) -> EvaluationResult:
            return EvaluationResult(
                questions=(
                    QuestionScore(
                        question_id="q1",
                        suggested_marks=8,
                        max_marks=10,
                        confidence=0.8,
                        explanation="Relevant answer evidence.",
                        feedback="Add detail.",
                        evidence=("Supported explanation.",),
                    ),
                ),
                suggested_total=8,
                maximum_marks=10,
                confidence=0.8,
                explanation="Provisional score.",
                feedback="Review before release.",
                needs_review=True,
                model_name="test-model",
                model_version="test-version",
            )

    monkeypatch.setattr(ai_evaluation_service, "create_pipeline", lambda: _Pipeline())
    monkeypatch.setattr(ai_evaluation_service, "SessionLocal", TestSessionLocal)
    ai_evaluation_service.process_evaluation_job(job_id)

    with TestSessionLocal() as db:
        saved_job = db.get(EvaluationJob, job_id)
        assert saved_job is not None
        assert saved_job.status == "completed"
        assert saved_job.evaluation is not None
        assert saved_job.evaluation.review_status == "pending"
        assert saved_job.evaluation.suggested_total == Decimal("8")
        assert len(saved_job.extracted_answers) == 1
        assert saved_job.evaluation.question_evaluations[0].suggested_marks == Decimal("8")

    student_token = _token("student@academix.app")
    official = client.get(
        f"/api/v1/student/submissions/{submission_id}",
        headers=_headers(student_token),
    )
    assert official.status_code == 200
    assert official.json()["marks_obtained"] is None


def test_failed_job_can_be_retried_without_exposing_model_error(monkeypatch) -> None:
    teacher_token, _, submission_id = _create_submission()
    monkeypatch.setattr(ai_evaluations, "submit_evaluation_job", lambda _: None)
    requested = client.post(
        f"/api/v1/submissions/{submission_id}/evaluations",
        headers=_headers(teacher_token),
        json={},
    )
    assert requested.status_code == 202
    with TestSessionLocal() as db:
        job = db.get(EvaluationJob, requested.json()["id"])
        assert job is not None
        job.status = "failed"
        job.error_summary = "PROCESSING_FAILED"
        job.attempt_count = 1
        db.commit()

    retried = client.post(
        f"/api/v1/evaluation-jobs/{requested.json()['id']}/retry",
        headers=_headers(teacher_token),
        json={},
    )
    assert retried.status_code == 202, retried.text
    assert retried.json()["status"] == "pending"
    assert retried.json()["error_summary"] is None


def test_stale_submission_evaluation_cannot_be_approved() -> None:
    teacher_token, student_token, submission_id = _create_submission()
    with TestSessionLocal() as db:
        submission = db.get(Submission, submission_id)
        assert submission is not None
        job = EvaluationJob(
            submission_id=submission.id,
            requested_by="teacher@academix.app",
            source_updated_at=submission.updated_at,
            status="completed",
            attempt_count=1,
        )
        db.add(job)
        db.flush()
        evaluation = AIEvaluation(
            job_id=job.id,
            suggested_total=Decimal("8"),
            maximum_marks=Decimal("10"),
            confidence=0.8,
            explanation="Suggestion.",
            feedback="Review.",
            model_name="test-model",
            model_version="test-version",
            review_status="pending",
        )
        db.add(evaluation)
        db.flush()
        db.add(
            QuestionEvaluation(
                evaluation_id=evaluation.id,
                question_id="q1",
                suggested_marks=Decimal("8"),
                maximum_marks=Decimal("10"),
                confidence=0.8,
                explanation="Evidence.",
                feedback="Review.",
                evidence=[],
                needs_review=False,
            )
        )
        submission.updated_at = datetime.now(UTC) + timedelta(seconds=5)
        db.commit()
        evaluation_id = evaluation.id

    response = client.post(
        f"/api/v1/evaluations/{evaluation_id}/approve",
        headers=_headers(teacher_token),
        json={
            "marks_obtained": "8",
            "teacher_feedback": "Reviewed.",
            "question_marks": {"q1": "8"},
        },
    )
    assert response.status_code == 409

    student_view = client.get(
        f"/api/v1/student/submissions/{submission_id}",
        headers=_headers(student_token),
    )
    assert student_view.status_code == 200
    assert student_view.json()["marks_obtained"] is None
