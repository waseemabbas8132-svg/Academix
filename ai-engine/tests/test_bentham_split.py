import json
from collections import Counter
from pathlib import Path

from PIL import Image
import pytest

from preprocessing.split_bentham_dataset import split_dataset, validate_coverage


@pytest.fixture
def dataset(tmp_path):
    root = tmp_path / 'processed'
    root.mkdir()
    records = []
    for page in range(43):
        for line in range(1 + page % 3):
            filename = f'{page}-{line}.png'
            Image.new('L', (12, 8), 255).save(root / filename)
            records.append({'page_id': str(page), 'crop_relative_path': filename,
                            'text_region_id': 'r1', 'text_line_id': str(line),
                            'transcription': '  Original é text.  ', 'extra': [1, 2]})
    manifest = root / 'manifest.jsonl'
    manifest.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in records), encoding='utf-8')
    return manifest, tmp_path / 'splits', records


def snapshot(root):
    return {str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in root.rglob('*') if path.is_file()}


def read_splits(output):
    return {name: [json.loads(line) for line in (output / f'{name}.jsonl').read_text(encoding='utf-8').splitlines()]
            for name in ('train', 'validation', 'test')}


def test_determinism_coverage_distribution_and_unchanged_sources(dataset):
    manifest, output, records = dataset
    before = snapshot(manifest.parent)
    report = split_dataset(manifest, output)
    first = snapshot(output)
    split_dataset(manifest, output, seed=42)
    assert snapshot(output) == first
    assert snapshot(manifest.parent) == before
    splits = read_splits(output)
    validate_coverage(records, splits)
    keys = lambda rows: Counter(json.dumps(row, sort_keys=True) for row in rows)
    assert keys(records) == keys([row for rows in splits.values() for row in rows])
    pages = [set(row['page_id'] for row in rows) for rows in splits.values()]
    assert not (pages[0] & pages[1] or pages[0] & pages[2] or pages[1] & pages[2])
    assert len(set.union(*pages)) == 43
    for name, ratio in [('train', .8), ('validation', .1), ('test', .1)]:
        assert abs(report['splits'][name]['pages'] - 43 * ratio) < 1
    assert report['writer_level_separation'] is False
    split_dataset(manifest, output, seed=7)
    assert read_splits(output) != splits
    assert snapshot(manifest.parent) == before


@pytest.mark.parametrize('failure', ['missing', 'corrupt', 'duplicate', 'duplicate_identity'])
def test_validation_preserves_existing_outputs(dataset, failure):
    manifest, output, records = dataset
    split_dataset(manifest, output)
    before = snapshot(output)
    crop = manifest.parent / records[0]['crop_relative_path']
    if failure == 'missing':
        crop.unlink()
    elif failure == 'corrupt':
        crop.write_bytes(b'not an image')
    else:
        duplicate = dict(records[0])
        if failure == 'duplicate_identity':
            duplicate['crop_relative_path'] = 'other.png'
            Image.new('L', (12, 8)).save(manifest.parent / 'other.png')
        with manifest.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(duplicate) + '\n')
    message = {'missing': 'Missing crop', 'corrupt': 'Unreadable crop'}.get(failure, 'Duplicate')
    with pytest.raises(ValueError, match=message):
        split_dataset(manifest, output)
    assert snapshot(output) == before


def test_coverage_rejects_overlap_missing_and_duplicate(dataset):
    _, _, records = dataset
    with pytest.raises(ValueError, match='Overlapping pages'):
        validate_coverage(records, {'train': records[:2], 'test': records[2:]})
    with pytest.raises(ValueError, match='Incomplete coverage'):
        validate_coverage(records, {'train': records[:-1]})
    with pytest.raises(ValueError, match='Duplicate'):
        validate_coverage(records, {'train': records + records[:1]})


def test_input_cannot_be_output(dataset):
    manifest, _, _ = dataset
    target = manifest.parent / 'train.jsonl'
    target.write_bytes(manifest.read_bytes())
    before = snapshot(manifest.parent)
    with pytest.raises(ValueError, match='overwrite'):
        split_dataset(target, manifest.parent)
    assert snapshot(manifest.parent) == before

