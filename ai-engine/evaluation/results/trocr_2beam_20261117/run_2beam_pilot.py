from __future__ import annotations

from collections import Counter, defaultdict
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.update(
    HF_HUB_OFFLINE="1",
    TRANSFORMERS_OFFLINE="1",
    TOKENIZERS_PARALLELISM="false",
)

from PIL import Image

from evaluation.evaluate_trocr_baseline import (
    CROP_ROOT,
    MODEL_NAME,
    NORMALIZATION,
    RESULTS,
    VALIDATION_MANIFEST,
    calculate_metrics,
    edit_distance,
    evaluate_sample,
    load_manifest,
    normalize_text,
)
from preprocessing.ocr_image_experiments import prepare_line_image
from preprocessing.handwritten_ocr import TrOCRHandwritingRecognizer

OUTPUT = Path(__file__).resolve().parent
BASELINE_DIR = RESULTS / "trocr_preprocessing_full_20261116"
BASELINE_PREDICTIONS = BASELINE_DIR / "existing_validation_predictions.jsonl"
BASELINE_METRICS = BASELINE_DIR / "existing_validation_metrics.json"
EXPECTED_COUNT = 1197
PILOT_COUNT = 50
SEED = 42
THREADS = 4
RAM_GUARD_GIB = 2.5
EMERGENCY_FREE_RAM_GIB = 0.75
GENERATION = {
    "max_new_tokens": 192,
    "do_sample": False,
    "use_cache": True,
}


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


