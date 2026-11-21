# Bentham TrOCR baseline

From `ai-engine`, run unit tests before evaluation:

```powershell
..\.venv\Scripts\python.exe -m pytest tests/test_trocr_baseline.py -v --basetemp=.pytest_cache/trocr-baseline-unit
..\.venv\Scripts\python.exe -u -m evaluation.evaluate_trocr_baseline --seed 42 --threads 4
..\.venv\Scripts\python.exe -u -m evaluation.evaluate_trocr_baseline --split validation --seed 42 --threads 4
```

The CLI fixes the model and crop root. `--split test` (the default) requires
exactly 1,116 unique test crop paths; `--split validation` requires 1,197 unique
validation crop paths. Only the selected manifest is loaded and evaluated in
manifest order. Training records are never evaluated. The pretrained model,
decoding settings and normalization are identical for both splits; test-set
predictions are not used to tune the model. Images and manifests are read only. The
existing `TrOCRHandwritingRecognizer` model loader is reused with
`local_files_only=True`; Hugging Face/Transformers offline flags are also set.
A missing or incomplete cached checkpoint stops the run without a download.

Prepared line crops are decoded by Pillow, converted to RGB and passed directly
to the cached TrOCR processor. Page enhancement and segmentation are omitted
because these are already line crops. Inference is CPU float32, one crop at a
time, with greedy decoding, one beam, no sampling and at most 192 new tokens.
Seeds and deterministic PyTorch algorithms are configured. Model revision,
software versions, generation settings, input-manifest hash and per-crop hashes
are recorded for reproducibility. Before/after fingerprints verify the selected
manifest and all readable selected crops; changes prevent finalizing aggregate
metrics. Reruns replace only the two result files for the selected split.

## Metrics and normalization

References come from the original `transcription` field. Both raw references
and raw decoded predictions are retained, alongside normalized strings.
Normalization applies Unicode NFC, collapses all Unicode whitespace to a single
ASCII space, and trims surrounding whitespace. Case, punctuation, accents and
historical spelling are preserved. No language correction is applied.

CER is the sum of per-line character Levenshtein distances divided by total
normalized reference characters, including spaces. WER uses the same corpus
aggregation on whitespace-delimited words. These are fractions, may exceed 1,
and are not averages of per-line rates. Exact-match accuracy is the proportion
of all input lines whose normalized strings match. For an entirely empty
reference corpus, the CER/WER denominator is 1 (insertions are still counted).

Missing/corrupt images and inference exceptions retain a prediction row with
`status=failed`, a null raw prediction, filename, failure stage and error text.
Failures count as empty predictions in CER/WER and incorrect exact matches;
they are never excluded from metric denominators. A completed run containing
failures exits with code 2. Model-loading or other run-level errors exit with
code 1 and do not fabricate sample predictions.

## Outputs

- `results/bentham_trocr_baseline_predictions.jsonl`: one row per test crop.
- `results/bentham_trocr_baseline_metrics.json`: test metrics and configuration.
- `results/bentham_trocr_validation_predictions.jsonl`: one row per validation crop.
- `results/bentham_trocr_validation_metrics.json`: validation metrics and configuration.

Predictions are streamed and flushed after each sample. The metrics file is
marked `running` before processing starts; only `status=complete` represents a
finished evaluation. An interrupted run must be rerun to complete the baseline.
The prediction-file SHA-256 in the final metrics binds the two artifacts.

Bentham separation is page-level only. Writer IDs are unavailable, so this is
not a writer-disjoint evaluation. It measures the unmodified pretrained
checkpoint on Bentham and involves no training or fine-tuning.

The cached model may warn about newly initialized `encoder.pooler.dense`
weights during loading. This is retained as a loading warning; no training or
fine-tuning is performed. The processor currently uses its cached slow image
processing implementation, as selected by the existing loader and recorded
Transformers version. Reproduction should use the recorded package versions.
