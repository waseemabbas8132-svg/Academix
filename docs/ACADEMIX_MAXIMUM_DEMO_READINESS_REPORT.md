# Academix Maximum Demo Readiness

## Executive status

The existing application is connected end to end for its ordinary class,
assignment, submission, review, and released-grade workflows. AI results remain
provisional until a teacher approves them, and approval is now distinct from
publishing the official grade.

No new real AI evaluation was generated for this report. The live teacher
dashboard showed **0 pending AI evaluations** and **0 AI-evaluated
submissions**. No grades or OCR text in this report are fabricated. Available
RAM at the final check was about 2.3 GB, so no large inference was started.

Fresh sign-ins were performed in the running Chrome application at
`http://localhost:55707`: the teacher form submitted to
`http://127.0.0.1:8000/api/v1/auth/login` with HTTP 200 and navigated to
`/#/teacher`; the student form also returned HTTP 200 and navigated to
`/#/student`. The browser was left signed in as the teacher. The teacher
dashboard request returned HTTP 200 and showed 33 active classes, one active
assignment, zero pending AI evaluations, and zero AI-evaluated submissions.
The student dashboard showed nine joined classes and one active assignment.

## Screens and navigation

### Top-level routes

The GoRouter routes are:

| Route | Screen |
| --- | --- |
| `/` and `/login` | Sign-in |
| `/teacher` | Teacher shell |
| `/student` | Student shell |
| `/dashboard` | Admin dashboard |

Authentication redirects users to the dashboard appropriate to their role.
Authenticated users cannot use a different role's dashboard route.

### Teacher navigation

The teacher shell exposes **Home, Classes, Calendar, Notifications, and
Profile**. From classes, teachers can open class streams, manage announcements,
create assignments, inspect submissions, and open submission details. A
submission can be reviewed manually or opened in the AI evaluation screen.
That screen links to the answer-key/rubric editor and original-file viewer.

### Student navigation

The student shell exposes **Home, Assignments, Classes, Calendar,
Notifications, and Profile**. Students can join a class with a code, read class
announcements, open available assignments, submit text or files, inspect their
submission, and see released marks and feedback.

### Role restrictions and workflows

- Class creation, roster controls, announcements management, rubric editing,
  AI review, and grading are teacher-only.
- Students can join classes using class codes; they do not receive teacher
  controls.
- Students do not receive AI evaluation records, provisional marks, teacher
  drafts, or unpublished feedback.

## Implemented and verified behavior

- Role-scoped dashboards use backend data and show assignment, submission,
  class, review, and released-grade counts. Teacher dashboards additionally
  show current pending AI evaluations and evaluated submissions; those metrics
  are not included in student dashboard responses.
- Teacher AI review displays the student identity available from the demo auth
  mapping, submission metadata, original uploaded file, extracted segments,
  OCR confidence/review warnings, rubric prompts and criteria, question-wise
  suggested and teacher-entered marks, explanations, evidence, and feedback.
- Teachers can save private review edits, approve an evaluation, reject a
  suggestion, and separately publish an approved grade. Marks are checked
  against question and assignment maxima; edited question marks must sum to the
  approved total.
- Published student results include released marks, percentage, and feedback.
  The displayed A–F band is explicitly illustrative, not an institutional
  grading policy.
- Original uploads are retained. The viewer previews supported PDF pages and
  images and provides original-file download. DOCX is download-only in the
  attachment viewer; extracted DOCX text is shown after evaluation.
- Manual-review drafts and release behavior remain separate from the AI review
  flow.

## Document extraction support

The supported pipeline is implemented in
[`text_extractor.py`](../ai-engine/preprocessing/text_extractor.py) and uses
the assignment's rubric before evaluation.

