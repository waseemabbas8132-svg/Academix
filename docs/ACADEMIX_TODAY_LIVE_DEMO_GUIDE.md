# Academix Today Live Demo Guide

**Status:** The teacher-to-student workflow has been exercised end to end. The prepared student grade is already teacher-approved and published.

## Demo accounts

Use the same browser origin, `http://localhost:5173/`, for both accounts:

| Role | Email | Password |
|---|---|---|
| Teacher | `teacher@academix.app` | `password123` |
| Student | `student@academix.app` | `password123` |

Sign out before switching roles. The browser session persists across refreshes and sign-ins.

## Prepared demo data

- **Class:** `ACADEMIX TODAY DEMO - Water Cycle`
- **Class code:** `YPSH1YBY`
- **Assignment:** `DEMO: Water Cycle - Evaporation, Condensation, Runoff`
- **Assignment status:** Published; 30 total marks; three 10-mark questions.
- **Student:** `student@academix.app`, already enrolled in the demo class.
- **Submission:** `academix_today_sample_submission.docx`, synthetic sample work; not a real student's work.
- **Final published result:** 24/30 (80.0%). The app displays an illustrative grade band B; this is not institutional grading policy.

The rubric questions and scoring guidance are visible to the student:

1. Explain how solar energy causes evaporation in the water cycle. (10)
2. Explain condensation and precipitation, and give one example of precipitation. (10)
3. Explain how collection and runoff return water to rivers or oceans. (10)

The prepared sample evaluation initially suggested 8/10, 8/10, and 7/10 (23/30). During verification, the teacher changed question 1 to 9/10, added question and overall feedback, saved the edits privately, approved the result, and explicitly published it. The final approved result is 9/10, 8/10, and 7/10 (24/30).

## Start the services

Do not reset or recreate PostgreSQL. The existing local database and records are in use.

**Terminal 1 — FastAPI** (from PowerShell):

```powershell
Set-Location C:\Users\SUNNY.COMPUTERS\academix\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — build and serve Flutter Web:**

```powershell
Set-Location C:\Users\SUNNY.COMPUTERS\academix
flutter build web --no-pub --no-web-resources-cdn --no-wasm-dry-run
python -m http.server 5173 --bind 127.0.0.1 --directory build\web
```

Keep both terminals running. Open:

- Teacher and student portal: [http://localhost:5173/](http://localhost:5173/)
- API health: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)
- API documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

The health endpoint returned `{"status":"ok"}` during verification. If the browser shows an older build, do a hard refresh or use a fresh browser session.

## Suggested presentation sequence

The seeded record is already published, so this sequence presents the completed live workflow and its persisted result.

### Teacher portal

1. Sign in as `teacher@academix.app`.
2. Show the teacher dashboard and recent classroom activity. It reports one graded and one released demo grade.
3. Open **Classes** → `ACADEMIX TODAY DEMO - Water Cycle` → **Assignments** → `DEMO: Water Cycle - Evaporation, Condensation, Runoff`.
4. Show the published assignment instructions, 30-mark total, deadline, and three-question rubric. The rubric was created and published through the teacher UI.
5. Select **View student submissions**. The roster shows the student and **Grade published** status.
6. Open the student submission. Show its submitted status/history, attached original, and released total/percentage/feedback.
7. Open **AI evaluation** to show the question-wise sample review, teacher-edited marks, approval state, and disclosure. Do **not** click **Run a new evaluation** during this demo.

The original is a DOCX. Its in-app preview reports that DOCX preview is unavailable; use **Download original**. The downloaded file was verified to match the uploaded original byte for byte.

### Student portal

1. Sign out of the teacher account and sign in as `student@academix.app`.
2. Open **Classes** and show the joined demo class. Students have **Join class**, not **Create class**.
3. Open **Assignments** and the published Water Cycle assignment. Show the assignment instructions and all three student-safe rubric questions and scoring guidance.
4. Open **My submissions** and show the submitted DOCX and its status.
5. After teacher publication, open the submission/recent grade activity. The student sees **24/30**, **80.0%**, the illustrative grade band, and released teacher feedback.

The student was refreshed and signed in again after publication; the grade remained visible. Before publication, including after the teacher saved private edits and after approval, the student endpoint returned a submitted status with no marks or feedback. The student does not receive the teacher's private sample suggestions.

### Showing the review controls again

The real prepared submission has already been approved and published, so its private edit/approval controls are no longer available. The teacher dashboard also has **Open isolated AI evaluation demo** for a clearly labeled, synthetic, in-memory walkthrough of review controls. Its changes do not affect the real student or backend record; do not present it as a live student grade.

To create a new backend sample evaluation for a **new supported demo submission**, run the guarded seeder once with that submission's ID:

```powershell
Set-Location C:\Users\SUNNY.COMPUTERS\academix\backend
.\venv\Scripts\python.exe -m scripts.seed_demo_sample_evaluation --submission-id "REPLACE_WITH_SUBMISSION_ID"
```

The seeder only accepts the dedicated published demo assignment, the demo student, and the required 30-mark rubric. It refuses to overwrite an existing evaluation and creates a pending teacher review; it runs no AI or OCR. The current prepared submission ID is `7d28f6c9-a9dc-498f-a0eb-73e831d7efbb` and already has a published evaluation, so do not use it to create another evaluation.

## AI versus sample content

- **No real handwritten AI evaluation was run.** Available RAM was approximately 6.1 GiB, below the project's documented 8 GiB safety target. No memory safeguard was bypassed, and no live TrOCR or Qwen/Ollama inference was started.
- The uploaded DOCX, extracted-answer examples, marks, and feedback are synthetic/manual demo content. The evaluation screen labels them **DEMO/SAMPLE — NOT GENERATED BY LIVE AI** and shows an extraction warning.
- Sample confidence is not measured. The sample text is not OCR output, and its feedback is not model-generated.
- The application has a TrOCR/Ollama evaluation path, but today's result must not be described as AI-generated.

## Verified checks

- Teacher and student login, dashboards, class enrollment, assignment creation/publication, and student rubric visibility were exercised in the browser.
- The student uploaded the synthetic DOCX and received submission confirmation; teacher and student submission status persisted after refresh/sign-in.
- Teacher opened the submission, viewed the original-download flow, inspected the sample evaluation and warnings, privately edited marks/feedback, and confirmed the student could not see the private result.
- Teacher explicitly approved 24/30 and confirmed **Publish grade**. The teacher dashboard and roster show a published grade.
- After signing in again, the student saw the released 24/30, 80.0%, and teacher feedback. The student class screen showed **Join class** and no **Create class** button.
- The downloaded original matched the uploaded DOCX by SHA-256.
- Backend tests: **10 passed** (two dependency deprecation warnings).
- Focused Flutter tests: **3 passed**. The fixture-presentation test still emits a non-fatal tap hit-test warning at a 600-pixel test viewport.
- Flutter Web production build: **passed**.

## Known limitations

- The real prepared sample is already published; it cannot be used to replay the pending-review state without a new submission.
- DOCX in-app preview is unavailable. The secure original download works.
- No live OCR warnings, extracted handwritten text, or AI-generated marks are available for this rehearsal.
- A prior full Flutter test run found an unrelated narrow-width dashboard overflow (about 124 px); it is not part of this demo workflow and was not changed here.
- Dashboard manual-review counters are separate from AI-evaluation publication; use the assignment roster and submission review to show this demo's actual published status.
