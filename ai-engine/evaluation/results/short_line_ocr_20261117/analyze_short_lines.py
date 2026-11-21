from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import ctypes
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont, ImageOps

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.analyze_trocr_errors import align_errors
from evaluation.evaluate_trocr_baseline import calculate_metrics, normalize_text

RESULTS = PROJECT_ROOT / "evaluation" / "results"
OUTPUT = Path(__file__).resolve().parent
VALIDATION_MANIFEST = PROJECT_ROOT / "datasets" / "manifests" / "bentham" / "validation.jsonl"
BEST_PREDICTIONS = (
    RESULTS
    / "trocr_preprocessing_full_20261116"
    / "existing_validation_predictions.jsonl"
)
IMAGE_DIAGNOSTICS = (
    RESULTS
    / "trocr_preprocessing_full_20261116"
    / "validation_image_diagnostics.json"
)
SCREEN_DIR = RESULTS / "trocr_preprocessing_screen_20261116"
EXPECTED_SHORT_LINES = 161
RAM_GUARD_GIB = 2.5
SHEET_CAPACITY = 32
TILE_SIZE = (430, 142)


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _memory_status() -> dict:
    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("length", ctypes.c_ulong),
            ("memory_load", ctypes.c_ulong),
            ("total_physical", ctypes.c_ulonglong),
            ("available_physical", ctypes.c_ulonglong),
            ("total_page_file", ctypes.c_ulonglong),
            ("available_page_file", ctypes.c_ulonglong),
            ("total_virtual", ctypes.c_ulonglong),
            ("available_virtual", ctypes.c_ulonglong),
            ("available_extended_virtual", ctypes.c_ulonglong),
        ]

    memory = MemoryStatus()
    memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise OSError("GlobalMemoryStatusEx failed.")
    return {
        "physical_ram_gib": memory.total_physical / 2**30,
        "available_ram_gib": memory.available_physical / 2**30,
        "memory_load_percent": memory.memory_load,
    }


