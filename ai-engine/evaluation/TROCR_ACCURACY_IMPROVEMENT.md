# TrOCR accuracy improvement sprint

Dates: 2026-11-16–17. Scope: cached-model inference and validation-only preprocessing experiments. No training, downloads, test-split evaluation, dataset regeneration, or application/backend/database changes.

**Completed: measured validation improvement using the existing enhancement.** Across all 1,197 validation crops, CER improved **17.3568% → 16.2436%**, WER **41.3574% → 40.3155%**, and exact match **71 → 79**; failures **0**. The original baseline bypassed enhancement. Academix already applies these enhancement operations before page segmentation, so **no second pass or new production default was added**. New thresholding, deskew, letterboxing, padding, and other experimental defaults were not promoted.

This establishes a benefit for the prepared Bentham line-crop benchmark. It does not establish the same accuracy on photographed student assignments or mixed-layout PDFs. Current page preprocessing remains unchanged; the new offline experiment tool and regression tests provide a reproducible way to evaluate future proposals.

## Existing pipeline findings

Inspected `preprocessing/handwritten_ocr.py`, `preprocessing/image_preprocessor.py`, `preprocessing/text_extractor.py`, `inference/evaluation_pipeline.py`, `evaluation/evaluate_trocr_baseline.py`, `preprocessing/prepare_bentham_dataset.py`, existing OCR/metric tests, validation error reports, readiness reports, and the saved diagnostic output from `test_trocr_pdf.py`.

The Bentham baseline and the application use different paths:

| Stage | Saved Bentham baseline | Current application path |
| --- | --- | --- |
| Input | Already segmented, polygon-masked RGB line crop | Uploaded page image or scanned PDF page |
| Orientation | RGB decode only | `ImageOps.exif_transpose`; no general 90-degree/upside-down detection |
| Enhancement | None before processor | Grayscale, median size 3, autocontrast cutoff 1%, contrast 1.15 |
| Resolution | Original crop dimensions into processor | Aspect-preserving thumbnail with maximum dimension 2400 |
| Segmentation | None | `_line_regions`: fixed gray cutoff 190, row-density threshold, scale-dependent whitespace gap, 8-pixel top/bottom margin; full input width retained |
| Model input | Cached processor's RGB bilinear resize to 384×384, normalization mean/std 0.5 | Same recognizer/processor, after page enhancement and line segmentation |
| PDF handling | Not used | Embedded text bypasses OCR; scanned pages rasterized at 2×72 = 144 DPI |

`test_trocr_pdf.py` is a separate diagnostic script: 300-DPI rasterization, CLAHE/threshold/Hough/component-based segmentation. Its saved two-page output has 59 candidate crops and 406 rejected regions, but no reference transcription or CER/WER. It cannot establish accuracy improvement, and its preprocessing is not the production pipeline.

All audited validation crops are smaller than the existing 2400-pixel limit. The measured `existing` candidate's benefit therefore comes from its grayscale/filter/contrast operations rather than its thumbnail limit; these operations were evaluated as a combination, not fully isolated filter ablations.

Potential causes and limits:

- Median filtering can erase narrow pen strokes; contrast clipping/thresholding can suppress faint strokes or amplify paper artifacts. These are plausible mechanisms to test, not established causes of every error.
- The processor stretches wide lines to a square. This changes shapes, but is also the existing checkpoint preprocessing convention. Replacing it with letterboxing may shrink text to only a few patch rows; preserving aspect ratio is not automatically more accurate.
- `_line_regions` can merge nearby lines or split detached marks on varied photographs/layouts. Low-contrast backgrounds can defeat its fixed threshold. Bentham line-crop experiments do not measure page segmentation quality.
- `_extract_pdf` skips all page OCR whenever `page.get_text('text')` returns any text. On mixed printed-question/handwritten-answer PDFs, graphical handwriting on that page can therefore be omitted. An in-memory synthetic PDF containing printed text and graphical ink made **zero OCR calls** and returned only `Printed assignment question` (`mixed_pdf_path_probe.json`). This proves the branch behavior, not real-handwriting CER. No unvalidated mixed-PDF extraction change was made.
- 144-DPI scanned-PDF rasterization and page downsampling can reduce fine-stroke information. Upsampling cannot restore information absent from a source. No unvalidated DPI/default change was made.
- Prepared crops include a four-pixel padded bounding box, but pixels outside the annotated polygon are whitened. Bounding-box padding does not recover strokes excluded by polygon geometry. Existing crops and masks were not regenerated or changed.
- Historical writing, proper names, punctuation, and annotation conventions differ from modern assignment text. Decoder language priors may favor plausible extra characters/words when evidence is weak. This is a hypothesis consistent with insertions; the experiment does not isolate model-domain causes.

