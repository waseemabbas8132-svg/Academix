# Advanced OCR Model Capability Investigation

**Date:** 2026-11-17  
**Project:** Academix AI Engine  
**Scope:** Read-only inspection of the local TrOCR setup and saved validation artifacts. No model was loaded, no held-out test data was accessed, no training or download was started, and no production behavior was changed.

## Executive findings

The best verified line-crop result remains the existing TrOCR setup: CER **16.2436%**, WER **40.3155%**, exact match **79/1,197 (6.60%)**, and zero inference failures. The 100% target is not close to achieved: **1,118 validation lines are non-exact**.

The current model is an autoregressive TrOCR encoder-decoder. Its clearest limitations in the observed results are visual character confusions, extra/missing characters and words, short isolated text with little context, and a fixed 384×384 representation that distorts highly horizontal lines. The saved metrics do not establish which individual errors were caused by the model, handwriting, crop geometry, or annotation conventions.

I performed a safe, read-only analysis of all saved validation predictions and line-image diagnostics, including a focused short-line breakdown. I did **not** run a new model inference experiment. At the current RAM check, only **1.83 GiB** was available (the prior investigation measured 1.43 GiB), below the existing experiment runner's 2.5 GiB pre-load guard. Beam search and other checkpoint experiments are deferred.

## Architecture, processor, and decoder

### Cached model configuration

The local checkpoint is `microsoft/trocr-base-handwritten`, revision `eaacaf452b06415df8f10bb6fad3a4c11e609406`. Configuration files were read directly from the local cache; checkpoint weights were not deserialized.

- **Encoder:** ViT, 12 layers, hidden size 768, 12 attention heads, 16-pixel patches. At 384×384 this yields a 24×24 grid (576 image patches, plus the ViT class representation).
- **Decoder:** TrOCR autoregressive Transformer, 12 layers, hidden size 1,024, 16 attention heads, 4,096-dimensional feed-forward layers, and cross-attention to the 768-dimensional visual features.
- **Image processor:** cached slow ViT processor; resize to 384×384 with bilinear interpolation, RGB, rescale by 1/255, normalize each channel with mean/std 0.5.
- **Tokenizer:** Roberta byte-level BPE, 50,265 vocabulary entries; max-position setting 512. BOS=0, PAD=1, EOS=2, decoder start=2.
- **Inference generation:** both paths set `max_new_tokens=192` and resolve to greedy, one-beam decoding with no sampling. The validation runner explicitly sets `use_cache=true` and omits token-score tensors. The production recognizer requests token scores but leaves `use_cache` to the cached generation configuration, which says `false`. Thus validation and application have a cache-setting difference; cache affects inference resource use, not the intended decoding policy.

The model config also contains legacy `max_length=20`, but both actual inference paths supply `max_new_tokens=192`, which takes precedence. The cached `generation_config.json` has `use_cache=false`; only the validation runner overrides it. Do not confuse those stored defaults with the measured baseline.

### What the architecture implies

The encoder converts all spatial evidence into a finite patch grid. The decoder then emits BPE token IDs sequentially, conditioning each next token on visual features and previous output tokens. It is not a character classifier with explicit per-letter boxes or alignments.

Greedy decoding chooses the highest-scoring next token at each step. An early character/token choice can change later word predictions. Byte-level BPE can represent fragments rather than one output token per character; character errors therefore cannot be corrected by simply changing a character class. The decoder's learned language prior can favor familiar words over visually ambiguous historical spellings, but this is a plausible explanation, not a causal finding for any particular row.

The evaluator preserves case, punctuation, accents, and spelling after NFC/whitespace normalization. No dictionary correction, spelling repair, or language-model postprocessing is used. This is important: automatic correction could make a string more fluent while changing what is actually written.

### Sequence truncation

The prior tokenizer audit found a maximum of **26 tokens including special tokens** among validation references (34 on training references); the decoder has a 512-position setting, while inference allows 192 new tokens. Saved best-candidate strings have at most 89 UTF-8 bytes, with none near 192 bytes. This makes ordinary visible-text truncation unlikely in the saved sample, but the prediction artifacts do not record generated token IDs or finish reasons, so absence of max-token stopping cannot be proved from them. No truncation-specific model rerun was safe here.

## Error evidence from validation

The complete 1,197-line saved candidate was reanalyzed. Error counts use deterministic minimum-edit alignment; these are error-pattern descriptions, not ground-truth visual diagnoses.

| Error type | Count |
|---|---:|
| Character substitutions | 5,639 |
| Character deletions | 973 |
| Character insertions | 2,187 |
| Word substitutions | 2,988 |
| Word deletions | 151 |
| Word insertions | 924 |
| Inference failures | 0 |

