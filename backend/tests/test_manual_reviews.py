"""Application workflows only. No AI workers, lifespan or live database."""
import io
from datetime import UTC, datetime, timedelta
from uuid import uuid4
import pytest
from PIL import Image
import pymupdf
from fastapi.testclient import TestClient
from app.main import app
from app.database.base import Base
from app.services.review_workflow import deadline_status
from conftest import test_engine
from test_assignments import _login, _create_class, _create_assignment, _join_class, _publish, _submit

client=TestClient(app)


@pytest.fixture(autouse=True)
def isolated():
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)
    yield
    Base.metadata.drop_all(test_engine)
    Base.metadata.create_all(test_engine)


def headers(token): return {'Authorization':f'Bearer {token}'}


def scenario(files=None):
    teacher=_login(f'teacher-{uuid4().hex}@school.test','teacher')
    student=_login(f'student-{uuid4().hex}@school.test','student')
    c=_create_class(teacher);a=_create_assignment(teacher,c['id'])
    _join_class(student,c['class_code']);_publish(teacher,a['id'])
    response=_submit(student,a['id'],files=files)
    assert response.status_code==201,response.text
    return teacher,student,c,a,response.json()


def context(t,s):
    response=client.get(f"/api/v1/submissions/{s['id']}/review",headers=headers(t))
    assert response.status_code==200,response.text
    return response.json()


def version(c):
    return dict(expected_version=c['latest']['version'] if c['latest'] else 0,
                source_updated_at=c['source_updated_at'],rubric_signature=c['rubric_signature'])


def save(t,s,c,**changes):
    body=dict(**version(c),state='draft',questions=[dict(question_id=q['question_id'],marks='7',feedback='Evidence reviewed') for q in c['questions']],overall_feedback='Good reasoning')
    body.update(changes)
    return client.put(f"/api/v1/submissions/{s['id']}/review",headers=headers(t),json=body)


def act(t,s,c,action='release',**changes):
    return client.post(f"/api/v1/submissions/{s['id']}/review/{action}",headers=headers(t),json=dict(**version(c),**changes))


def test_question_review_privacy_restore_release_and_history():
    t,student,_,a,s=scenario()
    rubric=client.put(f"/api/v1/assignments/{a['id']}/rubric",headers=headers(t),json=dict(questions=[
        dict(question_id='q1',prompt='Explain',max_marks='8',criteria=[dict(description='Reason',marks='8',keywords=['SECRET'])]),
        dict(question_id='q2',prompt='Apply',max_marks='12')]))
    assert rubric.status_code==200,rubric.text
    c=context(t,s)
    assert save(t,s,c).status_code==200
    restored=context(t,s)
    assert restored['latest']['questions'][0]['marks']=='7'
    student_view=client.get(f"/api/v1/student/submissions/{s['id']}",headers=headers(student)).json()
    assert student_view['marks_obtained'] is None
    for path in ('review','review/history'):
        assert client.get(f"/api/v1/submissions/{s['id']}/{path}",headers=headers(student)).status_code==403
    assert client.get(f"/api/v1/submissions/{s['id']}/released-review",headers=headers(student)).json() is None
    assert act(t,s,restored).status_code==409
    assert save(t,s,restored,state='reviewed',total_override='16',override_reason='Additional demonstrated understanding').status_code==200
    reviewed=context(t,s)
    release=act(t,s,reviewed)
    assert release.status_code==200,release.text
    assert act(t,s,reviewed).status_code==409
    official=client.get(f"/api/v1/student/submissions/{s['id']}",headers=headers(student)).json()
    assert official['status']=='graded' and float(official['marks_obtained'])==16
    breakdown=client.get(f"/api/v1/submissions/{s['id']}/released-review",headers=headers(student))
    assert len(breakdown.json()['questions'])==2
    assert 'SECRET' not in breakdown.text and 'override_reason' not in breakdown.text
    history=client.get(f"/api/v1/submissions/{s['id']}/review/history",headers=headers(t)).json()
    assert history['total']==3 and [h['state'] for h in history['items']]==['released','reviewed','draft']
    assert all(h['actor'] and h['created_at'] for h in history['items'])


