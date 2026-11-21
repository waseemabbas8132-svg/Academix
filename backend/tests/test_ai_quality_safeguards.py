from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.database.base import Base
from app.models.ai_evaluation import AIEvaluation, EvaluationJob, QuestionEvaluation
from app.models.submission import Submission
from app.schemas.ai_evaluation import EvaluationApprovalInput
from app.services import ai_evaluation_service as service
from conftest import TestSessionLocal, test_engine
from test_ai_evaluations import _create_submission, _headers, client


@pytest.fixture(autouse=True)
def isolated():
    Base.metadata.drop_all(bind=test_engine); Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine); Base.metadata.create_all(bind=test_engine)


def setup_job(*, completed=True, suggested=None):
    teacher,student,sid=_create_submission()
    with TestSessionLocal() as db:
        submission=db.get(Submission,sid);aid=submission.assignment_id
    response=client.put(f'/api/v1/assignments/{aid}/rubric',headers=_headers(teacher),json={
        'questions':[{'question_id':'q1','prompt':'Explain.','max_marks':'10','model_answer':'Supported explanation.'}]})
    assert response.status_code==200
    with TestSessionLocal() as db:
        submission=db.get(Submission,sid)
        job=EvaluationJob(submission_id=sid,requested_by='teacher@academix.app',
                          source_updated_at=submission.updated_at,
                          rubric_updated_at=datetime.fromisoformat(response.json()['updated_at']),
                          status='completed' if completed else 'pending',attempt_count=1 if completed else 0)
        db.add(job);db.flush();jid=job.id;eid=None
        if completed:
            evaluation=AIEvaluation(job_id=jid,suggested_total=suggested,maximum_marks=10,confidence=.1,
                                    explanation='Uncertain extraction.',feedback='Review required.',
                                    model_name='fake',model_version='test',review_status='pending')
            db.add(evaluation);db.flush();eid=evaluation.id
            db.add(QuestionEvaluation(evaluation_id=eid,question_id='q1',suggested_marks=suggested,
                                      maximum_marks=10,confidence=.1,explanation='Review.',feedback='Review.',
                                      evidence=[],needs_review=True))
        db.commit()
    return teacher,student,sid,jid,eid


def test_unscored_result_requires_complete_explicit_teacher_marks_before_release():
    teacher,student,sid,jid,eid=setup_job()
    response=client.post(f'/api/v1/evaluations/{eid}/approve',headers=_headers(teacher),
                         json={'marks_obtained':'6','teacher_feedback':'Reviewed the original.'})
    assert response.status_code==409
    assert client.get(f'/api/v1/student/submissions/{sid}',headers=_headers(student)).json()['marks_obtained'] is None
    response=client.post(f'/api/v1/evaluations/{eid}/approve',headers=_headers(teacher),
                         json={'marks_obtained':'6','teacher_feedback':'Reviewed the original.','question_marks':{'q1':'6'}})
    assert response.status_code==200,response.text
    assert response.json()['question_evaluations'][0]['teacher_marks']=='6.00'
    before_publish=client.get(f'/api/v1/student/submissions/{sid}',headers=_headers(student)).json()
    assert before_publish['marks_obtained'] is None
    publication=client.post(f'/api/v1/evaluations/{eid}/publish',headers=_headers(teacher))
    assert publication.status_code==200,publication.text
    official=client.get(f'/api/v1/student/submissions/{sid}',headers=_headers(student)).json()
    assert official['marks_obtained']=='6.00' and official['teacher_feedback']=='Reviewed the original.'


@pytest.mark.parametrize('value',['0.005','NaN','Infinity','-0.01'])
def test_question_marks_reject_rounding_drift_and_nonfinite_values(value):
    with pytest.raises(ValidationError):
        EvaluationApprovalInput.model_validate({'marks_obtained':0,'teacher_feedback':'Reviewed.', 'question_marks':{'q1':value}})


def test_manual_grade_invalidates_old_ai_proposal_even_in_same_second():
    teacher,student,sid,jid,eid=setup_job(suggested=Decimal('8'))
    response=client.post(f'/api/v1/submissions/{sid}/grade',headers=_headers(teacher),
                         json={'marks_obtained':'6','teacher_feedback':'Manual decision.'})
    assert response.status_code==200
    response=client.post(f'/api/v1/evaluations/{eid}/approve',headers=_headers(teacher),
                         json={'marks_obtained':'8','teacher_feedback':'Old proposal.','question_marks':{'q1':'8'}})
    assert response.status_code==409
    official=client.get(f'/api/v1/student/submissions/{sid}',headers=_headers(student)).json()
    assert official['marks_obtained']=='6.00' and official['teacher_feedback']=='Manual decision.'


