# Academix showcase feature gap audit

Audit date: 2026-11-16 (Asia/Karachi). Project: `C:\Users\SUNNY.COMPUTERS\academix`.

## Verdict and evidence boundaries

The existing application already supports assignment submission, teacher review of submission text, total-mark grading, feedback, AI-assisted question review, explicit AI-grade approval, and student access to official totals and feedback. These features should be reused. The full showcase workflow is **PARTIALLY IMPLEMENTED** because attachment viewing, AI-independent question grading, private review saving, approved-question-mark readback, and dashboard summaries have gaps.

Execution evidence: **33 existing backend tests passed**, **12 existing Flutter tests passed**, and an additional isolated API probe confirmed that an AI suggestion of 8 can be overridden to 6 and released as 6 to the student. Backend execution used disposable **in-memory SQLite**, not PostgreSQL. Flutter tests used fake repositories or mock HTTP responses. These results do not establish a running Flutter-to-FastAPI-to-PostgreSQL deployment, real PDF rendering, or successful real-model inference.

No application code, migrations, persistent database, datasets, manifests, predictions, or checkpoints were intentionally changed. This report is the only authored project document. Test runners produced disposable build/upload artifacts and normal tool caches. No migrations or production server startup were run. Hash checks around the backend tests confirmed that all 113 monitored source/test/migration/database files remained unchanged, including the existing root `academix.db`. No prior showcase audit report was found in the project file search.

### Status definitions

| Status | Meaning in this report |
| --- | --- |
| VERIFIED | The stated, bounded behavior exists and has passing execution evidence. This does not imply every platform or deployment was exercised. |
| PARTIALLY IMPLEMENTED | Useful parts exist, but a required part of the complete workflow is missing or defective. |
| MISSING | No implementation for the specified capability was found in the inspected routes, models, services, or UI. |
| BROKEN | An implemented capability has a concrete contradiction or defect. Static defects are distinguished from runtime reproductions. |
| NOT VERIFIED | Evidence is insufficient to establish runtime behavior; absence of verification is not evidence of failure. |

## Workflow assessment

All endpoint paths below use the configured default `/api/v1` prefix, established by `backend/app/main.py`, `backend/app/api/v1/router.py`, and `backend/app/core/config.py`.

