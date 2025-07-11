from typing import Annotated, Callable, Optional

from pydantic import Field
from starlette.requests import Request
from starlette.responses import Response
from starlette.websockets import WebSocket

from api.dependencies.rate_limiter import FastAPILimiter


class RateLimiter:
    def __init__(
        self,
        times: Annotated[int, Field(ge=0)] = 1,
        milliseconds: Annotated[int, Field(ge=-1)] = 0,
        seconds: Annotated[int, Field(ge=-1)] = 0,
        minutes: Annotated[int, Field(ge=-1)] = 0,
        hours: Annotated[int, Field(ge=-1)] = 0,
        identifier: Optional[Callable] = None,
        callback: Optional[Callable] = None,
    ):
        self.times = times
        self.milliseconds = (
            milliseconds + 1000 * seconds + 60000 * minutes + 3600000 * hours
        )
        self.identifier = identifier
        self.callback = callback

    async def _check(self, key):
        redis = FastAPILimiter.redis
        pexpire = await redis.fcall(
            FastAPILimiter.fn_name,
            1,
            key,
            str(self.times),
            str(self.milliseconds),
        )
        return pexpire

    async def __call__(self, request: Request, response: Response):
        if not FastAPILimiter.enabled:
            return

        if not FastAPILimiter.redis:
            raise Exception(
                "You must call FastAPILimiter.init in startup event of fastapi!"
            )
        route_index = 0
        dep_index = 0
        for i, route in enumerate(request.app.routes):
            if route.path == request.scope["path"] and request.method in route.methods:
                route_index = i
                for j, dependency in enumerate(route.dependencies):
                    if self is dependency.dependency:
                        dep_index = j
                        break

        # moved here because constructor run before app startup
        identifier = self.identifier or FastAPILimiter.identifier
        callback = self.callback or FastAPILimiter.http_callback
        rate_key = await identifier(request)
        key = f"{FastAPILimiter.prefix}:{rate_key}:{route_index}:{dep_index}"
        pexpire = await self._check(key)
        if pexpire != 0:
            return await callback(request, response, pexpire)


class WebSocketRateLimiter(RateLimiter):
    async def __call__(self, ws: WebSocket, context_key=""):
        if not FastAPILimiter.redis:
            raise Exception(
                "You must call FastAPILimiter.init in startup event of fastapi!"
            )
        identifier = self.identifier or FastAPILimiter.identifier
        rate_key = await identifier(ws)
        key = f"{FastAPILimiter.prefix}:ws:{rate_key}:{context_key}"
        pexpire = await self._check(key)
        callback = self.callback or FastAPILimiter.ws_callback
        if pexpire != 0:
            return await callback(ws, pexpire)