def test_resubmission_has_precise_version_and_invalidates_old_evaluation():
    teacher,student,sid,jid,eid=setup_job(suggested=Decimal('8'))
    with TestSessionLocal() as db:
        aid=db.get(Submission,sid).assignment_id
    changed_at=datetime.now(UTC)+timedelta(seconds=2,microseconds=123456)
    with patch('app.api.v1.routes.assignments.datetime') as clock:
        clock.now.return_value=changed_at
        response=client.post(f'/api/v1/assignments/{aid}/submissions',headers=_headers(student),
                             data={'submission_text':'A genuinely revised answer.'})
    assert response.status_code==201,response.text
    observed=datetime.fromisoformat(response.json()['updated_at'])
    if observed.tzinfo is None:observed=observed.replace(tzinfo=UTC)
    assert observed==changed_at
    approval=client.post(f'/api/v1/evaluations/{eid}/approve',headers=_headers(teacher),
                         json={'marks_obtained':'8','teacher_feedback':'Old answer.','question_marks':{'q1':'8'}})
    assert approval.status_code==409


def result():
    from academix_ai.contracts import EvaluationResult,QuestionScore
    return EvaluationResult((QuestionScore('q1',8,10,.8,'Reason.','Feedback.'),),8,10,.8,
                            'Provisional.','Review.',True,'fake','test')


@pytest.mark.parametrize('raises',[False,True])
def test_old_attempt_cannot_complete_or_fail_a_retried_job(monkeypatch,raises):
    teacher,student,sid,jid,eid=setup_job(completed=False)
    class Pipeline:
        def extract(self,request):
            from academix_ai.contracts import ExtractedDocument,TextSegment
            return ExtractedDocument((TextSegment('Supported explanation.',1,'typed_submission'),))
        def evaluate(self,request,extracted):
            with TestSessionLocal() as db:
                job=db.get(EvaluationJob,jid);job.attempt_count+=1;db.commit()
            if raises:raise RuntimeError('Old worker failed after a newer attempt started')
            return result()
    monkeypatch.setattr(service,'SessionLocal',TestSessionLocal)
    monkeypatch.setattr(service,'create_pipeline',lambda:Pipeline())
    service.process_evaluation_job(jid)
    with TestSessionLocal() as db:
        job=db.get(EvaluationJob,jid)
        assert job.attempt_count==2 and job.status=='processing' and job.evaluation is None


def test_worker_never_replaces_existing_official_teacher_grade(monkeypatch):
    teacher,student,sid,jid,eid=setup_job(completed=False)
    manual=client.post(f'/api/v1/submissions/{sid}/grade',headers=_headers(teacher),
                       json={'marks_obtained':'6','teacher_feedback':'Official teacher decision.'})
    assert manual.status_code==200
    with TestSessionLocal() as db:
        job=db.get(EvaluationJob,jid);job.source_updated_at=db.get(Submission,sid).updated_at;db.commit()
    class Pipeline:
        def extract(self,request):
            from academix_ai.contracts import ExtractedDocument,TextSegment
            return ExtractedDocument((TextSegment('Supported explanation.',1,'typed_submission'),))
        def evaluate(self,request,extracted):return result()
    monkeypatch.setattr(service,'SessionLocal',TestSessionLocal)
    monkeypatch.setattr(service,'create_pipeline',lambda:Pipeline())
    from app.models.ai_evaluation import EvaluationFeedback
    monkeypatch.setattr(service,'_compare_with_peers',lambda *args,**kwargs:[
        EvaluationFeedback(kind='similarity_signal',similarity_score=.99,
                           message='Investigation signal, not proof of misconduct.',details={})])
    service.process_evaluation_job(jid)
    with TestSessionLocal() as db:
        assert db.get(EvaluationJob,jid).evaluation.suggested_total==Decimal('8')
        assert db.get(EvaluationJob,jid).evaluation.feedback_items[0].kind=='similarity_signal'
        assert db.get(Submission,sid).marks_obtained==Decimal('6')
    official=client.get(f'/api/v1/student/submissions/{sid}',headers=_headers(student)).json()
    assert official['teacher_feedback']=='Official teacher decision.'
