import redis.asyncio as aioredis
from math import ceil
from typing import Callable, Optional, Union
from fastapi import HTTPException
from fastapi.security.utils import get_authorization_scheme_param
from starlette.requests import Request
from starlette.responses import Response
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from starlette.websockets import WebSocket


async def default_identifier(request: Union[Request, WebSocket]):
    authorization_header_value = request.cookies.get("auth_token")
    if authorization_header_value:
        _, token = get_authorization_scheme_param(authorization_header_value)
        return f"{token}:{request.scope['path']}"

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0]
    else:
        ip = request.client.host
    return f"{ip}:{request.scope['path']}"


async def http_default_callback(request: Request, response: Response, pexpire: int):
    """
    default callback when too many requests
    :param request:
    :param pexpire: The remaining milliseconds
    :param response:
    :return:
    """
    expire = ceil(pexpire / 1000)
    raise HTTPException(
        HTTP_429_TOO_MANY_REQUESTS,
        "Too Many Requests",
        headers={"Retry-After": str(expire)},
    )


async def ws_default_callback(ws: WebSocket, pexpire: int):
    """
    default callback when too many requests
    :param ws:
    :param pexpire: The remaining milliseconds
    :return:
    """
    expire = ceil(pexpire / 1000)
    raise HTTPException(
        HTTP_429_TOO_MANY_REQUESTS,
        "Too Many Requests",
        headers={"Retry-After": str(expire)},
    )


class FastAPILimiter:
    redis: Optional[aioredis.Redis] = None
    enabled: Optional[bool] = None
    prefix: Optional[str] = None
    identifier: Optional[Callable] = None
    http_callback: Optional[Callable] = None
    ws_callback: Optional[Callable] = None
    fn_name: Optional[str] = None

    @classmethod
    async def init(
        cls,
        redis: aioredis.Redis,
        *,
        fn_name: str = "check_rate_limit",
        enabled: bool = True,
        prefix: str = "fastapi-limiter",
        identifier: Callable = default_identifier,
        http_callback: Callable = http_default_callback,
        ws_callback: Callable = ws_default_callback,
    ) -> None:
        cls.redis = redis
        cls.enabled = enabled
        cls.prefix = prefix
        cls.identifier = identifier
        cls.http_callback = http_callback
        cls.ws_callback = ws_callback
        cls.fn_name = fn_name

    @classmethod
    async def close(cls) -> None:
        await cls.redis.close()
