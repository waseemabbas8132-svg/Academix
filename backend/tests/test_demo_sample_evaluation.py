from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from app.database.base import Base
from app.models import (
    AcademicClass,
    Assignment,
    AssignmentRubric,
    ClassMembership,
    EvaluationJob,
    RubricQuestion,
    Submission,
    UploadedFile,
)
from scripts.seed_demo_sample_evaluation import (
    DemoSampleError,
    seed_sample_evaluation,
)


@pytest.fixture
def sample_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with session_factory() as db:
        now = datetime.now(UTC)
        classroom = AcademicClass(
            id="demo-class",
            name="ACADEMIX TODAY DEMO - Science",
            section="A",
            subject="Science",
            class_code="DEMO1234",
            teacher_id="teacher@academix.app",
        )
        assignment = Assignment(
            id="demo-assignment",
            class_id=classroom.id,
            teacher_id="teacher@academix.app",
            title="DEMO: Water Cycle",
            instructions="Answer all three questions.",
            total_marks=Decimal("30.00"),
            due_date=now + timedelta(days=1),
            is_published=True,
        )
        rubric = AssignmentRubric(
            id="demo-rubric",
            assignment_id=assignment.id,
            updated_by="teacher@academix.app",
        )
        questions = [
            RubricQuestion(
                rubric_id=rubric.id,
                question_id=f"q{index}",
                position=index - 1,
                prompt=f"Demo question {index}.",
                max_marks=Decimal("10.00"),
            )
            for index in range(1, 4)
        ]
        submission = Submission(
            id="demo-submission",
            assignment_id=assignment.id,
            student_id="student@academix.app",
            submission_text=None,
            status="submitted",
            is_late=False,
            submitted_at=now,
            updated_at=now,
            created_at=now,
        )
        db.add_all(
            [
                classroom,
                assignment,
                rubric,
                *questions,
                submission,
                ClassMembership(
                    id="demo-membership",
                    class_id=classroom.id,
                    student_id="student@academix.app",
                ),
                UploadedFile(
                    id="demo-file",
                    submission_id=submission.id,
                    storage_key="demo-file-key",
                    original_filename="sample.docx",
                    content_type=(
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                    size_bytes=1,
                ),
            ]
        )
        db.commit()
        yield db
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_sample_evaluation_is_labeled_and_idempotent(sample_database) -> None:
    job_id, created = seed_sample_evaluation(sample_database, "demo-submission")

    assert created is True
    job = sample_database.get(EvaluationJob, job_id)
    assert job is not None
    assert job.status == "completed"
    assert job.evaluation is not None
    assert job.evaluation.review_status == "pending"
    assert job.evaluation.suggested_total == Decimal("23.00")
    assert job.evaluation.model_name == "DEMO SAMPLE - NOT AI GENERATED"
    assert len(job.extracted_answers) == 3
    assert all(answer.source == "demonstration_sample" for answer in job.extracted_answers)
    assert all(answer.ocr_confidence is None for answer in job.extracted_answers)
    assert any(
        item.kind == "demonstration_sample"
        and item.details["live_ai_ran"] is False
        for item in job.evaluation.feedback_items
    )

    sample_database.commit()
    repeated_id, repeated_created = seed_sample_evaluation(
        sample_database,
        "demo-submission",
    )
    assert (repeated_id, repeated_created) == (job_id, False)
    assert sample_database.scalar(select(func.count()).select_from(EvaluationJob)) == 1


def test_sample_evaluation_refuses_non_demo_records(sample_database) -> None:
    assignment = sample_database.get(Assignment, "demo-assignment")
    assert assignment is not None
    assignment.title = "Existing course assignment"
    sample_database.commit()

    with pytest.raises(DemoSampleError, match="dedicated Academix demo class"):
        seed_sample_evaluation(sample_database, "demo-submission")

    assert sample_database.scalar(select(func.count()).select_from(EvaluationJob)) == 0
