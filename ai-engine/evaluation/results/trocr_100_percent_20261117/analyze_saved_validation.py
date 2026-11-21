from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]

RESULTS = PROJECT_ROOT / "evaluation" / "results"
OUTPUT = Path(__file__).resolve().parent
ORIGINAL_PREDICTIONS = RESULTS / "bentham_trocr_validation_predictions.jsonl"
CURRENT_PREDICTIONS = (
    RESULTS
    / "trocr_preprocessing_full_20261116"
    / "existing_validation_predictions.jsonl"
)
CURRENT_METRICS = (
    RESULTS
    / "trocr_preprocessing_full_20261116"
    / "existing_validation_metrics.json"
)
DIAGNOSTICS = (
    RESULTS
    / "trocr_preprocessing_screen_20261116"
    / "input_diagnostics_summary.json"
)
SCREEN_COMPARISON = (
    RESULTS
    / "trocr_preprocessing_screen_20261116"
    / "comparison.json"
)
EXPECTED_SAMPLES = 1197


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _prediction_text(row: dict, normalize_text) -> str:
    return normalize_text(row["prediction_raw"]) if row["status"] == "ok" else ""


def _metrics_equal(actual: dict, expected: dict) -> bool:
    keys = (
        "cer",
        "wer",
        "exact_match_accuracy",
        "exact_matches",
        "total_evaluated_samples",
        "failed_samples",
        "character_errors",
        "reference_characters",
        "word_errors",
        "reference_words",
    )
    return all(actual[key] == expected[key] for key in keys)


