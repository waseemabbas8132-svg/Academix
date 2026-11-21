"""Validation-only CPU preprocessing comparison; exclusive NEW output directory.

Run screen first. Confirmation/full phases accept an explicit chosen variant.
Full validation should be run only after the screen and confirmation justify it.
Original saved validation predictions are a checked paired reference, never used
to select samples. No test manifest/predictions/crops are opened by this module.
"""
from __future__ import annotations

import argparse
import ctypes
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import random
import time

from PIL import Image

from evaluation.evaluate_trocr_baseline import (
    CROP_ROOT, MODEL_NAME, NORMALIZATION, RESULTS, VALIDATION_MANIFEST,
    calculate_metrics, crop_fingerprints, edit_distance, evaluate_sample, load_manifest,
    normalize_text, verify_inputs_unchanged,
)
from preprocessing.handwritten_ocr import TrOCRHandwritingRecognizer
from preprocessing.ocr_image_experiments import VARIANTS, image_diagnostics, prepare_line_image

GENERATION = {'max_new_tokens': 192, 'do_sample': False, 'num_beams': 1, 'use_cache': True}


def available_memory_gib():
    if os.name != 'nt':
        return None
    class Memory(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
            (name, ctypes.c_ulonglong) for name in
            ('total', 'available', 'page', 'available_page', 'virtual', 'available_virtual', 'extended')]
    memory = Memory()
    memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise RuntimeError('Could not check available RAM')
    return memory.available / 2**30


def select_records(records: list[dict], phase: str, seed: int = 42) -> list[dict]:
    """One line per validation page for screen, next two for disjoint confirmation.

    Page and line shuffles are seeded; no predictions/errors influence selection.
    Output order is original manifest order. Full includes every validation row.
    """
    if phase == 'full':
        return list(records)
    if phase not in ('screen', 'confirmation'):
        raise ValueError('Unknown phase')
    by_page = defaultdict(list)
    for record in records:
        by_page[record['page_id']].append(record)
    selected = set()
    rng = random.Random(seed)
    for page in sorted(by_page):
        values = sorted(by_page[page], key=lambda r: r['crop_relative_path'])
        rng.shuffle(values)
        for record in values[:1] if phase == 'screen' else values[1:3]:
            selected.add(record['crop_relative_path'])
    return [record for record in records if record['crop_relative_path'] in selected]


def paired_comparison(original: list[dict], candidate: list[dict]) -> dict:
    if [r['crop_relative_path'] for r in original] != [r['crop_relative_path'] for r in candidate]:
        raise ValueError('Paired samples/order differ')
    wins = losses = ties = 0
    for left, right in zip(original, candidate):
        if left['reference_raw'] != right['reference_raw']:
            raise ValueError('Paired references differ')
        ref = normalize_text(left['reference_raw'])
        a = edit_distance(ref, normalize_text(left['prediction_raw']) if left['status'] == 'ok' else '')
        b = edit_distance(ref, normalize_text(right['prediction_raw']) if right['status'] == 'ok' else '')
        wins += b < a
        losses += b > a
        ties += a == b
    baseline, improved = calculate_metrics(original), calculate_metrics(candidate)
    return {'cer_delta_percentage_points': (improved['cer'] - baseline['cer']) * 100,
            'wer_delta_percentage_points': (improved['wer'] - baseline['wer']) * 100,
            'exact_match_delta_percentage_points': (improved['exact_match_accuracy'] - baseline['exact_match_accuracy']) * 100,
            'lines_fewer_character_errors': wins, 'lines_more_character_errors': losses,
            'lines_equal_character_errors': ties}


def _write_json(path, value):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write('\n')


