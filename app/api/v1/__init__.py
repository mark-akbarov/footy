from fastapi import APIRouter
from core.config import settings

# from .blog_post import router as blog_post_router
from .authentication import router as auth_router
from .vacancy import router as vacancy_router
from .application import router as application_router
from .membership import router as membership_router
from .messaging import router as messaging_router
from .admin import router as admin_router
from .candidates import router as candidates_router
from .payment import router as payment_router

api_router = APIRouter(prefix=settings.API_V1_STR)
api_router.include_router(auth_router)
api_router.include_router(vacancy_router)
api_router.include_router(application_router)
api_router.include_router(membership_router)
api_router.include_router(payment_router)
api_router.include_router(messaging_router)
api_router.include_router(admin_router)
api_router.include_router(candidates_router)
