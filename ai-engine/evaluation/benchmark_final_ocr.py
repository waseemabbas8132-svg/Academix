"""Reanalyse existing validation OCR predictions; do not rerun model experiments.

Copied predictions retain their original measured inference provenance. New
runtime measures only reanalysis/decode/quality checks, never OCR throughput.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from PIL import Image

from evaluation.evaluate_trocr_baseline import (
    CROP_ROOT, RESULTS, VALIDATION_MANIFEST, calculate_metrics, edit_distance,
    load_manifest, normalize_text,
)
from preprocessing.handwritten_ocr import image_readability_warnings


def run():
    started = time.perf_counter()
    output = RESULTS / 'final_ai_sprint_20261117/ocr_benchmark'
    output.mkdir(exist_ok=False)
    original_path = RESULTS / 'bentham_trocr_validation_predictions.jsonl'
    enhanced_path = RESULTS / 'trocr_preprocessing_full_20261116/existing_validation_predictions.jsonl'
    sources = [original_path, enhanced_path, VALIDATION_MANIFEST]
    hashes = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    before = [json.loads(x) for x in original_path.read_text(encoding='utf-8').splitlines()]
    after = [json.loads(x) for x in enhanced_path.read_text(encoding='utf-8').splitlines()]
    records = load_manifest(VALIDATION_MANIFEST, CROP_ROOT, expected_samples=1197)
    if len(before) != len(records) or len(after) != len(records):
        raise ValueError('Saved validation prediction coverage differs')
    wins=losses=ties=quality_flags=0
    with (output/'paired_predictions.jsonl').open('x',encoding='utf-8') as pairs, (output/'regressions.jsonl').open('x',encoding='utf-8') as regressions:
        for record,a,b in zip(records,before,after):
            path=record['crop_relative_path']
            if (a['crop_relative_path'],a['reference_raw']) != (path,record['transcription']) or (b['crop_relative_path'],b['reference_raw']) != (path,record['transcription']):
                raise ValueError('Prediction/reference identity mismatch: '+path)
            digest=hashlib.sha256((CROP_ROOT/path).read_bytes()).hexdigest()
            if digest != a['crop_sha256'] or digest != b['crop_sha256']:
                raise ValueError('Validation crop changed: '+path)
            with Image.open(CROP_ROOT/path) as image:
                image.load();flags=image_readability_warnings(image)
            quality_flags += bool(flags)
            ref=normalize_text(record['transcription'])
            first=edit_distance(ref,normalize_text(a['prediction_raw']) if a['status']=='ok' else '')
            second=edit_distance(ref,normalize_text(b['prediction_raw']) if b['status']=='ok' else '')
            delta=second-first;wins+=delta<0;losses+=delta>0;ties+=delta==0
            row={'page_id':record['page_id'],'crop_relative_path':path,'reference_raw':record['transcription'],
                 'original_prediction_raw':a['prediction_raw'],'enhanced_prediction_raw':b['prediction_raw'],
                 'original_character_edits':first,'enhanced_character_edits':second,
                 'character_edit_change':delta,'current_readability_warnings':flags,
                 'predictions_reused_without_new_inference':True,'crop_sha256':digest}
            text=json.dumps(row,ensure_ascii=False)+'\n';pairs.write(text)
            if delta>0:regressions.write(text)
    for name,path in [('original_predictions.jsonl',original_path),('enhanced_predictions.jsonl',enhanced_path)]:
        with (output/name).open('xb') as handle:handle.write(path.read_bytes())
    if any(hashlib.sha256(p.read_bytes()).hexdigest()!=hashes[str(p)] for p in sources):
        raise RuntimeError('An original artifact changed during reanalysis')
    result={'status':'complete','original':calculate_metrics(before),'enhanced':calculate_metrics(after),
            'lines_improved':wins,'lines_regressed':losses,'lines_tied':ties,
            'validation_crops_decoded_and_hash_verified':len(records),'current_uniform_contrast_flags':quality_flags,
            'ocr_confidence_available_in_saved_predictions':False,
            'quality_gate_accuracy_effect':'NOT MEASURED: saved predictions have no confidence; no fabricated replay of uncertainty gating',
            'sources_sha256':hashes,'originals_unchanged':True,'new_inference_performed':False,
            'accuracy_change_this_sprint':'No new OCR transform or new accuracy gain; prior measured gain reanalysed.',
            'reanalysis_only_runtime_seconds':time.perf_counter()-started,
            'finished_at_utc':datetime.now(timezone.utc).isoformat()}
    with (output/'metrics.json').open('x',encoding='utf-8') as handle:json.dump(result,handle,indent=2)
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':run()
