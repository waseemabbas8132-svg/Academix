# TrOCR Accuracy Investigation — Academix

**Date:** 2026-11-17  
**Scope:** Existing Bentham validation predictions and artifacts; no held-out test data, training, downloads, dataset edits, or production OCR changes.

## Executive result

The 100% exact-transcription target was **not achieved**. On all **1,197 validation lines across 43 pages**, the best fully verified configuration has:

| Metric | User-supplied baseline / best verified | Target |
|---|---:|---:|
| CER | **16.2436%** | 0% |
| WER | **40.3155%** | 0% |
| Exact transcription | **79 / 1,197 (6.5998%)** | 1,197 / 1,197 |
| Failed inference rows | **0** | 0 |
| Non-exact predictions remaining | **1,118** | 0 |

This best verified result is already the user-supplied baseline; this investigation produced **no additional measured accuracy gain** over it. Compared with the saved pre-enhancement greedy baseline, the existing enhancement reduced CER by **1.1132 percentage points (6.41% relative)** and WER by **1.0419 points (2.52% relative)**, and added **8 exact lines** (**+0.6683 points; +11.27% relative**). It improved 415 lines, regressed 280, and left 502 unchanged. The result is not a guarantee of better recognition on every line or on contemporary student work.

## Scope and reproducibility

The requested baseline exactly matches the completed saved full-validation candidate. Its saved prediction file was re-read and its metrics recomputed; all 1,197 rows, references, paths, and statuses were paired against the original saved baseline. The new analysis records input hashes and preserves every non-exact raw reference/prediction pair in [`remaining_incorrect_predictions.jsonl`](results/trocr_100_percent_20261117/remaining_incorrect_predictions.jsonl).

The held-out test split was not opened or evaluated. No source images, manifests, prior predictions, or prior metrics were overwritten. The full model inference comparison and preprocessing screens listed below were already saved in the dated preprocessing experiment folders; this task analyzed those records rather than repeating an approximately 10-hour elapsed full-validation run.

## Pipeline and likely error sources

### Observed inference path

- Production handwritten OCR in [`handwritten_ocr.py`](../preprocessing/handwritten_ocr.py) and [`image_preprocessor.py`](../preprocessing/image_preprocessor.py) applies EXIF orientation, grayscale conversion, a 3×3 median filter, 1% autocontrast, contrast factor 1.15, and a 2,400-pixel maximum dimension before line segmentation.
- `_line_regions` thresholds at grayscale 190, requires at least `max(3, int(width × 0.002))` foreground pixels per row, merges row gaps up to a size-dependent threshold, adds 8 pixels vertically, and retains the full image width. These fixed thresholds can plausibly merge close lines or miss faint/small writing. The Bentham line-crop benchmark bypasses page segmentation, so it does **not** measure either failure mode.
- Prepared Bentham crops enter the cached `TrOCRProcessor` as RGB. Its 384×384 resize is square and therefore stretches very wide lines. Aspect-preserving square padding was tested and sharply worsened recognition; changing that geometry is not justified by these data.
- The application uses greedy decoding (`num_beams=1`, no sampling, `max_new_tokens=192`). The model produces a mean of per-step maximum token probabilities as a confidence signal, but this is not calibrated confidence. The existing low-confidence/review path should be retained; 0 failed rows does not mean predictions are correct.
- For PDFs, pages with embedded text bypass image OCR. Pages that also contain graphics/annotations are flagged for review, but extracted text can still omit handwritten content. This is a separate document-extraction limitation, not measured by line-crop CER/WER.

### Full-set error patterns

Error alignment is deterministic Levenshtein alignment; it identifies character/word edits, not their visual cause.

| Error category | Count |
|---|---:|
| Character substitutions | 5,639 |
| Character deletions | 973 |
| Character insertions | 2,187 |
| Word substitutions | 2,988 |
| Word deletions | 151 |
| Word insertions | 924 |
| Lines with aligned missing words | 117 |
| Lines with aligned extra words | 628 |
| Heuristic near-spelling candidates | 282 |
| Inference failures | 0 |

The most frequent character confusions are `e→o` (85), `t→l` (82), `e→a` (79), `b→h` (69), and `n→m` (66). Inserted spaces account for 758 character insertions; 155 inserted word tokens contain only punctuation, and 96 word substitutions differ only in case. Case, punctuation, and historical spelling remain part of the score. No spelling correction or prediction rewriting was applied.

Short references are particularly difficult; their low character counts amplify CER and WER:

| Reference length | Lines | CER | WER | Exact |
|---|---:|---:|---:|---:|
| 1–10 characters | 161 | 69.08% | 103.45% | 29 |
| 11–25 | 73 | 27.27% | 89.76% | 4 |
| 26–50 | 304 | 15.38% | 37.56% | 23 |
| 51–75 | 653 | 15.41% | 38.35% | 23 |
| 76–100 | 6 | 14.23% | 37.04% | 0 |

