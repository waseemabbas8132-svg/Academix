# Academix AI engine

This component provides private document extraction, handwritten OCR,
provisional answer evaluation, and assignment-scoped similarity signals. The
FastAPI backend persists jobs and exposes teacher-only review endpoints.
Flutter does not run OCR or model inference. AI marks remain suggestions until
a teacher explicitly approves them.

## Requirements and setup

- Python 3.11 or newer
- A PyTorch build compatible with the host's operating system and accelerator

From the Academix root, create a Python environment, install backend
requirements (including the AI engine OCR extra), and apply the database
migrations:

```powershell
py -3.12 -m venv .venv
Set-Location backend
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
..\.venv\Scripts\alembic.exe upgrade head
```

For AI-engine tests, install its test extra:

```powershell
Set-Location ..\ai-engine
..\.venv\Scripts\python.exe -m pip install -e ".[test]"
```

The evaluation model is local Ollama. On the backend host, bind Ollama to
loopback and download the configured model:

```powershell
ollama pull qwen2.5:3b
ollama serve
```

The API defaults to `http://127.0.0.1:11434` and rejects non-loopback model
URLs; student documents are not submitted to a hosted model service.

The OCR checkpoint is `microsoft/trocr-base-handwritten`. To download the
checkpoint and processor on a machine with internet access:

```powershell
..\.venv\Scripts\python.exe -c "from transformers import TrOCRProcessor, VisionEncoderDecoderModel; name='microsoft/trocr-base-handwritten'; TrOCRProcessor.from_pretrained(name); VisionEncoderDecoderModel.from_pretrained(name)"
```

The runtime uses local-only model loading by default, so it does not fetch
weights during a request. Keep the model cache private.

Start the API from `backend` after configuring the PostgreSQL URL and secret
environment variables:

```powershell
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Layout

- `datasets/raw/` — original, immutable source data; ignored by Git
- `datasets/processed/` — generated/preprocessed data; ignored by Git
- `datasets/manifests/` — dataset-specific JSON Lines manifests (keep manifests
  and documentation under version control)
- `preprocessing/` — image and text preprocessing
- `training/` — OCR model training workflows
- `evaluation/` — OCR and grading evaluation
- `inference/` — model loading and prediction services
- `models/` — local model assets/checkpoints; ignored by Git

The `academix_ai.manifest` utility reads and writes JSON Lines containing
arbitrary JSON objects. It intentionally does not assume filenames, columns,
labels, splits, or directory conventions for any external dataset. Adapt each
source dataset through an explicit manifest instead of reshaping or overwriting
the original files.

No datasets are downloaded and no training is started by setup.

## Dataset and measurement status

The local `iam_words` data has IAM-format annotations and a large image tree,
but no Kaggle source URL, license grant, or provenance record was found. It is
not used for training, tuning, or performance claims. Verify rights before
creating any dataset manifest. Audit the local tree from this directory:

```powershell
..\.venv\Scripts\python.exe -m evaluation.dataset_audit --raw-root datasets/raw --verify-images
```

The latest verified audit found 44,564 IAM-format annotation records: 38,305
`ok` and 6,259 `err`. It found 38,304 valid image/label candidates, one
corrupt image, one malformed annotation line, and no duplicate image content.
The files span 28 writer IDs; there was no source-provided split manifest. The
deterministic writer-hash split had no writer leakage in the audit. No manifest
was written because the source and license remain unverified; raw files were
left unchanged.

Only after verifying provenance and permitted use, create a deterministic
writer-disjoint manifest with `--license-confirmed` and
`--write-manifest datasets/manifests/iam_words.jsonl`. Corrupt and duplicate
image records are excluded. No model was trained, and no OCR accuracy or
human-grade agreement measurement is available.

Legacy `.doc` files are rejected for automatic extraction; convert them to
`.docx` or PDF. PDF and DOCX text extraction, PDF page references, typed
submissions, and scanned-image OCR are supported. Multi-question documents
without recognizable question headings are left unscored for teacher review.
Similarity results are investigation signals, not proof of plagiarism.

## Checks

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest
Set-Location ..\ai-engine
..\.venv\Scripts\python.exe -m pytest
Set-Location ..
flutter analyze
flutter test
```
