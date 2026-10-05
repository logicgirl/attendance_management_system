from fastapi import APIRouter

from app.api.routes import attendance, audit, auth, courses, reports, students, terms, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(students.router)
api_router.include_router(courses.router)
api_router.include_router(terms.router)
api_router.include_router(attendance.router)
api_router.include_router(reports.router)
api_router.include_router(audit.router)
