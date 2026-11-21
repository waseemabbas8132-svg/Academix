"""Split Bentham pages without changing source records or images.

Run from ai-engine: python -m preprocessing.split_bentham_dataset --seed 42
Output crop_relative_path values remain relative to the input manifest directory,
as recorded by crop_root in split_report.json. Writer separation is not possible.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import random
import tempfile

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_ROOT / "datasets/processed/bentham/manifest.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "datasets/manifests/bentham"
RATIOS = {"train": 0.8, "validation": 0.1, "test": 0.1}


def validate_coverage(records: list[dict], splits: dict[str, list[dict]]) -> None:
    """Reject page overlap, duplicates and dropped/added/changed records."""
    def key(record: dict) -> str:
        return json.dumps(record, sort_keys=True, ensure_ascii=False)

    expected = Counter(map(key, records))
    actual = Counter(key(record) for rows in splits.values() for record in rows)
    if any(count != 1 for count in expected.values()) or any(
        count != 1 for count in actual.values()
    ):
        raise ValueError("Duplicate records in input or splits")
    seen: set[str] = set()
    for rows in splits.values():
        pages = {record["page_id"] for record in rows}
        if seen & pages:
            raise ValueError("Overlapping pages between splits")
        seen.update(pages)
    if actual != expected:
        raise ValueError("Incomplete coverage: split records differ from input")


def split_dataset(
    manifest: Path = DEFAULT_MANIFEST,
    output_dir: Path = DEFAULT_OUTPUT,
    seed: int = 42,
) -> dict:
    manifest = Path(manifest).resolve()
    output_dir = Path(output_dir).resolve()
    targets = [output_dir / f"{name}.jsonl" for name in RATIOS]
    targets.append(output_dir / "split_report.json")
    if manifest in targets or output_dir.is_relative_to(PROJECT_ROOT / "datasets/raw"):
        raise ValueError("Output must not overwrite the input manifest or raw dataset")
    source = manifest.read_bytes()
    records, original_lines = [], []
    paths: set[Path] = set()
    identities: set[tuple] = set()
    for number, line in enumerate(source.splitlines(keepends=True), 1):
        try:
            record = json.loads(line)
        except (ValueError, UnicodeError) as exc:
            raise ValueError(f"Invalid JSON at manifest line {number}: {exc}") from exc
        if not isinstance(record, dict) or any(
            not isinstance(record.get(field), str) or not record[field].strip()
            for field in ("page_id", "crop_relative_path")
        ):
            raise ValueError(f"Invalid page_id or crop_relative_path at line {number}")
        crop = (manifest.parent / record["crop_relative_path"]).resolve()
        identity = (record["page_id"], record.get("text_region_id"), record.get("text_line_id"))
        if crop in paths or (identity[2] is not None and identity in identities):
            raise ValueError(f"Duplicate record or crop at line {number}: {crop}")
        paths.add(crop)
        identities.add(identity)
        if crop in targets:
            raise ValueError(f"Output would overwrite crop: {crop}")
        if not crop.is_file():
            raise ValueError(f"Missing crop at line {number}: {crop}")
        try:
            with Image.open(crop) as image:
                image.verify()
            with Image.open(crop) as image:
                image.load()
        except Exception as exc:
            raise ValueError(f"Unreadable crop at line {number}: {crop}: {exc}") from exc
        records.append(record)
        original_lines.append(line if line.endswith(b"\n") else line + b"\n")
    if not records:
        raise ValueError("Input manifest is empty")
    pages = sorted({record["page_id"] for record in records})
    random.Random(seed).shuffle(pages)
    counts = {name: int(len(pages) * ratio) for name, ratio in RATIOS.items()}
    remainder_order = sorted(
        RATIOS, key=lambda name: -(len(pages) * RATIOS[name] - counts[name])
    )
    for name in remainder_order[:len(pages) - sum(counts.values())]:
        counts[name] += 1
    assignments, offset = {}, 0
    for name, count in counts.items():
        assignments.update({page: name for page in pages[offset:offset + count]})
        offset += count
    splits = {name: [] for name in RATIOS}
    payloads = {name: bytearray() for name in RATIOS}
    for record, line in zip(records, original_lines):
        name = assignments[record["page_id"]]
        splits[name].append(record)
        payloads[name].extend(line)
    validate_coverage(records, splits)
    report = {
        "seed": seed,
        "split_unit": "page_id",
        "method": "Sorted page IDs, seeded Python shuffle, largest-remainder allocation (ties: train, validation, test)",
        "input_manifest": manifest.as_posix(),
        "input_sha256": hashlib.sha256(source).hexdigest(),
        "crop_root": manifest.parent.as_posix(),
        "crop_path_resolution": "crop_relative_path is relative to crop_root, not the split manifest directory",
        "total_pages": len(pages),
        "total_crops": len(records),
        "writer_level_separation": False,
        "limitations": "Only page-level separation is possible because writer IDs are unavailable in the manifest and PAGE XML metadata. Writers may occur in multiple splits. Crop ratios can differ from page ratios.",
        "validation": {"duplicate_records": 0, "missing_crops": 0, "unreadable_crops": 0,
                       "overlapping_pages": 0, "complete_coverage": True},
        "splits": {
            name: {"pages": counts[name], "crops": len(rows),
                   "target_percentage": RATIOS[name] * 100,
                   "page_percentage": counts[name] / len(pages) * 100,
                   "crop_percentage": len(rows) / len(records) * 100,
                   "page_ids": sorted({row["page_id"] for row in rows})}
            for name, rows in splits.items()
        },
    }
    # Stage every output only after all validation succeeds. Individual replacements
    # are atomic; a process interruption between replacements requires a rerun.
    output_dir.mkdir(parents=True, exist_ok=True)
    staged = []
    try:
        contents = [bytes(payloads[name]) for name in RATIOS]
        contents.append((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())
        for target, content in zip(targets, contents):
            with tempfile.NamedTemporaryFile(dir=output_dir, delete=False) as handle:
                staged.append((Path(handle.name), target))
                handle.write(content)
            if target.exists() and target.read_bytes() == content:
                staged[-1][0].unlink()
        for temporary, target in staged:
            if temporary.exists():
                os.replace(temporary, target)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        report = split_dataset(args.manifest, args.output_dir, args.seed)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Split validation failed: {exc}\n")
    print(json.dumps({name: {k: v for k, v in stats.items() if k != "page_ids"}
                      for name, stats in report["splits"].items()}, indent=2))


if __name__ == "__main__":
    main()
