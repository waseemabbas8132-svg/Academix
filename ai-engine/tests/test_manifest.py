import json
from pathlib import Path

import pytest

from academix_ai.manifest import read_manifest, write_manifest


def test_manifest_round_trip_preserves_arbitrary_fields(tmp_path: Path) -> None:
    manifest_path = tmp_path / "nested" / "manifest.jsonl"
    records = [
        {"source_id": "sample-1", "image": "raw/a.png", "split": "train"},
        {"custom_metadata": {"page": 2}, "transcription": "Hello"},
    ]

    write_manifest(manifest_path, records)

    assert list(read_manifest(manifest_path)) == records


def test_manifest_rejects_non_object_records(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

    with pytest.raises(ValueError, match="Expected a JSON object"):
        list(read_manifest(manifest_path))
