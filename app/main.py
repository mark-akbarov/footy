from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis

from api.dependencies.docs_security import basic_http_credentials
from api.dependencies.rate_limiter import FastAPILimiter
from core.config import settings, EnvironmentEnum
from utils.redis_manager import RedisManager

from db.session import engine

from api import v1

description = """
FastAPI template project 🚀
"""
version = "v0.0.1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    redis_url = str(settings.REDIS_URL)

    redis_pool = aioredis.ConnectionPool.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True
    )
    redis_client = aioredis.Redis.from_pool(redis_pool)

    try:
        await redis_client.ping()
    except Exception as e:
        print(f"Failed to connect to Redis: {e}")
        raise

    RedisManager.set_client(redis_client)

    await FastAPILimiter.init(
        redis_client,
        enabled=settings.ENVIRONMENT != EnvironmentEnum.TEST
    )

    yield

    await redis_client.close()
    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=description,
    version=version,
    lifespan=lifespan,
    contact={
        "name": "Jorilla Abdullaev",
        "url": "https://jorilla.t.me",
        "email": "jorilla.abdullaev@protonmail.com",
    },
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(TrustedHostMiddleware)

# include routes here
app.include_router(v1.api_router)


@app.get("/openapi.json", include_in_schema=False)
async def openapi(
    _: str = Depends(basic_http_credentials)
):
    schema = get_openapi(
        title="My App | API Documentation",
        version="1.0.0",
        description="Custom API Docs",
        routes=app.routes,
    )
    return schema


@app.get("/docs", include_in_schema=False)
async def swagger_ui(
    _: str = Depends(basic_http_credentials)
):
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Swagger | API Docs",
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_ui(_: str = Depends(basic_http_credentials)):
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="ReDoc | API Docs",
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins="*",
    allow_credentials=True,
    allow_methods=["GET", "PUT", "POST", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "Accept-Language"],
)