| # | Requested feature | Overall status | Existing implementation and concrete gap | API and test evidence |
| --- | --- | --- | --- | --- |
| 1 | Teacher manually reviews student assignments | **VERIFIED**, for submission text, metadata, and aggregate grading | `TeacherSubmissionsScreen`, `SubmissionDetailsScreen`, and `GradeSubmissionScreen` in `lib/features/assignments/presentation/screens/submission_screens.dart` provide the review path. Assignment details link to teacher submissions. Ownership checks exist in `backend/app/services/assignments.py`. Attachment preview and manual question grading have separate gaps in rows 2–3. | `GET /api/v1/assignments/{assignment_id}/submissions`; `POST /api/v1/submissions/{submission_id}/grade`, implemented in `backend/app/api/v1/routes/assignments.py`. Passing assignment tests cover teacher ownership, submission lists, and total grading; the Flutter grading test passes. |
| 2 | Teacher opens submitted PDF/images | **PARTIALLY IMPLEMENTED** | `_SubmissionDownloadTile` in `lib/features/assignments/presentation/screens/submission_screens.dart` fetches bytes and invokes file saving. `lib/features/assignments/data/services/assignment_file_picker.dart` uses `FilePicker.saveFile`. An in-app PDF/image viewer or automatic external opening was **MISSING** in the inspected UI and dependencies. Opening the saved document using the operating system is **NOT VERIFIED**. | `GET /api/v1/files/{file_id}` in `backend/app/api/v1/routes/assignments.py` returns an authorized attachment download. Passing file tests verify upload checks and access boundaries, not PDF/image rendering. The Flutter attachment test covers selecting/uploading a file, not viewing it. |
| 3 | Teacher checks answers question by question and assigns marks | **PARTIALLY IMPLEMENTED** | `TeacherAIEvaluationScreen` in `lib/features/assignments/presentation/screens/ai_evaluation_screens.dart` displays extracted text, rubric question results, evidence, feedback, and editable question marks. This requires an existing completed AI evaluation. `GradeSubmissionScreen` offers only a total and overall feedback. AI-independent manual question grading is **MISSING**; approval explicitly requires a rubric-based AI mark suggestion. | `GET/PUT /api/v1/assignments/{assignment_id}/rubric`, `GET/POST /api/v1/submissions/{submission_id}/evaluations`, and `POST /api/v1/evaluations/{evaluation_id}/approve` in `backend/app/api/v1/routes/ai_evaluations.py`. Rubric and approval tests pass. No existing test demonstrates manual question grading without AI. |
| 4 | Teacher edits or overrides AI-suggested marks | **PARTIALLY IMPLEMENTED** | Editing and saving overrides are implemented: the screen submits `question_marks`; the backend validates question coverage, ranges, and total, then persists `teacher_marks`. Core override persistence is **VERIFIED** by the isolated 8-to-6 probe. Approved override readback in the AI review screen is **BROKEN**: its Dart models discard `teacher_marks`, `approved_marks`, and teacher feedback, and the screen continues to display suggestions after approval. See defect detail below. | `POST /api/v1/evaluations/{evaluation_id}/approve`; `backend/app/models/ai_evaluation.py`; `lib/features/assignments/data/models/ai_evaluation.dart`; `lib/features/assignments/data/repositories/ai_evaluation_repository.dart`. Existing approval tests and Flutter approval test pass, but their unchanged-suggestion cases do not cover approved override readback. |
| 5 | Teacher writes feedback and saves the review | **PARTIALLY IMPLEMENTED** | Total grading and feedback persistence are **VERIFIED**. The manual screen saves feedback with marks, or returns work using feedback without marks. AI review requires overall teacher feedback for approval. A private, resumable review draft before release is **MISSING**: manual save immediately changes the student-visible submission, while AI edits remain in controllers until approval. No separate saved-review state or draft-review API was found. | `POST /api/v1/submissions/{submission_id}/grade`; `POST /api/v1/evaluations/{evaluation_id}/approve`. `backend/app/schemas/assignment.py`, `backend/app/schemas/ai_evaluation.py`, and `backend/app/models/submission.py`. Passing manual grading/feedback and draft-return-resubmission tests; passing Flutter grading test. |
| 6 | Teacher approves and releases the official grade | **VERIFIED**, for explicit AI approval and immediate manual grading | AI suggestions remain provisional until teacher approval; approval records reviewer/time, writes official marks/feedback, and grades the submission. Manual grading also releases a grade, through its save action. A separate approval step after a privately saved manual review is **MISSING**, as described in row 5; there is no universal release-state model. | `POST /api/v1/evaluations/{evaluation_id}/approve`; `POST /api/v1/submissions/{submission_id}/grade`. `test_only_teacher_approval_changes_official_grade`, unauthorized approval, and stale-submission tests pass in `backend/tests/test_ai_evaluations.py`. The Flutter approval test passes. |
| 7 | Student sees released marks and feedback | **VERIFIED**, for official total and overall feedback | `MySubmissionsScreen` and student-mode `SubmissionDetailsScreen` in `lib/features/assignments/presentation/screens/submission_screens.dart` show official totals/feedback and refresh the student's submission on opening. The response contains no provisional evaluation payload. A released per-question mark breakdown is **MISSING** from the student submission schema/UI. Real-time grade notifications were not established; viewing requires loading/refreshing the existing screens. | `GET /api/v1/student/submissions`; `GET /api/v1/student/submissions/{submission_id}` in `backend/app/api/v1/routes/assignments.py`. Passing manual grade test and AI approval test verify student-visible feedback/marks; the isolated probe verifies the edited total. A live student-device walkthrough is **NOT VERIFIED**. |
| 8 | Late submissions and submission statuses | **VERIFIED**, for current status, late flag, drafts, return/resubmission, and text/grade history | `Submission` supports `draft`, `submitted`, `returned`, `graded`; lateness is a separate Boolean computed against the due date in UTC. Submission forms/details display status/late information. `StudentAssignmentsScreen._groupFor` separates overdue/upcoming/submitted/submitted late/returned/graded work. Drafts fall into overdue/upcoming on that screen. Revision history exists, but attachment sets are not versioned: resubmission appends files to the current submission. | `POST /api/v1/assignments/{assignment_id}/submissions`, teacher list, and student submission GETs. `backend/app/models/submission.py`; `backend/app/services/assignments.py`; `lib/features/assignments/presentation/screens/assignment_list_screen.dart`. Passing late/upsert test, draft-return-resubmission test, graded-lock test, and submission widget test. Status-group variants do not all have dedicated widget assertions. |
| 9 | Teacher dashboard: pending reviews, submissions, class activity | **PARTIALLY IMPLEMENTED** | `lib/features/teachers/presentation/screens/teacher_dashboard_screen.dart` has a working Classes tab, but Home cards are static text. Class assignment lists have live submission/graded/pending counts; class streams have live announcements. A cross-class pending-review queue, live Home counts, and aggregated class activity are **MISSING**. The existing dashboard API returns a greeting/role only. | `GET /api/v1/teacher/dashboard` in `backend/app/api/v1/routes/auth.py`; `GET /api/v1/classes/{class_id}/assignments`, `GET /api/v1/assignments/{assignment_id}/submissions`, `GET /api/v1/classes/{class_id}/announcements`. Class/announcement tests and class-stream Flutter tests pass. No dynamic Home-dashboard implementation/test was found. |
| 10 | Student dashboard: pending assignments, submitted work, released grades | **PARTIALLY IMPLEMENTED** | `lib/features/students/presentation/screens/student_dashboard_screen.dart` has a static Home card but a real Assignments tab. `StudentAssignmentsScreen` in `lib/features/assignments/presentation/screens/assignment_list_screen.dart` combines assignments and submissions into status groups and links to My submissions/details. Thus assignment tracking and grade access already exist. Live Home summary counts, grade cards, and dashboard aggregates are **MISSING**. | `GET /api/v1/student/dashboard` is greeting/role only; `GET /api/v1/student/assignments` and student submission GETs provide real data. The three assignment-list widget tests pass for empty, upcoming, and retry behavior. API tests verify publication/membership boundaries and released feedback. No test proves live Home summaries. |