def _peak_working_set_bytes() -> int:
    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("page_fault_count", ctypes.c_ulong),
            ("peak_working_set_size", ctypes.c_size_t),
            ("working_set_size", ctypes.c_size_t),
            ("quota_peak_paged_pool_usage", ctypes.c_size_t),
            ("quota_paged_pool_usage", ctypes.c_size_t),
            ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
            ("quota_non_paged_pool_usage", ctypes.c_size_t),
            ("pagefile_usage", ctypes.c_size_t),
            ("peak_pagefile_usage", ctypes.c_size_t),
            ("private_usage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    process = ctypes.windll.kernel32.GetCurrentProcess()
    if not ctypes.windll.psapi.GetProcessMemoryInfo(
        process, ctypes.byref(counters), counters.cb
    ):
        raise OSError("GetProcessMemoryInfo failed.")
    return counters.peak_working_set_size


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as destination:
        json.dump(value, destination, ensure_ascii=False, indent=2)
        destination.write("\n")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as destination:
        for row in rows:
            destination.write(json.dumps(row, ensure_ascii=False) + "\n")


def _select_50(records: list[dict]) -> list[dict]:
    by_page: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_page[record["page_id"]].append(record)
    pages = sorted(by_page)
    if len(pages) > PILOT_COUNT:
        raise ValueError(f"Expected no more than {PILOT_COUNT} validation pages.")

    rng = random.Random(SEED)
    rng.shuffle(pages)
    shuffled_by_page = {}
    for page in pages:
        samples = sorted(
            by_page[page], key=lambda record: record["crop_relative_path"]
        )
        rng.shuffle(samples)
        shuffled_by_page[page] = samples

    selected = [shuffled_by_page[page][0] for page in pages]
    remaining = [
        record
        for page in pages
        for record in shuffled_by_page[page][1:]
    ]
    rng.shuffle(remaining)
    selected.extend(remaining[: PILOT_COUNT - len(selected)])
    if len(selected) != PILOT_COUNT:
        raise ValueError(f"Could not select exactly {PILOT_COUNT} crops.")
    paths = {record["crop_relative_path"] for record in selected}
    return [record for record in records if record["crop_relative_path"] in paths]


def _paired_changes(greedy: list[dict], beam: list[dict]) -> dict:
    if len(greedy) != len(beam):
        raise ValueError("Greedy and beam sample counts differ.")
    improved = regressed = unchanged = 0
    for old, new in zip(greedy, beam):
        if (
            old["crop_relative_path"] != new["crop_relative_path"]
            or old["reference_raw"] != new["reference_raw"]
        ):
            raise ValueError("Greedy and beam predictions are not aligned.")
        reference = normalize_text(old["reference_raw"])
        old_text = normalize_text(old["prediction_raw"] or "") if old["status"] == "ok" else ""
        new_text = normalize_text(new["prediction_raw"] or "") if new["status"] == "ok" else ""
        old_errors = edit_distance(reference, old_text)
        new_errors = edit_distance(reference, new_text)
        if new_errors < old_errors:
            improved += 1
        elif new_errors > old_errors:
            regressed += 1
        else:
            unchanged += 1
    return {
        "improved": improved,
        "regressed": regressed,
        "unchanged": unchanged,
    }


def _metrics_for_length(rows: list[dict]) -> dict:
    short_rows = [
        row
        for row in rows
        if 1 <= len(normalize_text(row["reference_raw"])) <= 10
    ]
    return {
        "samples": len(short_rows),
        "metrics": calculate_metrics(short_rows) if short_rows else None,
    }


def main() -> None:
    unexpected = [
        path.name
        for path in OUTPUT.iterdir()
        if path.name not in {Path(__file__).name, "preflight.json"}
    ]
    if unexpected:
        raise FileExistsError(
            f"Refusing to overwrite existing experiment outputs: {unexpected}"
        )

    memory_before_imports = _memory_status()
    if memory_before_imports["available_ram_gib"] < RAM_GUARD_GIB:
        _write_json(
            OUTPUT / "pilot_summary.json",
            {
                "status": "blocked_before_model_load",
                "reason": "Available RAM below the existing 2.5 GiB guard.",
                "ram_preflight": memory_before_imports,
            },
        )
        return

    manifest_bytes = VALIDATION_MANIFEST.read_bytes()
    records = load_manifest(
        VALIDATION_MANIFEST, CROP_ROOT, expected_samples=EXPECTED_COUNT
    )
    saved_predictions = _read_jsonl(BASELINE_PREDICTIONS)
    saved_metrics = json.loads(BASELINE_METRICS.read_text(encoding="utf-8"))
    if len(saved_predictions) != EXPECTED_COUNT:
        raise ValueError("Saved greedy baseline does not contain 1,197 rows.")
    if saved_metrics.get("status") != "complete":
        raise ValueError("Saved greedy baseline is incomplete.")
    if saved_metrics["configuration"]["manifest_sha256"] != hashlib.sha256(
        manifest_bytes
    ).hexdigest():
        raise ValueError("Saved greedy baseline was generated from a different manifest.")
    baseline_digest = hashlib.sha256(BASELINE_PREDICTIONS.read_bytes()).hexdigest()
    if saved_metrics.get("predictions_sha256") != baseline_digest:
        raise ValueError("Saved greedy prediction hash does not match its metrics.")
    configuration = saved_metrics["configuration"]
    expected_generation = {
        **GENERATION,
        "num_beams": 1,
    }
    if configuration["generation"] != expected_generation:
        raise ValueError("Saved greedy generation settings differ from the expected baseline.")
    if configuration["variants"].get("existing") is None:
        raise ValueError("Saved baseline does not use existing preprocessing.")

    record_by_path = {row["crop_relative_path"]: row for row in records}
    prediction_by_path = {
        row["crop_relative_path"]: row for row in saved_predictions
    }
    for path, record in record_by_path.items():
        old = prediction_by_path.get(path)
        if old is None or old["reference_raw"] != record["transcription"]:
            raise ValueError(f"Saved reference does not match validation manifest: {path}")
    selected = _select_50(records)
    baseline_rows = [
        prediction_by_path[row["crop_relative_path"]] for row in selected
    ]
    for record, old in zip(selected, baseline_rows):
        if old["crop_sha256"] is None:
            raise ValueError(
                f"Saved baseline has no crop fingerprint: {record['crop_relative_path']}"
            )
        actual = hashlib.sha256(
            (CROP_ROOT / record["crop_relative_path"]).read_bytes()
        ).hexdigest()
        if actual != old["crop_sha256"]:
            raise ValueError(
                f"Validation crop differs from saved baseline: {record['crop_relative_path']}"
            )

    torch = None
    recognizer = None
    try:
        import numpy as np
        import torch as torch_module

        torch = torch_module
        random.seed(SEED)
        np.random.seed(SEED)
        torch.manual_seed(SEED)
        torch.set_num_threads(THREADS)
        torch.use_deterministic_algorithms(True)
        memory_before_load = _memory_status()
        if memory_before_load["available_ram_gib"] < RAM_GUARD_GIB:
            _write_json(
                OUTPUT / "pilot_summary.json",
                {
                    "status": "blocked_before_model_load",
                    "reason": "Available RAM fell below 2.5 GiB before model load.",
                    "ram_preflight": {
                        "before_imports": memory_before_imports,
                        "before_model_load": memory_before_load,
                    },
                },
            )
            return

        recognizer = TrOCRHandwritingRecognizer(
            MODEL_NAME, local_files_only=True
        )
        _, processor, model = recognizer._loaded
        model.to("cpu").eval()
        checkpoint_revision = getattr(model.config, "_commit_hash", None)
        if checkpoint_revision != configuration["checkpoint_revision"]:
            raise ValueError("Loaded checkpoint differs from the saved greedy baseline.")

        _write_jsonl(
            OUTPUT / "selected_samples.jsonl",
            [
                {
                    "page_id": record["page_id"],
                    "crop_relative_path": record["crop_relative_path"],
                    "reference_raw": record["transcription"],
                    "reference_characters": len(normalize_text(record["transcription"])),
                }
                for record in selected
            ],
        )
        _write_json(
            OUTPUT / "RUNNING.json",
            {
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "sample_count": len(selected),
                "seed": SEED,
                "page_count": len({record["page_id"] for record in selected}),
                "baseline_predictions_sha256": baseline_digest,
                "checkpoint_revision": checkpoint_revision,
            },
        )

        memory_series = [
            memory_before_imports["available_ram_gib"],
            memory_before_load["available_ram_gib"],
            _memory_status()["available_ram_gib"],
        ]

        def predict(image: Image.Image, beams: int) -> str:
            transformed = prepare_line_image(image, "existing")
            try:
                pixels = processor(
                    images=transformed, return_tensors="pt"
                ).pixel_values
            finally:
                transformed.close()
            options = {**GENERATION, "num_beams": beams}
            with torch.inference_mode():
                tokens = model.generate(pixels.to("cpu"), **options)
            return processor.batch_decode(tokens, skip_special_tokens=True)[0]

        greedy_rows = []
        beam_rows = []
        greedy_runtime = beam_runtime = 0.0
        started = time.perf_counter()
        greedy_file = (OUTPUT / "greedy_replay_predictions.jsonl").open(
            "x", encoding="utf-8", newline="\n"
        )
        beam_file = (OUTPUT / "two_beam_predictions.jsonl").open(
            "x", encoding="utf-8", newline="\n"
        )
        try:
            for index, record in enumerate(selected, 1):
                greedy_row = evaluate_sample(
                    record, CROP_ROOT, lambda image: predict(image, 1)
                )
                beam_row = evaluate_sample(
                    record, CROP_ROOT, lambda image: predict(image, 2)
                )
                if greedy_row["crop_sha256"] != beam_row["crop_sha256"]:
                    raise ValueError("Paired inference used different crop bytes.")
                greedy_row["generation"] = {**GENERATION, "num_beams": 1}
                beam_row["generation"] = {**GENERATION, "num_beams": 2}
                greedy_rows.append(greedy_row)
                beam_rows.append(beam_row)
                greedy_runtime += greedy_row["runtime_seconds"]
                beam_runtime += beam_row["runtime_seconds"]
                greedy_file.write(json.dumps(greedy_row, ensure_ascii=False) + "\n")
                beam_file.write(json.dumps(beam_row, ensure_ascii=False) + "\n")
                greedy_file.flush()
                beam_file.flush()
                memory_series.append(_memory_status()["available_ram_gib"])
                if memory_series[-1] < EMERGENCY_FREE_RAM_GIB:
                    raise MemoryError(
                        "Available system RAM fell below the 0.75 GiB emergency stop."
                    )
                if index == 1 or index % 10 == 0 or index == len(selected):
                    print(
                        f"{index}/{len(selected)} paired crops; "
                        f"available_ram={memory_series[-1]:.3f} GiB",
                        flush=True,
                    )
        finally:
            greedy_file.close()
            beam_file.close()

        greedy_metrics = calculate_metrics(greedy_rows)
        beam_metrics = calculate_metrics(beam_rows)
        paired = _paired_changes(greedy_rows, beam_rows)
        baseline_replay = {
            "identical_predictions": sum(
                old["status"] == new["status"]
                and old["prediction_raw"] == new["prediction_raw"]
                for old, new in zip(baseline_rows, greedy_rows)
            ),
            "different_predictions": sum(
                old["status"] != new["status"]
                or old["prediction_raw"] != new["prediction_raw"]
                for old, new in zip(baseline_rows, greedy_rows)
            ),
        }
        differences = [
            {
                "page_id": old["page_id"],
                "crop_relative_path": old["crop_relative_path"],
                "crop_sha256": old["crop_sha256"],
                "reference_raw": old["reference_raw"],
                "saved_greedy_raw": saved["prediction_raw"],
                "greedy_replay_raw": old["prediction_raw"],
                "two_beam_raw": new["prediction_raw"],
                "changed_vs_greedy": old["prediction_raw"] != new["prediction_raw"],
                "greedy_status": old["status"],
                "two_beam_status": new["status"],
                "greedy_char_errors": edit_distance(
                    normalize_text(old["reference_raw"]),
                    normalize_text(old["prediction_raw"] or "")
                    if old["status"] == "ok"
                    else "",
                ),
                "two_beam_char_errors": edit_distance(
                    normalize_text(new["reference_raw"]),
                    normalize_text(new["prediction_raw"] or "")
                    if new["status"] == "ok"
                    else "",
                ),
            }
            for saved, old, new in zip(baseline_rows, greedy_rows, beam_rows)
        ]
        _write_jsonl(OUTPUT / "per_sample_comparison.jsonl", differences)

        cer_delta_pp = (beam_metrics["cer"] - greedy_metrics["cer"]) * 100
        wer_delta_pp = (beam_metrics["wer"] - greedy_metrics["wer"]) * 100
        exact_delta = beam_metrics["exact_matches"] - greedy_metrics["exact_matches"]
        meaningful_improvement = (
            cer_delta_pp <= -0.5
            and wer_delta_pp <= 0
            and exact_delta >= 0
            and beam_metrics["failed_samples"] == 0
        )
        summary = {
            "status": "complete",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "sample_count": len(selected),
            "selection": "seed 42; one shuffled crop from each validation page, then seven additional shuffled crops",
            "page_count": len({record["page_id"] for record in selected}),
            "short_line_sample_count": sum(
                1
                for record in selected
                if 1 <= len(normalize_text(record["transcription"])) <= 10
            ),
            "baseline": {
                "source": str(BASELINE_PREDICTIONS.relative_to(PROJECT_ROOT)),
                "saved_predictions_sha256": baseline_digest,
                "replay_match": baseline_replay,
                "metrics": greedy_metrics,
                "runtime_seconds": greedy_runtime,
                "generation": {**GENERATION, "num_beams": 1},
            },
            "two_beam": {
                "metrics": beam_metrics,
                "runtime_seconds": beam_runtime,
                "generation": {**GENERATION, "num_beams": 2},
            },
            "short_line_metrics": {
                "greedy": _metrics_for_length(greedy_rows),
                "two_beam": _metrics_for_length(beam_rows),
            },
            "paired_change_counts": paired,
            "delta": {
                "cer_percentage_points": cer_delta_pp,
                "wer_percentage_points": wer_delta_pp,
                "exact_matches": exact_delta,
            },
            "pilot_gate": {
                "criteria": "CER improvement >=0.5 pp, WER non-increasing, exact matches non-decreasing, zero failures",
                "meaningful_improvement": meaningful_improvement,
                "full_validation_recommended": meaningful_improvement,
            },
            "runtime_seconds_total": time.perf_counter() - started,
            "memory": {
                "preflight_before_imports": memory_before_imports,
                "preflight_before_model_load": memory_before_load,
                "lowest_available_system_ram_gib_during_inference": min(memory_series),
                "process_peak_working_set_gib": _peak_working_set_bytes() / 2**30,
                "available_ram_samples_gib": memory_series,
                "emergency_stop_threshold_gib": EMERGENCY_FREE_RAM_GIB,
            },
            "configuration": {
                "model_name": MODEL_NAME,
                "checkpoint_revision": checkpoint_revision,
                "device": "cpu",
                "dtype": str(next(model.parameters()).dtype),
                "threads": THREADS,
                "preprocessing": configuration["variants"]["existing"],
                "processor": configuration["processor"],
                "normalization": NORMALIZATION,
                "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "baseline_predictions_sha256": baseline_digest,
            },
            "held_out_test_accessed": False,
            "production_changed": False,
        }
        _write_json(OUTPUT / "pilot_summary.json", summary)
        (OUTPUT / "RUNNING.json").unlink()
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "greedy": greedy_metrics,
                    "two_beam": beam_metrics,
                    "paired_change_counts": paired,
                    "delta": summary["delta"],
                    "meaningful_improvement": meaningful_improvement,
                    "runtime_seconds": summary["runtime_seconds_total"],
                    "peak_working_set_gib": summary["memory"][
                        "process_peak_working_set_gib"
                    ],
                },
                indent=2,
            ),
            flush=True,
        )
    except Exception as error:
        _write_json(
            OUTPUT / "pilot_failure.json",
            {
                "status": "failed",
                "error": f"{type(error).__name__}: {error}",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        )
        raise


if __name__ == "__main__":
    main()