The validation crop audit found widths **37–1,993 px** (median 1,691), heights **32–326 px** (median 120), and median width/height **12.7**. Seven crops are shorter than 48 px; four contain no pixel below grayscale 160. No EXIF orientation tags or dark outer-edge pixels were detected. These descriptive signals do not prove crops are correctly segmented or that polygon masks retained every pen stroke. Source-to-crop geometry was not independently adjudicated.

The full-set evidence establishes where errors accumulate, not a single cause. Visual ambiguity, short-line context loss, domain/writer variation, masking, and line segmentation are plausible contributors but cannot be attributed per sample from prediction strings alone.

## Experiments and measured results

All prior OCR experiments used the cached `microsoft/trocr-base-handwritten` checkpoint, CPU float32, batch size 1, four Torch threads, and identical greedy generation. No reference labels were changed.

### Isolated preprocessing screen

The screen used 43 validation lines, one per page. `C/R/U` is the number of lines with fewer/more/equal character errors than the paired greedy baseline. Runtime is seconds for that variant. All had zero failures. Free RAM before/after loading the shared model was **3.13/3.04 GiB**; the whole nine-variant screen took **1,098 seconds** including model load and diagnostics.

| Variant | CER | WER | Exact | C/R/U | Runtime (s) |
|---|---:|---:|---:|---:|---:|
| Original replay | 17.77% | 41.67% | 1/43 | 0/0/43 | 114.70 |
| Existing median/autocontrast/contrast enhancement | **15.10%** | **37.78%** | 1/43 | 18/8/17 | 113.64 |
| Grayscale + global contrast | 16.74% | 38.89% | 1/43 | 9/7/27 | 110.38 |
| CLAHE | 16.90% | 39.72% | 0/43 | 14/9/20 | 121.56 |
| Bilateral denoise | 17.05% | 39.44% | 1/43 | 11/8/24 | 119.07 |
| Deskew heuristic | 17.41% | 39.17% | 0/43 | 8/8/27 | 112.46 |
| Otsu threshold | 33.54% | 55.00% | 1/43 | 20/15/8 | 107.22 |
| Aspect-preserving 384×384 pad | 84.80% | 105.83% | 1/43 | 2/37/4 | 110.66 |
| Added white margins | 17.98% | 41.94% | 1/43 | 13/13/17 | 113.47 |

The preselected existing enhancement then improved on the disjoint next-two-lines-per-page confirmation sample (86 lines): CER **19.38% → 18.59%**, WER **44.71% → 42.60%**, exact **4/86 → 4/86**, C/R/U **30/21/35**, runtime **230.40 s**, zero failures. This passed the prior confirmation criterion.

### Full validation and baseline comparison

The same existing enhancement was freshly run on all 1,197 validation lines. The paired saved original predictions had already been replay-checked on 43 lines with exact raw prediction agreement.

| Metric | Saved original greedy | Existing enhancement | Change |
|---|---:|---:|---:|
| CER | 17.3568% | **16.2436%** | −1.1132 pp / −6.41% relative |
| Character edits | 9,402 / 54,169 | **8,799 / 54,169** | −603 |
| WER | 41.3574% | **40.3155%** | −1.0419 pp / −2.52% relative |
| Word edits | 4,168 / 10,078 | **4,063 / 10,078** | −105 |
| Exact lines | 71 / 1,197 | **79 / 1,197** | +8 / +0.6683 pp / +11.27% relative |
| Failures | 0 | **0** | No change |
| Improved / regressed / unchanged lines | — | **415 / 280 / 502** | Paired character-edit comparison |

The confirmation run began with **3.72 GiB free RAM** and had **3.39 GiB** after model load. The prior full run began with **3.47 GiB** and had **3.42 GiB** after model load. It required **36,396.6 seconds of measured evaluation wall time** (36,432.0 seconds including model load and diagnostics); Windows process counters recorded 14,701 CPU-seconds. Wall time included long unaccounted gaps; it is not continuous compute time or an estimate of a new run's duration. A sample memory observation recorded a 1,730 MiB peak working set.

### Decoder and model-alternative investigation

No beam-search or decoding-parameter inference was run in this task. A fresh memory preflight found **15.69 GiB physical RAM but only 1.43 GiB available**, below the existing experiment runner's 2.5 GiB pre-model-load safety threshold. Checkpoint loading was therefore refused rather than risk memory pressure. The untested beam configurations are recorded in [`decoder_experiment_decision.json`](results/trocr_100_percent_20261117/decoder_experiment_decision.json) with no fabricated metrics.

