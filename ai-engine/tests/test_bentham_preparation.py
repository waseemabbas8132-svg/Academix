import json
import struct
import zlib
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageDraw
import pytest

from preprocessing.prepare_bentham_dataset import (
    DEFAULT_IMAGE_ROOT,
    DEFAULT_OUTPUT_ROOT,
    PAGE_NAMESPACE,
    _validate_written_manifest,
    _save_verified_crop,
    extract_polygon_crop,
    order_page_lines,
    parse_page_xml,
    prepare_dataset,
)


def _line_xml(
    line_id: str,
    points: list[tuple[int, int]],
    transcription: str | None,
) -> str:
    coords = "".join(f'<Point x="{x}" y="{y}" />' for x, y in points)
    if transcription is None:
        text_equiv = "<TextEquiv />"
    else:
        text_equiv = f"<TextEquiv><Unicode>{transcription}</Unicode></TextEquiv>"
    return (
        f'<TextLine id="{line_id}"><Coords>{coords}'
        f"</Coords>{text_equiv}</TextLine>"
    )


def _page_xml(
    image_filename: str,
    regions: list[tuple[str, int, list[str]]],
    page_id: str = "page-1",
) -> str:
    region_xml = []
    for region_id, region_x, lines in regions:
        region_xml.append(
            f'<TextRegion id="{region_id}">'
            f'<Coords><Point x="{region_x}" y="0" />'
            f'<Point x="{region_x + 20}" y="0" />'
            f'<Point x="{region_x + 20}" y="20" />'
            f'<Point x="{region_x}" y="20" /></Coords>'
            f"{''.join(lines)}</TextRegion>"
        )
    return (
        f'<PcGts xmlns="{PAGE_NAMESPACE}"><Page id="{page_id}" '
        f'imageFilename="{image_filename}">'
        f"{''.join(region_xml)}</Page></PcGts>"
    )


def _box_line(
    line_id: str,
    x: int,
    y: int,
    text: str,
) -> str:
    return _line_xml(
        line_id,
        [(x, y), (x + 12, y), (x + 12, y + 8), (x, y + 8)],
        text,
    )


def _write_page(
    xml_root: Path,
    image_root: Path,
    xml_name: str,
    image_name: str,
    regions: list[tuple[str, int, list[str]]],
    *,
    dark_mark: bool = True,
) -> tuple[Path, Path]:
    xml_root.mkdir(parents=True, exist_ok=True)
    image_path = image_root / "nested" / image_name
    image_path.parent.mkdir(parents=True, exist_ok=True)
    page = Image.new("RGB", (80, 60), "white")
    if dark_mark:
        draw = ImageDraw.Draw(page)
        draw.line((10, 10, 22, 16), fill=(20, 20, 20), width=2)
        draw.line((10, 32, 22, 36), fill=(20, 20, 20), width=2)
    page.save(image_path)

    xml_path = xml_root / xml_name
    xml_path.write_text(_page_xml(image_name, regions), encoding="utf-8")
    return xml_path, image_path


def _manifest_records(output_root: Path) -> list[dict[str, object]]:
    manifest_path = output_root / "manifest.jsonl"
    return [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
    ]


def _header_only_png(size: tuple[int, int]) -> bytes:
    width, height = size
    ihdr = b"IHDR" + struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    crc = zlib.crc32(ihdr) & 0xFFFFFFFF
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + ihdr + struct.pack(">I", crc)


def test_page_xml_namespace_image_filename_and_unicode_transcription(tmp_path: Path) -> None:
    xml_root = tmp_path / "xml"
    image_root = tmp_path / "images"
    xml_root.mkdir()
    image_root.mkdir()
    xml_path = xml_root / "not-the-image-name.xml"
    text = "  Été &amp; mémoire—A  "
    xml_path.write_text(
        _page_xml(
            "different-image-name.jpg",
            [("region-1", 1, [_box_line("line-1", 10, 20, text)])],
        ),
        encoding="utf-8",
    )

    annotation = parse_page_xml(xml_path)

    assert annotation.image_filename == "different-image-name.jpg"
    assert annotation.regions[0].lines[0].transcription == "  Été & mémoire—A  "
    assert annotation.regions[0].lines[0].average_y == 24


