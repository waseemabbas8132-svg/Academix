# Academix demo readiness

Prepared on 18 November 2026 for the 19 November demonstration, Asia/Karachi.

The configured PostgreSQL database is at the application’s current schema. Both demo accounts reached their FastAPI dashboards. A separate PostgreSQL schema was used to rehearse the data-changing workflow over HTTP, including upload, download and restart. Flutter analysis, widget tests and the web build passed. Interactive browser sign-in still needs a rehearsal on the presentation desktop. Use manual review for grading. The configured database contains no saved AI evaluation to open.

## 1. Features verified working

| Workflow | Verification |
| --- | --- |
| Teacher and student sign-in and dashboards | Both demo users logged in, passed JWT identity checks and received HTTP 200 for their dashboards. Student access to the teacher dashboard returned 403. Both portals have Home, Classes, Calendar, Notifications and Profile navigation. The student portal adds an Assignments tab. |
| Class creation, join code and roster | Teacher creation and student join returned 201 in isolated PostgreSQL. The teacher read back the generated code and the enrolled student. Student class creation returned 403. Flutter widget checks exercised role-specific controls, required fields and teacher-only code and roster visibility. |
| Announcements | Teacher creation returned 201. Student reading returned 403 before enrollment and 200 after enrollment. The backend suite also covers editing, pinning and deletion through isolated fixtures. |
| Assignment setup and publication | Teacher creation returned 201, rubric save and publishing returned 200. The test saved a question, maximum marks and a criterion. The student list excluded the draft and showed the published assignment. Student assignment details returned 200. |
| Submissions and attachments | Student multipart PNG upload returned 201. The teacher fetched the submissions list and downloaded bytes identical to the upload. Student status was `submitted`. The class, published assignment, submission and attachment remained accessible after stopping and restarting Uvicorn. |
| Grade privacy | A private manual draft saved successfully in PostgreSQL. Student marks and released review both remained null. Isolated backend tests also exercised marking reviewed, explicit release, student access to the official total and question breakdown, and authorization on private review routes. |
| Existing AI integration | Live PostgreSQL returned 404 for an owning teacher when the submission had no evaluation and 403 for a student. Backend tests used stubbed jobs/results to verify provisional marks and approval boundaries. Flutter tests used fake completed evaluations to exercise readback and review. |

## 2. Partially verified features

- File handling coverage includes live PNG upload/download and fixture-based PDF, image and DOCX handling. PDF and image preview have API and Flutter component coverage. DOCX uses original download.
- Manual release and student readback ran in automated fixtures. The PostgreSQL rehearsal stopped at the private draft, and the configured demonstration database still has no released marks.
- Calendar, notifications/activity, Profile, teacher submission review and attachment views were inspected in source. Their execution coverage varies by screen. The notification view displays app activity.
- The AI evaluation UI can show an existing result and allows teacher review. The configured database contains zero evaluation jobs and zero results. Live OCR, model scoring and AI accuracy were outside this rehearsal.

## 3. Broken or incomplete features

- The Classes UI previously exposed only the list. The role-specific create and join flows, code and roster are now linked from the application.
- The configured database was one migration behind the code and lacked the manual-review table and attachment revision column. The existing additive migration was applied after isolated PostgreSQL verification.
- The login backend defines one teacher and one student. A second student cannot sign in through the current account list. There is no account provisioning UI.
- The legacy generic dashboard contains placeholder interactions. The teacher and student role routes lead to their dedicated portals.

## 4. UI and workflow fixes

- Added teacher **Create class** and student **Join class** actions with required-field validation, save progress, specific feedback for invalid codes and role-specific empty states.
- Added a selectable and copyable class code and an enrolled student roster under teacher **Classes → class → About**. The roster includes loading, empty and retry states.
- Added **Configure rubric** to teacher assignment details so questions and marking criteria can be set before publication. Returning from successful creation refreshes the class assignment list immediately.
- Added **Teacher demo** and **Student demo** sign-in shortcuts and restricted authenticated dashboard routes to the signed-in role.
- Added an opt-in browser origin setting for a loopback web demonstration. Native clients keep using the existing API URL and contracts.

## 5. Tests and exact results

| Check | Result |
| --- | --- |
| Backend pytest from `backend` with `-q -p no:cacheprovider --basetemp=../build/demo-backend-final` | **70 passed**, 1 Starlette TestClient deprecation warning, 23.83 s. Tests used isolated in-memory SQLite and temporary upload storage. The migration test used a disposable SQLite file. An initial default-temp invocation hit a Windows permission error during fixture setup. |
| Isolated PostgreSQL 18.7 and Uvicorn HTTP rehearsal | Upgrade to `20261114_ai_evaluations`, then to `20261117_manual_reviews`, succeeded. The workflow and restart assertions in section 1 passed. The successful rehearsal used schema `demo_qa_5fa982fd0d` plus its own upload directory under `build`. An earlier rehearsal stopped at an incorrect probe field name after the API accepted the upload. |
| Configured PostgreSQL upgrade and lifespan check | `alembic upgrade head` advanced from `20261114_ai_evaluations` to `20261117_manual_reviews`. Verified matching row counts and row digests on the eight tables in section 6. Health, both logins, both dashboards and both class lists returned 200 through FastAPI TestClient with lifespan enabled. |
| Flutter widget suite with `test --no-pub --reporter expanded` | **32 passed**. The first run had 31 passing tests and one narrow-screen test failure because its helper matched multiple scrollables. Targeting the review page’s scrollable made the test exercise the intended interaction at 320 px. |
| `flutter analyze --no-pub lib test` | Exit 0, **No issues found**, 7.1 s. Direct `dart analyze lib test` also passed. |
| `flutter build web --no-pub --no-web-resources-cdn --no-wasm-dry-run` | Exit 0, **Built `build/web`**, 18.6 s. Flutter analysis, tests and build ran against a workspace-local copy of the cached SDK because the original SDK cache was read-only to the test process. |
| Configured PostgreSQL and real Uvicorn on port 8000 | Health returned 200. CORS preflight returned 200 for the configured local browser origin and 400 for an unlisted origin. |
| Static demo server on port 5173 | HTTP 200 for the landing page, Flutter bootstrap, compiled app JavaScript and local CanvasKit binary. |
| Headless browser smoke | In the test environment Edge’s GPU process failed on the first attempt. Edge and Chrome follow-ups opened the local page but timed out in the browser automation connection before rendering or sign-in could be confirmed. Browser-to-backend end-to-end execution is unverified. |

