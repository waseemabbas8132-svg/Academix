# Academix live AI evaluation demo report

**Checked:** 18 November 2026 (local machine, Asia/Karachi)

## Result

**A real end-to-end evaluation of the handwritten demo submission was not
generated.** No inference was started because available RAM was insufficient
for the configured OCR-plus-evaluator path. No database rows, grades, or model
files were changed, and no provisional grade was published.

The two existing sample images are
`assets/demo/handwritten_submission_page_1.png` (76,103 bytes) and
`assets/demo/handwritten_submission_page_2.png` (71,985 bytes). They were not
submitted or sent to OCR. Consequently, this report has **no actual OCR output,
no actual AI marks or feedback for those images, and no total or percentage**.

There is a prior local evaluator-only smoke result at
`ai-engine/evaluation/results/final_ai_sprint_20261117/production_smoke.json`.
It records a genuine response from `qwen2.5:3b` to a **synthetic typed test
answer**, not OCR of either image and not a result saved through the live
backend:

- Test answer: “Plants use light energy to turn carbon dioxide and water into
  glucose, releasing oxygen.”
- Question `q1`: **3 / 5**.
- Feedback: “The answer is correct but could benefit from more detailed
  explanation of the process.”
- The artifact records about 20.31 seconds for the Ollama request, no human
  verified marks, and `official_grade_written: false`.

This may be shown only as a clearly labelled **prior evaluator smoke test**.
It is not a handwritten, assignment-scoped, persisted, or approved demo result.
The Flutter fixture screen is also explicitly synthetic and must not be shown
as live AI output.

## Safe resource check

| Check | Observation |
| --- | --- |
| Available physical RAM | 3.56 GiB on the first reading; 4.25 GiB on the last pre-inference reading. No inference ran between readings. |
| Ollama | Running on loopback port 11434. `ollama list` showed `qwen2.5:3b` downloaded (listed as 1.9 GB); `ollama ps` showed no model loaded. |
| TrOCR checkpoint | Local Hugging Face snapshot exists for `microsoft/trocr-base-handwritten`; `model.safetensors` is 1,333,384,464 bytes (about 1.24 GiB), plus processor/tokenizer files. |
| Other processes | Chrome, VS Code, Word and other desktop processes were using memory. No process or listener for the FastAPI backend or PostgreSQL was observed. |
| Ports | Ollama 11434 listened. Nothing listened on 8000 or 5432; `GET http://127.0.0.1:8000/api/v1/health` could not connect. |

The TrOCR weights alone are about 1.24 GiB in memory at float32. The downloaded
Qwen model is about 1.9 GB as reported by the local CLI (a previous local
Ollama API observation recorded 2,420,574,780 bytes). The workflow loads OCR
weights and then calls Ollama; Python/PyTorch, image tensors, generation
activations, and Ollama context/runtime memory add to those model weights.
Thus, the model artifacts alone consume most of or more than the 4.25 GiB
available, before runtime overhead. The prior 2.3 GiB free-memory estimate is
even less adequate. This is an estimate, not a benchmark. **Inference was
skipped; no attempt was made to free memory by terminating user processes.**

## Existing pipeline inspected

1. A student uploads text and files through
   `POST /api/v1/assignments/{assignment_id}/submissions`. The backend stores
   original uploads and their metadata; the teacher can retrieve the original
   through the protected file endpoint.
2. A teacher configures an assignment rubric through
   `PUT /api/v1/assignments/{assignment_id}/rubric`, then requests an
   evaluation through `POST /api/v1/submissions/{submission_id}/evaluations`.
   The backend records a pending job with submission/rubric version snapshots
   and sends it to the evaluation worker.
3. The worker loads the saved files and invokes the AI engine:
   - JPG/JPEG/PNG: Pillow image decode, preprocessing, line segmentation and
     `microsoft/trocr-base-handwritten` OCR.
   - PDF: PyMuPDF extracts digital text per page; pages without text are
     rendered for OCR. Mixed text/graphics is flagged for review.
   - DOCX: `python-docx` extracts paragraphs and table cells.
   - Legacy `.doc` is rejected; it is not automatically extracted.
4. The engine maps extracted text to rubric questions. Uncertain OCR,
   missing text, or ambiguous question mapping causes abstention/manual review,
   not an inferred zero. `qwen2.5:3b` is called locally through Ollama with the
   question, rubric and answer. Output is schema-checked, marks are bounded by
   question maxima, and evidence must quote the answer. A total is suggested
   only when all questions have valid scores.
5. Extracted segments, question scores, feedback, model identity and an
   evaluation with review state `pending` are persisted by the backend.
6. In the teacher UI, open the submission, inspect/download the original, then
   open **AI evaluation**. The screen displays extracted text, question-wise
   suggested marks/maxima, explanation, evidence, feedback, total and
   percentage. A teacher can edit question marks and feedback, save changes
   privately, approve the result, and explicitly publish it.
7. The publish endpoint requires an approved evaluation and writes the official
   grade to the submission. The student-facing released-review endpoint returns
   question marks/feedback only for a graded submission with a released review.
   Provisional AI results are not student-visible.

The evaluator uses the loopback Ollama URL, model `qwen2.5:3b`, deterministic
generation settings, structured JSON output, and a 180-second default timeout.
The OCR recognizer loads local-only weights by default. The backend dependency
chain is `backend/requirements.txt`, including `../ai-engine[ocr]`; the AI
engine OCR extra includes PyTorch, Transformers and OpenCV, with Pillow, NumPy,
PyMuPDF and `python-docx` in the base engine dependencies. Python 3.11+ is
required. Ollama must have the configured Qwen model. No dependency install or
model download was run.

