"""Role-scoped SQL aggregates and bounded classroom activity, without AI calls."""
from datetime import UTC, datetime
from sqlalchemy import select, func, case, and_, or_
from app.models.ai_evaluation import AIEvaluation, EvaluationJob
from app.models.assignment import Assignment
from app.models.classroom import AcademicClass, ClassMembership
from app.models.submission import Submission
from app.models.announcement import Announcement
from app.models.submission_review import SubmissionReview
from app.models.assignment_rubric import AssignmentRubric
from app.services.review_workflow import deadline_status, utc


def dashboard(db, user, offset=0, limit=25, timezone_offset=0):
    teacher = user.role == 'teacher'
    classes = select(AcademicClass.id).where(AcademicClass.is_archived.is_(False))
    if teacher:
        classes = classes.where(AcademicClass.teacher_id == user.email)
    else:
        classes = classes.join(ClassMembership).where(ClassMembership.student_id == user.email)
    assignments = select(Assignment.id).where(Assignment.class_id.in_(classes),
        Assignment.is_archived.is_(False), Assignment.is_published.is_(True))
    if teacher: assignments = assignments.where(Assignment.teacher_id == user.email)
    sq = select(Submission).where(Submission.assignment_id.in_(assignments))
    if not teacher: sq = sq.where(Submission.student_id == user.email)
    subs = sq.subquery()
    def count(q): return db.scalar(select(func.count()).select_from(q.subquery())) or 0
    def status_count(value): return db.scalar(select(func.count()).select_from(subs).where(subs.c.status == value)) or 0
    now = datetime.now(UTC)
    assigned = count(select(Assignment.id).where(Assignment.id.in_(assignments)))
    total_submitted = db.scalar(select(func.count()).select_from(subs).where(subs.c.submitted_at.is_not(None))) or 0
    if teacher:
        expected = db.scalar(select(func.count()).select_from(ClassMembership).join(Assignment,
            Assignment.class_id == ClassMembership.class_id).where(Assignment.id.in_(assignments))) or 0
    else: expected = assigned
    latest_versions = select(SubmissionReview.submission_id, func.max(SubmissionReview.version).label('version')).group_by(SubmissionReview.submission_id).subquery()
    current_reviews = select(SubmissionReview.submission_id, SubmissionReview.state).join(latest_versions,
        (latest_versions.c.submission_id == SubmissionReview.submission_id) & (latest_versions.c.version == SubmissionReview.version))
    current_reviews = current_reviews.join(subs, (subs.c.id == SubmissionReview.submission_id) & (subs.c.updated_at == SubmissionReview.source_updated_at))
    current_reviews = current_reviews.subquery()
    draft_count = db.scalar(select(func.count()).select_from(current_reviews).where(current_reviews.c.state == 'draft')) if teacher else None
    reviewed_count = db.scalar(select(func.count()).select_from(current_reviews).where(current_reviews.c.state == 'reviewed')) if teacher else None
    stats = dict(classes=count(classes), active_assignments=assigned, pending_submissions=max(expected-total_submitted,0),
        submitted=total_submitted, late=db.scalar(select(func.count()).select_from(subs).where(subs.c.is_late.is_(True))) or 0,
        returned=status_count('returned'), graded=status_count('graded'), released_grades=status_count('graded'),
        student_drafts=status_count('draft'))
    if teacher:
        latest_job_id = (
            select(EvaluationJob.id)
            .where(EvaluationJob.submission_id == subs.c.id)
            .order_by(EvaluationJob.created_at.desc(), EvaluationJob.id.desc())
            .limit(1)
            .correlate(subs)
            .scalar_subquery()
        )
        current_rubric_updated_at = (
            select(AssignmentRubric.updated_at)
            .where(AssignmentRubric.assignment_id == subs.c.assignment_id)
            .limit(1)
            .correlate(subs)
            .scalar_subquery()
        )
        rubric_is_current = or_(
            and_(
                EvaluationJob.rubric_updated_at.is_(None),
                current_rubric_updated_at.is_(None),
            ),
            EvaluationJob.rubric_updated_at == current_rubric_updated_at,
        )
        current_ai_jobs = (
            select(
                EvaluationJob.status.label('status'),
                AIEvaluation.review_status.label('review_status'),
            )
            .join(subs, subs.c.id == EvaluationJob.submission_id)
            .outerjoin(AIEvaluation, AIEvaluation.job_id == EvaluationJob.id)
            .where(
                EvaluationJob.id == latest_job_id,
                EvaluationJob.source_updated_at == subs.c.updated_at,
                rubric_is_current,
            )
            .subquery()
        )
        ai_evaluated = db.scalar(
            select(func.count())
            .select_from(current_ai_jobs)
            .where(current_ai_jobs.c.status == 'completed')
        ) or 0
        ai_pending = db.scalar(
            select(func.count())
            .select_from(current_ai_jobs)
            .where(
                or_(
                    current_ai_jobs.c.status.in_(('pending', 'processing')),
                    and_(
                        current_ai_jobs.c.status == 'completed',
                        current_ai_jobs.c.review_status == 'pending',
                    ),
                )
            )
        ) or 0
        stats.update(students=db.scalar(select(func.count(func.distinct(ClassMembership.student_id))).where(ClassMembership.class_id.in_(classes))) or 0,
            not_submitted=max(expected-total_submitted,0), pending_manual_reviews=status_count('submitted'),
            draft_reviews=draft_count, reviewed=reviewed_count,
            pending_ai_evaluations=ai_pending,
            ai_evaluated_submissions=ai_evaluated)
    # SQL aggregation across all scoped rows. Display rows are paginated, not used
    # to compute totals. Grade percentages compare different assignment maxima.
    scope = [Submission.assignment_id.in_(assignments), Submission.status == 'graded', Submission.marks_obtained.is_not(None)]
    if not teacher: scope.append(Submission.student_id == user.email)
    performance_query = select(Assignment.id,Assignment.title,Assignment.total_marks,
        func.count(Submission.id).label('released'),func.avg(Submission.marks_obtained).label('average')).join(
        Submission,Submission.assignment_id == Assignment.id).where(*scope).group_by(Assignment.id,Assignment.title,Assignment.total_marks)
    performance = [dict(assignment_id=r.id,title=r.title,released=r.released,average=float(r.average),total_marks=str(r.total_marks))
        for r in db.execute(performance_query.order_by(Assignment.title).offset(offset).limit(limit))]
    progress_query = select(Submission.student_id, func.count(Submission.id).label('released'),
        func.avg(100.0*Submission.marks_obtained/Assignment.total_marks).label('percent')).join(Assignment).where(*scope).group_by(Submission.student_id)
    progress = [dict(student_id=r.student_id,released=r.released,average_percent=float(r.percent))
        for r in db.execute(progress_query.order_by(Submission.student_id).offset(offset).limit(limit))]
    deadlines_query = select(Assignment).where(Assignment.id.in_(assignments)).order_by(Assignment.due_date,Assignment.id)
    deadlines = list(db.scalars(deadlines_query.offset(offset).limit(limit)))
    own = {} if teacher else {s.assignment_id:s for s in db.scalars(select(Submission).where(
        Submission.student_id==user.email,Submission.assignment_id.in_([a.id for a in deadlines])))}
    deadline_rows = [dict(assignment_id=a.id,class_id=a.class_id,title=a.title,due_date=utc(a.due_date),
        total_marks=str(a.total_marks), status=deadline_status(a.due_date,now,timezone_offset,own.get(a.id)),
        submission_status=own[a.id].status if a.id in own else 'not_submitted') for a in deadlines]
    activity_query = select(Submission,Assignment.title).join(Assignment).where(Submission.id.in_(select(subs.c.id)))
    activity = [dict(kind='submission',assignment_id=s.assignment_id,submission_id=s.id,title=title,
        student_id=s.student_id,status=s.status,at=utc(s.updated_at),marks_obtained=s.marks_obtained,
        feedback=s.teacher_feedback) for s,title in db.execute(activity_query.order_by(Submission.updated_at.desc(),Submission.id).limit(limit))]
    announcements = db.scalars(select(Announcement).where(Announcement.class_id.in_(classes)).order_by(Announcement.created_at.desc()).limit(limit)).all()
    activity += [dict(kind='announcement',title=a.title,at=utc(a.created_at),class_id=a.class_id,feedback=a.content) for a in announcements]
    activity.sort(key=lambda r:r['at'],reverse=True)
    # Only current, explicitly released manual snapshots support question analytics.
    # Bounded sample; never presented as complete population statistics.
    snapshots = db.scalars(select(SubmissionReview).join(subs,
        (subs.c.id==SubmissionReview.submission_id)&(subs.c.updated_at==SubmissionReview.source_updated_at))
        .where(SubmissionReview.state=='released').order_by(SubmissionReview.created_at.desc()).limit(100)).all() if teacher else []
    questions = {}
    for review in snapshots:
        for q in review.data.get('questions',[]):
            key = (review.rubric_signature,q['question_id'])
            item = questions.setdefault(key,dict(question_id=q['question_id'],prompt=q['prompt'],count=0,total=0.0,max_marks=q['max_marks']))
            item['count'] += 1
            item['total'] += float(q['marks'])
    question_stats = [dict(question_id=q['question_id'],prompt=q['prompt'],samples=q['count'],
        average=q['total']/q['count'],max_marks=q['max_marks']) for q in questions.values()]
    return dict(message=f'Welcome, {user.name}',role=user.role,server_now=now,timezone_offset_minutes=timezone_offset,
        statistics=stats,deadlines=deadline_rows,activity=activity[:limit],performance=performance,progress=progress,
        question_performance=question_stats,question_analytics_scope='Latest at most 100 current manually released reviews; grouped by rubric version',
        question_analytics_samples=len(snapshots),offset=offset,limit=limit,total_assignments=assigned,
        total_performance_assignments=count(performance_query),total_progress_students=count(progress_query))
