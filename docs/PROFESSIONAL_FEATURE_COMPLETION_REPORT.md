# Professional feature completion

Implementation started 2026-11-17. This document records the inspected contracts,
implementation plan, and final verification. AI code and artifacts are protected.

## Inspection and implementation plan

Inspected the showcase audit, Flutter dependencies, router, authentication provider,
assignment repositories/models/screens, dashboard screens, backend routes, services,
repositories, schemas, SQLAlchemy models, migrations, file storage and existing tests.
Existing classes, announcements, submission upload/download, immediate total grading,
rubrics and explicit AI approval are retained. Approved AI question readback already
exists in the current code (the older showcase audit predates that fix).

1. Add one necessary private manual-review history table; reuse existing rubrics and
   official submission fields. Use optimistic versions and source/rubric checks for
   save/review/return/release. Preserve existing immediate-grade and AI APIs.
2. Add revision attachment snapshots while preserving storage bytes and existing
   ownership. Supply only current-attempt files to the existing submission pipeline.
3. Add authenticated, bounded PDF/image previews using installed libraries; DOCX
   stays download-only. Reuse original authenticated downloads.
4. Extend the existing dashboard endpoints with role-filtered SQL summaries and
   bounded activity/performance lists. Add a membership-aware filtered review roster.
5. Extend existing Flutter navigation with persistent question reviews, explicit
   release, read-only AI comparison, attachment viewing and real dashboard data.
6. Add isolated backend and Flutter coverage; run existing regression tests without
   models, inference, live database writes, downloads or deployment. Verify protected
   file hashes. Test the additive migration against a disposable database only.

The configured database can silently fall back to SQLite in existing infrastructure.
No live PostgreSQL or device-to-server verification is claimed. The login currently
supports demo accounts; production identity provisioning is outside this sprint.
