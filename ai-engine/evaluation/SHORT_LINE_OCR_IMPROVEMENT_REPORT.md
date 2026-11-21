# Short-Line OCR Improvement Investigation

**Run date:** 2026-11-17  
**Scope:** Bentham validation split only; 161 references with 1–10 normalized characters  
**Production status:** Unchanged

## Executive summary

Short-line recognition is substantially worse than the full validation baseline. The saved TrOCR predictions yield **69.08% CER**, **103.45% WER**, and **29/161 exact matches (18.01%)** on the 161 short lines. There were no inference failures.

No new model inference was run. The available-RAM preflight measured **2.424 GiB**, below the existing **2.5 GiB** minimum. The experiment stopped before model load, as required. Consequently, no preprocessing or decoding candidate was evaluated on all 1,197 samples, and no production change is justified.

The best verified production configuration therefore remains the existing `microsoft/trocr-base-handwritten` pipeline: **16.2436% CER, 40.3155% WER, and 79/1,197 exact matches** overall. The 100% exact-recognition target was not achieved. On short lines, 132/161 predictions are not exact.

## Baseline and error analysis

Metrics were recomputed from the saved full-validation predictions and matched to the validation manifest. Text normalization and edit alignment use the existing evaluation helpers. All 161 selected samples had successful saved predictions.

| Metric | Short-line baseline |
| --- | ---: |
| Samples | 161 |
| CER | 69.0756% (411 edits / 595 reference characters) |
| WER | 103.4483% (180 edits / 174 reference words) |
| Exact matches | 29/161 (18.01%) |
| Inference failures | 0 |
| Predictions with more words than reference | 40 |

Character edit operations comprised **234 substitutions, 167 insertions, and 10 deletions**. The most frequent aligned substitutions were `C` → `.` (15), `r` → `n` (6), and `C` → `c` (5). The alignment flagged 48 edits involving spaces and 85 involving punctuation; these are diagnostic edit counts and can overlap with other error patterns. The WER above 100% reflects insertions and additional predicted words, not a metric error.

### Results by reference length

Length is the number of characters after the existing text normalization.

| Characters | Samples | CER | Exact |
| ---: | ---: | ---: | ---: |
| 1 | 41 | 160.98% | 3/41 |
| 2 | 35 | 61.43% | 15/35 |
| 3 | 20 | 56.67% | 4/20 |
| 4 | 17 | 85.29% | 4/17 |
| 5 | 10 | 68.00% | 2/10 |
| 6 | 9 | 74.07% | 0/9 |
| 7 | 7 | 67.35% | 0/7 |
| 8 | 4 | 18.75% | 1/4 |
| 9 | 9 | 56.79% | 0/9 |
| 10 | 9 | 56.67% | 0/9 |

The largest short-line group contains 41 one-character references and has 160.98% CER. This is consistent with severe over-generation on some single-character inputs; it does not by itself identify whether the visual crop, decoder, or reference annotation caused a particular error. 150 of 161 references are a single whitespace-delimited token.

## Image and crop observations

The median crop is **127 × 75 pixels**, with median aspect ratio **1.56**. In the contact sheets, crops include single letters and digits, short words, irregular polygon-shaped boundaries, and substantial variation in stroke visibility. Twenty-five crops meet the analysis script's heuristic “possible low resolution” flag (width <64 or height <48); this is only a size heuristic, not a diagnosis of illegibility. The stored edge-pixel diagnostic flagged zero crops, but this does not prove that no written stroke was clipped.

The contact sheets support manually reviewing individual examples, but they do not establish that a specific reference is visually ambiguous or that its crop omitted a stroke. Those classifications were not inferred from text edit distance or basic image statistics. No validation crop or reference label was modified.

The processor's square image resizing and the small, often near-square input crops make aspect-preserving padding a reasonable hypothesis to test. They do not prove resizing is the root cause. TrOCR's existing generation limit is 192 new tokens; the short references are far below it. The limit is therefore not an evident truncation cause, although the observed insertions warrant a controlled decoding comparison when safe.

## Preprocessing evidence already available

The previous preprocessing screen covered only **six short lines** within a 43-line sample. Reanalysis of its saved predictions is exploratory and cannot establish generalization:

| Saved variant | Short samples | CER | Exact | Improved / regressed / unchanged vs. saved original |
| --- | ---: | ---: | ---: | ---: |
| Existing | 6 | 55% | 0/6 | 2 / 0 / 4 |
| Contrast | 6 | 65% | 0/6 | 0 / 0 / 6 |
| CLAHE | 6 | 70% | 0/6 | 0 / 1 / 5 |
| Denoise | 6 | 65% | 0/6 | 0 / 0 / 6 |
| Deskew | 6 | 65% | 0/6 | 0 / 0 / 6 |
| Threshold | 6 | 45% | 1/6 | 3 / 1 / 2 |
| Aspect-preserving resize/padding | 6 | 50% | 1/6 | 2 / 0 / 4 |
| Margin | 6 | 60% | 0/6 | 1 / 0 / 5 |

The paired counts compare each saved variant to that screen's original predictions, not to the full 161-line set. No variant achieved enough evidence for promotion. In particular, six samples cannot establish that thresholding or padding improves short-line accuracy without regressing other lengths or the full validation set.

## Experiment safety, runtime, and memory

- The new analysis read only the validation manifest, saved validation predictions/diagnostics, and corresponding processed crops. It did not load model weights or access the held-out test set.
- The post-hoc analysis script completed in **2.07 seconds**. This is analysis time, not OCR inference runtime.
- RAM at the preflight was **2.424 GiB available out of 15.688 GiB physical**, at 84% memory load. Since this is below the existing 2.5 GiB guard, inference was not started.
- Model inference runtime, peak inference memory, and inference stability for new candidates are therefore **not measured**.
- The analysis script and generated outputs are in [`evaluation/results/short_line_ocr_20261117/`](./results/short_line_ocr_20261117/). The output includes per-line edit records, aggregate metrics, source hashes, and six contact sheets.

## Decision and next steps

**No candidate is promoted; production OCR is unchanged.** No new candidate has been measured across all 1,197 validation samples, so overall CER/WER/exact-match regressions and impacts on other line-length categories are unknown.

Recommended next experiment, only after an immediate RAM preflight reports at least 2.5 GiB available:

1. Compare existing input handling against aspect-preserving resize with white padding, first on the same 161 short validation lines.
2. Record CER, WER, exact matches, paired improved/regressed/unchanged counts, runtime, and peak memory. Keep the saved original predictions unchanged.
3. If short-line CER and exact matches improve, run the candidate on all 1,197 validation samples. Compare overall metrics and every reference-length category before considering promotion.
4. Separately test a small, predeclared decoding comparison for over-generation; do not combine it with image preprocessing until each effect is measured independently.
5. Continue to route uncertain or low-confidence handwriting to human review. Do not repair text from language context alone.

If the RAM guard is not met, defer inference and keep production behavior unchanged.
