from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
import math
from pathlib import Path
from typing import Protocol

from PIL import Image

from academix_ai.contracts import TextSegment
from preprocessing.image_preprocessor import preprocess_image


class OCRUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class OCRLine:
    text: str
    confidence: float | None


class HandwritingRecognizer(Protocol):
    model_name: str
    model_version: str

    def recognize(self, image: Image.Image) -> OCRLine: ...


def _line_regions(image: Image.Image) -> list[Image.Image]:
    import numpy as np

    gray = image.convert("L")
    pixels = np.asarray(gray)
    foreground = pixels < 190
    row_density = foreground.sum(axis=1)
    minimum_density = max(3, int(gray.width * 0.002))
    active_rows = row_density >= minimum_density

    regions: list[Image.Image] = []
    start: int | None = None
    previous = -1
    for row, active in enumerate(active_rows):
        if active:
            if start is None:
                start = row
            previous = row
        elif start is not None and row - previous > max(12, gray.height // 120):
            top = max(0, start - 8)
            bottom = min(gray.height, previous + 9)
            if bottom - top >= 8:
                regions.append(gray.crop((0, top, gray.width, bottom)))
            start = None
    if start is not None:
        top = max(0, start - 8)
        bottom = min(gray.height, previous + 9)
        if bottom - top >= 8:
            regions.append(gray.crop((0, top, gray.width, bottom)))

    return regions or [gray]


class TrOCRHandwritingRecognizer:
    """Lazy local inference using Microsoft's pretrained handwritten TrOCR checkpoint."""

    def __init__(
        self,
        model_name: str = "microsoft/trocr-base-handwritten",
        *,
        local_files_only: bool = False,
    ) -> None:
        self.model_name = model_name
        self.model_version = model_name
        self.local_files_only = local_files_only

    @cached_property
    def _loaded(self):
        try:
            import torch
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        except ImportError as error:
            raise OCRUnavailable(
                "Handwriting OCR dependencies are missing. Install ai-engine[ocr]."
            ) from error

        try:
            processor = TrOCRProcessor.from_pretrained(
                self.model_name,
                local_files_only=self.local_files_only,
            )
            model = VisionEncoderDecoderModel.from_pretrained(
                self.model_name,
                local_files_only=self.local_files_only,
            )
            model.eval()
            return torch, processor, model
        except Exception as error:
            raise OCRUnavailable(
                f"Could not load local OCR model {self.model_name}."
            ) from error

    def recognize(self, image: Image.Image) -> OCRLine:
        torch, processor, model = self._loaded
        inputs = processor(images=image.convert("RGB"), return_tensors="pt").pixel_values
        with torch.inference_mode():
            output = model.generate(
                inputs,
                max_new_tokens=192,
                return_dict_in_generate=True,
                output_scores=True,
            )
        text = processor.batch_decode(output.sequences, skip_special_tokens=True)[0].strip()
        scores = output.scores or ()
        confidence = None
        if scores:
            token_confidences = [
                float(torch.softmax(step[0], dim=-1).max().item())
                for step in scores
            ]
            confidence = sum(token_confidences) / len(token_confidences)
        return OCRLine(text=text, confidence=confidence)


def recognize_page(
    image: Image.Image,
    recognizer: HandwritingRecognizer,
    *,
    page_number: int,
    low_confidence_threshold: float = 0.6,
) -> tuple[TextSegment, ...]:
    segments: list[TextSegment] = []
    if image_readability_warnings(image):
        # Near-uniform pixels establish insufficient readable contrast, not that
        # the student supplied no answer. Never ask the decoder to hallucinate it.
        return (TextSegment('', page_number, 'handwritten_ocr', None, True),)
    preprocessed = preprocess_image(image)
    for line in _line_regions(preprocessed):
        result = recognizer.recognize(line)
        confidence = result.confidence
        if (not isinstance(confidence, (int, float)) or isinstance(confidence, bool)
                or not math.isfinite(confidence) or not 0 <= confidence <= 1):
            confidence = None
        low_confidence = (
            not result.text.strip() or confidence is None
            or confidence < low_confidence_threshold
        )
        segments.append(
            TextSegment(
                text=result.text,
                page_number=page_number,
                source="handwritten_ocr",
                confidence=confidence,
                needs_review=low_confidence,
            )
        )
    return tuple(segments)


def image_readability_warnings(image: Image.Image) -> tuple[str, ...]:
    """A conservative near-uniform-image heuristic, not a legibility classifier."""
    low, high = image.convert('L').getextrema()
    return ('INSUFFICIENT_READABLE_CONTRAST',) if high - low <= 2 else ()