## 6. Available demo accounts and data

| Role | Email | Local demo password |
| --- | --- | --- |
| Teacher | `teacher@academix.app` | `password123` |
| Student | `student@academix.app` | `password123` |

Both accounts are defined by the local demo authentication code. The configured database contains 36 classes, 8 memberships and 6 announcements. There are zero assignments, submissions, uploaded-file records, AI evaluation jobs and AI evaluation results. The teacher account’s list returned 33 active classes and the student account’s list returned 8. Existing records were preserved. Test workflow data was written to separate PostgreSQL schemas and separate upload directories.

Recommended sample data for the demo:

- Use the verified teacher and student accounts. Reserve `student2@academix.app` as a second lab student only if a second demo identity is provisioned later. For this demonstration, show the workflow with the available student.
- Create **DEMO — Computing Lab**, section **A**, subject **Computing**. Post **DEMO — Lab instructions** with “Submit your answer as one PDF or PNG.”
- Create **DEMO — Algorithm trace**, worth 10 marks, with two 5-mark questions and a criterion for each. Publish it. Keep **DEMO — Data validation**, worth 10 marks, as a draft to show the visibility difference. Use future due dates.
- Use a small PDF or PNG of a written solution from the available demo student. Leave one submission at `submitted` or with a private teacher draft. If a second demo student is provisioned, use a second actual answer as a returned-for-revision example. If showing release, review the answer and release the marks earned during the demonstration.

## 7. Startup commands

Use two PowerShell terminals. The PostgreSQL Windows service was running during verification. The backend virtual environment and cached Flutter dependencies are already present.

**Terminal 1 — FastAPI**

```powershell
Set-Location C:\Users\SUNNY.COMPUTERS\academix\backend
Get-Service postgresql-x64-18
.\venv\Scripts\python.exe -m alembic current
$env:CORS_ALLOWED_ORIGINS='["http://127.0.0.1:5173"]'
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Expected revision is `20261117_manual_reviews (head)`. In another terminal, `Invoke-RestMethod http://127.0.0.1:8000/api/v1/health` should return `status = ok`. Use both role dashboards as the database-backed readiness check. The health route reports the API process status.

**Terminal 2 — Flutter web**

```powershell
Set-Location C:\Users\SUNNY.COMPUTERS\academix
.\backend\venv\Scripts\python.exe -m http.server 5173 --bind 127.0.0.1 --directory build/web
```

Open **http://127.0.0.1:5173/** in Edge or Chrome. Use this exact origin so the API permits requests. The verified web build already exists under `build/web`. To rebuild after a source change, run `flutter build web --no-pub --no-web-resources-cdn --no-wasm-dry-run` from the project root. A native Windows build additionally needs the Visual Studio C++ desktop toolchain.

## 8. Known limitations

- FastAPI can fall back to a local SQLite file when PostgreSQL connection fails. Check the configured database and both dashboards before presenting.
- A pending AI job can be resumed on ordinary backend startup. The configured job table was empty during verification. Avoid **Run evaluation** and **Retry evaluation** during the demonstration.
- The fixed default API URL is loopback. A separate phone or remote device would need its own API address and network setup.
- The local login accounts are demo fixtures. The JWT session duration is controlled by `ACCESS_TOKEN_EXPIRE_MINUTES`. Sign in again if the rehearsal session has expired.
- Verification covered the browser build, widget interactions and HTTP workflows separately. The test environment did not provide a verified interactive browser or a Visual Studio Windows desktop build toolchain.
- Verification used installed dependencies and cached Flutter assets. No model inference, training, fine-tuning, downloads or deployment were performed. Models, OCR, prompts, evaluation logic, benchmark artifacts and accuracy reports were outside the edits.

## 9. Recommended presentation sequence

1. Use the teacher shortcut and sign in. Show Home, then open **Classes → Create class**. Open the new class and copy the code from **About**.
2. Post one announcement. In **Assignments**, create the first assignment, open its details, choose **Configure rubric**, save the questions and criteria, then switch it to **Published**. Keep the second assignment as a draft.
3. Use a separate browser profile or private window for the student session. Join using the code, read the announcement and open the published assignment. Select a prepared file and submit. Open the submission status.
4. Return to the teacher session. Show the enrolled student in **About**, open **View student submissions**, and inspect the uploaded file. Use **Manual review → Save private draft**. In the student session, reload the submission and show that the draft marks are private.
5. If you choose to show release, mark the genuine review reviewed, release the official grade and refresh the student submission. Open **AI evaluation** only as an optional overview of the existing review surface. With the current data, it will show the empty state.