@pytest.mark.parametrize('change',[
    dict(questions=[dict(question_id='overall',marks='-1')]),
    dict(questions=[dict(question_id='overall',marks='21')]),
    dict(questions=[dict(question_id='overall',marks='1.234')]),
    dict(questions=[dict(question_id='overall',marks='NaN')]),
    dict(questions=[dict(question_id='overall',marks='Infinity')]),
    dict(questions=[dict(question_id='overall',marks='1'),dict(question_id='overall',marks='1')]),
    dict(questions=[]),dict(questions=[dict(question_id='unknown',marks=1)]),
    dict(total_override='21',override_reason='Reason'),dict(total_override='12',override_reason=' '),
    dict(state='reviewed',overall_feedback=' '),dict(state='reviewed',questions=[dict(question_id='overall',marks=None)]),
])
def test_invalid_marks_and_incomplete_reviews_rejected(change):
    t,_,_,_,s=scenario()
    response=save(t,s,context(t,s),**change)
    assert response.status_code==422,response.text


def test_owner_stale_and_optimistic_conflicts():
    t,student,_,a,s=scenario()
    c=context(t,s)
    other=_login('other@school.test','teacher')
    assert save(other,s,c).status_code==403
    assert save(student,s,c).status_code==403
    assert save(t,s,c).status_code==200
    assert save(t,s,c).status_code==409
    c=context(t,s)
    _submit(student,a['id'],text='New source')
    assert save(t,s,c).status_code==409
    assert context(t,s)['stale'] is True
    assert save(t,s,context(t,s),state='reviewed').status_code==200
    ready=context(t,s)
    immediate=client.post(f"/api/v1/submissions/{s['id']}/grade",headers=headers(t),json=dict(marks_obtained='3',teacher_feedback='Legacy release'))
    assert immediate.status_code==200
    assert act(t,s,ready).status_code==409


def test_rubric_changes_invalidate_review():
    t,_,_,a,s=scenario();c=context(t,s)
    assert save(t,s,c,state='reviewed').status_code==200
    before=context(t,s)
    updated=client.put(f"/api/v1/assignments/{a['id']}/rubric",headers=headers(t),json=dict(questions=[dict(question_id='q1',prompt='New criteria',max_marks=20)]))
    assert updated.status_code==200
    assert act(t,s,before).status_code==409


def test_return_revision_preserves_original_files_and_invalidates_reviews():
    original=io.BytesIO();Image.new('RGB',(40,30),'white').save(original,format='PNG')
    t,student,_,a,s=scenario([('files',('first.png',original.getvalue(),'image/png'))])
    c=context(t,s)
    assert act(t,s,c,'return',reason=' ').status_code==422
    assert act(t,s,c,'return',reason='Add evidence').status_code==200
    assert act(t,s,context(t,s),'return',reason='Again').status_code==409
    revised=_submit(student,a['id'],text='New evidence')
    assert revised.status_code==201,revised.text
    assert revised.json()['attachments']==[]
    assert revised.json()['revisions'][0]['attachments'][0]['id']==s['attachments'][0]['id']
    download=client.get(s['attachments'][0]['download_url'],headers=headers(t))
    assert download.content==original.getvalue()
    assert context(t,s)['stale'] is True
    assert context(t,s)['source_revision']==2


