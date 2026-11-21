from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE_ROOT = PROJECT_ROOT / "datasets" / "raw" / "BenthamDatasetR0-Images"
DEFAULT_XML_ROOT = PROJECT_ROOT / "datasets" / "raw" / "BenthamDatasetR0-GT" / "PAGE"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "datasets" / "processed" / "bentham"
PAGE_NAMESPACE = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2010-03-19"
NS = {"page": PAGE_NAMESPACE}

Point = tuple[float, float]
PolygonValue = int | float


@dataclass
class TextLine:
    line_id: str
    points: list[Point]
    original_points: list[list[PolygonValue]]
    average_y: float | None
    minimum_x: float | None
    transcription: str | None
    transcription_status: str | None
    polygon_status: str | None
    source_index: int


@dataclass
class TextRegion:
    region_id: str
    minimum_x: float | None
    lines: list[TextLine] = field(default_factory=list)
    ordering_height: float | None = None


@dataclass
class PageAnnotation:
    page_id: str
    image_filename: str
    regions: list[TextRegion]


class CropVerificationError(ValueError):
    """Raised when a saved crop is not a complete, decodable PNG."""


def _numeric_coordinate(raw_value: str | None) -> tuple[float, PolygonValue]:
    if raw_value is None:
        raise ValueError("missing coordinate")
    value = float(raw_value)
    if not math.isfinite(value):
        raise ValueError("non-finite coordinate")
    original: PolygonValue = int(value) if value.is_integer() else value
    return value, original


def _read_polygon(coords_element: ET.Element | None) -> tuple[list[Point], list[list[PolygonValue]], str | None]:
    if coords_element is None:
        return [], [], "missing_polygon"

    points: list[Point] = []
    originals: list[list[PolygonValue]] = []
    point_elements = coords_element.findall("./page:Point", NS)
    if point_elements:
        raw_points = [
            (point_element.get("x"), point_element.get("y"))
            for point_element in point_elements
        ]
    else:
        points_attribute = coords_element.get("points")
        if points_attribute is None:
            return [], [], "invalid_polygon"
        raw_points = []
        for raw_point in points_attribute.split():
            coordinates = raw_point.split(",")
            if len(coordinates) != 2:
                return [], [], "invalid_polygon"
            raw_points.append((coordinates[0], coordinates[1]))

    for raw_x, raw_y in raw_points:
        try:
            x, original_x = _numeric_coordinate(raw_x)
            y, original_y = _numeric_coordinate(raw_y)
        except (TypeError, ValueError):
            return [], [], "invalid_polygon"
        points.append((x, y))
        originals.append([original_x, original_y])

    if len(set(points)) < 3 or _polygon_area(points) == 0:
        return points, originals, "invalid_polygon"
    if _has_self_intersection(points):
        return points, originals, "invalid_polygon"
    return points, originals, None


def _polygon_area(points: list[Point]) -> float:
    if len(points) < 3:
        return 0.0
    return abs(
        sum(
            points[index][0] * points[(index + 1) % len(points)][1]
            - points[(index + 1) % len(points)][0] * points[index][1]
            for index in range(len(points))
        )
    ) / 2


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    first = _orientation(a, b, c)
    second = _orientation(a, b, d)
    third = _orientation(c, d, a)
    fourth = _orientation(c, d, b)
    return first * second < 0 and third * fourth < 0


