from fastapi import APIRouter

from app.api.v1 import auth, contributions, events, friends, public

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(friends.router)
api_router.include_router(events.router)
api_router.include_router(contributions.router)
api_router.include_router(public.router)
