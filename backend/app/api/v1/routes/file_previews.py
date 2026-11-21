"""Authenticated, read-only, bounded rendering; no OCR or AI imports."""
import io
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.api.v1.routes.auth import UserPublic, _current_user_from_token
from app.database.session import get_db
from app.services.assignments import get_file_for_user
from app.services.file_storage import FileStorage, get_file_storage

router = APIRouter()


def resolve(db, file_id, user, storage):
    record = get_file_for_user(db, file_id, user)
    try:
        path = storage.resolve(record.storage_key)
        if not path.is_file(): raise FileNotFoundError()
    except FileNotFoundError as error:
        raise HTTPException(404, 'Original file is missing.') from error
    return record, path


def render(path: Path, page: int | None):
    extension = path.suffix.lower()
    try:
        if extension == '.pdf':
            import pymupdf
            with pymupdf.open(path) as pdf:
                if pdf.needs_pass or pdf.page_count == 0:
                    raise HTTPException(422, 'PDF is encrypted or has no readable pages. Download the original.')
                if page is None: return dict(kind='pdf', page_count=pdf.page_count)
                if page > pdf.page_count: raise HTTPException(404, 'Page not found.')
                document_page = pdf[page - 1]
                longest = max(document_page.rect.width, document_page.rect.height)
                if not longest or longest > 100000: raise ValueError('Invalid page size')
                pixmap = document_page.get_pixmap(matrix=pymupdf.Matrix(1600 / longest, 1600 / longest), alpha=False)
                return pixmap.tobytes('png')
        if extension in {'.png','.jpg','.jpeg'}:
            with Image.open(path) as image:
                if image.width * image.height > 25_000_000:
                    raise HTTPException(413, 'Image is too large to preview safely. Download the original.')
                if page is None:
                    image.verify()
                    return dict(kind='image',page_count=1)
                if page != 1: raise HTTPException(404, 'Page not found.')
                image.load()
                preview = ImageOps.exif_transpose(image).convert('RGB')
                preview.thumbnail((1600,1600))
                output = io.BytesIO()
                preview.save(output,format='PNG')
                return output.getvalue()
        if page is None: return dict(kind='download_only',page_count=0)
        raise HTTPException(415, 'Preview unavailable. Download the original document.')
    except HTTPException:
        raise
    except ImportError as error:
        raise HTTPException(503, 'Preview renderer unavailable. Download the original.') from error
    except Exception as error:
        raise HTTPException(422, 'File cannot be decoded safely. Download the original.') from error


@router.get('/files/{file_id}/preview')
def info(file_id: str, user: UserPublic = Depends(_current_user_from_token), db: Session = Depends(get_db),
         storage: FileStorage = Depends(get_file_storage)):
    record, path = resolve(db,file_id,user,storage)
    return dict(filename=record.original_filename,**render(path,None))


@router.get('/files/{file_id}/preview/pages/{page}')
def preview(file_id: str, page: int, user: UserPublic = Depends(_current_user_from_token),
            db: Session = Depends(get_db), storage: FileStorage = Depends(get_file_storage)):
    if page < 1: raise HTTPException(422,'Pages start at 1.')
    _, path = resolve(db,file_id,user,storage)
    return Response(render(path,page),media_type='image/png',headers={
        'Cache-Control':'private, no-store', 'X-Content-Type-Options':'nosniff'})