def _has_self_intersection(points: list[Point]) -> bool:
    point_count = len(points)
    minimum_x = min(point[0] for point in points)
    maximum_x = max(point[0] for point in points)
    minimum_y = min(point[1] for point in points)
    maximum_y = max(point[1] for point in points)
    cell_width = max((maximum_x - minimum_x) / 32, 1.0)
    cell_height = max((maximum_y - minimum_y) / 32, 1.0)
    segments = []
    for index in range(point_count):
        first = points[index]
        second = points[(index + 1) % point_count]
        segments.append(
            (
                min(first[0], second[0]),
                max(first[0], second[0]),
                min(first[1], second[1]),
                max(first[1], second[1]),
                index,
                first,
                second,
            )
        )

    buckets: dict[tuple[int, int], list[int]] = {}
    for current in segments:
        min_x, max_x, min_y, max_y, current_index, a, b = current
        x_start = min(31, int((min_x - minimum_x) / cell_width))
        x_end = min(31, int((max_x - minimum_x) / cell_width))
        y_start = min(31, int((min_y - minimum_y) / cell_height))
        y_end = min(31, int((max_y - minimum_y) / cell_height))
        candidates: set[int] = set()
        for cell_x in range(x_start, x_end + 1):
            for cell_y in range(y_start, y_end + 1):
                candidates.update(buckets.get((cell_x, cell_y), ()))

        for previous_index in candidates:
            if (current_index - previous_index) % point_count in (1, point_count - 1):
                continue
            previous = segments[previous_index]
            if _segments_intersect(a, b, previous[5], previous[6]):
                return True

        for cell_x in range(x_start, x_end + 1):
            for cell_y in range(y_start, y_end + 1):
                buckets.setdefault((cell_x, cell_y), []).append(current_index)
    return False


def _read_transcription(line_element: ET.Element) -> tuple[str | None, str | None]:
    unicode_element = line_element.find("./page:TextEquiv/page:Unicode", NS)
    if unicode_element is None or unicode_element.text is None:
        return None, "missing_transcription"
    transcription = unicode_element.text
    if not transcription.strip():
        return transcription, "empty_transcription"
    return transcription, None


def parse_page_xml(xml_path: Path) -> PageAnnotation:
    """Parse PAGE XML using its 2010-03-19 namespace."""
    root = ET.parse(xml_path).getroot()
    page_element = root.find(".//page:Page", NS)
    if page_element is None:
        raise ValueError("PAGE XML has no Page element in the expected namespace.")

    image_filename = page_element.get("imageFilename", "")
    page_id = page_element.get("id") or Path(image_filename.replace("\\", "/")).stem or xml_path.stem
    regions: list[TextRegion] = []
    source_index = 0

    for region_index, region_element in enumerate(
        page_element.findall("./page:TextRegion", NS), start=1
    ):
        region_id = region_element.get("id") or f"region_{region_index}"
        region_points, _, _ = _read_polygon(region_element.find("./page:Coords", NS))
        region_minimum_x = min((point[0] for point in region_points), default=None)
        region = TextRegion(region_id=region_id, minimum_x=region_minimum_x)

        for line_index, line_element in enumerate(
            region_element.findall("./page:TextLine", NS), start=1
        ):
            source_index += 1
            line_id = line_element.get("id") or f"line_{line_index}"
            points, original_points, polygon_status = _read_polygon(
                line_element.find("./page:Coords", NS)
            )
            average_y = (
                sum(point[1] for point in points) / len(points) if points else None
            )
            minimum_x = min((point[0] for point in points), default=None)
            transcription, transcription_status = _read_transcription(line_element)
            region.lines.append(
                TextLine(
                    line_id=line_id,
                    points=points,
                    original_points=original_points,
                    average_y=average_y,
                    minimum_x=minimum_x,
                    transcription=transcription,
                    transcription_status=transcription_status,
                    polygon_status=polygon_status,
                    source_index=source_index,
                )
            )

        if region.minimum_x is None:
            line_x_values = [
                line.minimum_x for line in region.lines if line.minimum_x is not None
            ]
            region.minimum_x = min(line_x_values, default=None)
        regions.append(region)

    return PageAnnotation(
        page_id=page_id,
        image_filename=image_filename,
        regions=regions,
    )