def _write_json_exclusive(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as destination:
        json.dump(value, destination, ensure_ascii=False, indent=2)
        destination.write("\n")


def _write_jsonl_exclusive(path: Path, records: list[dict]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as destination:
        for record in records:
            destination.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            )


def _paired_changes(original: list[dict], candidate: list[dict]) -> dict:
    if len(original) != len(candidate):
        raise ValueError("Paired prediction sample counts differ.")
    counts = Counter()
    for left, right in zip(original, candidate):
        if (
            left["crop_relative_path"] != right["crop_relative_path"]
            or left["reference_raw"] != right["reference_raw"]
        ):
            raise ValueError("Candidate predictions are not aligned to the same references.")
        reference = normalize_text(left["reference_raw"])
        old_prediction = normalize_text(left["prediction_raw"] or "")
        new_prediction = normalize_text(right["prediction_raw"] or "")
        old_errors = len(align_errors(reference, old_prediction))
        new_errors = len(align_errors(reference, new_prediction))
        counts[
            "improved" if new_errors < old_errors else
            "regressed" if new_errors > old_errors else
            "unchanged"
        ] += 1
    return dict(counts)


def _make_contact_sheets(rows: list[dict], crop_root: Path) -> list[str]:
    font = ImageFont.load_default()
    filenames = []
    for start in range(0, len(rows), SHEET_CAPACITY):
        chunk = rows[start : start + SHEET_CAPACITY]
        columns = 4
        tile_width, tile_height = TILE_SIZE
        sheet = Image.new(
            "RGB",
            (columns * tile_width, ((len(chunk) + columns - 1) // columns) * tile_height),
            "white",
        )
        draw = ImageDraw.Draw(sheet)
        for offset, row in enumerate(chunk):
            x = (offset % columns) * tile_width
            y = (offset // columns) * tile_height
            crop_path = crop_root / row["crop_relative_path"]
            with Image.open(crop_path) as source:
                source.load()
                thumbnail = source.convert("RGB")
            thumbnail.thumbnail((tile_width - 12, 72), Image.Resampling.LANCZOS)
            image_x = x + (tile_width - thumbnail.width) // 2
            sheet.paste(thumbnail, (image_x, y + 3))
            label = (
                f"#{row['sample_index']:03d} {crop_path.name[:46]}\n"
                f"REF: {row['reference_normalized'][:54]}\n"
                f"HYP: {row['prediction_normalized'][:54]}"
            )
            draw.text((x + 5, y + 79), label, fill="black", font=font, spacing=2)
            thumbnail.close()
        filename = f"short_line_contact_sheet_{start // SHEET_CAPACITY + 1:02d}.png"
        with (OUTPUT / filename).open("xb") as file_object:
            sheet.save(file_object, format="PNG")
        sheet.close()
        filenames.append(filename)
    return filenames


def main() -> None:
    memory = _memory_status()
    manifest = _read_jsonl(VALIDATION_MANIFEST)
    predictions = _read_jsonl(BEST_PREDICTIONS)
    diagnostics = json.loads(IMAGE_DIAGNOSTICS.read_text(encoding="utf-8"))
    if len(manifest) != 1197 or len(predictions) != 1197 or len(diagnostics) != 1197:
        raise ValueError("Expected complete saved validation artifacts with 1,197 rows.")

    diagnostic_by_path = {
        item["crop_relative_path"]: item for item in diagnostics
    }
    manifest_by_path = {}
    for row in manifest:
        path = row["crop_relative_path"]
        if path in manifest_by_path:
            raise ValueError(f"Duplicate validation crop path: {path}")
        manifest_by_path[path] = row

    rows = []
    for index, prediction in enumerate(predictions):
        path = prediction["crop_relative_path"]
        record = manifest_by_path.get(path)
        diagnostic = diagnostic_by_path.get(path)
        if record is None or diagnostic is None:
            raise ValueError(f"Missing validation record or image diagnostic: {path}")
        reference = normalize_text(record["transcription"])
        if not 1 <= len(reference) <= 10:
            continue
        if prediction["reference_raw"] != record["transcription"]:
            raise ValueError(f"Prediction reference differs from manifest: {path}")
        predicted = (
            normalize_text(prediction["prediction_raw"])
            if prediction["status"] == "ok"
            else ""
        )
        char_edits = align_errors(reference, predicted)
        word_edits = align_errors(reference.split(), predicted.split())
        space_edits = [
            edit
            for edit in char_edits
            if edit["reference"] == " " or edit["prediction"] == " "
        ]
        punctuation_edits = [
            edit
            for edit in char_edits
            if any(
                value is not None
                and not (value.isalnum() or value.isspace())
                for value in (edit["reference"], edit["prediction"])
            )
        ]
        rows.append(
            {
                "sample_index": index,
                "crop_relative_path": path,
                "page_id": record["page_id"],
                "reference_raw": record["transcription"],
                "prediction_raw": prediction["prediction_raw"],
                "reference_normalized": reference,
                "prediction_normalized": predicted,
                "status": prediction["status"],
                "exact_match": prediction["status"] == "ok" and reference == predicted,
                "reference_characters": len(reference),
                "reference_words": len(reference.split()),
                "prediction_characters": len(predicted),
                "prediction_words": len(predicted.split()),
                "character_edits": char_edits,
                "word_edits": word_edits,
                "character_error_count": len(char_edits),
                "word_error_count": len(word_edits),
                "spacing_error_count": len(space_edits),
                "punctuation_error_count": len(punctuation_edits),
                "crop_width": diagnostic["width"],
                "crop_height": diagnostic["height"],
                "crop_aspect_ratio": diagnostic["aspect_ratio"],
                "dark_pixel_fraction": diagnostic["dark_pixel_fraction"],
                "laplacian_variance": diagnostic["laplacian_variance"],
                "dark_pixels_at_outer_edge": diagnostic["edge_dark_pixels"],
                "possible_low_resolution": (
                    diagnostic["width"] < 64 or diagnostic["height"] < 48
                ),
                "possible_edge_contact": diagnostic["edge_dark_pixels"] > 0,
                "reference_has_annotation_marker": any(
                    marker in reference for marker in ("<gap/>", "_", "=")
                ),
            }
        )
    if len(rows) != EXPECTED_SHORT_LINES:
        raise ValueError(f"Expected {EXPECTED_SHORT_LINES} short lines, found {len(rows)}.")

    short_predictions = [
        row
        for row in predictions
        if 1 <= len(normalize_text(row["reference_raw"])) <= 10
    ]
    metrics = calculate_metrics(short_predictions)
    operation_counts = Counter(
        edit["operation"]
        for row in rows
        for edit in row["character_edits"]
    )
    character_confusions = Counter(
        (edit["reference"], edit["prediction"])
        for row in rows
        for edit in row["character_edits"]
        if edit["operation"] == "substitution"
    )
    per_length = {}
    for length in range(1, 11):
        selected = [
            row
            for row in short_predictions
            if len(normalize_text(row["reference_raw"])) == length
        ]
        if selected:
            per_length[str(length)] = calculate_metrics(selected)

    screen_original = _read_jsonl(SCREEN_DIR / "original_validation_predictions.jsonl")
    screen_variants = {}
    screen_short_paths = {
        row["crop_relative_path"]
        for row in screen_original
        if 1 <= len(normalize_text(row["reference_raw"])) <= 10
    }
    screen_short_original = [
        row for row in screen_original if row["crop_relative_path"] in screen_short_paths
    ]
    for variant in (
        "existing",
        "contrast",
        "clahe",
        "denoise",
        "deskew",
        "threshold",
        "aspect",
        "margin",
    ):
        candidate = _read_jsonl(
            SCREEN_DIR / f"{variant}_validation_predictions.jsonl"
        )
        candidate_by_path = {row["crop_relative_path"]: row for row in candidate}
        paired = [
            candidate_by_path[row["crop_relative_path"]]
            for row in screen_short_original
        ]
        screen_variants[variant] = {
            "sample_count": len(paired),
            "metrics": calculate_metrics(paired),
            "improved_regressed_unchanged": _paired_changes(
                screen_short_original, paired
            ),
            "source": "Previously saved 43-line preprocessing screen; not a new inference run.",
        }

    current_ram_allows_inference = memory["available_ram_gib"] >= RAM_GUARD_GIB
    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Validation split only; 161 short lines analyzed; no model weights loaded.",
        "sample_count": len(rows),
        "full_short_line_metrics": metrics,
        "character_edit_operation_counts": dict(operation_counts),
        "most_common_character_substitutions": [
            {"reference": pair[0], "prediction": pair[1], "count": count}
            for pair, count in character_confusions.most_common(20)
        ],
        "spacing_edit_count": sum(row["spacing_error_count"] for row in rows),
        "punctuation_edit_count": sum(row["punctuation_error_count"] for row in rows),
        "failed_inference_count": sum(row["status"] != "ok" for row in rows),
        "exact_line_count": sum(row["exact_match"] for row in rows),
        "overworded_line_count": sum(
            row["prediction_words"] > row["reference_words"] for row in rows
        ),
        "possible_low_resolution_count": sum(
            row["possible_low_resolution"] for row in rows
        ),
        "possible_edge_contact_count": sum(
            row["possible_edge_contact"] for row in rows
        ),
        "annotation_marker_line_count": sum(
            row["reference_has_annotation_marker"] for row in rows
        ),
        "by_reference_character_length": per_length,
        "image_dimensions": {
            "width_median": sorted(row["crop_width"] for row in rows)[len(rows) // 2],
            "height_median": sorted(row["crop_height"] for row in rows)[len(rows) // 2],
            "aspect_ratio_median": sorted(
                row["crop_aspect_ratio"] for row in rows
            )[len(rows) // 2],
            "dark_pixel_fraction_median": sorted(
                row["dark_pixel_fraction"] for row in rows
            )[len(rows) // 2],
            "laplacian_variance_median": sorted(
                row["laplacian_variance"] for row in rows
            )[len(rows) // 2],
        },
        "previous_screen_short_subset": {
            "sample_count": len(screen_short_original),
            "variants": screen_variants,
        },
        "ram_preflight": {
            **memory,
            "minimum_free_gib_for_inference": RAM_GUARD_GIB,
            "inference_allowed": current_ram_allows_inference,
            "decision": (
                "inference_allowed"
                if current_ram_allows_inference
                else "stop_before_model_load"
            ),
        },
        "source_sha256": {
            str(path.relative_to(PROJECT_ROOT)): _sha256(path)
            for path in (VALIDATION_MANIFEST, BEST_PREDICTIONS, IMAGE_DIAGNOSTICS)
        },
        "classifications_not_inferable_from_saved_text_or_basic_diagnostics": [
            "whether a specific polygon clipped a written stroke",
            "whether a particular letter is visually ambiguous",
            "whether a high Laplacian variance represents handwriting detail or noise",
        ],
    }

    contact_sheets = _make_contact_sheets(
        rows, PROJECT_ROOT / "datasets" / "processed" / "bentham"
    )
    summary["contact_sheets"] = contact_sheets
    _write_json_exclusive(OUTPUT / "short_line_analysis.json", summary)
    _write_jsonl_exclusive(OUTPUT / "short_line_error_rows.jsonl", rows)
    print(
        json.dumps(
            {
                "short_samples": len(rows),
                "exact": metrics["exact_matches"],
                "cer": metrics["cer"],
                "wer": metrics["wer"],
                "operations": dict(operation_counts),
                "ram_gib": memory["available_ram_gib"],
                "inference_allowed": current_ram_allows_inference,
                "contact_sheets": contact_sheets,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