def test_page_xml_points_attribute_polygon_format(tmp_path: Path) -> None:
    xml_path = tmp_path / "attribute-points.xml"
    xml_path.write_text(
        f'<PcGts xmlns="{PAGE_NAMESPACE}"><Page imageFilename="page.jpg">'
        '<TextRegion id="r1"><TextLine id="l1">'
        '<Coords points="10,20 22,20 22,28 10,28" />'
        '<TextEquiv><Unicode>word</Unicode></TextEquiv>'
        "</TextLine></TextRegion></Page></PcGts>",
        encoding="utf-8",
    )

    annotation = parse_page_xml(xml_path)

    assert annotation.regions[0].lines[0].original_points == [
        [10, 20],
        [22, 20],
        [22, 28],
        [10, 28],
    ]


def test_bentham_region_and_line_ordering_and_horizontal_ties(tmp_path: Path) -> None:
    xml_path = tmp_path / "order.xml"
    xml_path.write_text(
        _page_xml(
            "page.jpg",
            [
                (
                    "region-right",
                    100,
                    [
                        _box_line("lower", 110, 10, "lower"),
                        _box_line("tie-right", 140, 50, "tie right"),
                        _box_line("highest", 120, 80, "highest"),
                        _box_line("tie-left", 105, 50, "tie left"),
                    ],
                ),
                ("region-left", 20, [_box_line("left-high", 30, 80, "left")]),
                ("region-middle", 60, [_box_line("middle-high", 70, 80, "middle")]),
                ("region-second", 40, [_box_line("second", 50, 70, "second")]),
            ],
        ),
        encoding="utf-8",
    )

    ordered = order_page_lines(parse_page_xml(xml_path))

    assert [
        (region.region_id, line.line_id, region_order, line_order)
        for region_order, line_order, region, line in ordered
    ] == [
        ("region-left", "left-high", 1, 1),
        ("region-middle", "middle-high", 2, 1),
        ("region-right", "highest", 3, 1),
        ("region-right", "tie-left", 3, 2),
        ("region-right", "tie-right", 3, 3),
        ("region-right", "lower", 3, 4),
        ("region-second", "second", 4, 1),
    ]


def test_polygon_crop_masks_neighbors_and_preserves_interior_pixels() -> None:
    image = Image.new("RGB", (30, 30), "white")
    draw = ImageDraw.Draw(image)
    draw.line((8, 15, 17, 15), fill=(10, 20, 30), width=2)
    draw.point((22, 15), fill=(0, 0, 0))
    polygon = [(5, 5), (20, 5), (20, 20), (5, 20)]

    crop, reason = extract_polygon_crop(image, polygon, padding=4)

    assert reason is None
    assert crop is not None
    assert crop.getpixel((8 - 1, 15 - 1)) == (10, 20, 30)
    assert crop.getpixel((22 - (5 - 4), 15 - (5 - 4))) == (255, 255, 255)
    assert crop.size == (24, 24)


def test_polygon_crop_clamps_points_outside_image_bounds() -> None:
    image = Image.new("RGB", (10, 10), "white")
    ImageDraw.Draw(image).line((0, 3, 3, 3), fill="black", width=2)

    crop, reason = extract_polygon_crop(
        image,
        [(-4, 1), (5, 1), (5, 7), (-4, 7)],
        padding=3,
    )

    assert reason is None
    assert crop is not None
    assert crop.size == (9, 10)


def test_faint_handwriting_is_not_discarded_as_blank() -> None:
    image = Image.new("RGB", (30, 30), "white")
    ImageDraw.Draw(image).line((8, 15, 17, 15), fill=(245, 245, 245), width=2)

    crop, reason = extract_polygon_crop(
        image,
        [(5, 5), (20, 5), (20, 20), (5, 20)],
        padding=2,
    )

    assert reason is None
    assert crop is not None
    assert crop.getpixel((5, 12)) == (245, 245, 245)


