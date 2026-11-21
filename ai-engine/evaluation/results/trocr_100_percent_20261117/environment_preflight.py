from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil

OUTPUT = Path(__file__).resolve().parent
MODEL_CACHE = Path.home() / ".cache" / "huggingface" / "hub"
MINIMUM_FREE_GIB = 2.5
OCR_MODULES = (
    "pytesseract",
    "easyocr",
    "paddleocr",
    "doctr",
    "onnxruntime",
)


def memory_status() -> dict:
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
    }


def write_exclusive(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as destination:
        json.dump(value, destination, indent=2, ensure_ascii=False)
        destination.write("\n")


def main() -> None:
    memory = memory_status()
    cached_repositories = (
        sorted(
            path.name
            for path in MODEL_CACHE.glob("models--*")
            if path.is_dir()
        )
        if MODEL_CACHE.is_dir()
        else []
    )
    installed_ocr_modules = {
        name: importlib.util.find_spec(name) is not None for name in OCR_MODULES
    }
    inventory = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "os": os.name,
        "python": "3.12.9 (Pylance-selected academix .venv)",
        **memory,
        "cached_huggingface_model_repositories": cached_repositories,
        "installed_optional_ocr_modules": installed_ocr_modules,
        "tesseract_executable": shutil.which("tesseract"),
        "no_downloads_or_model_loads_performed": True,
    }
    decision = {
        "created_at_utc": inventory["created_at_utc"],
        "decoder_experiment": "not_run_safely",
        "available_ram_gib_at_preflight": memory["available_ram_gib"],
        "existing_experiment_runner_minimum_free_ram_gib": MINIMUM_FREE_GIB,
        "reason": (
            "Available RAM is below the existing 2.5 GiB pre-model-load safety "
            "guard; checkpoint loading and beam-search inference were not started."
        ),
        "configs_not_evaluated": [
            {"num_beams": 2, "length_penalty": 1.0},
            {"num_beams": 4, "length_penalty": 1.0},
            {"num_beams": 2, "length_penalty": 0.8},
        ],
        "cer": None,
        "wer": None,
        "exact_matches": None,
        "runtime_seconds": None,
        "production_change": False,
    }
    write_exclusive(OUTPUT / "local_environment_inventory.json", inventory)
    write_exclusive(OUTPUT / "decoder_experiment_decision.json", decision)
    print(json.dumps({"inventory": inventory, "decoder_decision": decision}, indent=2))


if __name__ == "__main__":
    main()
