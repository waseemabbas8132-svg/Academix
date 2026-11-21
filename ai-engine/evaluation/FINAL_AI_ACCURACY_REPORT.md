# Final AI accuracy and evaluation-quality sprint

Date: 2026-11-17, Asia/Karachi. **Completed. READY WITH CONDITIONS for teacher-assisted use; not validated for autonomous grading.**

Final checks: **133 AI-engine + 50 backend + 17 Flutter tests passed (200 total)**. Native JSON-schema output reduced invalid assessments from **5/7 to 0/7 on matched model-call cases**. This is a format-reliability improvement, not a measured improvement in human mark agreement. No human-verified marking corpus was found or supplied.

## Phase 1: completed read-only audit before changes

The audit covered the AI-engine preprocessing, OCR, document extraction, segmentation, rubric/prompt/response validation, feedback, similarity, public contracts, FastAPI worker/routes/schemas/models, teacher review UI and repositories, student grade responses, existing tests and OCR reports. No source changes were made before this audit completed. Initial source/protected-file hashes and frozen Qwen/pipeline source are in `results/final_ai_sprint_20261117/audit_snapshot.json` and the two `baseline_*.py.txt` snapshots.

| Area and evidence | Finding before changes | Decision |
| --- | --- | --- |
| `preprocessing/image_preprocessor.py:preprocess_image`; previous validation experiments | Existing grayscale/median/contrast combination improved prepared-line CER 17.3568% to 16.2436%; WER 41.3574% to 40.3155%; 79 rather than 71 exact matches. Threshold and aspect-padding experiments regressed. 280 enhanced lines regressed. | Reuse these results and preserve transforms; no blind repeat of the long CPU experiment. No new OCR accuracy claim in this sprint. |
| `preprocessing/handwritten_ocr.py:recognize_page` | Empty OCR returns no segment and no warning. Mean token softmax maxima are uncalibrated but appear as confidence. No flat-image check before generation. | Preserve empty/uncertain provenance, conservative readability checks, keep scores explicitly heuristic. |
| `preprocessing/text_extractor.py:_extract_pdf` | Any PDF text bypasses OCR even on mixed graphical/handwritten pages. Blank-page accounting across files relies on emitted segments. | Flag potentially incomplete mixed pages instead of assuming completeness; correct page accounting. No unvalidated automatic mixed-page OCR. |
| `evaluation/answer_evaluator.py:segment_answers` | Probe: IDs `q1` and `part1` map `1. first answer` silently to `part1`; unknown `99.` content bleeds into q1. | Reject ambiguous mappings and preserve heading boundaries. Unmatched/missing text requires review. |
| `inference/evaluation_pipeline.py:EvaluationPipeline.evaluate` | OCR needs-review flags do not prevent model grading of uncertain extracted text. Float `0.1+0.2 > 0.3` can wrongly invalidate a valid total. | Abstain when extraction cannot be trusted; validate bounds and compute money-like marks with Decimal arithmetic. |
| `evaluation/answer_evaluator.py:_validate_output` | Unsupported positive evidence is rewritten to zero rather than unscored. `needs_review` is bool-coerced and optional; empty explanations allowed. Verbatim evidence alone cannot establish subject correctness. | Strict structure/finite/budget validation; unsupported evidence must not become a zero grade. Semantic accuracy remains a separate unverified question. |
| Rubrics: `backend/app/schemas/ai_evaluation.py`, `routes/ai_evaluations.py`, `models/assignment_rubric.py` | Teacher question/criterion budgets exist; API bounds rubric sums. LLM scalar output does not prove criterion allocation. Global model-answer context can be ambiguous. | Keep authoritative teacher budgets; test an explicit structured prompt separately. Do not fabricate semantic benchmark labels. |
| `evaluation/feedback_generator.py` | Provisional/teacher-review wording already present. Constructive-feedback relevance is not measured. | Retain teacher-controlled wording; do not report nonempty feedback as semantic relevance. |
| `evaluation/similarity_checker.py`; backend `_compare_with_peers` | Assignment-scoped token similarity is an investigation signal, never a grade penalty. Peer query combines historical jobs, which can distort signals. | Preserve no-penalty policy; test it. Historical-job aggregation remains a documented limitation unless separately fixed/tested. |
| `backend/app/services/ai_evaluation_service.py` | Atomic pending claim, bounded concurrency, retries and source/rubric version checks exist. Worker persistence checks status but not attempt number; an old attempt can finish into a retried processing job. | Add attempt identity checks for both success and failure. Worker must never write official marks. |
| Approval API and grade release | Explicit teacher approval writes official total/feedback; worker writes only provisional results. Stale submission/rubric checks exist. Unscored AI totals currently prevent even a complete teacher-entered question override. Question decimals can round independently of the total. | Preserve explicit release and ownership. Permit a complete explicit teacher override and validate two-decimal question marks. No migration or live DB changes. |
| `lib/features/assignments/data/models/ai_evaluation.dart`; review screen | Approved question marks/total/feedback are discarded on parsing. Controllers reuse question IDs across different evaluations, retaining old edits. Percent confidence labels imply precision/calibration not established. | Restore approved-value readback, reset by evaluation identity, label heuristic scores truthfully, validate finite/two-decimal edits. |
| Teacher OCR correction | Extract/evaluate execute together in one job; no correction endpoint, correction-version identity, or immutable correction audit exists. Current extracted text UI is read-only. | Not implemented through a cosmetic editor. A safe persisted correction/re-evaluation feature needs a separate contract/provenance design; manual grading remains available. |
| Human-verified answer/mark references | No verified marking corpus found in repository search. Demo tests/AI-approved grades are not independent human ground truth. Optional existing-path question sent to user. | Human agreement/MAE/partial-credit agreement/feedback relevance remain null/unmeasured unless verified examples are supplied. Synthetic functional cases are explicitly not accuracy labels. |