## Existing measured recognition errors

The existing validation analysis uses 1,197 samples from 43 pages. It reports 9,402 character edits: **6,004 substitutions, 963 deletions, 2,435 insertions**. Examples of frequent substitutions are `t→l` (89), `e→o` (87), `e→a` (83), `r→n` (74), and `b→h` (70). These can reflect visually ambiguous strokes; alignment alone cannot prove whether preprocessing, handwriting, transcription, or the decoder caused a particular edit.

There are 754 inserted spaces, 168 punctuation-only inserted word tokens, and 91 case-only word substitutions. Reference annotation markers such as `_` also contribute to error rates. The fixed policy intentionally preserves these distinctions. Removing punctuation, case, markers, or rewriting predictions using references would change the evaluation target rather than demonstrate better OCR; none was done.

Sources: `evaluation/results/bentham_trocr_error_analysis.json`, `bentham_trocr_error_analysis.md`, and `bentham_trocr_validation_predictions.jsonl`. No test predictions were read for this sprint.

Two inspected severe examples (original crops preserved):

| Crop under `datasets/processed/bentham/line_images/` | Raw reference | Saved raw prediction |
| --- | --- | --- |
| `071_120_002__r3__r103__r004_l001_g001573.png` | `Of Injuries affecting loco-motion` | `legislationary background activities` |
| `071_018_003__r4__r106__r001_l022_g000580.png` | `injury, an act of unlawful <gap/> an act of kid=` | `injury , an undergraduate conferences-maned effitted :` |

Visual inspection shows dense/overlapping strokes and irregular masked outlines. The `<gap/>` reference explicitly includes unreadable-source notation. These examples illustrate recognition/annotation difficulty, not proof of a single preprocessing defect.

## Input-quality audit

All 1,197 validation images were decoded and fingerprinted. They are colour RGB crops: **0** have identical R/G/B channels. **0** contain EXIF orientation tags; EXIF correction therefore cannot improve this dataset. **0** contain gray<160 pixels in the outer two-pixel boundary; this does not exclude stroke loss at internal polygon edges. Four crops have no pixels below that threshold; this does not mean they contain no handwriting.

| Descriptive signal | Minimum | Median | 95th percentile | Maximum |
| --- | ---: | ---: | ---: | ---: |
| Width, pixels | 37 | 1691 | 1855.2 | 1993 |
| Height, pixels | 32 | 120 | 172 | 326 |
| Width/height | 0.56 | 12.70 | 17.75 | 25.30 |
| Grayscale Laplacian variance | 69.60 | 254.80 | 556.30 | 1793.44 |

Seven crops are shorter than 48 pixels. Laplacian variance is an uncalibrated sharpness/noise signal, not a blur diagnosis. Its bottom-to-top quartiles have saved-baseline CER of approximately 17.70%, 17.70%, 17.00%, 16.91%; lengths and content differ, so the association does not establish blur as a causal explanation. White polygon background dominates tile 90th-percentile lighting statistics, making that signal inadequate for a strong uneven-lighting claim. No claim that lighting is uniformly good is justified.

Detailed signals and their paired baseline summaries are saved in the new screen directory as `validation_image_diagnostics.json` and `input_diagnostics_summary.json`.

## Controlled experiment protocol

Runner: `evaluation/experiment_trocr_preprocessing.py`; isolated candidate transforms: `preprocessing/ocr_image_experiments.py`. Production defaults and existing signatures remain unchanged.

