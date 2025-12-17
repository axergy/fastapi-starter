from fastapi import APIRouter

from src.app.api.v1 import admin, audit, auth, invites, projects, tenants, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(tenants.router)
api_router.include_router(invites.router)
api_router.include_router(projects.router)
api_router.include_router(admin.router)
api_router.include_router(audit.router)