## Document-format checks

Ran four existing focused extractor tests without running either AI model:

```powershell
Set-Location C:\Users\SUNNY.COMPUTERS\academix\ai-engine
..\backend\venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp "$env:TEMP\academix-format-check" tests\test_pipeline.py::test_pdf_and_docx_text_extraction_preserve_pdf_page_numbers tests\test_pipeline.py::test_scanned_pdf_ocr_preserves_page_references_and_low_confidence_warnings tests\test_pipeline.py::test_handwritten_image_extraction_preserves_low_confidence_for_review tests\test_pipeline.py::test_docx_table_content_empty_documents_and_corrupt_docx_are_explicit
```

Result: **4 passed in 1.93 seconds**.

| Format | Evidence and limit |
| --- | --- |
| Digital PDF | PyMuPDF extracted known text from a generated two-page PDF and preserved page numbers. Focused test passed. |
| DOCX | `python-docx` extracted known paragraph and table text from generated valid DOCX files. Focused test passed. |
| Handwritten JPG/PNG | The code route and confidence safeguards passed a test using a stub recognizer. **No actual TrOCR extraction was run on the supplied PNGs**, so model-backed handwriting extraction is not verified for this demo. |
| Scanned PDF | Page rendering, page references and low-confidence handling passed a test using a stub recognizer. **No actual TrOCR extraction was run**, so scanned-PDF OCR is not verified for this demo. |

The PDF/DOCX checks used valid generated test documents, not student submissions.
Do not claim live handwritten-image or scanned-PDF OCR success from these
stub-based tests.

## Chrome/live workflow status

Source inspection confirms that the teacher screen is connected to the
backend-backed AI repository, shows real extracted segments when given a real
job, and provides save-review, approve and publish actions. Submission review
provides access to the original attachment. The backend checks that the
evaluation still matches the current submission and rubric; publishing is
separate from approval. Student grade retrieval is gated on official graded /
released state.

**The live browser workflow was not verified in this check.** The API health
request failed because port 8000 was not listening, and PostgreSQL port 5432 was
also not listening. The user's earlier Chrome login report was not retested.
No evaluation result exists from this run to open in Chrome.

## Guarded repeat procedure

Do not start inference at the measured 4.25 GiB free RAM. For a future
demonstration, have the presenter close unneeded applications themselves, then
repeat the checks below. A conservative operational target is at least 8 GiB
free before attempting one assignment; this is a safety margin, not a measured
minimum or guarantee.

1. From PowerShell, check RAM, Ollama, model residency, listeners and backend
   health. Do not launch an evaluation unless memory headroom is sufficient:

   ```powershell
   $os = Get-CimInstance Win32_OperatingSystem
   [math]::Round($os.FreePhysicalMemory / 1MB, 2)
   ollama list
   ollama ps
   Get-NetTCPConnection -LocalPort 8000,5432,11434 -State Listen -ErrorAction SilentlyContinue
   Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
   ```

2. Before starting FastAPI, verify PostgreSQL is reachable and the schema is
   already current. **Do not run migrations as part of the demo.** FastAPI
   startup requeues persisted pending evaluation jobs, so first inspect their
   status read-only; if the query fails or reports pending/processing jobs,
   stop and investigate rather than starting the backend:

   ```powershell
   Set-Location C:\Users\SUNNY.COMPUTERS\academix\backend
   .\venv\Scripts\python.exe -m alembic current
   .\venv\Scripts\python.exe -c "from sqlalchemy import create_engine,text; from app.core.config import get_settings; e=create_engine(get_settings().database_url); c=e.connect(); print(c.execute(text('SELECT status, count(*) FROM evaluation_jobs GROUP BY status ORDER BY status')).all()); c.close()"
   ```

3. If checks are clean, start the existing backend and serve the existing web
   build. Do not reset the database or modify model settings:

   ```powershell
   # Terminal 1
   Set-Location C:\Users\SUNNY.COMPUTERS\academix\backend
   .\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

   # Terminal 2
   Set-Location C:\Users\SUNNY.COMPUTERS\academix
   .\backend\venv\Scripts\python.exe -m http.server 5173 --bind 127.0.0.1 --directory build\web
   ```

   Verify API health and that teacher/student sign-in works before opening the
   AI screen. If a rebuilt web app is needed, use the existing
   `flutter build web --no-pub --no-web-resources-cdn --no-wasm-dry-run`
   command from the project root.

4. Using genuine course content, configure and publish one demo assignment
   with a teacher-authored answer key and question rubric. Submit one small
   existing handwritten page as the demo student. From the teacher's
   submission-review screen, request **one** evaluation and wait for its
   persisted job to complete. Compare displayed OCR text against the original;
   if it is uncertain, leave marks provisional and review manually.
5. Present question-wise marks/maxima and feedback, suggested total and
   percentage as **provisional**. Edit marks/feedback if needed, save privately,
   approve as teacher, and publish only after review. Then refresh the student
   view and verify only the official published grade is visible. Record actual
   OCR, question results, total, percentage, and RAM before/after in an updated
   report; never substitute fixture or smoke-test values for this result.

If sufficient RAM or the live database is unavailable, the safe presentation
fallback is the labelled prior Ollama smoke result above, alongside the
existing non-AI submission/review UI. Do not present it as handwritten OCR,
an assignment result, a saved grade, or a live evaluation.
