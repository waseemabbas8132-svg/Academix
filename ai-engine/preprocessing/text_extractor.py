from __future__ import annotations

from io import BytesIO
from pathlib import PurePath
from typing import Protocol
from zipfile import BadZipFile

from PIL import Image

from academix_ai.contracts import ExtractedDocument, TextSegment
from preprocessing.handwritten_ocr import (
    HandwritingRecognizer,
    recognize_page,
)


class DocumentRejected(ValueError):
    pass


class OCRRecognizer(Protocol):
    model_name: str
    model_version: str

    def recognize(self, image: Image.Image): ...


def _extract_pdf(
    content: bytes,
    recognizer: OCRRecognizer,
    *,
    max_pages: int,
    low_confidence_threshold: float,
) -> ExtractedDocument:
    try:
        import fitz
    except ImportError as error:
        raise RuntimeError("PDF extraction requires PyMuPDF. Install the AI engine.") from error

    try:
        document = fitz.open(stream=content, filetype="pdf")
    except (fitz.FileDataError, fitz.EmptyFileError) as error:
        raise DocumentRejected('PDF file could not be decoded; no answer was inferred.') from error
    if document.needs_pass:
        document.close()
        raise DocumentRejected('Password-protected PDF requires manual review.')
    if document.page_count > max_pages:
        document.close()
        raise DocumentRejected(f"PDF has more than the configured {max_pages} pages.")

    segments: list[TextSegment] = []
    warnings: list[str] = []
    for page_index, page in enumerate(document):
        typed_text = page.get_text("text").strip()
        if typed_text:
            mixed = bool(page.get_images() or page.get_drawings() or page.first_annot)
            if mixed:
                warnings.append(f'Page {page_index + 1} has PDF text plus graphics/annotations; handwritten content may be missing. Check the original.')
            segments.append(
                TextSegment(
                    text=typed_text,
                    page_number=page_index + 1,
                    source="pdf_text",
                    needs_review=mixed,
                )
            )
            continue

        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = Image.open(BytesIO(pixmap.tobytes("png")))
        page_segments = recognize_page(
            image,
            recognizer,
            page_number=page_index + 1,
            low_confidence_threshold=low_confidence_threshold,
        )
        segments.extend(page_segments)
        if any(segment.needs_review for segment in page_segments):
            warnings.append(f"Page {page_index + 1} contains low-confidence OCR.")

    document.close()
    return ExtractedDocument(tuple(segments), tuple(warnings))


def _extract_docx(content: bytes) -> ExtractedDocument:
    try:
        from docx import Document
        from docx.opc.exceptions import PackageNotFoundError
    except ImportError as error:
        raise RuntimeError("DOCX extraction requires python-docx.") from error

    try:
        document = Document(BytesIO(content))
    except (BadZipFile, PackageNotFoundError, OSError, ValueError) as error:
        raise DocumentRejected(
            "DOCX file could not be decoded; no answer was inferred."
        ) from error
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs]
    paragraphs.extend(
        cell.text.strip()
        for table in document.tables
        for row in table.rows
        for cell in row.cells
    )
    text = "\n".join(value for value in paragraphs if value)
    if not text:
        return ExtractedDocument(
            (),
            ("DOCX contains no readable paragraph or table text; check the original.",),
        )
    return ExtractedDocument(
        (TextSegment(text=text, page_number=None, source="docx_text"),),
    )


def extract_document(
    filename: str,
    content: bytes,
    recognizer: OCRRecognizer,
    *,
    max_pages: int = 30,
    low_confidence_threshold: float = 0.6,
) -> ExtractedDocument:
    extension = PurePath(filename.replace("\\", "/")).suffix.lower()
    if extension in {".jpg", ".jpeg", ".png"}:
        try:
            image = Image.open(BytesIO(content))
            segments = recognize_page(
                image,
                recognizer,
                page_number=1,
                low_confidence_threshold=low_confidence_threshold,
            )
        except (OSError, ValueError) as error:
            raise DocumentRejected("Image file could not be decoded.") from error
        warnings = ("Image contains low-confidence OCR.",) if any(
            segment.needs_review for segment in segments
        ) else ()
        return ExtractedDocument(segments, warnings)
    if extension == ".pdf":
        return _extract_pdf(
            content,
            recognizer,
            max_pages=max_pages,
            low_confidence_threshold=low_confidence_threshold,
        )
    if extension == ".docx":
        return _extract_docx(content)
    if extension == ".doc":
        raise DocumentRejected(
            "Legacy .doc documents are not supported for automated extraction; "
            "please convert the file to .docx or PDF."
        )
    raise DocumentRejected("Unsupported document extension.")


def extract_submission(
    submission_text: str | None,
    files: list[tuple[str, bytes]],
    recognizer: OCRRecognizer,
    *,
    max_pages: int = 30,
    max_total_bytes: int = 30 * 1024 * 1024,
    low_confidence_threshold: float = 0.6,
) -> ExtractedDocument:
    if sum(len(content) for _, content in files) > max_total_bytes:
        raise DocumentRejected("Submission files exceed the configured processing limit.")

    segments: list[TextSegment] = []
    warnings: list[str] = []
    if submission_text and submission_text.strip():
        segments.append(
            TextSegment(
                text=submission_text.strip(),
                page_number=None,
                source="typed_submission",
            )
        )
    pages_used = 0
    for filename, content in files:
        remaining_pages = max_pages - pages_used
        if remaining_pages <= 0:
            raise DocumentRejected(f"Submission has more than the configured {max_pages} pages.")
        extracted = extract_document(
            filename,
            content,
            recognizer,
            max_pages=remaining_pages,
            low_confidence_threshold=low_confidence_threshold,
        )
        segments.extend(extracted.segments)
        warnings.extend(extracted.warnings)
        if PurePath(filename.replace('\\', '/')).suffix.lower() == '.pdf':
            import fitz
            with fitz.open(stream=content, filetype='pdf') as pdf:
                pages_used += pdf.page_count
        else:
            pages_used += max((segment.page_number or 1 for segment in extracted.segments), default=1)
    return ExtractedDocument(tuple(segments), tuple(warnings))
