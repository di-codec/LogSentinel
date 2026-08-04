import os
import secrets
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Header, HTTPException, Request, UploadFile, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

ALLOWED_EXTENSIONS = {".log", ".txt"}
DEFAULT_MAX_UPLOAD_BYTES = 1 * 1024 * 1024
DEFAULT_MAX_LOG_LINES = 1000
DEFAULT_RATE_LIMIT_REQUESTS = 10
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60
DEFAULT_JWT_EXPIRE_HOURS = 8
DEFAULT_MAX_LOGIN_ATTEMPTS = 5
DEFAULT_LOGIN_WINDOW_SECONDS = 300

_login_attempts: dict[str, list[float]] = defaultdict(list)


def is_production() -> bool:
    return os.getenv("APP_ENV", "development").lower() == "production"


def get_cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def get_api_key() -> str | None:
    value = os.getenv("API_KEY", "").strip()
    return value or None


def get_dashboard_username() -> str | None:
    value = os.getenv("DASHBOARD_USERNAME", "").strip()
    return value or None


def get_dashboard_password() -> str | None:
    value = os.getenv("DASHBOARD_PASSWORD", "").strip()
    return value or None


def is_auth_disabled() -> bool:
    if is_production():
        return False
    return os.getenv("AUTH_DISABLED", "false").lower() == "true"


def has_dashboard_credentials() -> bool:
    return bool(get_dashboard_username() and get_dashboard_password())


def is_login_required() -> bool:
    return not is_auth_disabled()


def is_dashboard_auth_enabled() -> bool:
    return is_login_required() and has_dashboard_credentials()


def get_jwt_secret() -> str:
    return (
        os.getenv("JWT_SECRET", "").strip()
        or get_api_key()
        or "logsentinel-dev-secret-change-me"
    )


def get_jwt_expire_hours() -> int:
    return int(os.getenv("JWT_EXPIRE_HOURS", str(DEFAULT_JWT_EXPIRE_HOURS)))


def get_max_upload_bytes() -> int:
    return int(os.getenv("MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES)))


def get_max_log_lines() -> int:
    return int(os.getenv("MAX_LOG_LINES", str(DEFAULT_MAX_LOG_LINES)))


def get_rate_limit_settings() -> tuple[int, int]:
    requests = int(os.getenv("RATE_LIMIT_REQUESTS", str(DEFAULT_RATE_LIMIT_REQUESTS)))
    window = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", str(DEFAULT_RATE_LIMIT_WINDOW_SECONDS)))
    return requests, window


def validate_startup_security() -> None:
    if is_auth_disabled():
        return

    if not has_dashboard_credentials():
        raise RuntimeError(
            "DASHBOARD_USERNAME and DASHBOARD_PASSWORD must be set in .env. "
            "For local dev-only bypass, set AUTH_DISABLED=true (never use in production)."
        )

    if is_production() and not get_api_key():
        raise RuntimeError("API_KEY must be set when APP_ENV=production")


def validate_dashboard_credentials(username: str, password: str) -> bool:
    expected_user = get_dashboard_username()
    expected_pass = get_dashboard_password()

    if not expected_user or not expected_pass:
        return False

    return secrets.compare_digest(username, expected_user) and secrets.compare_digest(
        password, expected_pass
    )


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def check_login_rate_limit(client_ip: str) -> None:
    now = time.time()
    window_start = now - DEFAULT_LOGIN_WINDOW_SECONDS
    recent = [timestamp for timestamp in _login_attempts[client_ip] if timestamp > window_start]
    _login_attempts[client_ip] = recent

    if len(recent) >= DEFAULT_MAX_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )

    _login_attempts[client_ip].append(now)


def create_access_token(username: str) -> str:
    expires = datetime.now(UTC) + timedelta(hours=get_jwt_expire_hours())
    payload = {
        "sub": username,
        "exp": expires,
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm="HS256")


def verify_access_token(token: str) -> str:
    payload = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
    username = payload.get("sub")
    if not username:
        raise jwt.InvalidTokenError("Missing subject")
    return username


async def require_auth(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> None:
    if is_auth_disabled():
        return

    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        try:
            verify_access_token(token)
            return
        except jwt.InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session. Please sign in again.",
            ) from exc

    expected_api_key = get_api_key()
    if expected_api_key and x_api_key == expected_api_key:
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


def validate_upload_filename(filename: str | None) -> None:
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    lower_name = filename.lower()
    if not any(lower_name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise HTTPException(status_code=400, detail="Only .log and .txt files are allowed")


async def read_upload_text(file: UploadFile) -> str:
    validate_upload_filename(file.filename)

    content = await file.read()
    max_bytes = get_max_upload_bytes()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {max_bytes // 1024} KB",
        )

    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be valid UTF-8 text") from exc


def validate_parsed_entries(entries: list[dict]) -> None:
    if not entries:
        raise HTTPException(status_code=400, detail="No valid log lines found")

    max_lines = get_max_log_lines()
    if len(entries) > max_lines:
        raise HTTPException(
            status_code=400,
            detail=f"Too many log lines. Maximum allowed is {max_lines}",
        )


def public_error_message(fallback: str, detailed: str) -> str:
    if is_production():
        return fallback
    return detailed


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if is_production():
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int, window_seconds: int) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _client_key(self, request: Request) -> str:
        return get_client_ip(request)

    def _is_allowed(self, key: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        recent = [timestamp for timestamp in self._requests[key] if timestamp > window_start]
        self._requests[key] = recent
        if len(recent) >= self.max_requests:
            return False
        self._requests[key].append(now)
        return True

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path == "/health":
            return await call_next(request)

        if not self._is_allowed(self._client_key(request)):
            return Response(
                content='{"detail":"Too many requests. Please try again later."}',
                status_code=429,
                media_type="application/json",
            )

        return await call_next(request)
