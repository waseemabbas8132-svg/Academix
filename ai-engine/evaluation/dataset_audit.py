from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from academix_ai.manifest import write_manifest


@dataclass(frozen=True)
class IAMWordRecord:
    source_id: str
    status: str
    transcription: str
    image_path: Path
    writer_id: str


def _parse_iam_words(annotation_file: Path, image_root: Path):
    seen_ids: set[str] = set()
    errors: list[str] = []
    records: list[IAMWordRecord] = []
    statuses: Counter[str] = Counter()
    for line_number, line in enumerate(
        annotation_file.read_text(encoding="utf-8", errors="replace").splitlines(),
        start=1,
    ):
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        fields = value.split()
        if len(fields) < 9:
            errors.append(f"line {line_number}: expected at least 9 fields")
            continue
        source_id, status = fields[0], fields[1]
        statuses[status] += 1
        if source_id in seen_ids:
            errors.append(f"line {line_number}: duplicate record {source_id}")
            continue
        seen_ids.add(source_id)
        transcription = " ".join(fields[8:]).strip()
        writer_id = source_id.split("-", maxsplit=1)[0]
        image_path = (
            image_root
            / source_id.split("-", maxsplit=1)[0]
            / "-".join(source_id.split("-")[:2])
            / f"{source_id}.png"
        )
        if not transcription:
            errors.append(f"line {line_number}: empty transcription for {source_id}")
        if not image_path.is_file():
            errors.append(f"line {line_number}: missing image for {source_id}")
        records.append(
            IAMWordRecord(
                source_id=source_id,
                status=status,
                transcription=transcription,
                image_path=image_path,
                writer_id=writer_id,
            )
        )
    return records, statuses, errors


def _valid_images(records: list[IAMWordRecord], *, verify_images: bool):
    valid: list[IAMWordRecord] = []
    seen_hashes: set[str] = set()
    errors: list[str] = []
    for record in records:
        if record.status != "ok" or not record.transcription or not record.image_path.is_file():
            continue
        if verify_images:
            try:
                from PIL import Image

                with Image.open(record.image_path) as image:
                    image.verify()
            except Exception:
                errors.append(f"corrupt image: {record.source_id}")
                continue
        digest = hashlib.sha256(record.image_path.read_bytes()).hexdigest()
        if digest in seen_hashes:
            errors.append(f"duplicate image content: {record.source_id}")
            continue
        seen_hashes.add(digest)
        valid.append(record)
    return valid, errors


def _split_for_writer(writer_id: str) -> str:
    bucket = hashlib.sha256(writer_id.encode("utf-8")).digest()[0] % 10
    if bucket < 8:
        return "train"
    return "validation" if bucket == 8 else "test"


def audit_dataset(
    raw_root: Path,
    *,
    verify_images: bool = False,
) -> dict[str, object]:
    annotation_file = raw_root / "iam_words" / "words.txt"
    image_root = raw_root / "iam_words" / "words"
    if not annotation_file.is_file() or not image_root.is_dir():
        raise FileNotFoundError("Expected IAM words.txt and words/ image directory.")

    records, statuses, parse_errors = _parse_iam_words(annotation_file, image_root)
    valid, image_errors = _valid_images(records, verify_images=verify_images)
    writer_splits: dict[str, set[str]] = {}
    for record in valid:
        writer_splits.setdefault(record.writer_id, set()).add(
            _split_for_writer(record.writer_id)
        )
    leakage = sorted(writer for writer, splits in writer_splits.items() if len(splits) > 1)

    line_folders = [
        "Cursive writing",
        "Heavy strokes",
        "Irregular spacing",
        "Mixed handwriting",
        "Neat handwriting",
    ]
    line_summary: dict[str, dict[str, int]] = {}
    for folder in line_folders:
        category_root = raw_root / folder
        image_count = len(list(category_root.rglob("*.png")))
        annotation_count = len(list(category_root.rglob("*.txt")))
        line_summary[folder] = {
            "images": image_count,
            "annotations": annotation_count,
        }

    return {
        "iam_annotation_records": len(records),
        "status_counts": dict(statuses),
        "valid_manifest_candidates": len(valid),
        "image_verification_performed": verify_images,
        "writers": len(writer_splits),
        "writer_split_leakage": leakage,
        "parse_errors": parse_errors[:50],
        "image_errors": image_errors[:50],
        "line_dataset_folders": line_summary,
        "split_method": "stable SHA-256 bucket of writer ID (80/10/10)",
    }


def write_writer_disjoint_manifest(
    raw_root: Path,
    output_path: Path,
    *,
    license_confirmed: bool,
) -> int:
    if not license_confirmed:
        raise ValueError(
            "Manifest creation requires an explicit confirmation that the source "
            "license and provenance permit this use."
        )
    records, _, _ = _parse_iam_words(
        raw_root / "iam_words" / "words.txt",
        raw_root / "iam_words" / "words",
    )
    valid, _ = _valid_images(records, verify_images=True)
    manifest = [
        {
            "source_dataset": "iam_words",
            "source_id": record.source_id,
            "image": record.image_path.relative_to(raw_root).as_posix(),
            "transcription": record.transcription,
            "writer_id": record.writer_id,
            "split": _split_for_writer(record.writer_id),
        }
        for record in valid
    ]
    splits: dict[str, set[str]] = {}
    for record in manifest:
        splits.setdefault(record["writer_id"], set()).add(record["split"])
    if any(len(values) != 1 for values in splits.values()):
        raise ValueError("Writer leakage detected; no manifest was written.")
    write_manifest(output_path, manifest)
    return len(manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the local IAM word dataset.")
    parser.add_argument("--raw-root", type=Path, default=Path("datasets/raw"))
    parser.add_argument("--verify-images", action="store_true")
    parser.add_argument("--write-manifest", type=Path)
    parser.add_argument(
        "--license-confirmed",
        action="store_true",
        help="Confirm that the dataset license permits this use.",
    )
    args = parser.parse_args()
    report = audit_dataset(args.raw_root, verify_images=args.verify_images)
    if args.write_manifest is not None:
        report["manifest_records_written"] = write_writer_disjoint_manifest(
            args.raw_root,
            args.write_manifest,
            license_confirmed=args.license_confirmed,
        )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