Ollama's local `/api/tags` confirmed cached `qwen2.5:3b`, digest `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`, Q4_K_M, 3.1B, stored size 1,929,912,432 bytes. No pull/download endpoint is authorized or used. TrOCR remains the cached checkpoint from the prior report.

## Evidence classifications and scope

Measured OCR improvement from the previous sprint is retained with provenance. New deterministic guard improvements must be demonstrated by regression tests. Experimental prompt semantic quality is **tested but unproven** without human labels. Thresholding/letterboxing are prior **regressions** and stay disabled. No new OCR transform is promoted. Test-split selection/evaluation, training, model downloads, dependency upgrades and live PostgreSQL writes are excluded.

The completed results below distinguish measured reliability from unmeasured semantic accuracy. No claim of 100% accuracy or calibrated model confidence is justified.

## Completed results by evidence category

| Classification | Result |
| --- | --- |
| **Measured improvement** | Native output grammar: invalid assessments **5/7 → 0/7** on matched model-call cases, with identical semantic prompts and generation options. Regression tests demonstrate safe abstention, precise arithmetic, stale-attempt protection, teacher-approved mark readback, and similarity persistence without grade penalties. |
| **Prior measured improvement, reused** | Bentham validation CER **17.3568% → 16.2436%**, WER **41.3574% → 40.3155%**, exact matches **71 → 79**. All 1,197 crops decoded/hash-checked again; all 280 regressed lines retained. This sprint did not produce a new OCR accuracy gain. |
| **Tested but unproven** | Conceptual correctness, fair partial credit, paraphrases, spelling fairness, constructive feedback and semantic rubric compliance. Synthetic scenario names are not human-verified labels. |
| **No improvement / unmeasured effect** | OCR pixel transforms remain unchanged. The near-uniform-image check flagged **0/1,197** validation crops. Saved predictions lack confidence, so the new uncertainty-routing effect on CER/WER cannot be reconstructed honestly. |
| **Regression / rejected** | The text-only experimental semantic prompt produced **7/7 invalid assessments** and was not deployed. Prior Otsu and aspect-padding regressions remain disabled. Conservative gates reduce automation coverage on long/uncertain material; abstention is not counted as marking accuracy. |
| **Not tested / not established** | Human mark agreement/MAE, feedback relevance, calibrated confidence, modern student-page CER, combined TrOCR+Qwen peak memory, live PostgreSQL locking and a live device-to-database walkthrough. No test-split selection or evaluation occurred. |