Frequent character substitutions include `e→o` (85), `t→l` (82), `e→a` (79), `b→h` (69), and `n→m` (66). The analysis also finds 758 inserted spaces, 155 punctuation-only inserted word tokens, and 96 case-only word substitutions. Thus word-boundary and punctuation conventions contribute alongside letter recognition.

### Short-line analysis

For **161 references of 1–10 characters**, the current enhanced configuration has CER **69.08%**, WER **103.45%**, and **29 exact lines**. The pre-enhancement saved baseline was CER **73.28%**, WER **108.05%**, and 26 exact lines. The enhancement helps modestly, but does not solve the short-line problem.

The short-line references are mostly isolated one-word items: **150 of 161** have one whitespace-delimited word. Median crop dimensions are **127×75 px**, median aspect ratio **1.56**. For the other 1,036 lines, median dimensions are **1,704×124.5 px**, median aspect ratio **13.23**. Short lines are therefore much less horizontally elongated, but their small originals are upscaled to the 384-square processor input (about 3× width and 5× height at the short-line medians). Upsampling cannot restore missing pen detail and interpolation may soften strokes; these measurements alone do not prove this is the dominant cause.

The short-line errors include one-character references such as `C`→`c.` and `G`→`cv`, as well as `him.`→`huise .` and `regarding.`→`seguandering .`. A one-word line offers little neighboring linguistic context, and one added punctuation mark or letter can make the whole line non-exact. The “word accuracy” rates above 100% reflect this short reference denominator and inserted tokens; they are not percentages of lines that failed.

In the previous 43-line preprocessing screen, only **six** samples were 1–10 characters. On those six, aspect-preserving padding changed CER from 65% to 50% and exact from 0/6 to 1/6, while its whole-screen CER/WER deteriorated to 84.80%/105.83%. Six samples are insufficient evidence for short-line promotion or for a causal resizing conclusion.

### Image quality, cropping, and segmentation

The saved image audit reports widths 37–1,993 px, heights 32–326 px, median aspect ratio 12.7 across all validation crops, seven crops shorter than 48 px, no EXIF orientations, and no dark pixels on the outer two-pixel borders. Four crops had no grayscale pixel below 160. Laplacian variance and darkness are descriptive signals, not calibrated legibility or blur measures.

The validation benchmark uses PAGE-prepared, already segmented and polygon-masked line crops. Consequently:

- The high short-line errors occur **even when page line segmentation is bypassed**; the production row-density segmenter is not required to explain these benchmark errors.
- Polygon masks/crop edges could still exclude faint or crossing strokes; the image diagnostics cannot rule that out.
- Production page OCR uses a fixed foreground threshold and row-density/gap heuristic in [`handwritten_ocr.py`](../preprocessing/handwritten_ocr.py). Its split/merge behavior on modern photographed assignments has not been measured against page-level ground truth.
- The PDF extractor also routes pages with embedded text around OCR; pages with text plus graphics receive a review warning, but handwritten content may be omitted. This is an extraction-path issue, not a TrOCR line-recognition metric.

## Locally available alternatives

The local Hugging Face cache contains `microsoft/trocr-base-handwritten` and a CLIP image-text model. CLIP is not a handwriting transcription checkpoint. The selected Python 3.12.9 environment has PyTorch/Transformers and OpenCV, but no installed `pytesseract`, EasyOCR, PaddleOCR, docTR, or ONNX Runtime. No Tesseract executable was found. Their absence means no alternative handwriting engine was available for a fair local benchmark; it is **not** evidence that Tesseract or any other engine is unsuitable.

No model, dataset, or dependency was downloaded. No second model or ensemble was run. Fine-tuning remains out of scope and is not currently a safe fallback: the separate [readiness report](TROCR_FINE_TUNING_READINESS.md) documents unresolved Bentham licensing/provenance, missing training plumbing, and a loss/label alignment blocker in addition to compute constraints.

## Recognition strategies and experiment ranking

