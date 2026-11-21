"""Offline CPU TrOCR baseline on a selected Bentham evaluation split.

Run from ai-engine with the root environment:
    ..\\.venv\\Scripts\\python.exe -m evaluation.evaluate_trocr_baseline
No page enhancement/segmentation: prepared RGB line crops go directly through the
cached TrOCR processor. Normalization is NFC plus whitespace collapse/trim;
case, punctuation, accents and historical spelling are preserved. Corpus CER
and WER include failures as empty predictions; exact match counts failures as
incorrect. Rates are fractions, can exceed 1, and use max(1, reference units)
for an entirely empty reference corpus. Raw strings are retained in JSONL.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import random
import time
from datetime import datetime, timezone
import unicodedata
from collections.abc import Callable, Sequence

from PIL import Image

from preprocessing.handwritten_ocr import TrOCRHandwritingRecognizer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_MANIFEST = PROJECT_ROOT / 'datasets/manifests/bentham/test.jsonl'
VALIDATION_MANIFEST = PROJECT_ROOT / 'datasets/manifests/bentham/validation.jsonl'
CROP_ROOT = PROJECT_ROOT / 'datasets/processed/bentham'
RESULTS = PROJECT_ROOT / 'evaluation/results'
MODEL_NAME = 'microsoft/trocr-base-handwritten'
NORMALIZATION = {
    'unicode': 'NFC', 'whitespace': 'collapse Unicode whitespace to one ASCII space and trim',
    'case': 'preserved', 'punctuation': 'preserved', 'accents': 'preserved',
    'cer_units': 'Unicode code points including normalized spaces',
    'wer_units': 'whitespace-delimited words',
    'aggregation': 'corpus edit distance / total reference units; denominator at least 1',
    'failures': 'empty prediction for CER/WER; incorrect for exact match; all samples included',
}


def normalize_text(text: str) -> str:
    return ' '.join(unicodedata.normalize('NFC', text).split())


def edit_distance(reference: Sequence, prediction: Sequence) -> int:
    """Levenshtein distance with O(min(n, m)) memory."""
    if len(reference) < len(prediction):
        reference, prediction = prediction, reference
    previous = list(range(len(prediction) + 1))
    for i, expected in enumerate(reference, 1):
        current = [i]
        for j, actual in enumerate(prediction, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (expected != actual)))
        previous = current
    return previous[-1]


def calculate_metrics(rows: list[dict]) -> dict:
    char_errors = word_errors = chars = words = exact = 0
    failures = []
    for row in rows:
        reference = normalize_text(row['reference_raw'])
        failed = row['status'] != 'ok'
        prediction = '' if failed else normalize_text(row['prediction_raw'])
        char_errors += edit_distance(reference, prediction)
        word_errors += edit_distance(reference.split(), prediction.split())
        chars += len(reference)
        words += len(reference.split())
        exact += int(not failed and reference == prediction)
        if failed:
            failures.append({'crop_relative_path': row['crop_relative_path'],
                             'error': row['error'], 'stage': row['failure_stage']})
    total = len(rows)
    return {
        'cer': char_errors / max(1, chars), 'wer': word_errors / max(1, words),
        'exact_match_accuracy': exact / total if total else 0.0,
        'exact_matches': exact, 'total_evaluated_samples': total,
        'successful_samples': total - len(failures), 'failed_samples': len(failures),
        'character_errors': char_errors, 'reference_characters': chars,
        'word_errors': word_errors, 'reference_words': words,
        'failures': failures,
    }


def load_manifest(path: Path, crop_root: Path, *, expected_samples: int | None = None) -> list[dict]:
    """Validate metadata, but leave missing/broken images for per-sample reporting."""
    crop_root = crop_root.resolve()
    records = []
    seen = set()
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise ValueError(f'Invalid JSON on manifest line {number}') from exc
        if not isinstance(row, dict) or any(
            not isinstance(row.get(key), str) for key in
            ('page_id', 'crop_relative_path', 'transcription')
        ) or not row['page_id'].strip() or not row['crop_relative_path'].strip():
            raise ValueError(f'Invalid manifest fields on line {number}')
        relative = Path(row['crop_relative_path'])
        resolved = (crop_root / relative).resolve()
        if relative.is_absolute() or not resolved.is_relative_to(crop_root):
            raise ValueError(f'Crop path escapes crop root on line {number}')
        if resolved in seen:
            raise ValueError(f'Duplicate crop on line {number}: {relative}')
        seen.add(resolved)
        records.append(row)
    if not records:
        raise ValueError('Evaluation manifest is empty')
    if expected_samples is not None and len(records) != expected_samples:
        raise ValueError(f'Expected {expected_samples} crops, found {len(records)}')
    return records


def evaluate_sample(record: dict, crop_root: Path, predict: Callable[[Image.Image], str]) -> dict:
    row = {
        'page_id': record['page_id'], 'crop_relative_path': record['crop_relative_path'],
        'reference_raw': record['transcription'], 'prediction_raw': None,
        'reference_normalized': normalize_text(record['transcription']),
        'prediction_normalized': '', 'status': 'failed', 'error': None,
        'failure_stage': 'image', 'crop_sha256': None,
    }
    started = time.perf_counter()
    try:
        path = crop_root / record['crop_relative_path']
        row['crop_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        with Image.open(path) as source:
            source.load()
            image = source.convert('RGB')
        try:
            row['failure_stage'] = 'inference'
            prediction = predict(image)
            if not isinstance(prediction, str):
                raise TypeError('Model prediction must be a string')
            row.update(prediction_raw=prediction, prediction_normalized=normalize_text(prediction),
                       status='ok', failure_stage=None)
        finally:
            image.close()
    except Exception as exc:
        row['error'] = f'{type(exc).__name__}: {exc}'
    row['runtime_seconds'] = time.perf_counter() - started
    return row


def evaluation_paths(split: str) -> tuple[Path, int, Path, Path]:
    """Keep split selection explicit and test/validation outputs separate."""
    if split == 'test':
        manifest, expected, prefix = TEST_MANIFEST, 1116, 'bentham_trocr_baseline'
    elif split == 'validation':
        manifest, expected, prefix = VALIDATION_MANIFEST, 1197, 'bentham_trocr_validation'
    else:
        raise ValueError(f'Unsupported evaluation split: {split}')
    return (manifest, expected, RESULTS / f'{prefix}_predictions.jsonl',
            RESULTS / f'{prefix}_metrics.json')


def crop_fingerprints(records: list[dict], crop_root: Path) -> dict[str, str | None]:
    """Fingerprint readable crops; missing/unreadable files still get failure rows."""
    fingerprints = {}
    for record in records:
        relative = record['crop_relative_path']
        try:
            fingerprints[relative] = hashlib.sha256((crop_root / relative).read_bytes()).hexdigest()
        except OSError:
            fingerprints[relative] = None
    return fingerprints


def verify_inputs_unchanged(manifest: Path, manifest_bytes: bytes, records: list[dict],
                            crop_root: Path, before: dict[str, str | None]) -> dict:
    if manifest.read_bytes() != manifest_bytes:
        raise RuntimeError('Evaluation manifest changed; aggregate metrics not finalized')
    after = crop_fingerprints(records, crop_root)
    changed = [relative for relative in before if before[relative] != after.get(relative)]
    if changed:
        raise RuntimeError(f'Evaluation crops changed; aggregate metrics not finalized: {changed}')
    return {'manifest_unchanged': True, 'crop_fingerprints_unchanged': True,
            'readable_crops_verified': sum(value is not None for value in before.values()),
            'unreadable_or_missing_crops': sum(value is None for value in before.values())}


def run_evaluation(*, seed: int = 42, threads: int = 4, split: str = 'test') -> dict:
    # Both explicit loader flags and offline environment prevent network access.
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    manifest, expected_samples, predictions_path, metrics_path = evaluation_paths(split)
    manifest_bytes = manifest.read_bytes()
    records = load_manifest(manifest, CROP_ROOT, expected_samples=expected_samples)
    initial_crop_hashes = crop_fingerprints(records, CROP_ROOT)
    import torch

    random.seed(seed)
    import numpy as np
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(threads)
    torch.use_deterministic_algorithms(True)
    recognizer = TrOCRHandwritingRecognizer(MODEL_NAME, local_files_only=True)
    # Reuse the established lazy loader and processor, omitting confidence-score
    # tensors and page processing for this already segmented line-crop baseline.
    _, processor, model = recognizer._loaded
    model.to('cpu')
    model.eval()
    generation = {'max_new_tokens': 192, 'do_sample': False, 'num_beams': 1,
                  'use_cache': True}

    def predict(image: Image.Image) -> str:
        pixels = processor(images=image, return_tensors='pt').pixel_values
        with torch.inference_mode():
            tokens = model.generate(pixels.to('cpu'), **generation)
        return processor.batch_decode(tokens, skip_special_tokens=True)[0]

    RESULTS.mkdir(parents=True, exist_ok=True)
    configuration = {
        'model_name': MODEL_NAME, 'checkpoint_revision': getattr(model.config, '_commit_hash', None),
        'local_files_only': True, 'split': split, 'evaluation_seed': seed,
        'split_seed': 42, 'device': 'cpu', 'dtype': str(next(model.parameters()).dtype),
        'threads': threads, 'batch_size': 1, 'deterministic_algorithms': True,
        'generation': generation, 'normalization': NORMALIZATION,
        'image_preprocessing': 'Pillow decode and RGB conversion, then cached TrOCRProcessor; no page segmentation or enhancement',
        'manifest': str(manifest), 'crop_root': str(CROP_ROOT),
        'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
        'versions': {name: importlib.metadata.version(name) for name in
                     ('torch', 'transformers', 'Pillow', 'numpy')},
        'started_at_utc': started_at,
        'limitations': f'Page-level {split} separation only; writer IDs unavailable. Only the selected split is evaluated. CPU float32 greedy baseline; results depend on recorded software and hardware.',
    }
    # Mark the run as incomplete before predictions are streamed, so interruption
    # cannot leave old aggregate metrics paired with a new partial predictions file.
    metrics_path.write_text(json.dumps({'status': 'running', 'configuration': configuration},
                                      indent=2) + '\n', encoding='utf-8')
    rows = []
    print(f'Local model loaded; evaluating {len(records)} {split} crops on CPU ({threads} threads).', flush=True)
    with predictions_path.open('w', encoding='utf-8', newline='\n') as handle:
        for index, record in enumerate(records, 1):
            row = evaluate_sample(record, CROP_ROOT, predict)
            rows.append(row)
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')
            handle.flush()
            if row['status'] != 'ok':
                print(f"FAILED {row['crop_relative_path']}: {row['error']}", flush=True)
            if index == 1 or index % 10 == 0 or index == len(records):
                elapsed = time.perf_counter() - started
                print(f'{index}/{len(records)} | {elapsed:.1f}s elapsed | '
                      f'{sum(r["status"] != "ok" for r in rows)} failed', flush=True)
    integrity = verify_inputs_unchanged(manifest, manifest_bytes, records, CROP_ROOT, initial_crop_hashes)
    result = {'status': 'complete', **calculate_metrics(rows), 'configuration': configuration,
              'input_integrity': integrity,
              'finished_at_utc': datetime.now(timezone.utc).isoformat(),
              'runtime_seconds': time.perf_counter() - started,
              'predictions_sha256': hashlib.sha256(predictions_path.read_bytes()).hexdigest()}
    temporary = metrics_path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, metrics_path)
    print(json.dumps({k: v for k, v in result.items() if k not in ('configuration', 'failures')}, indent=2), flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=('test', 'validation'), default='test')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error('--threads must be positive')
    try:
        result = run_evaluation(seed=args.seed, threads=args.threads, split=args.split)
    except Exception as exc:
        parser.exit(1, f'Evaluation could not complete: {type(exc).__name__}: {exc}\n')
    if result['failed_samples']:
        parser.exit(2, 'Evaluation completed with failures; inspect metrics and prediction rows.\n')


if __name__ == '__main__':
    main()