The local Hugging Face cache contains TrOCR and a CLIP image-text model; CLIP is not a handwriting transcription replacement. No Tesseract executable or installed `pytesseract`, EasyOCR, PaddleOCR, docTR, or ONNX Runtime package was found. No alternative checkpoint, dependency, or dataset was downloaded. No fine-tuning was attempted: the separate [fine-tuning readiness investigation](TROCR_FINE_TUNING_READINESS.md) and [blockers investigation](TROCR_BLOCKERS_INVESTIGATION.md) report unresolved Bentham licensing/provenance, absent training plumbing/dependencies, and model-loss alignment blockers.

## Best verified configuration

- Checkpoint: `microsoft/trocr-base-handwritten`, cached revision `eaacaf452b06415df8f10bb6fad3a4c11e609406`.
- Preprocessing on the validation line crops: current existing enhancement—grayscale, median filter size 3, autocontrast cutoff 1%, contrast 1.15, maximum dimension 2,400; converted back to RGB before the processor.
- Processor/tokenizer: cached slow TrOCR/ViT image processor and Roberta byte-level BPE tokenizer (50,265-token vocabulary). RGB input is bilinearly resized to 384×384, rescaled by 1/255, then normalized with channel mean/std 0.5. Token IDs are BOS 0, PAD 1, EOS 2; decoder start is 2. Processor and checkpoint revision were reused unchanged.
- Generation: greedy, `num_beams=1`, `do_sample=false`, `max_new_tokens=192`, `use_cache=true`.
- Evaluation: CPU float32, batch size 1, four threads; NFC and whitespace collapse only. Case, punctuation, accents, and spelling preserved.

This is the best **measured** setup in these artifacts. The line-crop transform applies the same image operations as the page preprocessor, but the experiment does not validate page segmentation, mixed PDFs, camera perspective, or current student handwriting end-to-end.

## Production and integrity decision

**Production OCR was not changed or further improved by this task.** The current application already contains the enhancement operations. The preprocessing experiment is not wired in as a second pass; unmeasured transforms and decoder alternatives were not promoted. Existing review warnings remain important because the confidence score is not calibrated and most lines are not exact.

Regression checks run from `ai-engine` using the root `.venv` interpreter and a fresh temporary directory:

```powershell
..\.venv\Scripts\python.exe -B -m pytest tests\test_ocr_preprocessing_experiments.py tests\test_trocr_baseline.py tests\test_pipeline.py -q -p no:cacheprovider --basetemp=<fresh-temp-directory> --tb=short
```

Result: **49 passed in 4.88 seconds**; see [`regression_test_results.json`](results/trocr_100_percent_20261117/regression_test_results.json). The saved-validation analyzer also verified metric recomputation, pairing, full coverage, and 1,118 non-exact rows before writing its additive artifacts. Original prediction and metric files were read only.

## Remaining work toward higher accuracy

1. When free RAM safely exceeds the preflight threshold, screen beam widths/length penalties on a fresh page-stratified validation subset; evaluate a candidate on all 1,197 rows before promotion. Beam search may improve or worsen exact transcription and is not presumed better.
2. Measure page segmentation and mixed-PDF extraction on independently transcribed modern student pages; Bentham line crops cannot validate these stages.
3. Review crop polygons and short-line cases against source pixels, then evaluate narrowly justified padding/crop adjustments without changing reference labels.
4. Calibrate uncertainty against human-reviewed correctness before treating decoder token probabilities as confidence. Continue human review; do not infer missing words or automatically normalize spelling.
5. Revisit fine-tuning only after rights, data provenance, compute headroom, and the loss/label pipeline are independently cleared.

## Artifacts

New, additive artifacts are under [`results/trocr_100_percent_20261117/`](results/trocr_100_percent_20261117/):

- [`validation_analysis.json`](results/trocr_100_percent_20261117/validation_analysis.json): recomputed full-set metrics, paired counts, error patterns, length bins, data diagnostics, and source hashes.
- [`remaining_incorrect_predictions.jsonl`](results/trocr_100_percent_20261117/remaining_incorrect_predictions.jsonl): all 1,118 non-exact raw reference/prediction pairs.
- [`paired_sample_changes.json`](results/trocr_100_percent_20261117/paired_sample_changes.json): per-line improved/regressed/unchanged comparison.
- [`decoder_experiment_decision.json`](results/trocr_100_percent_20261117/decoder_experiment_decision.json) and [`local_environment_inventory.json`](results/trocr_100_percent_20261117/local_environment_inventory.json): safety and local-alternative findings.
- [`analyze_saved_validation.py`](results/trocr_100_percent_20261117/analyze_saved_validation.py) and [`environment_preflight.py`](results/trocr_100_percent_20261117/environment_preflight.py): reproducible local analysis/preflight scripts.

Prior measured preprocessing artifacts remain in the [screen results](results/trocr_preprocessing_screen_20261116/), [confirmation results](results/trocr_preprocessing_confirmation_20261116/), and [full-validation results](results/trocr_preprocessing_full_20261116/).
