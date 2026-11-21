from __future__ import annotations

import argparse
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.ai_evaluation import (
    AIEvaluation,
    EvaluationFeedback,
    EvaluationJob,
    ExtractedAnswer,
    QuestionEvaluation,
)
from app.models.assignment import Assignment
from app.models.assignment_rubric import AssignmentRubric
from app.models.classroom import AcademicClass, ClassMembership
from app.models.submission import Submission

_TEACHER = "teacher@academix.app"
_STUDENT = "student@academix.app"
_SAMPLE_ANSWERS = (
    "The sun warms water in lakes and oceans. Some liquid changes into water vapor and rises into the air.",
    "When water vapor cools, it condenses into tiny droplets. Heavy droplets fall as precipitation, such as rain.",
    "Rain returns water to land. Runoff carries water into rivers and oceans, where the cycle begins again.",
)
_SAMPLE_MARKS = (Decimal("8.00"), Decimal("8.00"), Decimal("7.00"))
_SAMPLE_FEEDBACK = (
    "Good explanation of solar heating and the change from liquid water to vapor.",
    "Correctly distinguishes condensation from precipitation and gives rain as an example.",
    "Identifies collection and runoff; add more detail about how water returns to the oceans.",
)
_SAMPLE_NOTICE = (
    "DEMO/SAMPLE ONLY: These answer excerpts and marks were prepared for this "
    "demonstration. No OCR or AI model generated them."
)


class DemoSampleError(ValueError):
    pass


def seed_sample_evaluation(
    db: Session,
    submission_id: str,
) -> tuple[str, bool]:
    with db.begin():
        submission = db.scalar(
            select(Submission).where(Submission.id == submission_id)
        )
        if submission is None:
            raise DemoSampleError("Submission was not found.")
        assignment = db.get(Assignment, submission.assignment_id)
        if assignment is None:
            raise DemoSampleError("Submission assignment was not found.")
        classroom = db.get(AcademicClass, assignment.class_id)
        if (
            assignment.teacher_id != _TEACHER
            or classroom is None
            or classroom.teacher_id != _TEACHER
            or not assignment.title.startswith("DEMO:")
            or not classroom.name.startswith("ACADEMIX TODAY DEMO")
        ):
            raise DemoSampleError(
                "Sample evaluations are limited to the dedicated Academix demo class."
            )
        if not assignment.is_published:
            raise DemoSampleError("Publish the demo assignment before seeding its sample.")
        if submission.student_id != _STUDENT or submission.status != "submitted":
            raise DemoSampleError(
                "The submission must belong to the demo student and be submitted."
            )
        if submission.marks_obtained is not None:
            raise DemoSampleError("Refusing to replace an already graded submission.")
        if not submission.attachments or not any(
            Path(item.original_filename).suffix.lower()
            in {".png", ".jpg", ".jpeg", ".pdf", ".docx"}
            for item in submission.attachments
        ):
            raise DemoSampleError(
                "Upload a supported original assignment file before seeding the sample."
            )
        membership = db.scalar(
            select(ClassMembership).where(
                ClassMembership.class_id == assignment.class_id,
                ClassMembership.student_id == _STUDENT,
            )
        )
        if membership is None:
            raise DemoSampleError("The demo student must join the demo class first.")
        rubric = db.scalar(
            select(AssignmentRubric).where(
                AssignmentRubric.assignment_id == assignment.id
            )
        )
        if rubric is None:
            raise DemoSampleError("Save the assignment's three-question rubric first.")
        questions = list(rubric.questions)
        if (
            assignment.total_marks != Decimal("30.00")
            or len(questions) != 3
            or [question.question_id for question in questions]
            != ["q1", "q2", "q3"]
            or any(question.max_marks != Decimal("10.00") for question in questions)
        ):
            raise DemoSampleError(
                "The demo assignment must total 30 marks with q1, q2, and q3 worth 10 each."
            )

        existing_jobs = list(
            db.scalars(
                select(EvaluationJob)
                .where(EvaluationJob.submission_id == submission.id)
                .order_by(EvaluationJob.created_at)
            )
        )
        if existing_jobs:
            if (
                len(existing_jobs) == 1
                and existing_jobs[0].evaluation is not None
                and any(
                    item.kind == "demonstration_sample"
                    for item in existing_jobs[0].evaluation.feedback_items
                )
            ):
                return existing_jobs[0].id, False
            raise DemoSampleError(
                "An evaluation already exists for this submission; refusing to replace it."
            )

        now = datetime.now(UTC)
        job = EvaluationJob(
            submission_id=submission.id,
            requested_by=_TEACHER,
            source_updated_at=submission.updated_at,
            rubric_updated_at=rubric.updated_at,
            status="completed",
            attempt_count=0,
            started_at=now,
            completed_at=now,
            extracted_answers=[
                ExtractedAnswer(
                    segment_number=index,
                    page_number=None,
                    text=answer,
                    source="demonstration_sample",
                    ocr_confidence=None,
                    needs_review=True,
                )
                for index, answer in enumerate(_SAMPLE_ANSWERS, start=1)
            ],
        )
        total = sum(_SAMPLE_MARKS, Decimal("0.00"))
        job.evaluation = AIEvaluation(
            suggested_total=total,
            maximum_marks=Decimal("30.00"),
            confidence=0,
            explanation=(
                "Illustrative rubric-mapped example only; no OCR or AI model was run."
            ),
            feedback=_SAMPLE_NOTICE,
            model_name="DEMO SAMPLE - NOT AI GENERATED",
            model_version="not-run",
            review_status="pending",
            question_evaluations=[
                QuestionEvaluation(
                    question_id=question.question_id,
                    suggested_marks=mark,
                    maximum_marks=Decimal("10.00"),
                    confidence=0,
                    explanation="Illustrative teacher-authored sample feedback.",
                    feedback=feedback,
                    evidence=[answer],
                    needs_review=True,
                )
                for question, answer, mark, feedback in zip(
                    questions,
                    _SAMPLE_ANSWERS,
                    _SAMPLE_MARKS,
                    _SAMPLE_FEEDBACK,
                    strict=True,
                )
            ],
            feedback_items=[
                EvaluationFeedback(
                    kind="demonstration_sample",
                    message=_SAMPLE_NOTICE,
                    details={"live_ai_ran": False, "source": "manually_prepared_demo"},
                ),
                EvaluationFeedback(
                    kind="extraction_warning",
                    message=(
                        "Sample answer text is illustrative, not extracted from the "
                        "uploaded original. Compare the original file before grading."
                    ),
                    details={"ocr_ran": False},
                ),
            ],
        )
        db.add(job)
        db.flush()
        return job.id, True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed one clearly labeled, non-AI sample evaluation for the live demo."
    )
    parser.add_argument("--submission-id", required=True)
    args = parser.parse_args()
    try:
        with SessionLocal() as db:
            job_id, created = seed_sample_evaluation(db, args.submission_id)
    except DemoSampleError as error:
        parser.exit(2, f"ERROR: {error}\n")
    print(
        ("Created" if created else "Already present")
        + f" DEMO/SAMPLE evaluation job {job_id}; no AI or OCR was run."
    )


if __name__ == "__main__":
    main()