def order_page_lines(
    annotation: PageAnnotation,
) -> list[tuple[int, int, TextRegion, TextLine]]:
    """Apply Bentham's documented bottom-up region and line ordering.

    TextLine average Y is computed from all of that line polygon's points.
    Lines sort by descending average Y; a line-X fallback resolves ties because
    a TextRegion's minimum X is identical for every line within that region.
    A region's ordering height is the average Y of its highest line (the first
    line in Bentham's descending-Y order). Regions also sort descending by that
    height, with minimum region X ascending for equal heights.
    """
    for region in annotation.regions:
        region.lines.sort(
            key=lambda line: (
                line.average_y is None,
                -(line.average_y if line.average_y is not None else 0.0),
                region.minimum_x if region.minimum_x is not None else math.inf,
                line.minimum_x if line.minimum_x is not None else math.inf,
                line.line_id,
                line.source_index,
            )
        )
        region.ordering_height = next(
            (line.average_y for line in region.lines if line.average_y is not None),
            None,
        )

    ordered_regions = sorted(
        annotation.regions,
        key=lambda region: (
            region.ordering_height is None,
            -(region.ordering_height if region.ordering_height is not None else 0.0),
            region.minimum_x if region.minimum_x is not None else math.inf,
            region.region_id,
        ),
    )

    ordered: list[tuple[int, int, TextRegion, TextLine]] = []
    for region_order, region in enumerate(ordered_regions, start=1):
        for line_order, line in enumerate(region.lines, start=1):
            ordered.append((region_order, line_order, region, line))
    return ordered


def _polygon_is_blank(masked_crop: Image.Image, mask: Image.Image) -> bool:
    grayscale = masked_crop.convert("L")
    histogram = grayscale.histogram(mask)
    total = sum(histogram)
    if total == 0:
        return True

    cumulative = 0
    percentile_90 = 255
    for value, count in enumerate(histogram):
        cumulative += count
        if cumulative >= total * 0.9:
            percentile_90 = value
            break
    ink_threshold = max(0, percentile_90 - 8)
    ink_count = sum(histogram[:ink_threshold])
    pixel_count = total // 255
    return ink_count < max(2, int(pixel_count * 0.0002))


def extract_polygon_crop(
    image: Image.Image,
    points: list[Point],
    padding: int = 4,
    *,
    polygon_validated: bool = False,
) -> tuple[Image.Image | None, str | None]:
    """Crop original pixels to a polygon mask and clamp the padded box."""
    if padding < 0:
        raise ValueError("padding must be non-negative")
    if len(set(points)) < 3 or _polygon_area(points) == 0:
        return None, "invalid_polygon"
    if not polygon_validated and _has_self_intersection(points):
        return None, "invalid_polygon"

    image_width, image_height = image.size
    left = max(0, math.floor(min(point[0] for point in points)) - padding)
    top = max(0, math.floor(min(point[1] for point in points)) - padding)
    right = min(image_width, math.ceil(max(point[0] for point in points)) + padding + 1)
    bottom = min(image_height, math.ceil(max(point[1] for point in points)) + padding + 1)
    if right <= left or bottom <= top:
        return None, "zero_sized_crop"

    source_crop = image.convert("RGB").crop((left, top, right, bottom))
    mask = Image.new("L", source_crop.size, 0)
    translated_points = [
        (round(x) - left, round(y) - top) for x, y in points
    ]
    ImageDraw.Draw(mask).polygon(translated_points, fill=255)
    if mask.getbbox() is None:
        return None, "zero_sized_crop"

    white_background = Image.new("RGB", source_crop.size, "white")
    white_background.paste(source_crop, mask=mask)
    if _polygon_is_blank(white_background, mask):
        return None, "blank_crop"
    return white_background, None


