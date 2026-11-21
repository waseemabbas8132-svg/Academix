import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import pymupdf
import torch
from PIL import Image
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

DEFAULT_PDF = Path("243742_EW_Assignment_03.pdf")
MODEL_NAME = "microsoft/trocr-base-handwritten"
OUTPUT_ROOT = Path(__file__).resolve().parent / "evaluation" / "ocr_test_results"
DPI = 300


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Segment handwritten PDF pages and optionally recognize each line with local TrOCR."
    )
    parser.add_argument(
        "pdf",
        nargs="?",
        type=Path,
        default=DEFAULT_PDF,
        help="PDF to process (default: 243742_EW_Assignment_03.pdf)",
    )
    parser.add_argument(
        "--segment-only",
        action="store_true",
        help="Run page preprocessing and segmentation without loading TrOCR.",
    )
    return parser.parse_args()


def threshold_page(gray: np.ndarray) -> np.ndarray:
    """Produce a binary mask where ink, including faint marks, is white."""
    min_dimension = min(gray.shape)
    block_size = min(75, min_dimension if min_dimension % 2 else min_dimension - 1)
    block_size = max(3, block_size)
    return cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block_size,
        9,
    )


def estimate_skew(binary: np.ndarray) -> float:
    """Estimate small page rotations from long near-horizontal/vertical strokes."""
    height, width = binary.shape
    edges = cv2.Canny(binary, 50, 150)
    segments = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 1800,
        threshold=max(30, min(height, width) // 20),
        minLineLength=max(50, min(height, width) // 12),
        maxLineGap=12,
    )
    if segments is None:
        return 0.0

    angles = []
    for (x1, y1, x2, y2) in segments[:, 0]:
        dx, dy = x2 - x1, y2 - y1
        length = float(np.hypot(dx, dy))
        angle = float(np.degrees(np.arctan2(dy, dx)))
        if length >= min(height, width) * 0.08 and abs(angle) <= 12:
            angles.append(angle)
        elif length >= min(height, width) * 0.08 and abs(abs(angle) - 90) <= 12:
            angles.append(angle - np.sign(angle) * 90)

    if not angles:
        return 0.0
    correction = -float(np.median(angles))
    return correction if 0.15 <= abs(correction) <= 12 else 0.0


def preprocess_page(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Denoise and enhance a page, then deskew and threshold it."""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    denoised = cv2.medianBlur(gray, 3)
    enhanced = cv2.createCLAHE(clipLimit=1.7, tileGridSize=(8, 8)).apply(denoised)
    binary = threshold_page(enhanced)
    angle = estimate_skew(binary)

    if angle:
        height, width = enhanced.shape
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
        enhanced = cv2.warpAffine(
            enhanced,
            matrix,
            (width, height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255,
        )
        binary = threshold_page(enhanced)
    return enhanced, binary, angle


def _component_records(
    mask: np.ndarray,
) -> tuple[list[dict[str, int]], list[dict[str, object]]]:
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    height, width = mask.shape
    accepted = []
    rejected = []
    for label in range(1, count):
        x, y, component_width, component_height, area = (
            int(value) for value in stats[label]
        )
        reason = None
        if area < 2 or component_width < 1 or component_height < 2:
            reason = "tiny_noise"
        elif (
            component_width > width * 0.72
            or component_height > height * 0.18
            or area > height * width * 0.003
        ):
            reason = "large_graphic_component"
        elif (
            max(component_width / max(component_height, 1), component_height / max(component_width, 1))
            > 18
            and max(component_width, component_height) > min(height, width) * 0.025
        ):
            reason = "long_thin_graphic_component"

        record = {
            "component_id": label,
            "x": x,
            "y": y,
            "width": component_width,
            "height": component_height,
            "area": area,
        }
        if reason:
            rejected.append({**record, "reason": reason})
        else:
            accepted.append(record)
    return accepted, rejected


def _row_bands(
    mask: np.ndarray, accepted: list[dict[str, int]]
) -> list[tuple[int, int, list[dict[str, int]]]]:
    if not accepted:
        return []

    _, width = mask.shape
    useful_heights = [
        item["height"] for item in accepted if item["area"] >= 10 and item["height"] >= 5
    ]
    typical_height = float(np.median(useful_heights)) if useful_heights else 12.0
    projection = mask.sum(axis=1).astype(np.float32)
    projection = np.convolve(projection, np.ones(3, dtype=np.float32), mode="same")
    active_rows = np.flatnonzero(
        projection >= int(255 * max(8, width * 0.015))
    )
    if active_rows.size == 0:
        return []
    max_gap = max(8, min(14, int(typical_height * 0.2)))
    bands = []
    start = previous = int(active_rows[0])
    for row in active_rows[1:]:
        row = int(row)
        if row - previous > max_gap:
            bands.append((start, previous + 1))
            start = row
        previous = row
    bands.append((start, previous + 1))

    result = []
    for y1, y2 in bands:
        components = [
            item
            for item in accepted
            if item["y"] < y2 + typical_height * 0.3
            and item["y"] + item["height"] > y1 - typical_height * 0.3
        ]
        if components:
            result.append((y1, y2, components))
    return result


def _split_horizontal_regions(
    components: list[dict[str, int]], page_width: int
) -> list[list[dict[str, int]]]:
    components = sorted(components, key=lambda item: item["x"])
    typical_height = float(np.median([item["height"] for item in components]))
    max_word_gap = max(40, int(typical_height * 3.2), int(page_width * 0.03))
    groups: list[list[dict[str, int]]] = []
    for item in components:
        if groups:
            previous_right = max(
                member["x"] + member["width"] for member in groups[-1]
            )
            if item["x"] - previous_right <= max_word_gap:
                groups[-1].append(item)
                continue
        groups.append([item])
    return groups


def _split_vertical_lines(
    components: list[dict[str, int]], binary: np.ndarray
) -> list[list[dict[str, int]]]:
    useful = [
        item for item in components if item["area"] >= 8 and item["height"] >= 4
    ]
    if not useful:
        return []

    _, page_width = binary.shape
    x1 = max(0, min(item["x"] for item in components))
    x2 = min(page_width, max(item["x"] + item["width"] for item in components))
    local_mask = binary[:, x1:x2]
    if local_mask.size == 0:
        return []

    typical_height = float(np.median([item["height"] for item in useful]))
    projection = local_mask.sum(axis=1).astype(np.float32)
    projection = np.convolve(projection, np.ones(3, dtype=np.float32), mode="same")
    active_rows = np.flatnonzero(
        projection >= int(255 * max(3, (x2 - x1) * 0.012))
    )
    if active_rows.size == 0:
        active_rows = np.asarray(
            [
                row
                for item in useful
                for row in range(item["y"], item["y"] + item["height"])
            ],
            dtype=np.int32,
        )
    if active_rows.size == 0:
        return []

    max_gap = max(8, min(14, int(typical_height * 0.2)))
    bands = []
    start = previous = int(active_rows[0])
    for row in active_rows[1:]:
        row = int(row)
        if row - previous > max_gap:
            bands.append((start, previous + 1))
            start = row
        previous = row
    bands.append((start, previous + 1))

    clusters = []
    for top, bottom in bands:
        selected = [
            item
            for item in components
            if item["y"] < bottom + typical_height * 0.2
            and item["y"] + item["height"] > top - typical_height * 0.2
        ]
        if selected:
            clusters.append(selected)
    return clusters


def detect_text_lines(
    binary: np.ndarray,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Group connected ink components into horizontal lines and diagram labels."""
    height, width = binary.shape
    horizontal_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(28, width // 45), 1)
    )
    vertical_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (1, max(28, height // 45))
    )
    horizontal_strokes = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
    vertical_strokes = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
    graphic_mask = cv2.bitwise_or(horizontal_strokes, vertical_strokes)

    # Remove only thin detected strokes; dilation breaks connectors without
    # erasing full character shapes that touch a box or arrow.
    connector_mask = cv2.dilate(
        graphic_mask, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    )
    text_mask = cv2.subtract(binary, connector_mask)
    edge_x = int(width * 0.035)
    footer_y = int(height * 0.965)
    text_mask[:, :edge_x] = 0
    text_mask[:, width - edge_x :] = 0
    text_mask[footer_y:, :] = 0
    accepted, rejected_components = _component_records(text_mask)
    row_bands = _row_bands(text_mask, accepted)

    candidates = []
    rejected_regions: list[dict[str, object]] = [
        {**item, "reason": item["reason"], "kind": "component"}
        for item in rejected_components
    ]
    for _, _, components in row_bands:
        for horizontal_group in _split_horizontal_regions(components, width):
            for group in _split_vertical_lines(horizontal_group, binary):
                x1 = min(item["x"] for item in group)
                y1 = min(item["y"] for item in group)
                x2 = max(item["x"] + item["width"] for item in group)
                y2 = max(item["y"] + item["height"] for item in group)
                span, line_height = x2 - x1, y2 - y1
                component_area = sum(item["area"] for item in group)
                reason = None

                if len(group) < 2 and span < max(14, width * 0.012):
                    reason = "isolated_mark"
                elif span < max(14, width * 0.008) or line_height < 4:
                    reason = "too_small_for_text"
                elif line_height > height * 0.12:
                    reason = "tall_graphic_region"
                elif component_area < max(5, width * 0.00002):
                    reason = "insufficient_ink"

                padding_x = max(8, int(width * 0.003))
                padding_y = max(6, int(height * 0.0025))
                box = (
                    max(0, x1 - padding_x),
                    max(0, y1 - padding_y),
                    min(width, x2 + padding_x),
                    min(height, y2 + padding_y),
                )

                if box[1] > height * 0.95 and box[0] > width * 0.65:
                    reason = "footer_watermark"
                elif box[0] < width * 0.05:
                    reason = "page_edge_graphic"
                elif (
                    box[2] > width * 0.93
                    and box[0] > width * 0.6
                    and box[2] - box[0] < width * 0.4
                ):
                    reason = "page_edge_graphic"

                if reason:
                    rejected_regions.append(
                        {
                            "bbox": list(box),
                            "component_count": len(group),
                            "reason": reason,
                            "kind": "region",
                        }
                    )
                    continue

                candidates.append(
                    {
                        "bbox": list(box),
                        "component_count": len(group),
                        "ink_area": component_area,
                        "region_type": "text_line",
                    }
                )

    candidates.sort(key=lambda item: (item["bbox"][1], item["bbox"][0]))
    unique_candidates = []
    seen_boxes = set()
    for candidate in candidates:
        box_key = tuple(candidate["bbox"])
        if box_key in seen_boxes:
            continue
        seen_boxes.add(box_key)
        unique_candidates.append(candidate)

    candidates = unique_candidates
    for index, candidate in enumerate(candidates, start=1):
        x1, y1, x2, y2 = candidate["bbox"]
        expanded = (
            max(0, x1 - 20),
            max(0, y1 - 20),
            min(width, x2 + 20),
            min(height, y2 + 20),
        )
        ex1, ey1, ex2, ey2 = expanded
        nearby_graphics = graphic_mask[ey1:ey2, ex1:ex2].copy()
        nearby_graphics[y1 - ey1 : y2 - ey1, x1 - ex1 : x2 - ex1] = 0
        if nearby_graphics.size and np.count_nonzero(nearby_graphics) > max(
            20, candidate["ink_area"] * 0.08
        ):
            candidate["region_type"] = "diagram_label"
        candidate["line_number"] = index

    return candidates, rejected_regions


def save_overlay(
    rgb: np.ndarray, candidates: list[dict[str, object]], path: Path
) -> None:
    overlay = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    for item in candidates:
        x1, y1, x2, y2 = item["bbox"]
        number = item["line_number"]
        cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 170, 0), 3)
        cv2.putText(
            overlay,
            str(number),
            (x1, max(22, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
    cv2.imwrite(str(path), overlay)


def write_reports(
    output_dir: Path,
    records: list[dict[str, object]],
    rejected: list[dict[str, object]],
    errors: list[str],
    page_count: int,
    candidate_count: int,
    valid_count: int,
) -> None:
    structured = {
        "dpi": DPI,
        "bbox_coordinates": "300-DPI pixels on the preprocessed, deskewed page",
        "pages_processed": page_count,
        "candidate_regions_detected": candidate_count,
        "valid_text_line_crops": valid_count,
        "rejected_blank_or_graphic_crops": len(rejected),
        "regions": records,
        "rejected_regions": rejected,
        "processing_errors": errors,
    }
    (output_dir / "structured_results.json").write_text(
        json.dumps(structured, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    text_lines = []
    for record in records:
        text_lines.append(
            "Page {page_number}, line {line_number} ({region_type}), "
            "bbox={bbox}: {text}".format(**record)
        )
    (output_dir / "extracted_text.txt").write_text(
        "\n".join(text_lines) + ("\n" if text_lines else ""), encoding="utf-8"
    )
    (output_dir / "rejected_regions.json").write_text(
        json.dumps(rejected, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "processing_errors.txt").write_text(
        "\n".join(errors) + ("\n" if errors else ""), encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    pdf_path = args.pdf
    output_dir = OUTPUT_ROOT / pdf_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    records: list[dict[str, object]] = []
    rejected_regions: list[dict[str, object]] = []
    pages_processed = candidate_count = valid_count = 0

    if not pdf_path.is_file():
        error = (
            f"PDF not found: {pdf_path.resolve()}\n"
            "Pass the PDF path as the first argument or run from its containing folder."
        )
        errors.append(error)
        write_reports(output_dir, records, rejected_regions, errors, 0, 0, 0)
        print(error)
        print(f"Processing error report: {(output_dir / 'processing_errors.txt').resolve()}")
        return 1

    processor = model = device = None
    if not args.segment_only:
        torch.set_num_threads(4)
        print("Loading the locally cached TrOCR checkpoint...")
        try:
            processor = TrOCRProcessor.from_pretrained(
                MODEL_NAME, local_files_only=True
            )
            model = VisionEncoderDecoderModel.from_pretrained(
                MODEL_NAME, local_files_only=True
            )
            model.eval()
            device = torch.device("cpu")
            model.to(device)
        except Exception as exc:
            errors.append(
                f"Could not load local model {MODEL_NAME}: {type(exc).__name__}: {exc}"
            )
            write_reports(output_dir, records, rejected_regions, errors, 0, 0, 0)
            print(errors[-1])
            print(
                f"Processing error report: {(output_dir / 'processing_errors.txt').resolve()}"
            )
            return 1

    try:
        document = pymupdf.open(pdf_path)
    except Exception as exc:
        errors.append(f"Could not open PDF: {type(exc).__name__}: {exc}")
        write_reports(output_dir, records, rejected_regions, errors, 0, 0, 0)
        print(errors[-1])
        return 1

    try:
        scale = DPI / 72
        for page_index, page in enumerate(document):
            page_number = page_index + 1
            prefix = f"page_{page_number:03d}"
            try:
                pixmap = page.get_pixmap(
                    matrix=pymupdf.Matrix(scale, scale),
                    colorspace=pymupdf.csRGB,
                    alpha=False,
                )
                rgb = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                    pixmap.height, pixmap.width, 3
                )
                Image.fromarray(rgb).save(output_dir / f"{prefix}_original.png")
                enhanced, binary, angle = preprocess_page(rgb)
                Image.fromarray(enhanced).save(output_dir / f"{prefix}_processed.png")
                Image.fromarray(binary).save(output_dir / f"{prefix}_threshold.png")
                candidates, rejected = detect_text_lines(binary)
                overlay_rgb = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)
                save_overlay(
                    overlay_rgb, candidates, output_dir / f"{prefix}_boxes.png"
                )
                pages_processed += 1
                candidate_count += len(candidates)
                rejected_regions.extend(
                    {"page_number": page_number, **item} for item in rejected
                )
                for candidate in candidates:
                    x1, y1, x2, y2 = candidate["bbox"]
                    line_number = candidate["line_number"]
                    crop = enhanced[y1:y2, x1:x2]
                    crop_mask = binary[y1:y2, x1:x2]
                    crop_path = output_dir / f"{prefix}_line_{line_number:03d}.png"
                    Image.fromarray(crop).save(crop_path)
                    candidate["page_number"] = page_number
                    candidate["deskew_degrees"] = angle
                    candidate["crop_path"] = crop_path.name

                    if crop.size == 0 or np.count_nonzero(crop_mask) < 5:
                        rejected_regions.append(
                            {
                                "page_number": page_number,
                                "line_number": line_number,
                                "bbox": list(candidate["bbox"]),
                                "kind": "crop",
                                "reason": "blank_crop",
                            }
                        )
                        continue

                    valid_count += 1
                    text = ""
                    if model is not None and processor is not None:
                        try:
                            line_image = Image.fromarray(
                                cv2.cvtColor(crop, cv2.COLOR_GRAY2RGB)
                            )
                            pixel_values = processor(
                                images=line_image, return_tensors="pt"
                            ).pixel_values.to(device)
                            with torch.inference_mode():
                                generated_ids = model.generate(
                                    pixel_values, max_new_tokens=96, num_beams=4
                                )
                            text = processor.batch_decode(
                                generated_ids, skip_special_tokens=True
                            )[0].strip()
                        except Exception as exc:
                            errors.append(
                                f"Page {page_number}, line {line_number} OCR failed: "
                                f"{type(exc).__name__}: {exc}"
                            )
                    candidate["text"] = text
                    records.append(candidate)
                    if args.segment_only:
                        print(
                            f"Page {page_number}, line {line_number}: "
                            f"{candidate['region_type']} bbox={candidate['bbox']}"
                        )
                    else:
                        print(
                            f"Page {page_number}, line {line_number}: "
                            f"{text or '[no text recognized]'}"
                        )
                print(
                    f"Page {page_number}: {len(candidates)} candidate(s), "
                    f"{sum(item.get('page_number') == page_number for item in records)} "
                    "valid crop(s), "
                    f"{len(rejected)} rejected component/region(s), "
                    f"deskew={angle:.2f} degrees"
                )
            except Exception as exc:
                errors.append(
                    f"Page {page_number} processing failed: {type(exc).__name__}: {exc}"
                )
                print(errors[-1])
    finally:
        document.close()

    write_reports(
        output_dir,
        records,
        rejected_regions,
        errors,
        pages_processed,
        candidate_count,
        valid_count,
    )
    print("========== TEST COMPLETE ==========")
    print(f"Pages processed: {pages_processed}")
    print(f"Candidate regions detected: {candidate_count}")
    print(f"Valid text-line crops: {valid_count}")
    print(f"Rejected blank/graphic components or regions: {len(rejected_regions)}")
    print("OCR output:")
    print((output_dir / "extracted_text.txt").read_text(encoding="utf-8"))
    print(f"Text file: {(output_dir / 'extracted_text.txt').resolve()}")
    print(f"Structured output: {(output_dir / 'structured_results.json').resolve()}")
    print(f"Processing errors: {len(errors)}")
    for error in errors:
        print(f"- {error}")
    print(f"Debug images and reports: {output_dir.resolve()}")
    if args.segment_only:
        print("Segmentation only: OCR was not run.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
