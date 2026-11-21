"""Run real Alembic upgrades only against a disposable SQLite database."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_additive_upgrade_preserves_existing_attachment_and_submission_rows(tmp_path):
    database=tmp_path/'migration.sqlite'
    env={**os.environ,'DATABASE_URL':f'sqlite:///{database.as_posix()}','PYTHONDONTWRITEBYTECODE':'1'}
    backend=Path(__file__).resolve().parents[1]
    def upgrade(revision):
        result=subprocess.run([sys.executable,'-B','-m','alembic','upgrade',revision],cwd=backend,
                              env=env,text=True,capture_output=True,timeout=90)
        assert result.returncode==0,result.stdout+result.stderr
    upgrade('20261114_ai_evaluations')
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO classes (id,name,section,subject,class_code,teacher_id,is_archived) VALUES ('c','Class','A','Science','UNIQUE','teacher',0)")
        db.execute("INSERT INTO assignments (id,class_id,teacher_id,title,instructions,total_marks,due_date,is_published,is_archived) VALUES ('a','c','teacher','Work','Instructions',20,'2026-11-20',1,0)")
        db.execute("INSERT INTO submissions (id,assignment_id,student_id,status,is_late,submission_text) VALUES ('s','a','student','submitted',0,'Original text')")
        db.execute("INSERT INTO uploaded_files (id,submission_id,storage_key,original_filename,content_type,size_bytes) VALUES ('f','s','original.pdf','Original.pdf','application/pdf',123)")
        before=db.execute('SELECT * FROM submissions').fetchall()
        file_before=db.execute('SELECT id,submission_id,storage_key,original_filename,content_type,size_bytes FROM uploaded_files').fetchall()
    upgrade('head')
    with sqlite3.connect(database) as db:
        assert db.execute('SELECT * FROM submissions').fetchall()==before
        assert db.execute('SELECT id,submission_id,storage_key,original_filename,content_type,size_bytes FROM uploaded_files').fetchall()==file_before
        assert db.execute('SELECT submission_revision_id FROM uploaded_files').fetchone()==(None,)
        assert db.execute('SELECT count(*) FROM submission_reviews').fetchone()==(0,)
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()==('20261117_manual_reviews',)
    # Upgrading the same database again is a no-op, not a second migration.
    upgrade('head')