## Production-integrated improvements

1. **Extraction checks:** near-uniform images bypass decoder hallucination. Empty OCR segments remain present and flagged. Nonfinite/out-of-range/non-numeric OCR signals become unknown. Mixed PDF text plus graphics/annotations raises a completeness warning; it does not silently assume the extracted text covers handwriting. Corrupt/encrypted PDFs fail clearly. Actual PDF pages count against the cross-file processing budget. No new image transform was enabled.
2. **Uncertain answers remain unscored:** missing, unmapped or uncertain extracted text does not receive an inferred zero. Uncertain extraction is withheld from automatic marking. This is currently document-wide abstention when any extraction segment needs review, not a calibrated per-question quality classifier.
3. **Strict local model contract:** required fields, booleans, finite/two-decimal marks, question bounds and teacher criterion budgets are checked. Native JSON schema constrains evidence arrays and output fields. Unsupported quotes produce an unscored result. Verifiable quotes alone do not establish correct subject knowledge. Missing per-criterion allocation remains unverified and flags review; semantic compliance is not claimed.
4. **Bounded evaluation:** absent teacher references, context-heavy prompts and the tested instruction-like grading vector abstain. The 6,000-byte prompt boundary is conservative, not an exact tokenizer capacity measurement. The original semantic prompt remains; the experimental semantic prompt is isolated in `qwen_prompt_experiment.py` and not selected by production. Native grammar changes output structure, not the teacher rubric.
5. **Correct matching and arithmetic:** numeric ID collisions, repeated headings and unknown-heading bleed require review instead of silently misassigning answers. Question IDs/maxima are validated. Decimal addition fixes `0.1 + 0.2` total drift. Supplied criterion allocations must identify teacher criteria exactly once, respect budgets and sum to the question mark.
6. **Worker isolation:** success/failure persistence checks the claimed attempt count. Retry and persistence use row locks where supported. Covered interleavings prove an old attempt cannot complete or fail a newer processing attempt. PostgreSQL locking semantics were not exercised by SQLite tests.
7. **Teacher authority and versioning:** precise timestamps after manual grades, resubmissions and approvals invalidate stale AI proposals, including with SQLite's second-resolution defaults. Complete explicit teacher question marks and feedback can release an otherwise unscored AI review. Nonfinite/sub-cent question marks are rejected, preventing independent rounding from disagreeing with totals. Worker results never replace official grades.
8. **Review UI:** teacher marks, approved totals and teacher feedback are parsed and displayed separately from suggestions. New evaluation IDs reset unsaved controls even when question IDs are unchanged. Nonfinite/sub-cent edits are rejected. Scores are labelled uncalibrated heuristics; incomplete text has a review warning. Manual grade/return saves retain their existing role as explicit teacher publication actions; no private draft-review workflow was added.
9. **Similarity persistence bug fixed:** a regression test exposed a pre-existing missing `evaluation_id` on peer feedback. A match could cause a NOT NULL failure and roll back the evaluation. Findings now receive the parent ID before persistence. The test confirms a 0.99 signal persists without changing either suggested marks or the official teacher grade. Similarity remains an investigation signal, never a grade penalty or proof of misconduct.

Public endpoints and existing response fields remain compatible. New Dart fields read values the backend already returned. No database schema, migrations, model weights or dependency versions changed. No live database records were written and no automatic grade release was introduced.

## OCR benchmark and regression tracking

TrOCR provenance: `microsoft/trocr-base-handwritten`, revision `eaacaf452b06415df8f10bb6fad3a4c11e609406`, CPU float32, from the preserved prior inference configurations; no new TrOCR inference was performed.

New artifacts: `ai-engine/evaluation/results/final_ai_sprint_20261117/ocr_benchmark/`.

| Metric, 1,197 validation crops | Original saved inference | Existing enhancement saved inference |
| --- | ---: | ---: |
| CER | 17.3568% (9,402/54,169 edits) | 16.2436% (8,799/54,169) |
| WER | 41.3574% (4,168/10,078 edits) | 40.3155% (4,063/10,078) |
| Exact match | 5.9315% (71) | 6.5998% (79) |
| Failure rate | 0/1,197 (0%) | 0/1,197 (0%) |

