"""Generic JSON Lines manifest helpers that do not assume dataset-specific fields."""

import json
from collections.abc import Iterable, Iterator, Mapping
from os import PathLike
from pathlib import Path
from typing import Any

ManifestPath = str | PathLike[str]


def _coerce_path(path: ManifestPath) -> Path:
    """Normalize manifest path inputs so callers may pass either strings or Path-like values."""
    return Path(path)


def read_manifest(path: ManifestPath) -> Iterator[dict[str, Any]]:
    """Yield JSON objects from a JSON Lines file with line-specific errors."""
    manifest_path = _coerce_path(path)
    with manifest_path.open(encoding="utf-8") as manifest_file:
        for line_number, line in enumerate(manifest_file, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSON in {manifest_path} at line {line_number}: {error.msg}"
                ) from error
            if not isinstance(record, dict):
                raise ValueError(
                    f"Expected a JSON object in {manifest_path} at line {line_number}."
                )
            yield record


def write_manifest(path: ManifestPath, records: Iterable[Mapping[str, Any]]) -> None:
    """Write JSON objects as JSON Lines, creating the parent directory if needed."""
    manifest_path = _coerce_path(path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8", newline="\n") as manifest_file:
        for record in records:
            if not isinstance(record, Mapping):
                raise TypeError("Manifest records must be mappings.")
            manifest_file.write(
                json.dumps(dict(record), ensure_ascii=False, separators=(",", ":"))
            )
            manifest_file.write("\n")
