# Academix component boundaries

Academix is split into three deployable components:

- **Flutter frontend** owns user experience and communicates with the backend
  over HTTP. It does not host model training or heavy OCR processing.
- **FastAPI backend** owns versioned APIs, authentication, PostgreSQL
  persistence, and orchestration of asynchronous submission processing.
- **Python AI engine** owns isolated dataset preparation, model training,
  OCR, evaluation, and inference. The backend is its integration boundary.

Assignment evaluation jobs are persisted and processed by a bounded local
worker pool. They are visible only to the owning teacher. An evaluation stays
pending teacher review until a teacher explicitly approves marks and feedback;
the existing submission grade is updated only in that approval transaction.
Students continue to receive only the official submission grade and released
teacher feedback.

Handwritten-submission processing should preserve the original upload and
store OCR confidence independently from grading confidence. Model output is a
teacher-review suggestion, not a published grade; only an explicit teacher
approval should make a final grade visible to a student.

Dataset source files, processed data, and model checkpoints are intentionally
not tracked in Git. Manifests should describe the dataset-specific source
records without requiring a single fixed directory or column layout.