`original_predictions.jsonl` and `enhanced_predictions.jsonl` preserve the measured original records. `paired_predictions.jsonl` contains every raw reference, both predictions, edit changes, crop hash and current readability warnings. `regressions.jsonl` contains **all 280 worsened lines**; 415 improved and 502 tied. No line was dropped to improve a metric. `metrics.json` explicitly records `new_inference_performed=false` and source hashes.

Normalization remains Unicode NFC with collapsed/trimmed whitespace; case, punctuation, accents and spelling are preserved. CER/WER are corpus edit totals divided by total reference units, with a minimum denominator of one. Failures are scored as empty predictions and never exact matches. Raw text is retained.

Current reanalysis/decode/hash/quality-check runtime: **11.58 seconds**, not model inference throughput. Prior original inference took 3,069.99 seconds; the prior enhanced full phase took 36,432.04 wall seconds including documented overnight gaps, with median 3.019 seconds/crop. These are historical timings, not new runs or a speed comparison. Near-uniform contrast is only a narrow readability heuristic; general blur, illumination and legibility calibration remain unproven. No TrOCR model was loaded for this sprint's reanalysis.

Executed from `ai-engine`:

```powershell
..\.venv\Scripts\python.exe -B -u -m evaluation.benchmark_final_ocr
```

## Qwen benchmark and human comparison

Detailed report: `ai-engine/evaluation/QWEN_EVALUATION_BENCHMARK_REPORT.md`. Raw requests, responses, prompts, scores, errors and timings are preserved in `results/final_ai_sprint_20261117/qwen_*/`.

| Phase | Model calls / 11 cases | Failed assessments | Scored | Unscored | Runtime |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen before | 10 | 8 (80% of calls) | 3 | 0 | 183.67 s |
| Guards, ordinary JSON | 7 | 6 (85.71% of calls) | 1 | 4 | 113.49 s |
| Experimental semantic prompt | 7 | 7 (100% of calls) | 0 | 4 | 112.20 s |
| Original prompt + native schema, selected | 7 | **0** | 3 | 8 | 118.43 s |

Because guards bypass some calls, whole-suite denominators differ. On the **same seven model-called cases**, invalid assessments fell **5/7 → 0/7**. `matched_prompt_verification.json` confirms identical semantic prompts and generation options. Cases bypassed or left unscored are not counted as correct model assessments. Bounds compliance is not fair-mark agreement.

All 11 synthetic functional scenarios use **one test-defined question/rubric**, not a broad subject corpus: intended correct/partial/incorrect, alternative wording, short/long, spelling, missing text, uncertain OCR, off-topic and grading instructions. Category names are not verified labels. Raw responses still invent detail requirements and penalize spelling despite the supplied no-grammar-penalty rule. A raw baseline response awarded full marks to a grading-override instruction while calling it irrelevant in its explanation; the existing schema rejected that response. The new narrow instruction-like guard bypasses the tested vector, but is not a complete attack detector and can overflag legitimate discussion.

No human-verified marking corpus was found in inspected files or supplied during work. Demo grades and AI-approved marks were not treated as independent ground truth. `human_verified_comparison.json` records **0 verified examples**, with **null** MAE, exact agreement, partial-credit agreement and feedback relevance. Semantic rubric compliance is unmeasured. Scores were not fabricated from intended categories, confidence or keyword overlap.

Future MAE and mark agreement require independently teacher-verified questions, answers, rubric, marks and assessor provenance, with abstention coverage reported separately. Partial-credit comparison needs the teacher's policy; feedback relevance needs human judgement. These are prerequisites for accuracy claims and semantic prompt promotion, not blockers to deterministic safety fixes.

The direct production-evaluator smoke passed in **20.31 seconds**, using real cached Qwen with no request format/options override. It returned a structurally valid provisional result flagged for review, not a verified correct grade. `production_smoke.json` retains the raw call; no official grade was written.

Executed benchmark commands from `ai-engine`:

```powershell
..\.venv\Scripts\python.exe -B -u -m evaluation.benchmark_qwen_quality --phase before
..\.venv\Scripts\python.exe -B -u -m evaluation.benchmark_qwen_quality --phase after
..\.venv\Scripts\python.exe -B -u -m evaluation.benchmark_qwen_quality --phase experimental_prompt
..\.venv\Scripts\python.exe -B -u -m evaluation.benchmark_qwen_quality --phase experimental_schema
```

These historical phase directories are immutable and the runners refuse overwrite. Use a clean, explicitly prepared output root with the frozen baseline sources for intentional reruns. The recorded `after` phase preceded grammar activation; current production already uses grammar, so a future `after` run is not the old ordinary-JSON stage. Raw request formats/source hashes preserve the historical distinction.

## Final testing evidence

**200 passed:** 133 AI-engine, 50 backend, 17 Flutter. Metadata: `results/final_ai_sprint_20261117/test_results.json`.

From `ai-engine`:

```powershell
..\.venv\Scripts\python.exe -B -m pytest tests -q -p no:cacheprovider --basetemp=../build/final_ai_quality_04 --tb=short
```

Result: **133 passed in 6.24 seconds**. New tests cover strict response fields/booleans; finite/two-decimal marks; unsupported quotes; uncertainty versus zero; criterion budgets; context/instruction-like bypass; segmentation ambiguity; uncertain extraction; Decimal totals; mixed, blank, corrupt and encrypted PDFs; nonfinite OCR signals; native schema requests; and absence of fabricated human metrics. The existing unsupported-evidence expectation intentionally changed from zero to unscored.

From `backend`, force the database into memory before importing the app:

```powershell
@'
import os
from pathlib import Path
os.environ['DATABASE_URL']='sqlite://'
os.environ['UPLOAD_STORAGE_PATH']=str((Path.cwd()/'../build/final_ai_backend_uploads').resolve())
import pytest
raise SystemExit(pytest.main(['tests','-q','-p','no:cacheprovider','--basetemp=../build/final_ai_backend_05','--tb=short']))
'@ | ..\.venv\Scripts\python.exe -B -
```

Result: **50 passed in 3.45 seconds**, one existing Starlette/httpx TestClient deprecation warning. Tests use the existing in-memory SQLite `StaticPool` and `get_db` override. No live PostgreSQL connection, migration or production lifespan was started. New cases cover complete explicit teacher overrides, nonfinite/sub-cent rejection, precise grade/resubmission versions, stale approval rejection, superseded worker completion/failure, official-grade preservation and similarity persistence without a mark penalty. SQLite does not verify native PostgreSQL row locking.

From project root, actual installed-SDK command:

```powershell
& 'C:\flutter\flutter\bin\cache\dart-sdk\bin\dart.exe' --packages='C:\flutter\flutter\packages\flutter_tools\.dart_tool\package_config.json' 'C:\flutter\flutter\bin\cache\flutter_tools.snapshot' test --no-pub test
```

Result: **17 passed**, runner about **3 seconds**, excluding SDK startup. Existing authorized SDK cache access was used; no dependency update was requested. New tests cover approved decimal-string values, controller reset across evaluations, explicit marking/readback of an unscored result, and nonfinite edit rejection. Existing assignment/class/login tests remain passing. Repositories/HTTP are faked; this is not a live device/database walkthrough.

Intermediate failures were resolved: new widget tests initially tapped before keyboard/scroll settling; the harness was corrected. Strict validation retained the existing error-message prefix expected by an old test. The similarity regression exposed the real missing-parent-FK bug, which was fixed before the final backend pass. No dependency upgrade was used to suppress the deprecation warning.

## Hardware, integration verdict and manual approval

Verified setup: Windows, root Python 3.12 environment, approximately 16 GB RAM, CPU-only model requests. Qwen used temperature 0, seed 42, four threads, `num_gpu=0`, context 8192 and max generation 512. Ollama **0.40.16** served the same cached Q4_K_M 3.1B digest in every phase. `/api/ps` reported **2,420,574,780 bytes (~2.25 GiB)** resident model size and **0 VRAM**. This is a server-reported residency figure, not whole-system peak RAM. TrOCR was not loaded concurrently; the previous roughly 1.7-GiB OCR working set does not certify combined residency.