## Specific defects and workflow limits

### Approved AI question-mark display: BROKEN (static data-contract defect)

The backend persists `QuestionEvaluation.teacher_marks`, `AIEvaluation.approved_marks`, and `AIEvaluation.teacher_feedback`, and exposes them through response schemas in `backend/app/schemas/ai_evaluation.py`. The approval API correctly wrote a suggested mark of 8 as a teacher mark of 6 in the isolated probe; student retrieval returned 6 and the teacher feedback.

However, `QuestionEvaluation.fromJson` and `AIEvaluation.fromJson` in `lib/features/assignments/data/models/ai_evaluation.dart` do not parse those approved fields. `TeacherAIEvaluationScreen._buildEvaluation` in `lib/features/assignments/presentation/screens/ai_evaluation_screens.dart` renders `suggestedTotal` and `suggestedMarks`; editable controls exist only while `reviewStatus == 'pending'`. After approval or reopening, the screen cannot show persisted teacher-approved question marks or approved feedback. It may accurately label the old values as suggestions, but it cannot verify the final review values. The official total on submission details remains available. This finding is established by source inspection and a passing backend override probe; an end-to-end Flutter reproduction was not run.

Related **NOT VERIFIED** risk: `_syncReviewControllers` in the same screen keys reuse on the set of question IDs. A new evaluation with the same question IDs may retain old controller values rather than initialize from the new evaluation. The passing tests do not cover forced reruns with changed suggestions; this needs a focused reproduction before classifying it as a runtime failure.

