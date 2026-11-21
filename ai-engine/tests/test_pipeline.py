from io import BytesIO

import pytest
import fitz
from docx import Document
from PIL import Image, ImageDraw

from academix_ai.contracts import QuestionInput, QuestionScore
from evaluation.answer_evaluator import OllamaAnswerEvaluator, segment_answers
from evaluation.dataset_audit import write_writer_disjoint_manifest
from evaluation.similarity_checker import compare_answers
from inference.evaluation_pipeline import EvaluationPipeline, EvaluationRequest
from preprocessing.handwritten_ocr import OCRLine
from preprocessing.text_extractor import DocumentRejected, extract_document


class _Recognizer:
    model_name = "test-ocr"
    model_version = "test"

    def recognize(self, image: Image.Image) -> OCRLine:
        return OCRLine("recognized handwriting", 0.4)


class _Evaluator:
    model_name = "test-evaluator"
    model_version = "test"

    def evaluate(self, question: QuestionInput, answer: str) -> QuestionScore:
        return QuestionScore(
            question_id=question.question_id,
            suggested_marks=2,
            max_marks=question.max_marks,
            confidence=0.8,
            explanation="The response includes relevant evidence.",
            feedback="Add more detail.",
            evidence=(answer[:15],),
            needs_review=False,
        )


def test_handwritten_image_extraction_preserves_low_confidence_for_review() -> None:
    image = Image.new("RGB", (240, 80), "white")
    content = BytesIO()
    image.save(content, format="PNG")

    result = extract_document("answer.png", content.getvalue(), _Recognizer())

    assert result.segments
    assert all(segment.page_number == 1 for segment in result.segments)
    assert all(segment.needs_review for segment in result.segments)
    assert result.warnings


def test_pipeline_does_not_invent_marks_without_rubric() -> None:
    pipeline = EvaluationPipeline(recognizer=_Recognizer(), evaluator=_Evaluator())
    request = EvaluationRequest(
        submission_id="submission-1",
        submission_text="Typed response",
        files=[],
        questions=(),
        assignment_total_marks=10,
    )

    result = pipeline.evaluate(request)

    assert result.suggested_total is None
    assert result.needs_review is True
    assert result.metadata["preliminary_only"] is True


def test_multi_question_segmentation_does_not_guess_unlabeled_answers() -> None:
    questions = (
        QuestionInput("q1", "First question", 5),
        QuestionInput("q2", "Second question", 5),
    )

    answers, failed = segment_answers("A response without headings.", questions)

    assert answers == {}
    assert failed is True


def test_model_marks_require_verbatim_support_and_obey_maximum() -> None:
    question = QuestionInput("q1", "Explain", 5)
    supported = OllamaAnswerEvaluator._validate_output(
        {
            "marks": 3,
            "confidence": 0.8,
            "explanation": "Relevant.",
            "feedback": "Expand.",
            "evidence": ["supported evidence"],
            "needs_review": False,
        },
        question,
        "The answer contains supported evidence.",
    )
    assert supported.marks == 3
    assert supported.evidence == ("supported evidence",)

    unsupported = OllamaAnswerEvaluator._validate_output(
        {
            "marks": 3,
            "confidence": 0.8,
            "explanation": "Relevant.",
            "feedback": "Expand.",
            "evidence": ["not present"],
            "needs_review": False,
        },
        question,
        "Student response.",
    )
    assert unsupported.marks is None
    assert unsupported.needs_review is True

    with pytest.raises(ValueError, match="failed validation"):
        OllamaAnswerEvaluator._validate_output(
            {
                "marks": 6,
                "confidence": 0.8,
                "explanation": "Too many.",
                "feedback": "Review.",
                "evidence": ["supported evidence"],
            },
            question,
            "supported evidence",
        )