- Validation manifest only: `datasets/manifests/bentham/validation.jsonl`, expected 1,197 crops. The runner has no test/train input option.
- Seed 42. Sort each page's crop paths, shuffle with one seeded RNG over sorted page IDs. Screen = first line per page (43). Confirmation = next two per page, disjoint from the screen. Selection uses no prediction/error information. Full = all validation rows in manifest order.
- Screen reference lengths: 6 at 1–10 characters, 1 at 11–25, 12 at 26–50, and 24 at 51+. Every validation page is represented. One line per page is small evidence, not an independent final test.
- Checkpoint `microsoft/trocr-base-handwritten`, revision `eaacaf452b06415df8f10bb6fad3a4c11e609406`. Reuse `TrOCRHandwritingRecognizer._loaded`, processor, and baseline metric/image/error utilities.
- `local_files_only=True`, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`. CPU float32, four Torch threads, batch size one, inference mode, no gradients/optimizer/backward. One model serves all variants in each phase. Before loading, refuse if available Windows RAM is below 2.5 GiB.
- Unchanged generation: greedy, `do_sample=False`, `num_beams=1`, `max_new_tokens=192`, `use_cache=True`. No decoding/language-model tuning.
- The fresh original replay matched **43/43 saved raw predictions and statuses exactly**. Every saved validation row's identifier, reference, crop hash, manifest hash, and aggregate metrics are checked before comparison. Existing full-validation metrics can therefore be used as a paired baseline; they are never overwritten.
- Normalization: Unicode NFC, collapse Unicode whitespace to one space and trim; preserve case, punctuation, accents and spelling. CER counts Unicode code points including spaces. WER uses whitespace-delimited tokens. Both are corpus edit totals divided by total reference units, with a minimum denominator of one. Empty references can have rates above 100%. Failures are scored as empty predictions and non-exact matches, with filenames/stages/errors retained. Raw references/predictions are preserved.
- Every run creates an exclusive new directory. Predictions stream to new JSONL files; metrics are created only after each complete variant. `comparison.json` is the authoritative completion marker. `RUNNING.json` records the initial launch and may remain in completed directories. Interrupted runs lack the completed comparison.
- Recheck validation manifest/crop hashes and existing validation result hashes at phase completion. No source images or manifests are written.

The cached loader emits its existing warning about two newly initialized encoder-pooler tensors. The installed `VisionEncoderDecoderModel` uses `encoder_outputs[0]` (hidden states), not the pooler output; the exact original-prediction replay is the empirical control. The warning's generic suggestion to train was not acted on. Slow cached processor behavior was retained. One sampled process observation showed approximately 1,731 MiB peak working set and 1,932 MiB private memory; memory use was not extrapolated to a concurrent backend deployment.

Do not add a second enhancement call inside `TrOCRHandwritingRecognizer.recognize`: `recognize_page` already applies it before segmentation. Page-wide versus per-line histogram enhancement can differ, so this line-crop experiment is not an end-to-end student-page accuracy estimate.

Predeclared gates, saved in `protocol.json` before inference: screen CER reduction at least **0.5 percentage points**, WER non-increasing, exact matches non-decreasing, zero failures; disjoint confirmation CER reduction at least **0.25 points**, WER non-increasing, zero failures. Full validation only for candidates passing both. Production integration requires full-validation evidence and an appropriate scope of use, not a subset win alone.

| Variant | Operation |
| --- | --- |
| `original` | RGB crop and unchanged cached processor |
| `existing` | Current application page enhancement applied to each line; page segmentation deliberately excluded |
| `contrast` | Grayscale + global autocontrast with zero histogram-tail cutoff |
| `clahe` | Grayscale local CLAHE, clip limit 1.5, 8×2 tiles |
| `denoise` | Grayscale bilateral filter, diameter 5, sigmaColour 15, sigmaSpace 2 |
| `deskew` | Grayscale projection search ±3°, step 0.5°, at least 5% projection-score gain; expanded white canvas |
| `threshold` | Grayscale global Otsu; no color/gray stroke levels retained |
| `aspect` | Grayscale, aspect-preserving Lanczos fit into white 384×384 canvas |
| `margin` | White border on all sides: max(2, round(height×0.05)); no crop or filtering |

Deskew is guarded but can confuse writing slant with baseline skew. It cannot correct arbitrary rotation. Thresholding and letterboxing remain experimental unless measured results justify them.

The deskew heuristic selected a nonzero correction on **19/43** screen crops (absolute corrections 0.5–3 degrees). This is not evidence that those crops truly required rotation; `screen_skew_diagnostics.json` preserves every selected angle and projection-score gain.

## Measured results and decision

### Representative screen: 43 crops, all 43 validation pages

| Variant | CER | WER | Exact match | Failures | Runtime, seconds | Screen decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Original replay | 17.7709% | 41.6667% | 2.3256% (1/43) | 0 | 114.70 | Control; all raw predictions match saved baseline |
| Existing enhancement | **15.1002%** | **37.7778%** | 2.3256% (1/43) | 0 | 113.64 | Pass; selected for disjoint confirmation |
| Grayscale + global contrast | 16.7437% | 38.8889% | 2.3256% (1/43) | 0 | 110.38 | Pass, behind selected candidate |
| CLAHE | 16.8978% | 39.7222% | 0% | 0 | 121.56 | Reject gate: lost exact match |
| Bilateral denoise | 17.0519% | 39.4444% | 2.3256% (1/43) | 0 | 119.07 | Pass, behind selected candidate |
| Deskew | 17.4114% | 39.1667% | 0% | 0 | 112.46 | Reject gate: insufficient CER gain and lost exact match |
| Otsu threshold | 33.5388% | 55.0000% | 2.3256% (1/43) | 0 | 107.22 | Reject: substantially worse |
| Aspect-preserving square padding | 84.7971% | 105.8333% | 2.3256% (1/43) | 0 | 110.66 | Reject: substantially worse |
| Added white margins | 17.9764% | 41.9444% | 2.3256% (1/43) | 0 | 113.47 | Reject: worse |

All rows use the same 1,947 reference characters and 360 reference words. Total screen runtime, including model load, diagnostics and all nine variants: **1098.00 seconds (18.30 minutes)**. Per-variant runtimes include decoding, transformation, inference, metrics and output work, but exclude the shared initial model load/quality audit. They are single-run end-to-end timings, not isolated filter benchmarks; output token lengths also change inference time.

The existing enhancement reduced substitutions **248→194** and insertions **67→63**, but increased deletions **31→37**. Total character edits fell **346→294**. Otsu increased deletions **31→386**. Aspect padding produced **1,164 substitutions**, showing that preventing geometric stretch alone did not preserve recognition. All aligned operation counts are in `character_edit_operations.json`, calculated using the existing deterministic Levenshtein backtrace. No single filter's contribution is isolated by the multi-operation existing enhancement.

Original and improved examples retain raw strings in separate variant JSONL files. `screen_decision.json` records all eligibility decisions; the lowest-CER eligible candidate was chosen (WER then variant name break ties). No candidate's full-validation result was consulted for this choice.

Existing full validation baseline: CER **17.3568%**, WER **41.3574%**, exact match **5.9315%** (71/1,197), failures **0**, recorded runtime **3069.99 seconds**. It is historical baseline evidence, not a new full run from this sprint.

### Confirmation and final decision

The selected existing enhancement passed on the next two shuffled lines per page: **86 crops, all 43 pages, no crop overlap with the screen**. Confirmation shares the validation pages; it is not an independent writer/page/domain test.

| Disjoint confirmation | CER | WER | Exact match | Failures | Candidate runtime |
| --- | ---: | ---: | ---: | ---: | ---: |
| Paired saved original | 19.3848% | 44.7109% | 4.6512% (4/86) | 0 | Historical predictions, not rerun |
| Existing enhancement, fresh inference | **18.5892%** | **42.5952%** | 4.6512% (4/86) | 0 | **230.40 seconds** |

Character edits fell **731→701** over 3,771 reference characters; word edits **317→302** over 709 reference words. CER improved **0.7955 percentage points**, WER **2.1157 points**. There were 30 lines with fewer character errors, 21 with more, and 35 tied. This passes the predeclared confirmation gate; `confirmation_decision.json` records the decision. The smaller effect than on the screen reinforces the need for full validation.

Full validation was therefore run to completion for **all 1,197 crops** using only `existing`. No other candidate was promoted or retrospectively retuned.

### Full validation: final results

| Measure | Paired saved original | Fresh existing enhancement | Change |
| --- | ---: | ---: | ---: |
| Evaluated samples | 1,197 | 1,197 | Complete coverage |
| CER | 17.3568% | **16.2436%** | **−1.1132 percentage points** |
| Character edits / reference characters | 9,402 / 54,169 | **8,799 / 54,169** | 603 fewer edits |
| WER | 41.3574% | **40.3155%** | **−1.0419 percentage points** |
| Word edits / reference words | 4,168 / 10,078 | **4,063 / 10,078** | 105 fewer edits |
| Exact match | 5.9315% (71) | **6.5998% (79)** | 8 additional exact lines; +0.6683 points |
| Failed samples | 0 | **0** | No failure filenames/errors |

The full candidate was freshly inferred on every crop; it did not reuse candidate predictions from the screen/confirmation. The original column uses the preserved saved validation predictions, whose complete input/reference/crop hashes were checked and whose 43-crop replay matched exactly. No claim is made that the original 1,197-crop baseline was freshly rerun in this sprint.

Character substitutions fell **6,004→5,639** (−365), insertions **2,435→2,187** (−248), while deletions increased **963→973** (+10). The improvement primarily addresses substitutions and insertions; it does **not** solve deletions. There were **415 improved**, **280 regressed**, and **502 tied** lines by character-edit count. Aggregate gains are not a guarantee for each crop. A successful inference status means decoding completed; it does not mean the recognized text is correct.

| Normalized reference length | Crops | Original CER | Enhanced CER | Original WER | Enhanced WER |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1–10 characters | 161 | 73.2773% | 69.0756% | 108.0460% | 103.4483% |
| 11–25 | 73 | 30.8072% | 27.2652% | 92.1951% | 89.7561% |
| 26–50 | 304 | 16.1819% | 15.3770% | 38.6252% | 37.5614% |
| 51–75 | 653 | 16.4334% | 15.4055% | 39.1692% | 38.3468% |
| 76+ | 6 | 20.8068% | 14.2251% | 45.6790% | 37.0370% |

Very short references remain difficult and yield amplified error rates; the longest bin contains only six samples. These bins describe the fixed validation set, not a causal effect of length.

Two ranked examples from the new `paired_validation_examples.jsonl` (raw strings preserved in that file):

- Improvement, `line_images/072_167_004__r1__r107__r001_l007_g004574.png`: reference `For a Simple Personal Injury the Offender's Punish:`; original `For a disciple's historical highway the offender's Minister`; enhanced `For a Simple Personal Injury the offender's Minister`. Character edits **25→6**; the result is still not exact.
- Regression, `line_images/071_018_003__r4__r47__r001_l005_g000563.png`: reference `3. A man is always punishable for withholding his `; original `is not more in always punishable for earth-holding has`; enhanced `is a former challenge from the middle for another holding that`. Character edits **14→37**.

Exploratory paired page bootstrap: seed 42, 5,000 replicates; sort the 43 page IDs, draw 43 pages with replacement per replicate using NumPy `default_rng`, sum each selected page's error/reference and exact/sample counts, then compute candidate-minus-original corpus-rate deltas. The 2.5th–97.5th percentiles are **[−1.4956, −0.7339] CER points**, **[−1.6040, −0.4315] WER points**, and **[−0.3314, +1.6380] exact-match points**. These are exploratory validation intervals after candidate selection, not an independent test or a guarantee of modern-assignment performance. The exact-match interval includes zero. Counts, bins, intervals, and method are saved in `paired_validation_analysis.json`.

### Runtime and integrity

The full phase took **36,432.04 seconds wall time (10 h 7 min 12 s)** including load/diagnostics. The candidate's evaluation loop/metrics/output time was **36,396.59 seconds**. Both include the observed overnight wall-clock gaps; they must not be presented as continuous compute time or evidence that the enhancement itself is that slow.

Two sample timers recorded **21,473.74** and **10,970.16 seconds**. Their cause was not established from system event logs. Across all samples the median timer was **3.019 seconds**, P95 **4.878 seconds**. Read-only Windows counters measured **14,701.05 total process CPU seconds** summed across threads (kernel 1,272.94; user 13,428.11), distinct from elapsed wall seconds. `process_resource_final.json` preserves the counters and process UTC creation/exit timestamps. These observations do not establish a speedup against the historical original run.

The process continued sequentially through the gaps without replacing or fabricating predictions. All **1,197** new rows have unique paths; original raw references, page IDs, and crop hashes match exactly. Metrics and the new prediction-file SHA-256 were recomputed from the saved JSONL. The final `comparison.json` confirms **validation manifest unchanged**, **all 1,197 crop fingerprints unchanged**, and **existing validation prediction/metric files unchanged**. The test split was not read/evaluated for this sprint.

### What is safe to use in Academix

- **Retain the existing production preprocessing and processor defaults.** The existing enhancement is a measured winner for this validation-line benchmark and is reused directly by the new runner. No duplicate enhancement pass is needed in the application.
- **Use the new offline runner for controlled comparisons**, with fresh output names and the recorded settings. It is not wired into FastAPI, Flutter, or the deployed inference pipeline.
- **Reject Otsu and aspect-padding defaults** on this evidence. Added margins also failed to improve the screen. Deskew and CLAHE failed their gates; grayscale/contrast and bilateral denoising had smaller screen gains and were not independently confirmed/full-validated.
- **Do not claim all OCR errors are fixed.** Deletions increased slightly; 280 lines regressed, WER remains 40.3155%, and only 79/1,197 lines are exact. Continue teacher verification of recognized answers.
- **Validate page extraction separately before changing it.** Page-level enhancement/segmentation, mixed PDFs, arbitrary rotation, lighting, and modern student handwriting remain outside this line-crop accuracy result. The documented mixed-PDF bypass needs its own reference-backed evaluation before an extraction change is promoted.

Accepted integration is limited to the new comparison tooling and regression coverage; application inference modules and their signatures remain unchanged. No new image-transform default was accepted for deployment. No training, model download, dataset modification, or test-set tuning was performed.

### Reproduction and new output locations

From `ai-engine`, using the root environment:

```powershell
..\.venv\Scripts\python.exe -B -u -m evaluation.experiment_trocr_preprocessing --phase screen --output-name trocr_preprocessing_screen_20261116 --threads 4
..\.venv\Scripts\python.exe -B -u -m evaluation.experiment_trocr_preprocessing --phase confirmation --variants existing --output-name trocr_preprocessing_confirmation_20261116 --threads 4
..\.venv\Scripts\python.exe -B -u -m evaluation.experiment_trocr_preprocessing --phase full --variants existing --output-name trocr_preprocessing_full_20261116 --threads 4
```

Use a fresh output name for any rerun; existing directories are refused rather than overwritten.

- Screen: `evaluation/results/trocr_preprocessing_screen_20261116/`; each variant has separate `<variant>_validation_predictions.jsonl` and `<variant>_validation_metrics.json`, plus `comparison.json` and diagnostics/decision files.
- Confirmation: `evaluation/results/trocr_preprocessing_confirmation_20261116/`; selected candidate uses `existing_validation_predictions.jsonl` and `existing_validation_metrics.json`.
- Full validation: `evaluation/results/trocr_preprocessing_full_20261116/`; final candidate predictions are `existing_validation_predictions.jsonl`, final metrics/configuration are `existing_validation_metrics.json`, and completed aggregate integrity evidence is `comparison.json`. Additional paired analysis/examples and resource counters are in the same directory.

## Tests and file scope

Added `tests/test_ocr_preprocessing_experiments.py`: deterministic transforms, RGB outputs, original pixel preservation, aspect ratio/padding, blank deskew, binary threshold, disjoint reproducible selection, corrupt image/transform failure reporting, paired metrics including empty references/failures, unchanged OCR/extraction contracts, and line-edge retention.

Targeted command, from `ai-engine`:

```powershell
..\.venv\Scripts\python.exe -B -m pytest tests/test_ocr_preprocessing_experiments.py tests/test_trocr_baseline.py tests/test_pipeline.py -q -p no:cacheprovider --basetemp=../build/ocr_sprint_tests_02 --tb=short
```

Result: **46 passed in 1.52 seconds**. Full existing AI-engine suite including new tests:

```powershell
..\.venv\Scripts\python.exe -B -m pytest tests -q -p no:cacheprovider --basetemp=../build/ocr_sprint_all_tests_01 --tb=short
```

Result: **95 passed in 14.30 seconds**. The initial targeted attempt encountered sandbox denial in the default external pytest temp directory (27 passed, 18 fixture errors); using a fresh workspace-local `--basetemp` resolved the environment issue. No package installation was needed.

Three further regression cases check deskew correction sign for synthetic ±2-degree lines, retention of edge information on expanded rotations, and non-mutating EXIF rotation. The new test file alone subsequently passed **20 tests in 1.20 seconds** using `--basetemp=../build/ocr_sprint_tests_03`.

The complete final suite, including those three cases, passed **98 tests in 13.70 seconds**, using the same full-suite command with fresh `--basetemp=../build/ocr_sprint_all_tests_02`.

New source/document/test files:

- `evaluation/experiment_trocr_preprocessing.py`
- `preprocessing/ocr_image_experiments.py`
- `tests/test_ocr_preprocessing_experiments.py`
- `evaluation/TROCR_ACCURACY_IMPROVEMENT.md`

New prediction/metric/diagnostic files are confined to the three `evaluation/results/trocr_preprocessing_*_20261116/` directories listed above. The directory suffix is the run's launch date; full validation finished on November 17. Existing baseline/validation files, model cache, datasets, splits, production OCR modules, FastAPI, PostgreSQL, and Flutter are preserved. No existing application source file was modified.