def test_preview_pdf_pages_image_docx_corrupt_missing_and_access():
    pdf=pymupdf.open();pdf.new_page();pdf.new_page();content=pdf.tobytes();pdf.close()
    t,student,_,a,s=scenario([('files',('work.pdf',content,'application/pdf'))])
    f=s['attachments'][0];url=f"/api/v1/files/{f['id']}/preview"
    info=client.get(url,headers=headers(t))
    assert info.json()['page_count']==2,info.text
    for page in (1,2):
        rendered=client.get(f'{url}/pages/{page}',headers=headers(student))
        assert rendered.status_code==200
        with Image.open(io.BytesIO(rendered.content)) as image: assert max(image.size)<=1600
        assert rendered.headers['cache-control']=='private, no-store'
    assert client.get(f'{url}/pages/3',headers=headers(t)).status_code==404
    assert client.get(url,headers=headers(_login('intruder@school.test','student'))).status_code==404
    assert client.get(url,headers=headers(_login('intruder@school.test','teacher'))).status_code==403
    assert client.get(f['download_url'],headers=headers(t)).content==content
    corrupt=_submit(student,a['id'],files=[('files',('bad.pdf',b'%PDF-1.7\nbad','application/pdf'))]).json()['attachments'][0]
    assert client.get(f"/api/v1/files/{corrupt['id']}/preview",headers=headers(t)).status_code==422
    doc=_submit(student,a['id'],files=[('files',('work.docx',b'PK\x03\x04test','application/vnd.openxmlformats-officedocument.wordprocessingml.document'))]).json()['attachments'][0]
    assert client.get(f"/api/v1/files/{doc['id']}/preview",headers=headers(t)).json()['kind']=='download_only'
    from app.services.file_storage import get_file_storage
    storage=app.dependency_overrides[get_file_storage]()
    from conftest import TestSessionLocal
    from app.models.uploaded_file import UploadedFile
    with TestSessionLocal() as db:
        record=db.get(UploadedFile,doc['id']);storage.resolve(record.storage_key).unlink()
    assert client.get(f"/api/v1/files/{doc['id']}/preview",headers=headers(t)).status_code==404


def test_image_preview_and_roster_filters_and_dashboard_privacy():
    image=io.BytesIO();Image.new('RGB',(20,30),'white').save(image,format='PNG')
    t,student,cl,a,s=scenario([('files',('page.png',image.getvalue(),'image/png'))])
    url=f"/api/v1/files/{s['attachments'][0]['id']}/preview"
    assert client.get(url,headers=headers(t)).json()['kind']=='image'
    assert client.get(url+'/pages/1',headers=headers(t)).status_code==200
    missing=_login('missing@school.test','student');_join_class(missing,cl['class_code'])
    assert save(t,s,context(t,s)).status_code==200
    root=f"/api/v1/assignments/{a['id']}/review-roster"
    for state,total in [('all',2),('not_submitted',1),('under_review',1),('draft',1),('reviewed',0)]:
        result=client.get(root,headers=headers(t),params={'state':state})
        assert result.status_code==200,result.text
        assert result.json()['total']==total
    teacher=client.get('/api/v1/teacher/dashboard',headers=headers(t))
    assert teacher.status_code==200,teacher.text
    stats=teacher.json()['statistics']
    assert stats['classes']==1 and stats['students']==2 and stats['not_submitted']==1
    assert stats['pending_manual_reviews']==1 and stats['draft_reviews']==1
    other=client.get('/api/v1/teacher/dashboard',headers=headers(_login('other@school.test','teacher'))).json()
    assert other['statistics']['classes']==0 and other['activity']==[]
    student_view=client.get('/api/v1/student/dashboard',headers=headers(student))
    assert student_view.status_code==200,student_view.text
    assert student_view.json()['statistics']['released_grades']==0
    assert 'draft_reviews' not in student_view.text and 'Evidence reviewed' not in student_view.text
    assert save(t,s,context(t,s),state='reviewed').status_code==200
    assert act(t,s,context(t,s)).status_code==200
    released=client.get('/api/v1/teacher/dashboard',headers=headers(t)).json()
    assert released['statistics']['released_grades']==1
    assert released['performance'][0]['average']==7
    assert released['question_performance'][0]['average']==7
    student_released=client.get('/api/v1/student/dashboard',headers=headers(student)).json()
    assert student_released['statistics']['released_grades']==1
    assert student_released['progress'][0]['average_percent']==35


def test_deadline_utc_and_local_day_boundaries():
    now=datetime(2026,11,17,20,tzinfo=UTC)
    assert deadline_status(now-timedelta(seconds=1),now)=='overdue'
    assert deadline_status(now+timedelta(hours=2),now,300)=='due_today'
    assert deadline_status(now+timedelta(hours=5),now,0)=='upcoming'
    assert deadline_status(now,now)=='due_today'