def run_experiment(output: Path, phase: str, variants: list[str], *, seed=42, threads=4):
    if not variants or len(set(variants)) != len(variants) or any(v not in VARIANTS for v in variants):
        raise ValueError('Provide unique valid variants')
    # No configurable input path/split: this runner cannot evaluate test/train.
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    manifest_bytes = VALIDATION_MANIFEST.read_bytes()
    all_records = load_manifest(VALIDATION_MANIFEST, CROP_ROOT, expected_samples=1197)
    records = select_records(all_records, phase, seed)
    if not records:
        raise ValueError('Selection is empty')
    # Full validation integrity check even for a small screen, without reading test.
    before = crop_fingerprints(all_records, CROP_ROOT)
    saved_predictions = RESULTS / 'bentham_trocr_validation_predictions.jsonl'
    saved_metrics = RESULTS / 'bentham_trocr_validation_metrics.json'
    protected = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (saved_predictions, saved_metrics)}
    saved = [json.loads(line) for line in saved_predictions.read_text(encoding='utf-8').splitlines()]
    old_metrics = json.loads(saved_metrics.read_text(encoding='utf-8'))
    if len(saved) != len(all_records) or calculate_metrics(saved) != {k: old_metrics[k] for k in calculate_metrics(saved)}:
        raise ValueError('Saved validation metric/coverage inconsistency')
    for record, old in zip(all_records, saved):
        if (record['crop_relative_path'], record['page_id'], record['transcription'], before[record['crop_relative_path']]) != (old['crop_relative_path'], old['page_id'], old['reference_raw'], old['crop_sha256']):
            raise ValueError('Saved validation input/reference mismatch')
    if old_metrics['configuration']['manifest_sha256'] != hashlib.sha256(manifest_bytes).hexdigest():
        raise ValueError('Saved validation manifest hash mismatch')
    if old_metrics['predictions_sha256'] != protected[saved_predictions]:
        raise ValueError('Saved prediction hash mismatch')
    # Refuse overwrite of any earlier run or baseline. Parent must be results.
    output = output.resolve()
    if output.parent != RESULTS.resolve():
        raise ValueError('Output must be a new direct child of evaluation/results')
    output.mkdir(exist_ok=False)
    _write_json(output / 'RUNNING.json', {'phase': phase, 'variants': variants, 'started_at_utc': started_at})
    _write_json(output / 'protocol.json', {
        'screen_gate': 'CER reduction >=0.5 percentage points, WER non-increasing, exact matches non-decreasing, zero failures',
        'confirmation_gate': 'On disjoint next-two-lines/page: CER reduction >=0.25 percentage points, WER non-increasing, zero failures',
        'full_gate': 'Run only for a candidate passing both gates; accept no production change based only on subset evidence',
        'test_split': 'Never read or evaluated',
    })
    quality = []
    for record in all_records:
        with Image.open(CROP_ROOT / record['crop_relative_path']) as image:
            image.load()
            quality.append({'crop_relative_path': record['crop_relative_path'], **image_diagnostics(image)})
    _write_json(output / 'validation_image_diagnostics.json', quality)
    import numpy as np
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(threads)
    torch.use_deterministic_algorithms(True)
    memory_before_load = available_memory_gib()
    if memory_before_load is not None and memory_before_load < 2.5:
        raise RuntimeError(f'Only {memory_before_load:.2f} GiB available before model load; refuse memory pressure')
    recognizer = TrOCRHandwritingRecognizer(MODEL_NAME, local_files_only=True)
    _, processor, model = recognizer._loaded
    model.to('cpu').eval()
    revision = getattr(model.config, '_commit_hash', None)
    if revision != old_metrics['configuration']['checkpoint_revision']:
        raise ValueError('Checkpoint differs from saved baseline')
    if GENERATION != old_metrics['configuration']['generation'] or NORMALIZATION != old_metrics['configuration']['normalization']:
        raise ValueError('Generation or normalization differs from baseline')
    configuration = {'model_name': MODEL_NAME, 'checkpoint_revision': revision,
                     'local_files_only': True, 'split': 'validation', 'phase': phase,
                     'seed': seed, 'threads': threads, 'device': 'cpu', 'batch_size': 1,
                     'dtype': str(next(model.parameters()).dtype), 'generation': GENERATION,
                     'normalization': NORMALIZATION, 'variants': {v: VARIANTS[v] for v in variants},
                     'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
                     'baseline_predictions_sha256': protected[saved_predictions],
                     'selection': 'seeded per-page shuffle; screen first, confirmation next two; full all',
                     'selected_samples': [{'page_id': r['page_id'], 'crop_relative_path': r['crop_relative_path']} for r in records],
                     'reference_length_bins': dict(Counter('1-10' if len(normalize_text(r['transcription'])) <= 10 else '11-25' if len(normalize_text(r['transcription'])) <= 25 else '26-50' if len(normalize_text(r['transcription'])) <= 50 else '51+' for r in records)),
                     'processor': processor.image_processor.to_dict(),
                     'versions': {n: importlib.metadata.version(n) for n in ('torch', 'transformers', 'Pillow', 'numpy', 'opencv-python-headless')},
                     'started_at_utc': started_at}
    configuration['available_ram_gib_before_model_load'] = memory_before_load
    configuration['available_ram_gib_after_model_load'] = available_memory_gib()
    _write_json(output / 'configuration.json', configuration)
    reference_by_path = {r['crop_relative_path']: r for r in saved}
    original = [reference_by_path[r['crop_relative_path']] for r in records]
    _write_json(output / 'paired_saved_baseline_metrics.json', calculate_metrics(original))
    metrics = {}
    predictions = {}
    for variant in variants:
        variant_started = time.perf_counter()
        rows = []
        def predict(image):
            transformed = prepare_line_image(image, variant)
            try:
                pixels = processor(images=transformed, return_tensors='pt').pixel_values
            finally:
                transformed.close()
            with torch.inference_mode():
                tokens = model.generate(pixels.to('cpu'), **GENERATION)
            return processor.batch_decode(tokens, skip_special_tokens=True)[0]
        path = output / f'{variant}_validation_predictions.jsonl'
        print(f'BEGIN {phase} {variant}: {len(records)} crops', flush=True)
        with path.open('x', encoding='utf-8', newline='\n') as handle:
            for index, record in enumerate(records, 1):
                row = evaluate_sample(record, CROP_ROOT, predict)
                row['preprocessing_variant'] = variant
                rows.append(row)
                handle.write(json.dumps(row, ensure_ascii=False) + '\n')
                handle.flush()
                if index == 1 or index % 10 == 0 or index == len(records):
                    print(f'{variant} {index}/{len(records)} elapsed={time.perf_counter()-variant_started:.1f}s failures={sum(r["status"]!="ok" for r in rows)}', flush=True)
        result = {**calculate_metrics(rows), 'status': 'complete', 'variant': variant,
                  'configuration': configuration, 'runtime_seconds': time.perf_counter() - variant_started,
                  'comparison_to_saved_original': paired_comparison(original, rows),
                  'finished_at_utc': datetime.now(timezone.utc).isoformat(),
                  'predictions_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        if variant == 'original':
            result['replayed_predictions_identical_to_saved'] = all(
                (a['status'], a['prediction_raw']) == (b['status'], b['prediction_raw']) for a, b in zip(original, rows))
        _write_json(output / f'{variant}_validation_metrics.json', result)
        metrics[variant] = result
        predictions[variant] = rows
        print('RESULT ' + json.dumps({k: result[k] for k in ('variant','cer','wer','exact_match_accuracy','failed_samples','runtime_seconds')}), flush=True)
    integrity = verify_inputs_unchanged(VALIDATION_MANIFEST, manifest_bytes, all_records, CROP_ROOT, before)
    if any(hashlib.sha256(p.read_bytes()).hexdigest() != digest for p, digest in protected.items()):
        raise RuntimeError('Existing validation results changed')
    summary = {'status': 'complete', 'configuration': configuration, 'metrics': metrics,
               'input_integrity': integrity, 'existing_validation_outputs_unchanged': True,
               'runtime_seconds_including_load_and_diagnostics': time.perf_counter()-started}
    _write_json(output / 'comparison.json', summary)
    print('COMPLETE ' + str(output), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('screen', 'confirmation', 'full'), default='screen')
    parser.add_argument('--variants', nargs='+', choices=VARIANTS, default=list(VARIANTS))
    parser.add_argument('--output-name', required=True)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    if args.threads < 1 or Path(args.output_name).name != args.output_name:
        parser.error('threads must be positive and output-name must be a directory name')
    run_experiment(RESULTS / args.output_name, args.phase, args.variants,
                   seed=args.seed, threads=args.threads)


if __name__ == '__main__':
    main()
