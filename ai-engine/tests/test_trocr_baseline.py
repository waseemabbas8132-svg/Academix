import json
from pathlib import Path

from PIL import Image
import pytest

from evaluation.evaluate_trocr_baseline import (
    calculate_metrics, edit_distance, evaluate_sample, load_manifest, normalize_text,
)


def result(reference, prediction, failed=False):
    return {'reference_raw': reference, 'prediction_raw': prediction,
            'status': 'failed' if failed else 'ok', 'crop_relative_path': 'crop.png',
            'error': 'broken' if failed else None, 'failure_stage': 'image' if failed else None}


def test_normalization_preserves_case_punctuation_accents():
    assert normalize_text('  Cafe\u0301\t old\ntext! \u00a0') == 'Café old text!'
    assert normalize_text('Hello, WORLD!') == 'Hello, WORLD!'
    assert normalize_text('') == ''


def test_known_corpus_metrics():
    metrics = calculate_metrics([result('cat dog', 'cat dig'), result('a', 'a b')])
    assert metrics['character_errors'] == 3
    assert metrics['reference_characters'] == 8
    assert metrics['cer'] == pytest.approx(3 / 8)
    assert metrics['word_errors'] == 2
    assert metrics['reference_words'] == 3
    assert metrics['wer'] == pytest.approx(2 / 3)
    assert metrics['exact_match_accuracy'] == 0
    assert metrics['total_evaluated_samples'] == 2


def test_metrics_normalize_and_count_failures_in_full_denominator():
    metrics = calculate_metrics([result(' é  test ', 'e\u0301\ttest'),
                                 result('a b', None, failed=True)])
    assert metrics['exact_matches'] == 1
    assert metrics['exact_match_accuracy'] == .5
    assert metrics['failed_samples'] == 1
    assert metrics['successful_samples'] == 1
    assert metrics['cer'] == pytest.approx(3 / 9)
    assert metrics['wer'] == .5
    assert metrics['failures'][0]['crop_relative_path'] == 'crop.png'


def test_edits_empty_references_and_rates_above_one():
    assert edit_distance('kitten', 'sitting') == 3
    assert edit_distance('abc', '') == 3
    assert edit_distance('', 'abc') == 3
    metrics = calculate_metrics([result('', 'one two')])
    assert metrics['wer'] == 2
    assert metrics['cer'] == 7
    assert calculate_metrics([])['total_evaluated_samples'] == 0
    assert calculate_metrics([result('', None, failed=True)])['exact_matches'] == 0


def write_manifest(tmp_path, rows):
    manifest = tmp_path / 'test.jsonl'
    manifest.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    return manifest


def record(path='line.png'):
    return {'page_id': 'page-1', 'crop_relative_path': path, 'transcription': '  Original! '}


def test_manifest_preserves_reference_and_resolves_against_crop_root(tmp_path):
    row = record('line_images/line.png')
    path = write_manifest(tmp_path, [row])
    assert load_manifest(path, tmp_path, expected_samples=1) == [row]
    with pytest.raises(ValueError, match='Expected 1116'):
        load_manifest(path, tmp_path, expected_samples=1116)


@pytest.mark.parametrize('rows, message', [
    ([], 'empty'), ([record(), record()], 'Duplicate'),
    ([record('../outside.png')], 'escapes'),
    ([{'page_id': 'p', 'crop_relative_path': 'a.png'}], 'fields'),
    ([{**record(), 'transcription': None}], 'fields'),
    ([[]], 'fields'),
])
def test_invalid_manifest_rejected(tmp_path, rows, message):
    with pytest.raises(ValueError, match=message):
        load_manifest(write_manifest(tmp_path, rows), tmp_path)


def test_invalid_json(tmp_path):
    manifest = tmp_path / 'test.jsonl'
    manifest.write_text('broken json\n')
    with pytest.raises(ValueError, match='line 1'):
        load_manifest(manifest, tmp_path)


@pytest.mark.parametrize('kind', ['missing', 'corrupt', 'inference', 'ok'])
def test_per_image_errors_and_unchanged_sources(tmp_path, kind):
    path = tmp_path / 'line.png'
    if kind == 'corrupt':
        path.write_bytes(b'broken image')
    elif kind != 'missing':
        Image.new('L', (10, 10)).save(path)
    before = path.read_bytes() if path.exists() else None
    calls = []

    def predict(image):
        assert image.mode == 'RGB'
        calls.append(True)
        if kind == 'inference':
            raise RuntimeError('inference failed')
        return '  Raw prediction!  '

    row = evaluate_sample(record(), tmp_path, predict)
    assert row['reference_raw'] == '  Original! '
    assert row['status'] == ('ok' if kind == 'ok' else 'failed')
    if kind == 'ok':
        assert row['prediction_raw'] == '  Raw prediction!  '
        assert row['prediction_normalized'] == 'Raw prediction!'
    else:
        assert row['error']
        assert row['prediction_raw'] is None
        assert row['failure_stage'] == ('inference' if kind == 'inference' else 'image')
        assert calculate_metrics([row])['failed_samples'] == 1
    assert bool(calls) == (kind in ('inference', 'ok'))
    assert (path.read_bytes() if path.exists() else None) == before


def test_split_selection_keeps_outputs_separate():
    from evaluation.evaluate_trocr_baseline import evaluation_paths

    test_manifest, test_count, test_predictions, test_metrics = evaluation_paths('test')
    manifest, count, predictions, metrics = evaluation_paths('validation')
    assert manifest.name == 'validation.jsonl'
    assert count == 1197
    assert predictions.name == 'bentham_trocr_validation_predictions.jsonl'
    assert metrics.name == 'bentham_trocr_validation_metrics.json'
    assert test_manifest.name == 'test.jsonl'
    assert test_count == 1116
    assert test_predictions.name == 'bentham_trocr_baseline_predictions.jsonl'
    assert test_metrics.name == 'bentham_trocr_baseline_metrics.json'
    assert {predictions, metrics}.isdisjoint({test_predictions, test_metrics})
    with pytest.raises(ValueError, match='Unsupported'):
        evaluation_paths('train')


