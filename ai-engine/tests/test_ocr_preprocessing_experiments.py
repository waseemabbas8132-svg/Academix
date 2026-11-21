from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw
import pytest

from evaluation.experiment_trocr_preprocessing import paired_comparison, select_records
from evaluation.evaluate_trocr_baseline import evaluate_sample
from preprocessing.handwritten_ocr import OCRLine, _line_regions, recognize_page
from preprocessing.ocr_image_experiments import VARIANTS, estimate_line_skew, prepare_line_image
from preprocessing.text_extractor import extract_document


def sample_image():
    image = Image.new('RGB', (320, 48), (220, 218, 210))
    draw = ImageDraw.Draw(image)
    draw.line((0, 20, 319, 20), fill=(30, 30, 30), width=2)
    draw.text((8, 25), 'handwriting 123', fill=(70, 70, 70))
    return image


@pytest.mark.parametrize('variant', list(VARIANTS))
def test_variants_deterministic_rgb_and_leave_source_unchanged(variant):
    source = sample_image()
    before = source.tobytes()
    one, two = prepare_line_image(source, variant), prepare_line_image(source, variant)
    assert one.mode == 'RGB'
    assert one.size == two.size and one.tobytes() == two.tobytes()
    assert source.tobytes() == before and source.size == (320, 48)
    if variant not in ('aspect',):
        assert one.width >= source.width and one.height >= source.height


def test_unknown_transform_and_blank_deskew():
    with pytest.raises(ValueError, match='Unknown'):
        prepare_line_image(sample_image(), 'invalid')
    assert estimate_line_skew(Image.new('L', (100, 20), 255)) == (0, 0)


@pytest.mark.parametrize('angle', [-2, 2])
def test_deskew_corrects_sign_and_expands_without_cutting_line_edges(angle):
    source = Image.new('L', (400, 70), 255)
    draw = ImageDraw.Draw(source)
    for y in (18, 35, 51):
        draw.line((35, y, 365, y), fill=30, width=2)
    rotated = source.rotate(angle, expand=True, fillcolor=255)
    correction, gain = estimate_line_skew(rotated)
    assert correction == -angle and gain >= .05
    corrected = prepare_line_image(rotated, 'deskew')
    assert corrected.width >= rotated.width and corrected.height >= rotated.height
    assert (np.asarray(corrected.convert('L')) < 160).sum() >= .9 * (np.asarray(rotated) < 160).sum()


def test_exif_orientation_is_applied_without_mutating_source():
    source = Image.new('RGB', (20, 40), 'white')
    source.getexif()[274] = 6
    corrected = prepare_line_image(source, 'original')
    assert corrected.size == (40, 20)
    assert source.size == (20, 40) and source.getexif()[274] == 6


def test_aspect_resize_and_margin_preserve_content():
    source = Image.new('RGB', (200, 40), 'black')
    padded = prepare_line_image(source, 'aspect')
    pixels = np.asarray(padded)[:, :, 0]
    ys, xs = np.nonzero(pixels < 128)
    assert padded.size == (384, 384)
    assert (xs.max()-xs.min()+1)/(ys.max()-ys.min()+1) == pytest.approx(5, abs=.08)
    margin = prepare_line_image(source, 'margin')
    assert margin.size == (204, 44)
    assert margin.crop((2, 2, 202, 42)).tobytes() == source.tobytes()
    assert margin.getpixel((0, 0)) == (255, 255, 255)


def test_original_no_pixel_change_and_threshold_binary():
    source = sample_image()
    assert prepare_line_image(source, 'original').tobytes() == source.tobytes()
    assert set(np.unique(np.asarray(prepare_line_image(source, 'threshold')))) <= {0, 255}


def records():
    return [{'page_id': f'p{p}', 'crop_relative_path': f'{p}-{i}.png', 'transcription': 'reference'}
            for p in range(5) for i in range(6)]


def test_selection_repeatable_page_covering_disjoint_no_prediction_input():
    rows = records()
    screen, confirmation = select_records(rows, 'screen'), select_records(rows, 'confirmation')
    assert screen == select_records(rows, 'screen')
    assert screen != select_records(rows, 'screen', 7)
    assert len(screen) == 5 and len(confirmation) == 10
    assert {r['page_id'] for r in screen} == {r['page_id'] for r in rows}
    assert {r['crop_relative_path'] for r in screen}.isdisjoint(r['crop_relative_path'] for r in confirmation)
    assert select_records(rows, 'full') == rows


def test_corrupt_image_and_transform_error_counted_not_dropped(tmp_path):
    record = {'page_id': 'p', 'crop_relative_path': 'bad.png', 'transcription': 'text'}
    (tmp_path / 'bad.png').write_bytes(b'not an image')
    row = evaluate_sample(record, tmp_path, lambda _: 'never')
    assert row['status'] == 'failed' and row['failure_stage'] == 'image'
    Image.new('RGB', (10, 10)).save(tmp_path / 'bad.png')
    row = evaluate_sample(record, tmp_path, lambda image: prepare_line_image(image, 'invalid'))
    assert row['status'] == 'failed' and 'Unknown' in row['error']


def test_paired_metrics_keep_empty_and_failed_samples():
    def row(text, predicted, status='ok'):
        return {'crop_relative_path': text+'.png', 'reference_raw': text,
                'prediction_raw': predicted, 'status': status, 'error': 'error', 'failure_stage': 'image'}
    comparison = paired_comparison([row('cat', 'cot'), row('', '')],
                                   [row('cat', 'cat'), row('', None, 'failed')])
    assert comparison['lines_fewer_character_errors'] == 1
    assert comparison['lines_equal_character_errors'] == 1
    assert comparison['cer_delta_percentage_points'] < 0
    assert comparison['exact_match_delta_percentage_points'] == 0
    with pytest.raises(ValueError, match='samples'):
        paired_comparison([row('a', '')], [row('b', '')])


def test_current_ocr_and_extraction_contracts_remain_compatible():
    class Recognizer:
        def recognize(self, image):
            assert image.width > 0 and image.height > 0
            return OCRLine('handwritten text', .4)
    source = sample_image()
    before = source.tobytes()
    segments = recognize_page(source, Recognizer(), page_number=2)
    assert segments and all(s.page_number == 2 and s.needs_review for s in segments)
    assert source.tobytes() == before
    content = BytesIO()
    source.save(content, format='PNG')
    extracted = extract_document('student.png', content.getvalue(), Recognizer())
    assert extracted.text and extracted.warnings


def test_line_regions_do_not_drop_ink_on_left_or_right_edge():
    source = Image.new('L', (200, 60), 255)
    draw = ImageDraw.Draw(source)
    draw.rectangle((0, 20, 199, 30), fill=0)
    regions = _line_regions(source)
    assert len(regions) == 1 and regions[0].width == source.width
    assert regions[0].getpixel((0, 8)) == 0
    assert regions[0].getpixel((199, 8)) == 0
