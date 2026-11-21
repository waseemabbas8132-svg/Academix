from fastapi import APIRouter

from app.api.v1.routes import (
    ai_evaluations,
    announcements,
    assignments,
    auth,
    classes,
    health,
    submission_reviews,
    file_previews,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(classes.router, tags=["classes"])
api_router.include_router(announcements.router, tags=["announcements"])
api_router.include_router(assignments.router, tags=["assignments"])
api_router.include_router(ai_evaluations.router, tags=["AI evaluations"])
api_router.include_router(submission_reviews.router, tags=["Manual reviews"])
api_router.include_router(file_previews.router, tags=["Private file previews"])
