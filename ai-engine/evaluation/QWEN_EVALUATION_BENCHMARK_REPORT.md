# Qwen evaluation-quality benchmark

Date: 2026-11-17. Real local inference with cached `qwen2.5:3b`; no human-verified marking labels.

| Phase | Model calls | Invalid/failed calls | All cases failed | Scored | Abstained | Runtime (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| before | 10 | 80.00% | 8 | 3 | 0 | 183.67 |
| after | 7 | 85.71% | 6 | 1 | 4 | 113.49 |
| experimental_prompt | 7 | 100.00% | 7 | 0 | 4 | 112.20 |
| experimental_schema | 7 | 0.00% | 0 | 3 | 8 | 118.43 |

Matched common model-call cases: **7**. Invalid assessments: **5/7 before**, **0/7 with native schema**. Different whole-suite call counts reflect explicit abstention for long, uncertain, or instruction-like text; do not hide this denominator change.

## Interpretation

- **Measured improvement:** native JSON-schema constraints remove observed evidence-string/array and missing-field failures in this small functional suite. The original semantic prompt is retained.
- **Regression / rejected:** the text-only structured semantic prompt produced 7/7 invalid assessments; it is not selected by production.
- **Coverage tradeoff:** new guards leave long/context-heavy, absent, uncertain-OCR and instruction-like answers unscored. Low heuristic confidence and missing verifiable criterion allocation can also require review. Zero is not a substitute for uncertain extraction.
- **Tested but unproven:** correctness, partial credit, paraphrases and spelling fairness. The raw model invents additional detail requirements and sometimes criticizes spelling despite the rubric. Verifiable quotes do not establish conceptual correctness.
- **NOT MEASURED:** human mark agreement, MAE, exact mark agreement, partial-credit agreement, feedback relevance and semantic rubric compliance. Values are null, never inferred from synthetic scenario names or confidence.

## Method and reproducibility

11 synthetic functional scenarios using one test-defined question/rubric cover intended correct/partial/incorrect, alternative wording, short/long, spelling, missing text, uncertain OCR, off-topic, and grading instructions. The test-defined rubric/categories are not a human-verified evaluation dataset. No corpus was downloaded or created for training.

The baseline evaluator and pipeline are frozen before implementation in `results/final_ai_sprint_20261117/baseline_*.py.txt`. Real requests and raw responses, prompts, scores, per-case runtimes, model digest and source fingerprints are preserved in each phase directory. All phases use temperature 0, seed 42, four CPU threads, num_gpu=0, context 8192, max generation 512. Ollama 0.40.16 is recorded. Seed controls do not establish cross-version/platform bitwise determinism.

The before/after-with-guards/experimental-prompt phases requested ordinary JSON; the native-schema phase constrains types while preserving the original prompt. The production activation followed the native-schema measurement and regression tests. JSON grammar does not validate scientific facts or fair grades.

Run from `ai-engine` with `..\.venv\Scripts\python.exe -B -u -m evaluation.benchmark_qwen_quality --phase before` (then `after`, `experimental_prompt`, `experimental_schema`). Each phase refuses an existing output directory. Archive/change the output root explicitly for a new run; never overwrite original artifacts.

Human metrics require independent teacher-reviewed examples and a declared scoring policy. Future MAE = mean absolute prediction/reference mark difference with abstention coverage reported separately; exact agreement compares verified marks at two-decimal precision; partial-credit results must use the teacher-defined partial-credit cases/policy. Feedback relevance requires human judgement, not word overlap. No such numeric results are available here.

## Integration and limits

Accepted: output grammar, finite/precision/budget validation, extraction/blank/context/instruction-like abstention, honest confidence labels and teacher controls. Not accepted: the experimental semantic prompt, new image transforms, uncalibrated probabilities, keyword-only correctness grading, or automatic release.

The instruction-like guard is a narrow heuristic and can overflag legitimate discussion of prompt injection; it is not a complete attack detector. Weighted criterion allocation absent from a model response remains unverified and flags review. Similarity remains an investigation signal, never a grade penalty.

Local resource observation: Ollama reported resident model size **2,420,574,780 bytes (~2.25 GiB)**, `size_vram=0`, active context 8192. This is a server-reported residency measure, not whole-system peak RSS. TrOCR was not loaded concurrently. Combined production memory and live PostgreSQL concurrency remain unverified.

The direct production smoke result is in `results/final_ai_sprint_20261117/production_smoke.json`; it uses the real evaluator with no format/options override and writes no official grade. Teacher approval remains mandatory.

Production now requests the accepted native output schema. The historical after phase was recorded before activation; future after runs use current production and must be labelled accordingly. The original semantic prompt is unchanged.