### Save versus release: PARTIALLY IMPLEMENTED

`grade_submission` in `backend/app/api/v1/routes/assignments.py` commits immediately. With marks it sets `status='graded'` and `graded_at`; without marks it sets `status='returned'`. Student responses expose stored totals/feedback. `Submission` has no private-review, approved-review, or released-at field. Therefore “save draft review → reopen → approve → release” cannot be demonstrated for manual reviews. Existing immediate grading and AI approval work and should not be duplicated.

AI approval already protects important boundaries: owning teacher only, completed pending evaluation only, current submission/rubric versions, bounded marks, all supplied question IDs, and matching total. Approval requires a non-null AI suggested total and question evaluations, so it cannot substitute for a fully manual rubric review when AI inference is unavailable or unscored overall.

### Dashboard count semantics: PARTIALLY IMPLEMENTED

`assignment_counts` in `backend/app/services/assignments.py` computes:

```text
submitted_count = submitted + returned submissions
graded_count = graded submissions
pending_count = max(enrolled students - submitted_count - graded_count, 0)
```

Consequently, existing `pending_count` means students without a non-draft submission/grade, not submissions awaiting teacher review. Draft submissions remain in that pending population, and returned submissions are included in submitted counts. It must not be presented as a teacher pending-review total. Existing class streams support announcements; they are not a combined submissions/grades/activity event feed.

### Attachments and attempts

`GET /api/v1/files/{file_id}` enforces assignment ownership/student membership or submission ownership and returns `FileResponse` with attachment disposition. The app saves the downloaded bytes. No PDF/image rendering capability was found in the submission path. File tests use signature-level fixtures; passing them does not establish full document decoding or preview quality.

`SubmissionRevision` snapshots text/status/marks/feedback/timestamps, but `UploadedFile` belongs to a submission rather than a revision. The existing resubmission test expects accumulated attachments. Historical text/grade display should not be described as a complete historical snapshot of each attempt's attachments.

## API inventory relevant to the showcase

| Endpoint | Purpose / current limit | Implementation |
| --- | --- | --- |
| `GET /api/v1/classes`; class creation/join routes | Existing teacher class management and student membership | `backend/app/api/v1/routes/classes.py` |
| `GET/POST /api/v1/classes/{class_id}/announcements` | Existing class stream; additional announcement edit/pin/delete actions also exist | `backend/app/api/v1/routes/announcements.py` |
| `GET/POST /api/v1/classes/{class_id}/assignments` | Assignment lists/create; teacher counts, published student access | `backend/app/api/v1/routes/assignments.py` |
| `GET/PUT /api/v1/assignments/{assignment_id}` | Read/edit assignment | Same assignments route file |
| `PATCH /api/v1/assignments/{assignment_id}/publish`; `DELETE /api/v1/assignments/{assignment_id}` | Publish/archive | Same assignments route file |
| `GET/POST /api/v1/assignments/{assignment_id}/submissions` | Teacher list / student draft or submitted upsert | Same assignments route file |
| `POST /api/v1/submissions/{submission_id}/grade` | Manual total + feedback; save immediately returns/grades work | Same assignments route file |
| `GET /api/v1/student/assignments` | Student's published joined-class assignments | Same assignments route file |
| `GET /api/v1/student/submissions`; `GET /api/v1/student/submissions/{submission_id}` | Student's own submissions, official marks/feedback | Same assignments route file |
| `POST /api/v1/assignments/{assignment_id}/attachments`; `GET /api/v1/files/{file_id}` | Assignment upload / authorized file download | Same assignments route file |
| `GET/PUT /api/v1/assignments/{assignment_id}/rubric` | Teacher-owned question rubric | `backend/app/api/v1/routes/ai_evaluations.py` |
| `GET/POST /api/v1/submissions/{submission_id}/evaluations` | Latest evaluation / enqueue or reuse evaluation | Same AI routes file |
| `GET /api/v1/evaluation-jobs/{job_id}`; `POST /api/v1/evaluation-jobs/{job_id}/retry` | Job progress/retry | Same AI routes file |
| `POST /api/v1/evaluations/{evaluation_id}/approve` | Persist approved question marks and release official total/feedback | Same AI routes file |
| `POST /api/v1/evaluations/{evaluation_id}/reject` | Reject pending evaluation without releasing its grade | Same AI routes file |
| `GET /api/v1/teacher/dashboard`; `GET /api/v1/student/dashboard` | Existing role-protected greeting endpoints; no aggregates | `backend/app/api/v1/routes/auth.py` |