| Source | Extraction behavior | Limitations and review signals |
| --- | --- | --- |
| JPG, JPEG, PNG | Existing TrOCR handwriting recognizer; page/segment source and confidence are retained. | Low-confidence or blank OCR is flagged for teacher review; no accuracy guarantee. |
| Digital PDF | Embedded text is extracted page by page. | Pages mixing text and graphics/annotations receive a warning because embedded images may contain omitted handwriting. |
| Scanned PDF | Pages without embedded text are rendered and sent through OCR. Page numbers and low-confidence warnings are retained. | Blank/unreadable pages remain reviewable; PDF processing is capped at 30 pages per submission. |
| DOCX | Paragraph and table-cell text is extracted. | Empty files warn that no readable text was found; malformed files are rejected clearly. |
| Legacy DOC | Not evaluated automatically. | Student must convert to DOCX or PDF. |
| Other extensions | Rejected as unsupported. | No content is silently discarded as a successful extraction. |

Extraction does not guarantee that question/answer boundaries are known. The
rubric-scoped evaluator can abstain when the answer cannot be confidently
associated with a rubric question. OCR confidence is a review signal, not a
calibrated probability of correctness.

## AI results and demonstration data

- **New real AI results generated:** none.
- **Stored AI evaluations shown on the live teacher dashboard:** zero.
- **Real OCR or marks presented as demo output:** none.
- Existing demo accounts are configured in
  [`auth.py`](../backend/app/api/v1/routes/auth.py), not in PostgreSQL.
- AI inference was not started because no saved result was available to review
  and only about 2.3 GB RAM was free. A real submission and configured AI
  evaluator are needed for a genuine result.

## Demo credentials

These are local demonstration credentials from the in-code demo account map:

| Role | Email | Password |
| --- | --- | --- |
| Teacher | `teacher@academix.app` | `password123` |
| Student | `student@academix.app` | `password123` |

They are not production credentials. Replace the demo authentication design
before exposing the service publicly; do not reuse these passwords.

## Configuration and startup

The Flutter API base URL is selected in
[`api_constants.dart`](../lib/core/constants/api_constants.dart):

- Flutter Web and local browser: `http://127.0.0.1:8000`
- Android emulator: `http://10.0.2.2:8000`
- Login endpoint: `/api/v1/auth/login`

The development CORS configuration allows loopback browser origins including
`http://localhost:55707`. Production deployments should configure the exact
trusted origins using `CORS_ALLOWED_ORIGINS`.

With PostgreSQL already configured and the backend virtual environment
available, use separate PowerShell terminals:

```powershell
# Terminal 1: from the repository root
Set-Location C:\Users\SUNNY.COMPUTERS\academix\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
# Terminal 2: from the repository root
Set-Location C:\Users\SUNNY.COMPUTERS\academix
flutter run -d chrome --web-port 55707
```

Open `http://localhost:55707/#/login`. Keep the backend on port **8000**.
This task did not run migrations, reset data, or alter PostgreSQL records.

## Verification results

| Check | Result |
| --- | --- |
| Backend full suite (`backend/venv`, `pytest -q -p no:cacheprovider`) | **73 passed**; two upstream deprecation warnings. Test fixtures use isolated test databases. |
| AI-engine extraction/evaluator tests (`test_pipeline.py`, `test_evaluation_quality.py`) | **45 passed**, including handwritten images, scanned and digital PDFs, DOCX paragraphs/tables, empty/corrupt DOCX, and unsupported DOC. |
| Flutter full widget/unit suite (`flutter test -r expanded`) | **35 passed**. |
| Flutter static analysis (`flutter analyze`) | **No issues found**. |
| Flutter Web release build | **Succeeded**. The Wasm compatibility dry run reports the secure-storage web dependency uses `dart:html`/`dart:js_util`; the standard Web release build succeeds. |
| Running browser/backend | Fresh teacher and student sign-ins were completed in Chrome. Both `/api/v1/auth/login` requests returned **200**; the app navigated to the correct role dashboards. `/api/v1/teacher/dashboard` returned **200** with the live counts recorded above. |
| PostgreSQL data and migrations | No reset, schema drop, migration, or direct data write was performed for this work. |

## Remaining work

- Generate a genuine AI evaluation only after confirming the evaluator service,
  an appropriate real submission/rubric, and sufficient available RAM.
- Define and configure the institution's official grade-band policy rather
  than using the explicitly illustrative A–F display.
- Add inline DOCX preview if desired; current support is original download and
  extracted-text display after evaluation.
- Replace in-code demo authentication before deployment and configure exact
  production CORS origins.
