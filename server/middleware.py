from __future__ import annotations

from collections import defaultdict

import logging
import re
import time
from typing import Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import JWTError, jwt

from config import settings

logger = logging.getLogger("repopress")

# Rate limiting state
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
LOGIN_RATE_LIMIT_MAX = 10
LOGIN_RATE_LIMIT_WINDOW = 60  # seconds

# Paths that bypass the anti-scraping checks (internal / infra).
_ANTI_SCRAPE_EXEMPT = (
    "/api/health",
    "/api/auth/check-auth",
    "/robots.txt",
    "/docs",
    "/openapi.json",
    "/redoc",
)

# Search-engine crawlers and common scraper/script user agents.
DEFAULT_BOT_UA = (
    "googlebot|google-inspectiontool|storebot-google|bingbot|bingpreview|msnbot|"
    "baiduspider|sogou|360spider|haosouspider|yisouspider|shenmaspider|bytespider|"
    "yandex|duckduckbot|slurp|applebot|petalbot|exabot|ahrefsbot|semrushbot|mj12bot|"
    "dotbot|dataforseo|blexbot|megaindex|serpstatbot|zoominfobot|"
    "gptbot|ccbot|claudebot|anthropic-ai|perplexitybot|youbot|omgili|imagesiftbot|"
    "scrapy|python-requests|python-urllib|httpx|aiohttp|wget|curl|java/|"
    "go-http-client|okhttp|libwww|mechanize|phantomjs|headlesschrome|"
    "puppeteer|playwright|httpclient|node-fetch|axios|postmanruntime|insomnia|"
    "zgrab|masscan|nmap|nuclei"
)

_bot_pattern: Optional[re.Pattern] = None
_bot_pattern_source: Optional[str] = None


def _bot_regex() -> Optional[re.Pattern]:
    """Compile (and cache) the bot user-agent regex."""
    global _bot_pattern, _bot_pattern_source
    source = settings.bot_user_agents or DEFAULT_BOT_UA
    if _bot_pattern is None or _bot_pattern_source != source:
        _bot_pattern = re.compile(source, re.IGNORECASE) if source else None
        _bot_pattern_source = source
    return _bot_pattern


def _client_ip(request: Request) -> str:
    """Real client IP, honouring X-Forwarded-For from the reverse proxy."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limited(key: str, limit: int, window: int) -> bool:
    """Sliding-window rate check. Records the hit and returns True if over limit."""
    now = time.time()
    window_start = now - window
    timestamps = _rate_limit_store[key]
    timestamps[:] = [t for t in timestamps if t > window_start]
    if len(timestamps) >= limit:
        return True
    timestamps.append(now)
    return False


async def _verify_jwt(request: Request) -> dict | None:
    """Verify JWT from the Authorization header or the auth cookie. Returns payload dict or None."""
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get("repopress_token")
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None


class AntiScrapeMiddleware:
    """Strict anti-scraping: block crawler/scraper user agents, rate-limit the API,
    and add hardening response headers."""

    SECURITY_HEADERS = [
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"no-referrer"),
        (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
    ]

    def __init__(self, app: FastAPI):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path

        if not path.startswith(_ANTI_SCRAPE_EXEMPT):
            # 1) Block crawlers / scrapers by user agent.
            if settings.block_bots:
                user_agent = request.headers.get("user-agent", "")
                pattern = _bot_regex()
                if pattern is not None and (not user_agent.strip() or pattern.search(user_agent)):
                    logger.warning("Blocked bot UA %r on %s", user_agent, path)
                    response = JSONResponse(status_code=403, content={"detail": "Forbidden"})
                    await response(scope, receive, send)
                    return

            # 2) Rate limit the API per client IP.
            if path.startswith("/api/"):
                ip = _client_ip(request)
                if _rate_limited(f"api:{ip}", settings.rate_limit_requests, settings.rate_limit_window):
                    logger.warning("Rate limited IP %s on %s", ip, path)
                    response = JSONResponse(
                        status_code=429,
                        content={"detail": "Too many requests. Slow down."},
                        headers={"Retry-After": str(settings.rate_limit_window)},
                    )
                    await response(scope, receive, send)
                    return

        async def _send(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.extend(self.SECURITY_HEADERS)
            await send(message)

        await self.app(scope, receive, _send)


class RateLimitMiddleware:
    """Rate limiting middleware applied selectively to login endpoint."""

    def __init__(self, app: FastAPI):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        if request.url.path == "/api/auth/login" and request.method == "POST":
            ip = _client_ip(request)
            if _rate_limited(f"login:{ip}", LOGIN_RATE_LIMIT_MAX, LOGIN_RATE_LIMIT_WINDOW):
                response = JSONResponse(
                    status_code=429,
                    content={"detail": "Too many login attempts. Try again later."},
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


class RequestLoggingMiddleware:
    """Middleware to log all requests."""

    def __init__(self, app: FastAPI):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.time()
        request = Request(scope, receive)

        async def _send(message):
            if message["type"] == "http.response.start":
                elapsed = time.time() - start
                logger.info(
                    "%s %s -> %s (%.2fms)",
                    request.method,
                    request.url.path,
                    message["status"],
                    elapsed * 1000,
                )
            await send(message)

        await self.app(scope, receive, _send)


class JWTAuthMiddleware:
    """Extract JWT and attach user info to request.state.user."""

    def __init__(self, app: FastAPI):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = request.url.path

        # Skip auth for login, docs/openapi, and static
        public_paths = [
            "/api/auth/login",
            "/api/auth/logout",
            "/api/auth/check-auth",
            "/api/health",
            "/robots.txt",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]
        if any(path.startswith(p) for p in public_paths):
            await self.app(scope, receive, send)
            return

        payload = await _verify_jwt(request)
        if payload is None and path.startswith("/api/"):
            response = JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
            )
            await response(scope, receive, send)
            return

        # Store user info in scope for later use
        if payload:
            scope["user"] = {
                "id": payload.get("sub"),
                "username": payload.get("username"),
            }

        await self.app(scope, receive, send)


def setup_middleware(app: FastAPI):
    """Configure all middleware on the FastAPI app.

    Starlette applies middleware in reverse order of registration (the last
    added runs first), so AntiScrapeMiddleware is added last to run outermost.
    """
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RateLimitMiddleware)  # type: ignore[arg-type]
    app.add_middleware(JWTAuthMiddleware)  # type: ignore[arg-type]
    app.add_middleware(RequestLoggingMiddleware)  # type: ignore[arg-type]
    app.add_middleware(AntiScrapeMiddleware)  # type: ignore[arg-type]