Frontend request wiring is in `lib/features/assignments/data/repositories/assignment_repository.dart`, `lib/features/assignments/data/repositories/ai_evaluation_repository.dart`, and `lib/features/classes/data/repositories/class_stream_repository.dart`. These should remain the integration points for future work.

## PostgreSQL models and persistence assessment

The SQLAlchemy schema and Alembic migrations were inspected without connecting to the configured persistent database or applying migrations.

| Model / file | Verified schema support | Limit |
| --- | --- | --- |
| `backend/app/models/classroom.py` | Classes and student memberships; teacher ownership | Live class data and PostgreSQL constraints not exercised |
| `backend/app/models/announcement.py` | Class announcements, author and pin metadata | No general activity-event feed |
| `backend/app/models/assignment.py` | Due date, total marks, publish/archive, class/teacher association | Not a review-draft or grade-release entity |
| `backend/app/models/submission.py` | Unique assignment/student pair; four status values; late flag; numeric official marks; feedback; grade timestamp; revision relationship | No independent manual question grades, private review, release state, or attachment revision snapshots |
| `backend/app/models/uploaded_file.py` | Assignment/submission ownership and one-parent constraint; local-storage metadata | Bytes are served from local file storage; document viewer not implemented here |
| `backend/app/models/assignment_rubric.py` | Rubric and question prompts, max marks, reference answer/criteria | Does not itself hold manual student question grades |
| `backend/app/models/ai_evaluation.py` | Job states, source/rubric versions, evaluation review status, approved reviewer/time/total, question suggested/teacher marks | Question grading is attached to an AI evaluation |

Inspected migrations: `backend/migrations/versions/20261114_001_create_classes.py`, `20261114_002_create_announcements.py`, `20261114_003_create_assignments.py`, and `20261114_004_ai_evaluations.py`, plus `backend/migrations/env.py`. Numeric marks, timezone-aware timestamps, foreign keys, checks, JSON fields, and active-job uniqueness are represented; the AI migration includes PostgreSQL and SQLite partial-index predicates.

**PostgreSQL deployment: NOT VERIFIED.** `backend/app/core/config.py` defaults to SQLite. `backend/app/database/session.py` attempts the configured engine and falls back to `sqlite:///./academix.db` on connection failure. A working API therefore does not prove PostgreSQL is in use. Actual PostgreSQL schema version, migration application, data, concurrency, and constraint behavior were not checked. No claim is made that the current deployment is broken. Before a showcase claiming PostgreSQL persistence, verify the effective database dialect and migration revision using a separately authorized read-only check.

`backend/app/api/v1/routes/auth.py` uses demo identities rather than a persistent SQL user model. Existing role/ownership tests establish the tested demo authorization boundaries, not production identity provisioning. `backend/app/main.py` starts pending-evaluation recovery in lifespan; the audit did not start that lifespan against application data.

## Tests executed and reproducibility

### Backend: 33 passed, one deprecation warning