def _filename_token(value: str, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._-")
    return token or fallback


def _make_crop_filename(
    page_id: str,
    region_id: str,
    line_id: str,
    region_order: int,
    line_order: int,
    global_line_order: int,
) -> str:
    return (
        f"{_filename_token(page_id, 'page')}__"
        f"{_filename_token(region_id, 'region')}__"
        f"{_filename_token(line_id, 'line')}__"
        f"r{region_order:03d}_l{line_order:03d}_g{global_line_order:06d}.png"
    )


def _jsonable_polygon(points: list[list[PolygonValue]]) -> list[list[PolygonValue]]:
    return points


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary_path.open("w", encoding="utf-8", newline="\n") as output_file:
            for record in records:
                output_file.write(
                    json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                )
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _verify_png(path: Path, expected_size: tuple[int, int]) -> None:
    try:
        with Image.open(path) as image:
            if image.format != "PNG":
                raise CropVerificationError(
                    f"Expected PNG format, found {image.format!r}."
                )
            if image.size != expected_size:
                raise CropVerificationError(
                    f"Expected dimensions {expected_size}, found {image.size}."
                )
            image.verify()

        with Image.open(path) as image:
            image.load()
            if image.size != expected_size:
                raise CropVerificationError(
                    f"Decoded dimensions {image.size} do not match {expected_size}."
                )
    except CropVerificationError:
        raise
    except (OSError, SyntaxError, ValueError) as error:
        raise CropVerificationError(f"PNG verification failed: {error}") from error


def _save_verified_crop(crop: Image.Image, destination: Path) -> None:
    """Atomically save a crop, preserving valid existing files."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        try:
            _verify_png(destination, crop.size)
            return
        except CropVerificationError:
            pass

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w+b",
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            crop.save(temporary_file, format="PNG")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        _verify_png(temporary_path, crop.size)
        temporary_path.replace(destination)
        _verify_png(destination, crop.size)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _image_index(image_root: Path) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for path in sorted(image_root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_file():
            index.setdefault(path.name.casefold(), []).append(path)
    return index


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _rejection_record(
    *,
    reason: str,
    xml_path: Path,
    xml_root: Path,
    annotation: PageAnnotation,
    region_order: int,
    line_order: int,
    global_line_order: int,
    region: TextRegion,
    line: TextLine,
) -> dict[str, Any]:
    return {
        "reason": reason,
        "source_xml_filename": xml_path.name,
        "source_xml_path": _relative_path(xml_path, xml_root),
        "original_image_filename": annotation.image_filename,
        "page_id": annotation.page_id,
        "text_region_id": region.region_id,
        "text_line_id": line.line_id,
        "region_order": region_order,
        "line_order_within_region": line_order,
        "global_line_order": global_line_order,
        "original_polygon_coordinates": _jsonable_polygon(line.original_points),
        "transcription": line.transcription,
    }


def _validate_written_manifest(
    manifest_path: Path, output_root: Path
) -> tuple[int, list[str]]:
    errors = []
    records: list[dict[str, Any]] = []
    verified_crop_count = 0
    try:
        with manifest_path.open("r", encoding="utf-8") as manifest_file:
            for line_number, raw_line in enumerate(manifest_file, start=1):
                try:
                    value = json.loads(raw_line)
                except json.JSONDecodeError as error:
                    errors.append(f"Manifest line {line_number} is invalid JSON: {error}")
                    continue
                if not isinstance(value, dict):
                    errors.append(f"Manifest line {line_number} is not a JSON object.")
                    continue
                records.append(value)
    except OSError as error:
        return 0, [f"Could not read manifest: {error}"]

    filenames = [record.get("crop_filename") for record in records]
    if len(filenames) != len(set(filenames)):
        errors.append("Manifest contains duplicate crop filenames.")

    for record in records:
        relative_crop_path = record.get("crop_relative_path")
        transcription = record.get("transcription")
        if not isinstance(transcription, str) or not transcription.strip():
            errors.append(f"Manifest crop {record.get('crop_filename')} has empty transcription.")
        if not isinstance(relative_crop_path, str):
            errors.append(f"Manifest crop {record.get('crop_filename')} has no relative path.")
            continue
        crop_path = output_root / relative_crop_path
        try:
            _verify_png(
                crop_path,
                (record.get("crop_width"), record.get("crop_height")),
            )
        except CropVerificationError as error:
            errors.append(f"Manifest crop is missing or unreadable: {relative_crop_path}: {error}")
        else:
            verified_crop_count += 1
    return verified_crop_count, errors


def _ensure_output_is_not_raw(output_root: Path, project_root: Path) -> None:
    raw_root = (project_root / "datasets" / "raw").resolve()
    resolved_output = output_root.resolve()
    try:
        resolved_output.relative_to(raw_root)
    except ValueError:
        return
    raise ValueError(f"Refusing to write output inside raw dataset directory: {raw_root}")


def prepare_dataset(
    *,
    xml_root: Path,
    image_root: Path,
    output_root: Path,
    padding: int = 4,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Prepare Bentham line crops and metadata without changing source files."""
    if padding < 0:
        raise ValueError("padding must be non-negative")
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    if not xml_root.is_dir():
        raise FileNotFoundError(f"PAGE XML directory does not exist: {xml_root}")
    if not image_root.is_dir():
        raise FileNotFoundError(f"Page image directory does not exist: {image_root}")
    _ensure_output_is_not_raw(output_root, PROJECT_ROOT)

    xml_files = sorted(
        xml_root.rglob("*.xml"),
        key=lambda item: item.relative_to(xml_root).as_posix().casefold(),
    )
    if limit is not None:
        xml_files = xml_files[:limit]
    image_matches = _image_index(image_root)

    manifest_records: list[dict[str, Any]] = []
    rejected_records: list[dict[str, Any]] = []
    matching_issues: list[dict[str, Any]] = []
    xml_errors: list[dict[str, str]] = []
    rejection_counts: dict[str, int] = {}
    empty_transcription_count = 0
    missing_transcription_count = 0
    invalid_polygon_count = 0
    total_lines = 0
    matched_pages = 0
    missing_images = 0
    duplicate_image_matches = 0
    global_line_order = 0
    valid_crop_count = 0

    if not dry_run:
        (output_root / "line_images").mkdir(parents=True, exist_ok=True)

    for xml_path in xml_files:
        try:
            annotation = parse_page_xml(xml_path)
        except (ET.ParseError, OSError, ValueError) as error:
            xml_errors.append(
                {
                    "source_xml_filename": xml_path.name,
                    "source_xml_path": _relative_path(xml_path, xml_root),
                    "error": f"{type(error).__name__}: {error}",
                }
            )
            continue

        ordered_lines = order_page_lines(annotation)
        total_lines += len(ordered_lines)
        image_filename = annotation.image_filename.replace("\\", "/").rsplit("/", 1)[-1]
        matches = image_matches.get(image_filename.casefold(), [])
        if not matches:
            missing_images += 1
            page_match_reason = "missing_page_image"
            matching_issues.append(
                {
                    "source_xml_filename": xml_path.name,
                    "page_id": annotation.page_id,
                    "image_filename": annotation.image_filename,
                    "reason": page_match_reason,
                }
            )
            page_image_path = None
        elif len(matches) > 1:
            duplicate_image_matches += 1
            page_match_reason = "duplicate_page_image_match"
            matching_issues.append(
                {
                    "source_xml_filename": xml_path.name,
                    "page_id": annotation.page_id,
                    "image_filename": annotation.image_filename,
                    "reason": page_match_reason,
                    "matches": [_relative_path(path, image_root) for path in matches],
                }
            )
            page_image_path = None
        else:
            matched_pages += 1
            page_match_reason = None
            page_image_path = matches[0]

        page_image: Image.Image | None = None
        image_read_error = None
        if page_image_path is not None and not dry_run:
            try:
                with Image.open(page_image_path) as source_image:
                    page_image = source_image.convert("RGB")
            except (OSError, ValueError) as error:
                image_read_error = f"{type(error).__name__}: {error}"
                matching_issues.append(
                    {
                        "source_xml_filename": xml_path.name,
                        "page_id": annotation.page_id,
                        "image_filename": annotation.image_filename,
                        "reason": "image_read_error",
                        "error": image_read_error,
                    }
                )

        for region_order, line_order, region, line in ordered_lines:
            global_line_order += 1
            if line.transcription_status == "empty_transcription":
                empty_transcription_count += 1
            elif line.transcription_status == "missing_transcription":
                missing_transcription_count += 1
            if line.polygon_status is not None:
                invalid_polygon_count += 1

            reason = (
                page_match_reason
                or ("image_read_error" if image_read_error else None)
                or line.transcription_status
                or line.polygon_status
            )
            if reason is None and dry_run:
                valid_crop_count += 1
                continue

            crop: Image.Image | None = None
            if reason is None and page_image is not None:
                crop, reason = extract_polygon_crop(
                    page_image,
                    line.points,
                    padding,
                    polygon_validated=True,
                )

            if reason is not None:
                rejected_records.append(
                    _rejection_record(
                        reason=reason,
                        xml_path=xml_path,
                        xml_root=xml_root,
                        annotation=annotation,
                        region_order=region_order,
                        line_order=line_order,
                        global_line_order=global_line_order,
                        region=region,
                        line=line,
                    )
                )
                rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
                continue

            if crop is None:
                raise RuntimeError("Crop extraction returned no crop and no rejection reason.")

            valid_crop_count += 1
            crop_filename = _make_crop_filename(
                annotation.page_id,
                region.region_id,
                line.line_id,
                region_order,
                line_order,
                global_line_order,
            )
            crop_relative_path = f"line_images/{crop_filename}"
            if not dry_run:
                try:
                    _save_verified_crop(crop, output_root / crop_relative_path)
                except CropVerificationError as error:
                    rejection = _rejection_record(
                        reason="crop_verification_error",
                        xml_path=xml_path,
                        xml_root=xml_root,
                        annotation=annotation,
                        region_order=region_order,
                        line_order=line_order,
                        global_line_order=global_line_order,
                        region=region,
                        line=line,
                    )
                    rejection["error"] = str(error)
                    rejected_records.append(rejection)
                    rejection_counts["crop_verification_error"] = (
                        rejection_counts.get("crop_verification_error", 0) + 1
                    )
                    valid_crop_count -= 1
                    continue
                except (OSError, ValueError) as error:
                    rejection = _rejection_record(
                        reason="crop_write_error",
                        xml_path=xml_path,
                        xml_root=xml_root,
                        annotation=annotation,
                        region_order=region_order,
                        line_order=line_order,
                        global_line_order=global_line_order,
                        region=region,
                        line=line,
                    )
                    rejection["error"] = str(error)
                    rejected_records.append(rejection)
                    rejection_counts["crop_write_error"] = (
                        rejection_counts.get("crop_write_error", 0) + 1
                    )
                    valid_crop_count -= 1
                    continue

            manifest_records.append(
                {
                    "crop_filename": crop_filename,
                    "crop_relative_path": crop_relative_path,
                    "original_image_filename": annotation.image_filename,
                    "original_image_path": (
                        _relative_path(page_image_path, image_root)
                        if page_image_path is not None
                        else None
                    ),
                    "source_xml_filename": xml_path.name,
                    "source_xml_path": _relative_path(xml_path, xml_root),
                    "page_id": annotation.page_id,
                    "text_region_id": region.region_id,
                    "text_line_id": line.line_id,
                    "region_order": region_order,
                    "line_order_within_region": line_order,
                    "global_line_order": global_line_order,
                    "original_polygon_coordinates": _jsonable_polygon(
                        line.original_points
                    ),
                    "transcription": line.transcription,
                    "crop_width": crop.width,
                    "crop_height": crop.height,
                    "source_image_width": page_image.width if page_image else None,
                    "source_image_height": page_image.height if page_image else None,
                }
            )

    validation_errors: list[str] = []
    output_crop_count = 0
    if not dry_run:
        output_root.mkdir(parents=True, exist_ok=True)
        _write_jsonl(output_root / "manifest.jsonl", manifest_records)
        _write_jsonl(output_root / "rejected_lines.jsonl", rejected_records)
        output_crop_count, validation_errors = _validate_written_manifest(
            output_root / "manifest.jsonl", output_root
        )
        if output_crop_count != len(manifest_records):
            validation_errors.append(
                "Validated manifest record count differs from the in-memory manifest."
            )

    report: dict[str, Any] = {
        "xml_file_count": len(xml_files),
        "matched_page_image_count": matched_pages,
        "missing_image_count": missing_images,
        "duplicate_image_match_count": duplicate_image_matches,
        "total_annotated_text_lines": total_lines,
        "successfully_extracted_crops": output_crop_count,
        "eligible_lines_without_writing": valid_crop_count if dry_run else None,
        "rejected_lines": len(rejected_records),
        "rejection_counts_by_reason": dict(sorted(rejection_counts.items())),
        "empty_transcription_count": empty_transcription_count,
        "invalid_polygon_count": invalid_polygon_count,
        "missing_transcription_count": missing_transcription_count,
        "output_crop_count": output_crop_count,
        "padding_pixels": padding,
        "dry_run": dry_run,
        "xml_parse_error_count": len(xml_errors),
        "xml_parse_errors": xml_errors,
        "image_matching_issues": matching_issues,
        "manifest_validation_errors": validation_errors,
    }

    if not dry_run:
        output_root.mkdir(parents=True, exist_ok=True)
        report_path = output_root / "dataset_report.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report


def _non_negative_integer(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be an integer") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract transcription-aligned Bentham PAGE text-line crops."
    )
    parser.add_argument("--limit", type=_non_negative_integer)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--padding", type=_non_negative_integer, default=4)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = prepare_dataset(
            xml_root=DEFAULT_XML_ROOT,
            image_root=DEFAULT_IMAGE_ROOT,
            output_root=args.output,
            padding=args.padding,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, OSError, ValueError) as error:
        print(f"Dataset preparation failed: {error}", file=sys.stderr)
        return 1

    print("========== Bentham dataset preparation ==========")
    print(f"XML files processed: {report['xml_file_count']}")
    print(f"Matched page images: {report['matched_page_image_count']}")
    print(f"Missing images: {report['missing_image_count']}")
    print(f"Duplicate image matches: {report['duplicate_image_match_count']}")
    print(f"Annotated text lines: {report['total_annotated_text_lines']}")
    if args.dry_run:
        print(
            "Annotation-valid candidates (pixels not checked or written): "
            f"{report['eligible_lines_without_writing']}"
        )
    else:
        print(f"Successfully extracted crops: {report['successfully_extracted_crops']}")
    print(f"Rejected lines: {report['rejected_lines']}")
    print(f"Rejections by reason: {report['rejection_counts_by_reason']}")
    print(f"Empty transcriptions: {report['empty_transcription_count']}")
    print(f"Missing transcriptions: {report['missing_transcription_count']}")
    print(f"Invalid polygons: {report['invalid_polygon_count']}")
    print(f"XML parse errors: {report['xml_parse_error_count']}")
    print(f"Manifest validation errors: {len(report['manifest_validation_errors'])}")
    if args.dry_run:
        print("Dry run: no output files or crops were written.")
    else:
        print(f"Output directory: {args.output.resolve()}")
    has_errors = any(
        (
            report["missing_image_count"],
            report["duplicate_image_match_count"],
            report["xml_parse_error_count"],
            report["manifest_validation_errors"],
        )
    )
    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