The prompt-byte guard is conservative and may reject text the tokenizer could fit. Oversized/uncertain input is unscored, not silently truncated or assigned zero. Other inputs can still exhaust the generation cap and produce invalid JSON; validation and existing retry behavior remain. Seed/temperature settings do not guarantee bitwise reproducibility across versions/platforms.

**READY WITH CONDITIONS for teacher-assisted use:** deterministic guards, output grammar, arithmetic, job isolation, similarity persistence and review readback are integrated and tested. The installed Ollama supports the schema format; other versions require compatibility checking. Public endpoints and stored schema remain compatible. No migration, live record rewrite or deployment was performed.

**Not validated for autonomous grading or measured semantic accuracy.** Confidence is uncalibrated, OCR errors remain substantial and Qwen's explanations can be unfair or factually inconsistent. Teachers must check originals and marks. For a cautious CPU showcase, run one evaluation at a time until combined-model memory/concurrency is measured; no environment setting was changed here to claim such a measurement.

**Manual approval:** normal teacher approval remains mandatory for grade release. Complete manual question marks and feedback are required to release an unscored AI review. Human-verified references are required before semantic accuracy claims or semantic prompt promotion. No additional user approval was needed for the requested local edits/tests; no automatic release or external deployment occurred.

Remaining limitations: no persisted teacher OCR-correction workflow; no general calibrated blur/rotation/lighting detector; document-wide rather than per-question uncertainty gating; conservative/unsupported heading styles; historical peer-job aggregation; combined model memory; and live PostgreSQL/device integration. Mixed-page checks may overflag logos/diagrams, and instruction checks may overflag legitimate discussion. False-positive rates are unmeasured. A cosmetic OCR editor would not safely alter evaluated text; a correction/staging contract and provenance are needed first. Existing manual grading and original-file download/review remain available.

## Exact changed files and preservation

Modified existing files:

- `ai-engine/evaluation/answer_evaluator.py`
- `ai-engine/inference/evaluation_pipeline.py`
- `ai-engine/preprocessing/handwritten_ocr.py`
- `ai-engine/preprocessing/text_extractor.py`
- `ai-engine/tests/test_pipeline.py`
- `backend/app/api/v1/routes/ai_evaluations.py`
- `backend/app/api/v1/routes/assignments.py`
- `backend/app/schemas/ai_evaluation.py`
- `backend/app/services/ai_evaluation_service.py`
- `lib/features/assignments/data/models/ai_evaluation.dart`
- `lib/features/assignments/presentation/screens/ai_evaluation_screens.dart`
- `test/features/assignments/presentation/ai_evaluation_screen_test.dart`

Created source/test/report files:

- `ai-engine/evaluation/FINAL_AI_ACCURACY_REPORT.md`
- `ai-engine/evaluation/QWEN_EVALUATION_BENCHMARK_REPORT.md`
- `ai-engine/evaluation/benchmark_final_ocr.py`
- `ai-engine/evaluation/benchmark_qwen_quality.py`
- `ai-engine/evaluation/qwen_prompt_experiment.py` (not production-selected)
- `ai-engine/tests/test_evaluation_quality.py`
- `backend/tests/test_ai_quality_safeguards.py`
- `test/features/assignments/data/ai_evaluation_model_test.dart`

Generated deliverables are exclusively under `ai-engine/evaluation/results/final_ai_sprint_20261117/`: frozen source/audit hashes; four Qwen phases with configurations/raw predictions/metrics; OCR original/enhanced/paired predictions, all regressions and metrics; comparisons; human-label-unavailable record; direct production smoke; resource observation; matched-prompt verification; test results; preservation checks. `changed_files_manifest.json` lists every generated path. Normal Flutter caches and `build/final_ai_*` pytest scratch fixtures are excluded from authored deliverables.

All **16 protected original artifact/database-file hashes** match the initial snapshot. Frozen source hashes match pre-change source. All 1,197 validation crop hashes and the manifest were rechecked. Datasets, manifests/splits, previous baseline/validation results and cached model weights were not rewritten. No test split was used for selection, and no dataset/model download, training, fine-tuning or unnecessary dependency upgrade occurred.