Interpreter: root `.venv\Scripts\python.exe`, using `-B` to avoid writing Python bytecode. Before importing application modules, the audit wrapper set `DATABASE_URL=sqlite://`, selected scratch upload storage, and enabled AI offline mode. Pytest's existing `backend/tests/conftest.py` supplies a separate in-memory SQLite `StaticPool`, overrides `get_db`, and redirects uploaded files to a temporary fixture directory. It creates only disposable in-memory tables.

From the `backend` working directory the wrapper invoked:

```python
pytest.main([
    '-p', 'no:cacheprovider', '-q',
    'tests/test_assignments.py', 'tests/test_ai_evaluations.py',
    'tests/test_classes.py', 'tests/test_announcements.py',
    '--basetemp=C:/Users/SUNNY.COMPUTERS/academix/build/showcase_backend_tests/fixtures_completed',
    '--tb=short',
])
```

Result: **33 passed in 3.24 seconds**. One Starlette/httpx TestClient deprecation warning; no product-code change was made. An initial audit-harness attempt failed fixture setup because the scratch parent directory was absent. Creating that scratch directory resolved it; the successful run above is the test result. This setup failure is not classified as a feature failure.

Passing evidence in `backend/tests/test_assignments.py` (10 tests):

- `test_teacher_creates_edits_and_only_manages_own_assignments`
- `test_students_only_see_published_assignments_for_joined_classes`
- `test_submission_upserts_once_supports_multiple_files_and_flags_late_work`
- `test_draft_return_and_resubmission_preserve_attempt_history`
- `test_failed_submission_upload_does_not_commit_submission`
- `test_teacher_grading_checks_marks_and_student_sees_feedback`
- `test_assignment_files_validate_content_and_enforce_download_access`
- `test_students_cannot_read_other_students_submission_files`
- `test_student_cannot_access_drafts_and_teacher_cannot_submit`
- `test_teacher_can_archive_assignment_without_erasing_submission_history`

Passing evidence in `backend/tests/test_ai_evaluations.py` (7 tests):

- `test_rubric_is_teacher_owned_and_not_visible_to_students`
- `test_evaluation_request_is_deduplicated_and_teacher_only`
- `test_only_teacher_approval_changes_official_grade`
- `test_teacher_cannot_approve_another_teachers_evaluation`
- `test_worker_persists_extraction_and_provisional_question_results`
- `test_failed_job_can_be_retried_without_exposing_model_error`
- `test_stale_submission_evaluation_cannot_be_approved`

`backend/tests/test_classes.py` (10 tests) and `backend/tests/test_announcements.py` (6 tests) also passed, covering class management/membership and class-stream access/management. These are supporting evidence for existing class navigation and announcements, not dashboard aggregation. The auth, security, health, and AI-engine suites were not run for this scoped audit.

Additional **ad hoc API probe**, not a new committed test: in the same isolated test setup, create a training-independent text submission and seed a completed provisional evaluation with one question suggested at 8/10. Confirm no official student mark before approval. Approve with `marks_obtained=6`, `question_marks={'q1': 6}`, and teacher feedback. Assert HTTP 200, persisted/returned `teacher_marks=6.00`, and student GET `marks_obtained=6.00` with matching feedback and no `evaluation`/`question_evaluations` payload. All assertions passed. No real AI model, persistent database, or uploaded dataset was used.

### Flutter: 12 passed

Logical command from the project root:

```powershell
flutter test --no-pub `
  test/features/assignments/presentation/submission_screens_test.dart `
  test/features/assignments/presentation/assignment_list_screen_test.dart `
  test/features/assignments/presentation/ai_evaluation_screen_test.dart `
  test/features/classes/presentation/class_stream_screen_test.dart `
  test/features/classes/data/class_stream_repository_test.dart