@pytest.mark.parametrize('change', ['none', 'manifest', 'crop'])
def test_input_integrity_validation(tmp_path, change):
    from evaluation.evaluate_trocr_baseline import crop_fingerprints, verify_inputs_unchanged

    rows = [record()]
    manifest = write_manifest(tmp_path, rows)
    original = manifest.read_bytes()
    crop = tmp_path / 'line.png'
    Image.new('RGB', (8, 8)).save(crop)
    before = crop_fingerprints(rows, tmp_path)
    if change == 'manifest':
        manifest.write_bytes(original + b'\n')
    elif change == 'crop':
        crop.write_bytes(b'changed')
    if change != 'none':
        with pytest.raises(RuntimeError, match='changed'):
            verify_inputs_unchanged(manifest, original, rows, tmp_path, before)
    else:
        report = verify_inputs_unchanged(manifest, original, rows, tmp_path, before)
        assert report == {'manifest_unchanged': True, 'crop_fingerprints_unchanged': True,
                          'readable_crops_verified': 1, 'unreadable_or_missing_crops': 0}


def test_validation_run_uses_local_cpu_loader_and_preserves_test_outputs(tmp_path, monkeypatch):
    import sys
    from contextlib import nullcontext
    from types import SimpleNamespace
    from evaluation import evaluate_trocr_baseline as evaluator

    root = tmp_path / 'crops'
    root.mkdir()
    Image.new('RGB', (8, 8)).save(root / 'line.png')
    rows = [record(), record('missing.png')]
    manifest = tmp_path / 'validation.jsonl'
    manifest.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    results = tmp_path / 'results'
    results.mkdir()
    sentinels = {}
    for suffix in ('predictions.jsonl', 'metrics.json'):
        path = results / f'bentham_trocr_baseline_{suffix}'
        path.write_bytes(b'existing test output must remain unchanged')
        sentinels[path] = path.read_bytes()
    monkeypatch.setattr(evaluator, 'VALIDATION_MANIFEST', manifest)
    monkeypatch.setattr(evaluator, 'CROP_ROOT', root)
    monkeypatch.setattr(evaluator, 'RESULTS', results)
    calls = []

    def load(path, crop_root, *, expected_samples):
        assert path == manifest
        assert crop_root == root
        assert expected_samples == 1197
        return rows  # Small fixture replaces only the manifest loader.

    monkeypatch.setattr(evaluator, 'load_manifest', load)
    fake_torch = SimpleNamespace(
        manual_seed=lambda seed: calls.append(('seed', seed)),
        set_num_threads=lambda threads: calls.append(('threads', threads)),
        use_deterministic_algorithms=lambda enabled: calls.append(('deterministic', enabled)),
        inference_mode=nullcontext,
    )
    monkeypatch.setitem(sys.modules, 'torch', fake_torch)
    # monkeypatch restores environment flags after this in-process fixture run.
    for key in ('HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE', 'TOKENIZERS_PARALLELISM'):
        monkeypatch.setenv(key, 'fixture')

    class Pixels:
        def to(self, device):
            assert device == 'cpu'
            return self

    class Processor:
        def __call__(self, *, images, return_tensors):
            assert images.mode == 'RGB'
            assert return_tensors == 'pt'
            return SimpleNamespace(pixel_values=Pixels())

        def batch_decode(self, tokens, *, skip_special_tokens):
            assert skip_special_tokens is True
            return ['  Original! ']

    class Model:
        config = SimpleNamespace(_commit_hash='cached-revision')

        def to(self, device):
            assert device == 'cpu'

        def eval(self):
            calls.append(('eval', True))

        def parameters(self):
            return iter([SimpleNamespace(dtype='torch.float32')])

        def generate(self, pixels, **options):
            assert options == {'max_new_tokens': 192, 'do_sample': False,
                               'num_beams': 1, 'use_cache': True}
            return ['tokens']

    class Recognizer:
        def __init__(self, name, *, local_files_only):
            assert name == 'microsoft/trocr-base-handwritten'
            assert local_files_only is True
            assert evaluator.os.environ['HF_HUB_OFFLINE'] == '1'
            assert evaluator.os.environ['TRANSFORMERS_OFFLINE'] == '1'
            self._loaded = fake_torch, Processor(), Model()

    monkeypatch.setattr(evaluator, 'TrOCRHandwritingRecognizer', Recognizer)
    metrics = evaluator.run_evaluation(split='validation')
    assert metrics['configuration']['split'] == 'validation'
    assert metrics['configuration']['checkpoint_revision'] == 'cached-revision'
    assert metrics['configuration']['device'] == 'cpu'
    assert metrics['total_evaluated_samples'] == 2
    assert metrics['failed_samples'] == 1
    assert metrics['failures'][0]['crop_relative_path'] == 'missing.png'
    assert ('seed', 42) in calls and ('deterministic', True) in calls
    predictions = results / 'bentham_trocr_validation_predictions.jsonl'
    saved = [json.loads(line) for line in predictions.read_text(encoding='utf-8').splitlines()]
    assert len(saved) == 2
    assert saved[0]['reference_raw'] == '  Original! '
    assert saved[0]['prediction_raw'] == '  Original! '
    assert saved[1]['status'] == 'failed'
    saved_metrics = json.loads((results / 'bentham_trocr_validation_metrics.json').read_text())
    assert saved_metrics == metrics
    assert all(path.read_bytes() == original for path, original in sentinels.items())