def test_manifest_excludes_duplicate_images_after_license_confirmation(tmp_path) -> None:
    raw_root = tmp_path / "raw"
    image_root = raw_root / "iam_words" / "words"
    ids = ("a01-000u-00-00", "a02-000u-00-00")
    for source_id in ids:
        writer, document, *_ = source_id.split("-")
        directory = image_root / writer / f"{writer}-{document}"
        directory.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (20, 20), "white")
        image.save(directory / f"{source_id}.png")
    annotation = raw_root / "iam_words" / "words.txt"
    annotation.write_text(
        "\n".join(
            f"{source_id} ok 154 0 0 20 20 N word"
            for source_id in ids
        ),
        encoding="utf-8",
    )
    output = tmp_path / "manifest.jsonl"

    with pytest.raises(ValueError, match="license"):
        write_writer_disjoint_manifest(
            raw_root,
            output,
            license_confirmed=False,
        )

    count = write_writer_disjoint_manifest(
        raw_root,
        output,
        license_confirmed=True,
    )

    assert count == 1
    assert output.exists()


def test_legacy_doc_is_explicitly_rejected() -> None:
    with pytest.raises(DocumentRejected, match="convert"):
        extract_document("answer.doc", b"legacy word document", _Recognizer())


def test_pdf_and_docx_text_extraction_preserve_pdf_page_numbers() -> None:
    pdf = fitz.open()
    for text in ("First page answer.", "Second page answer."):
        page = pdf.new_page()
        page.insert_text((72, 72), text)
    pdf_bytes = pdf.tobytes()
    pdf.close()

    pdf_result = extract_document("answers.pdf", pdf_bytes, _Recognizer())
    assert [(item.text.strip(), item.page_number) for item in pdf_result.segments] == [
        ("First page answer.", 1),
        ("Second page answer.", 2),
    ]

    document = Document()
    document.add_paragraph("Typed answer in a DOCX.")
    docx_bytes = BytesIO()
    document.save(docx_bytes)
    docx_result = extract_document("answers.docx", docx_bytes.getvalue(), _Recognizer())
    assert docx_result.text == "Typed answer in a DOCX."
    assert docx_result.segments[0].source == "docx_text"


def test_scanned_pdf_ocr_preserves_page_references_and_low_confidence_warnings() -> None:
    pdf = fitz.open()
    for blank in (True, False):
        image = Image.new("RGB", (240, 100), "white")
        if not blank:
            draw = ImageDraw.Draw(image)
            draw.rectangle((20, 20, 200, 30), fill="black")
            draw.rectangle((20, 50, 180, 60), fill="black")
        image_bytes = BytesIO()
        image.save(image_bytes, format="PNG")
        page = pdf.new_page()
        page.insert_image(page.rect, stream=image_bytes.getvalue())
    pdf_bytes = pdf.tobytes()
    pdf.close()

    result = extract_document("scanned.pdf", pdf_bytes, _Recognizer())

    assert {segment.page_number for segment in result.segments} == {1, 2}
    assert all(segment.source == "handwritten_ocr" for segment in result.segments)
    assert all(segment.needs_review for segment in result.segments)
    assert any("Page 1" in warning for warning in result.warnings)
    assert any("Page 2" in warning for warning in result.warnings)


def test_docx_table_content_empty_documents_and_corrupt_docx_are_explicit() -> None:
    table_document = Document()
    table = table_document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Question"
    table.cell(0, 1).text = "Answer"
    table.cell(1, 0).text = "q1"
    table.cell(1, 1).text = "Typed table answer."
    table_bytes = BytesIO()
    table_document.save(table_bytes)

    table_result = extract_document("table.docx", table_bytes.getvalue(), _Recognizer())
    assert "Typed table answer." in table_result.text
    assert table_result.segments[0].source == "docx_text"

    empty_bytes = BytesIO()
    Document().save(empty_bytes)
    empty_result = extract_document("empty.docx", empty_bytes.getvalue(), _Recognizer())
    assert empty_result.segments == ()
    assert empty_result.warnings

    with pytest.raises(DocumentRejected, match="could not be decoded"):
        extract_document("broken.docx", b"not a DOCX package", _Recognizer())


def test_similarity_is_assignment_input_bounded_and_investigation_only() -> None:
    shared_tail = " ".join(f"shared{index}" for index in range(30))
    answer = f"alpha beta gamma delta epsilon zeta eta theta {shared_tail}"
    peer_answer = f"one two three four five six seven eight {shared_tail}"
    findings = compare_answers(
        "current",
        answer,
        [("peer", peer_answer)],
        max_tokens=8,
    )

    assert findings == ()