def main() -> None:
    sys.path.insert(0, str(PROJECT_ROOT))
    from evaluation.analyze_trocr_errors import analyze
    from evaluation.evaluate_trocr_baseline import (
        calculate_metrics,
        edit_distance,
        normalize_text,
    )

    original_rows = _read_jsonl(ORIGINAL_PREDICTIONS)
    current_rows = _read_jsonl(CURRENT_PREDICTIONS)
    current_metrics_file = json.loads(CURRENT_METRICS.read_text(encoding="utf-8"))
    if len(original_rows) != EXPECTED_SAMPLES or len(current_rows) != EXPECTED_SAMPLES:
        raise ValueError("Saved prediction files do not cover all validation samples.")

    original_metrics = calculate_metrics(original_rows)
    current_metrics = calculate_metrics(current_rows)
    if not _metrics_equal(original_metrics, json.loads(
        (RESULTS / "bentham_trocr_validation_metrics.json").read_text(
            encoding="utf-8"
        )
    )):
        raise ValueError("Original saved validation predictions fail metric verification.")
    if not _metrics_equal(current_metrics, current_metrics_file):
        raise ValueError("Enhanced full-validation predictions fail metric verification.")
    if current_metrics["failed_samples"] != 0:
        raise ValueError("The selected candidate contains failed validation predictions.")

    changed = Counter()
    paired_changes: list[dict] = []
    for index, (original, current) in enumerate(zip(original_rows, current_rows)):
        identity = ("crop_relative_path", "page_id", "reference_raw")
        if any(original[key] != current[key] for key in identity):
            raise ValueError(f"Saved predictions are not paired at sample {index}.")
        reference = normalize_text(current["reference_raw"])
        original_text = _prediction_text(original, normalize_text)
        current_text = _prediction_text(current, normalize_text)
        old_errors = edit_distance(reference, original_text)
        new_errors = edit_distance(reference, current_text)
        category = "improved" if new_errors < old_errors else (
            "regressed" if new_errors > old_errors else "unchanged"
        )
        changed[category] += 1
        paired_changes.append(
            {
                "sample_index": index,
                "crop_relative_path": current["crop_relative_path"],
                "page_id": current["page_id"],
                "original_character_errors": old_errors,
                "current_character_errors": new_errors,
                "change": category,
            }
        )

    error_summary, examples = analyze(current_rows, top_n=20)
    inaccurate_predictions = []
    for example in examples:
        if example["exact_match"]:
            continue
        row = example["source_record"]
        inaccurate_predictions.append(
            {
                "sample_index": example["sample_index"],
                "crop_relative_path": row["crop_relative_path"],
                "page_id": row["page_id"],
                "reference_raw": row["reference_raw"],
                "prediction_raw": row["prediction_raw"],
                "reference_normalized": example["reference_normalized"],
                "prediction_normalized": example["prediction_normalized"],
                "character_errors": example["character_errors"],
                "word_errors": example["word_errors"],
                "reference_characters": example["reference_characters"],
                "reference_words": example["reference_words"],
                "categories": example["categories"],
            }
        )

    if len(inaccurate_predictions) != EXPECTED_SAMPLES - current_metrics["exact_matches"]:
        raise ValueError("Incorrect-prediction output does not account for every non-exact row.")

    screen_comparison = json.loads(SCREEN_COMPARISON.read_text(encoding="utf-8"))
    current_configuration = current_metrics_file["configuration"]
    user_baseline = {
        "cer": 0.162436,
        "wer": 0.403155,
        "exact_matches": 79,
        "total_evaluated_samples": EXPECTED_SAMPLES,
    }
    if (
        round(current_metrics["cer"], 6) != user_baseline["cer"]
        or round(current_metrics["wer"], 6) != user_baseline["wer"]
        or current_metrics["exact_matches"] != user_baseline["exact_matches"]
    ):
        raise ValueError("Saved best candidate does not match the user's validated baseline.")

    summary = {
        "status": "complete",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Saved validation predictions only; no test split, labels, images, or model weights were modified.",
        "sample_count": EXPECTED_SAMPLES,
        "unique_pages": len({row["page_id"] for row in current_rows}),
        "user_supplied_baseline": user_baseline,
        "best_verified_candidate": {
            "model_name": current_configuration["model_name"],
            "checkpoint_revision": current_configuration["checkpoint_revision"],
            "preprocessing": current_configuration["variants"]["existing"],
            "generation": current_configuration["generation"],
            "metrics": current_metrics,
            "runtime_seconds": current_metrics_file["runtime_seconds"],
            "failed_samples": current_metrics["failed_samples"],
        },
        "comparison_with_pre_enhancement_saved_baseline": {
            "baseline_metrics": original_metrics,
            "candidate_metrics": current_metrics,
            "cer_absolute_reduction_percentage_points": (
                original_metrics["cer"] - current_metrics["cer"]
            )
            * 100,
            "cer_relative_reduction_percent": (
                (original_metrics["cer"] - current_metrics["cer"])
                / original_metrics["cer"]
                * 100
            ),
            "wer_absolute_reduction_percentage_points": (
                original_metrics["wer"] - current_metrics["wer"]
            )
            * 100,
            "wer_relative_reduction_percent": (
                (original_metrics["wer"] - current_metrics["wer"])
                / original_metrics["wer"]
                * 100
            ),
            "exact_match_change": (
                current_metrics["exact_matches"] - original_metrics["exact_matches"]
            ),
            "exact_match_absolute_change_percentage_points": (
                current_metrics["exact_match_accuracy"]
                - original_metrics["exact_match_accuracy"]
            )
            * 100,
            "exact_match_relative_gain_percent": (
                (
                    current_metrics["exact_matches"]
                    - original_metrics["exact_matches"]
                )
                / original_metrics["exact_matches"]
                * 100
            ),
            "improved_samples": changed["improved"],
            "regressed_samples": changed["regressed"],
            "unchanged_samples": changed["unchanged"],
        },
        "comparison_with_user_supplied_baseline": {
            "cer_absolute_reduction_percentage_points": 0.0,
            "cer_relative_reduction_percent": 0.0,
            "wer_absolute_reduction_percentage_points": 0.0,
            "wer_relative_reduction_percent": 0.0,
            "exact_match_change": 0,
            "remaining_incorrect_predictions": len(inaccurate_predictions),
        },
        "error_analysis": error_summary,
        "data_quality_diagnostics": json.loads(
            DIAGNOSTICS.read_text(encoding="utf-8")
        ),
        "prior_preprocessing_screen": {
            "source": "trocr_preprocessing_screen_20261116/comparison.json",
            "metrics": {
                name: {
                    "cer": result["cer"],
                    "wer": result["wer"],
                    "exact_matches": result["exact_matches"],
                    "failed_samples": result["failed_samples"],
                    "runtime_seconds": result["runtime_seconds"],
                }
                for name, result in screen_comparison["metrics"].items()
            },
        },
        "paired_change_counts": dict(changed),
        "source_artifacts": {
            str(path.relative_to(PROJECT_ROOT)): _sha256(path)
            for path in (
                ORIGINAL_PREDICTIONS,
                CURRENT_PREDICTIONS,
                CURRENT_METRICS,
                DIAGNOSTICS,
                SCREEN_COMPARISON,
            )
        },
    }
    _write_json_exclusive(OUTPUT / "validation_analysis.json", summary)
    _write_json_exclusive(
        OUTPUT / "paired_sample_changes.json",
        {"sample_count": EXPECTED_SAMPLES, "samples": paired_changes},
    )
    _write_jsonl_exclusive(
        OUTPUT / "remaining_incorrect_predictions.jsonl",
        inaccurate_predictions,
    )
    print(
        json.dumps(
            {
                "samples": EXPECTED_SAMPLES,
                "pages": summary["unique_pages"],
                "cer": current_metrics["cer"],
                "wer": current_metrics["wer"],
                "exact_matches": current_metrics["exact_matches"],
                "incorrect_predictions": len(inaccurate_predictions),
                "paired_changes": dict(changed),
                "output": str(OUTPUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