| Rank | Strategy | Expected benefit / confidence | Cost and principal risk | Decision |
|---:|---|---|---|---|
| 1 | Offline beam-search screen (2 and 4 beams; controlled length penalty) | **Unknown; moderate potential.** Can compare alternative token sequences for the same visual evidence. | More CPU time and decoder memory; can favor fluent but visually unsupported insertions. | **Defer** until RAM exceeds the safety guard. Keep greedy as control; compare exact/CER/WER, not fluency. |
| 2 | Targeted short-line resampling/scale experiment | **Unknown; low-to-moderate potential.** Only six short lines appeared in the prior screen; 161 exist in full validation. | Processor is fixed at 384×384; sharpening/upscaling can invent edges or erase faint strokes. Prior aspect-padding screen was poor overall. | Evaluate one transform at a time on short lines plus page-matched longer controls; do not promote from the six-line screen. |
| 3 | Review-assisted uncertainty and abstention | **High practical value for reducing unreviewed mistakes; no expected automatic CER change.** | Current score is mean max-token probability, not calibrated. Incorrect high-confidence output is possible. | Calibrate sequence/token uncertainty on human-reviewed validation examples; route uncertain or disagreeing lines to a person. Never auto-correct them. |
| 4 | Better page/word segmentation and crop verification | **Potentially high for real page submissions; unmeasured on this line-crop benchmark.** | Requires page-level annotated handwriting and geometry; word boxes can split cursive strokes or remove context. | Collect/verify modern page-level line boxes before testing. Keep line recognition as control; compare line-level with word-level only where boxes are reliable. |
| 5 | Character-level recognizer or second-model ensemble | **Potentially useful but unsupported by local evidence.** | No local alternative checkpoint/engine; model downloads are prohibited. Ensembling adds memory/runtime and can combine correlated errors. | Do not add a model. Revisit only after a locally available, licensed candidate can be evaluated on the same validation rows. |
| 6 | Fine-tuning TrOCR | **Could address historical/writer domain mismatch, but cannot be justified now.** | Explicitly prohibited; license/provenance unresolved, training code/loss path unvalidated, and RAM headroom inadequate. | Do not train. Reconsider only after permissions, dataset quality, loss alignment, and resource feasibility are independently cleared. |

Other decoding options have tradeoffs: sampling is nondeterministic and can produce unsupported alternatives; diverse beams increase search and cost but do not guarantee lower character error; dictionary/grammar constraints risk changing historical words and are not acceptable without evidence from the pixels. Candidate generation can help a reviewer compare alternatives, but automatic voting cannot know which string was written without reliable evidence.

## Experiment safety and measured work

The safe experiment performed for this investigation was a post-hoc analysis of preserved validation predictions and saved crop diagnostics; it did not initialize PyTorch model weights. It confirmed the short-line metrics/dimensions above and preserved the original predictions.

A fresh Windows memory query measured **15.69 GiB physical RAM**, **1.83 GiB available** (88% loaded). The prior investigation recorded **1.43 GiB available**. The existing experiment runner refuses to load the model below 2.5 GiB free. No beam search, new preprocessing inference, or alternative-model run was attempted. This is the safe decision; no metrics are claimed for unrun configurations.

Previous controlled preprocessing screen/confirmation/full-validation evidence is preserved in [`trocr_preprocessing_screen_20261116`](results/trocr_preprocessing_screen_20261116/), [`trocr_preprocessing_confirmation_20261116`](results/trocr_preprocessing_confirmation_20261116/), and [`trocr_preprocessing_full_20261116`](results/trocr_preprocessing_full_20261116/). The 1,197-row error inventory is in [`validation_analysis.json`](results/trocr_100_percent_20261117/validation_analysis.json); all non-exact lines remain listed in [`remaining_incorrect_predictions.jsonl`](results/trocr_100_percent_20261117/remaining_incorrect_predictions.jsonl).

## Exact next implementation recommendation

**Do not change production OCR.** First implement a research-only decoder screen that reuses the existing offline validation harness and saved paired baseline:

1. Check RAM before loading; require at least the existing **2.5 GiB free-memory guard**. Stop if below it.
2. Select a deterministic page-stratified validation screen, retaining raw outputs and comparing greedy against beam width 2 and 4; vary length penalty separately rather than combining it with image changes.
3. Record CER, WER, exact lines, improved/regressed/unchanged samples, failures, elapsed time, and peak working set. Run a disjoint confirmation before a full-validation run.
4. Require the candidate to improve CER without increasing WER, exact-match loss, or failures on screen and confirmation; then evaluate the candidate on all 1,197 validation lines. Do not promote from a subset result.
5. After decoding is isolated, run a separate short-line experiment comparing the current bilinear square input against one alternative resampler at the same 384×384 geometry, on all 161 short lines plus matched longer controls. This isolates interpolation from aspect ratio and decoder settings.

If RAM remains constrained, the next most useful investment is human-reviewed page/line ground truth plus calibrated review routing, not another speculative transform or a second model. The current short-line evidence suggests limited context and small-source resolution are plausible constraints, but does not justify a production preprocessing change.