def test_empty_transcription_is_rejected_with_a_reason(tmp_path: Path) -> None:
    xml_root, image_root = tmp_path / "xml", tmp_path / "images"
    output_root = tmp_path / "processed"
    _write_page(
        xml_root,
        image_root,
        "page-a.xml",
        "source-a.jpg",
        [("r1", 1, [_box_line("l1", 10, 10, "   ")])],
    )

    report = prepare_dataset(
        xml_root=xml_root,
        image_root=image_root,
        output_root=output_root,
    )
    rejected = [
        json.loads(line)
        for line in (output_root / "rejected_lines.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]

    assert report["empty_transcription_count"] == 1
    assert report["rejection_counts_by_reason"] == {"empty_transcription": 1}
    assert rejected[0]["reason"] == "empty_transcription"
    assert report["output_crop_count"] == 0


def test_invalid_polygon_is_rejected_and_counted(tmp_path: Path) -> None:
    xml_root, image_root = tmp_path / "xml", tmp_path / "images"
    output_root = tmp_path / "processed"
    invalid_line = _line_xml(
        "self-intersecting-line",
        [(10, 10), (14, 14), (10, 14), (14, 10), (15, 15)],
        "has text",
    )
    _write_page(
        xml_root,
        image_root,
        "page-a.xml",
        "source-a.jpg",
        [("r1", 1, [invalid_line])],
    )

    report = prepare_dataset(
        xml_root=xml_root,
        image_root=image_root,
        output_root=output_root,
    )

    assert report["invalid_polygon_count"] == 1
    assert report["rejection_counts_by_reason"] == {"invalid_polygon": 1}
    assert report["output_crop_count"] == 0


def test_filename_uniqueness_and_manifest_consistency(tmp_path: Path) -> None:
    xml_root, image_root = tmp_path / "xml", tmp_path / "images"
    output_root = tmp_path / "processed"
    xml_path, image_path = _write_page(
        xml_root,
        image_root,
        "arbitrary-xml-name.xml",
        "source-a.jpg",
        [
            (
                "reused-id",
                1,
                [
                    _box_line("same-line-id", 8, 8, "one"),
                    _box_line("same-line-id", 8, 30, "two"),
                ],
            )
        ],
    )
    xml_before, image_before = xml_path.read_bytes(), image_path.read_bytes()

    report = prepare_dataset(
        xml_root=xml_root,
        image_root=image_root,
        output_root=output_root,
        padding=1,
    )
    records = _manifest_records(output_root)
    filenames = [record["crop_filename"] for record in records]

    assert report["total_annotated_text_lines"] == 2
    assert report["output_crop_count"] == 2
    assert report["manifest_validation_errors"] == []
    assert len(set(filenames)) == 2
    assert all((output_root / record["crop_relative_path"]).is_file() for record in records)
    assert all(record["transcription"] in {"one", "two"} for record in records)
    assert all(record["crop_width"] > 0 and record["crop_height"] > 0 for record in records)
    assert [record["global_line_order"] for record in records] == [1, 2]
    assert xml_path.read_bytes() == xml_before
    assert image_path.read_bytes() == image_before


def test_incomplete_png_is_rejected_and_not_added_to_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    xml_root, image_root = tmp_path / "xml", tmp_path / "images"
    output_root = tmp_path / "processed"
    _write_page(
        xml_root,
        image_root,
        "page-a.xml",
        "page-a.jpg",
        [("r1", 1, [_box_line("l1", 10, 10, "word")])],
    )

    def save_header_only(
        image: Image.Image,
        file_object: BinaryIO,
        format: str | None = None,
    ) -> None:
        if format != "PNG":
            raise AssertionError(f"Expected PNG save, got {format!r}.")
        file_object.write(_header_only_png(image.size))

    monkeypatch.setattr(Image.Image, "save", save_header_only)

    report = prepare_dataset(
        xml_root=xml_root,
        image_root=image_root,
        output_root=output_root,
    )

    rejected = [
        json.loads(line)
        for line in (output_root / "rejected_lines.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    assert report["output_crop_count"] == 0
    assert report["rejection_counts_by_reason"] == {"crop_verification_error": 1}
    assert rejected[0]["reason"] == "crop_verification_error"
    assert "PNG verification failed" in rejected[0]["error"]
    assert _manifest_records(output_root) == []
    assert list((output_root / "line_images").iterdir()) == []


def test_unreadable_manifest_crop_is_not_counted_as_successful(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "processed"
    crop_root = output_root / "line_images"
    crop_root.mkdir(parents=True)
    Image.new("RGB", (2, 2), "white").save(crop_root / "valid.png")
    (crop_root / "incomplete.png").write_bytes(_header_only_png((2, 2)))
    manifest_path = output_root / "manifest.jsonl"
    manifest_path.write_text(
        "".join(
            json.dumps(
                {
                    "crop_filename": filename,
                    "crop_relative_path": f"line_images/{filename}",
                    "crop_width": 2,
                    "crop_height": 2,
                    "transcription": "word",
                }
            )
            + "\n"
            for filename in ("valid.png", "incomplete.png")
        ),
        encoding="utf-8",
    )

    verified_crop_count, errors = _validate_written_manifest(
        manifest_path,
        output_root,
    )

    assert verified_crop_count == 1
    assert len(errors) == 1
    assert "line_images/incomplete.png" in errors[0]


def test_exact_corrupt_bentham_crop_can_be_regenerated_and_opened(
    tmp_path: Path,
) -> None:
    crop_filename = "035_320_001__r1__r210__r001_l016_g000142.png"
    manifest_path = DEFAULT_OUTPUT_ROOT / "manifest.jsonl"
    source_path = DEFAULT_IMAGE_ROOT / "Images" / "Pages" / "035_320_001.jpg"
    if not manifest_path.is_file() or not source_path.is_file():
        pytest.skip("Bentham source image or extraction manifest is not available.")

    record = next(
        record
        for record in _manifest_records(DEFAULT_OUTPUT_ROOT)
        if record["crop_filename"] == crop_filename
    )
    assert record["transcription"] == "such argumentation as is on this occasion made:"
    polygon = [
        (float(x), float(y))
        for x, y in record["original_polygon_coordinates"]
    ]
    with Image.open(source_path) as source:
        source_image = source.convert("RGB")
    crop, reason = extract_polygon_crop(
        source_image,
        polygon,
        padding=4,
        polygon_validated=True,
    )

    assert reason is None
    assert crop is not None
    expected_size = (record["crop_width"], record["crop_height"])
    assert crop.size == expected_size == (1739, 271)

    destination = tmp_path / crop_filename
    destination.write_bytes(_header_only_png(expected_size))
    _save_verified_crop(crop, destination)
    with Image.open(destination) as regenerated:
        regenerated.verify()
    with Image.open(destination) as regenerated:
        regenerated.load()
        assert regenerated.size == expected_size
        assert regenerated.format == "PNG"


def test_case_insensitive_nested_image_matching_and_duplicate_reporting(
    tmp_path: Path,
) -> None:
    xml_root, image_root = tmp_path / "xml", tmp_path / "images"
    output_root = tmp_path / "processed"
    _write_page(
        xml_root,
        image_root,
        "different-xml-name.xml",
        "Bentham-Page.JPG",
        [("r1", 1, [_box_line("l1", 10, 10, "word")])],
    )
    duplicate = image_root / "other" / "bentham-page.jpg"
    duplicate.parent.mkdir(parents=True)
    Image.new("RGB", (80, 60), "white").save(duplicate)

    report = prepare_dataset(
        xml_root=xml_root,
        image_root=image_root,
        output_root=output_root,
        dry_run=True,
    )

    assert report["matched_page_image_count"] == 0
    assert report["duplicate_image_match_count"] == 1
    assert report["rejection_counts_by_reason"] == {"duplicate_page_image_match": 1}
    assert not output_root.exists()


def test_dry_run_validates_without_writing_crops_or_reports(tmp_path: Path) -> None:
    xml_root, image_root = tmp_path / "xml", tmp_path / "images"
    output_root = tmp_path / "processed"
    _, image_path = _write_page(
        xml_root,
        image_root,
        "page-a.xml",
        "page-a.jpg",
        [("r1", 1, [_box_line("l1", 10, 10, "word")])],
    )
    image_path.write_bytes(b"not decoded during a dry run")

    report = prepare_dataset(
        xml_root=xml_root,
        image_root=image_root,
        output_root=output_root,
        dry_run=True,
    )

    assert report["eligible_lines_without_writing"] == 1
    assert report["output_crop_count"] == 0
    assert not output_root.exists()