```

The initial batch-wrapper attempt produced no test result and was interrupted. Direct SDK invocation exposed a sandbox denial opening `C:\flutter\flutter\bin\cache\lockfile`. The command was rerun with approved SDK-cache access using the existing Dart executable, Flutter tool snapshot, and the same arguments:

```powershell
& 'C:\flutter\flutter\bin\cache\dart-sdk\bin\dart.exe' `
  --packages='C:\flutter\flutter\packages\flutter_tools\.dart_tool\package_config.json' `
  'C:\flutter\flutter\bin\cache\flutter_tools.snapshot' test --no-pub `
  test/features/assignments/presentation/submission_screens_test.dart `
  test/features/assignments/presentation/assignment_list_screen_test.dart `
  test/features/assignments/presentation/ai_evaluation_screen_test.dart `
  test/features/classes/presentation/class_stream_screen_test.dart `
  test/features/classes/data/class_stream_repository_test.dart
```

Result: **12 passed**, runner displayed `00:02 +12: All tests passed!` (excluding tool startup). No dependency resolution was requested (`--no-pub`). SDK update availability was displayed; no upgrade was requested.

| Existing Flutter test file | Executed evidence |
| --- | --- |
| `test/features/assignments/presentation/submission_screens_test.dart` | 2 passing widget tests: student attaches/submits; teacher validates total marks and saves feedback |
| `test/features/assignments/presentation/assignment_list_screen_test.dart` | 3 passing widget tests: empty state, upcoming assignment, load failure/retry |
| `test/features/assignments/presentation/ai_evaluation_screen_test.dart` | 2 passing widget tests: request/processing status; explicit approve before release |
| `test/features/classes/presentation/class_stream_screen_test.dart` | 2 passing widget tests: student/teacher announcement management visibility |
| `test/features/classes/data/class_stream_repository_test.dart` | 3 passing mocked HTTP tests: authenticated announcement list, forbidden handling, validation-error mapping |

These tests do not exercise actual operating-system file saving/opening, device networking, PostgreSQL, real OCR/LLM evaluation, dashboard aggregates, approved edited-question readback, or all assignment-status groups. The AI approval widget test approves existing suggestions rather than demonstrating an edited mark. `test/widget_test.dart` was not included.

## Files inspected

Paths below are relative to the project root. This is the substantive inspection inventory; generated caches/build files were excluded from feature conclusions.

### Flutter implementation

- `pubspec.yaml`
- `lib/app/router/app_router.dart`
- `lib/app/providers/app_providers.dart`
- `lib/core/constants/api_constants.dart`
- `lib/core/network/api_client.dart`
- `lib/features/authentication/presentation/providers/auth_provider.dart`
- `lib/features/teachers/presentation/screens/teacher_dashboard_screen.dart`
- `lib/features/students/presentation/screens/student_dashboard_screen.dart`
- `lib/features/classes/presentation/screens/classes_screen.dart`
- `lib/features/classes/presentation/screens/class_stream_screen.dart`
- `lib/features/classes/data/repositories/class_stream_repository.dart`
- `lib/features/assignments/presentation/screens/assignment_list_screen.dart`
- `lib/features/assignments/presentation/screens/assignment_details_screen.dart`
- `lib/features/assignments/presentation/screens/assignment_form_screen.dart`
- `lib/features/assignments/presentation/screens/submission_screens.dart`
- `lib/features/assignments/presentation/screens/ai_evaluation_screens.dart`
- `lib/features/assignments/data/models/assignment.dart`
- `lib/features/assignments/data/models/submission.dart`
- `lib/features/assignments/data/models/ai_evaluation.dart`
- `lib/features/assignments/data/repositories/assignment_repository.dart`
- `lib/features/assignments/data/repositories/ai_evaluation_repository.dart`
- `lib/features/assignments/data/services/assignment_file_picker.dart`

### Backend implementation and schema

- `backend/app/main.py`
- `backend/app/api/v1/router.py`
- `backend/app/api/v1/routes/auth.py`
- `backend/app/api/v1/routes/classes.py`
- `backend/app/api/v1/routes/announcements.py`
- `backend/app/api/v1/routes/assignments.py`
- `backend/app/api/v1/routes/ai_evaluations.py`
- `backend/app/core/config.py`
- `backend/app/database/session.py`
- `backend/app/models/classroom.py`
- `backend/app/models/announcement.py`
- `backend/app/models/assignment.py`
- `backend/app/models/submission.py`
- `backend/app/models/uploaded_file.py`
- `backend/app/models/assignment_rubric.py`
- `backend/app/models/ai_evaluation.py`
- `backend/app/schemas/assignment.py`
- `backend/app/schemas/ai_evaluation.py`
- `backend/app/repositories/assignments.py`
- `backend/app/services/assignments.py`
- `backend/app/services/file_storage.py`
- `backend/app/services/ai_evaluation_service.py`
- `backend/migrations/env.py`
- `backend/migrations/versions/20261114_001_create_classes.py`
- `backend/migrations/versions/20261114_002_create_announcements.py`
- `backend/migrations/versions/20261114_003_create_assignments.py`
- `backend/migrations/versions/20261114_004_ai_evaluations.py`

### Test evidence

- `backend/tests/conftest.py`
- `backend/tests/test_assignments.py`
- `backend/tests/test_ai_evaluations.py`
- `backend/tests/test_classes.py`
- `backend/tests/test_announcements.py`
- The five Flutter test files listed in the execution table above.

## Remaining showcase work, without duplicating existing features

These are recommendations only; no implementation was performed.

| Priority | Gap and status | Smallest useful follow-up / acceptance evidence |
| --- | --- | --- |
| 1 | Approved AI question-mark readback **BROKEN** | Extend the existing Dart evaluation models and review screen to represent persisted teacher/approved fields. Test a changed mark, approval, and reopening; show official values and preserve the labeled suggestion. Keep the working approval endpoint. |
| 1 | In-app submitted PDF/image opening **MISSING** | Extend the existing authenticated attachment download path with an explicit view/open action. Verify a real multi-page PDF and a real image, unauthorized access, and failure handling on the showcase target platform. Do not rebuild submission upload/download. |
| 1 | AI-independent manual question grading **MISSING** | Extend existing rubric/review components so a teacher can enter every question mark even when no AI job succeeds. Validate sums/maxima and expose the final breakdown appropriately. Keep existing total grading available. |
| 1 if required for the demo | Private save-then-release manual workflow **MISSING** | Decide whether immediate manual save is acceptable. If a staged workflow is required, extend existing review/grade persistence with a private saved state and explicit release transition; verify student invisibility before release and visibility afterward. Do not silently relabel immediate save as private save. |
| 2 | Live teacher Home review queue/activity **MISSING** | Reuse class, assignment, submission, and announcement data. Define awaiting-review semantics separately from existing `pending_count`. Extend the existing dashboard endpoint or compose existing APIs; avoid a second assignment/submission system. |
| 2 | Live student Home summaries **MISSING** | Reuse `StudentAssignmentsScreen` groups and student submission data for pending/submitted/released summaries with navigation. The Assignments tab and My submissions already work. |
| 2 | New-evaluation controller refresh **NOT VERIFIED** | Reproduce a rerun with identical question IDs and different suggestions, then cover controller initialization by evaluation identity/version if confirmed. |
| Before deployment claims | PostgreSQL and complete device/API/AI path **NOT VERIFIED** | Establish effective database dialect/migration state read-only; perform a separately authorized staged teacher/student walkthrough with actual uploaded files and the configured AI engine. Existing fake-engine tests are not real-model proof. |

Recommended acceptance walkthrough after future fixes: student submits PDF/image → teacher opens it → manually reviews questions (with or without AI) → changes marks and feedback → saves privately if supported → explicitly releases → student loads final totals/feedback. Include a late submission and a returned/resubmitted attempt. Assert ownership boundaries throughout. Do not claim the currently missing steps were demonstrated by this audit.
