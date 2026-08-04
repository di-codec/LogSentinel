from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import NotFoundError
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from azure_openai import require_env
from embedder import embed_records
from indexer import upload_records
from main import analyze_logs
from parser import parse_log_file
from search import search_similar_for_entries
from security import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    check_login_rate_limit,
    create_access_token,
    get_client_ip,
    get_cors_origins,
    get_rate_limit_settings,
    has_dashboard_credentials,
    is_auth_disabled,
    is_login_required,
    is_production,
    public_error_message,
    read_upload_text,
    require_auth,
    validate_dashboard_credentials,
    validate_parsed_entries,
    validate_startup_security,
    verify_access_token,
)

load_dotenv()

REQUIRED_ENV = [
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_KEY",
    "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
    "AZURE_SEARCH_ENDPOINT",
    "AZURE_SEARCH_KEY",
    "AZURE_SEARCH_INDEX",
]

app = FastAPI(
    title="LogSentinel API",
    docs_url=None if is_production() else "/docs",
    redoc_url=None if is_production() else "/redoc",
    openapi_url=None if is_production() else "/openapi.json",
)

rate_limit_requests, rate_limit_window = get_rate_limit_settings()
app.add_middleware(RateLimitMiddleware, max_requests=rate_limit_requests, window_seconds=rate_limit_window)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)


@app.on_event("startup")
def validate_config() -> None:
    validate_startup_security()
    missing = [name for name in REQUIRED_ENV if not require_env(name, optional=True)]
    if missing:
        raise RuntimeError(f"Missing required .env variables: {', '.join(missing)}")


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class AuthConfigResponse(BaseModel):
    login_required: bool


class AnalyzeResponse(BaseModel):
    analysis: str
    records_processed: int
    similar_patterns_found: int


@app.get("/")
def root():
    payload = {
        "service": "LogSentinel API",
        "health": "/health",
        "auth": "/auth/login",
        "analyze": "POST /analyze (upload .log file)",
    }
    if not is_production():
        payload["docs"] = "/docs"
    return payload


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/auth/config", response_model=AuthConfigResponse)
def auth_config():
    return AuthConfigResponse(login_required=is_login_required())


@app.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest, request: Request):
    if is_auth_disabled():
        raise HTTPException(status_code=403, detail="Login is disabled on this server")

    if not has_dashboard_credentials():
        raise HTTPException(
            status_code=503,
            detail="Dashboard login is not configured. Contact the administrator.",
        )

    check_login_rate_limit(get_client_ip(request))

    if not validate_dashboard_credentials(body.username, body.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(body.username)
    return LoginResponse(access_token=token, username=body.username)


@app.get("/auth/session")
def auth_session(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    token = authorization.removeprefix("Bearer ").strip()
    username = verify_access_token(token)
    return {"username": username}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    file: UploadFile = File(...),
    _: None = Depends(require_auth),
):
    log_text = await read_upload_text(file)
    entries = parse_log_file(log_text)
    validate_parsed_entries(entries)

    try:
        embedded = embed_records(entries)
        upload_records(embedded)
        similar = search_similar_for_entries(embedded, top_k=3)
        analysis = analyze_logs(log_text, embedded_entries=embedded)
    except NotFoundError as exc:
        if "DeploymentNotFound" in str(exc):
            raise HTTPException(
                status_code=503,
                detail=public_error_message(
                    "Analysis service is temporarily unavailable",
                    (
                        "Azure OpenAI deployment not found. Verify "
                        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT in .env and restart the API."
                    ),
                ),
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=public_error_message("Analysis service is temporarily unavailable", str(exc)),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail=public_error_message("Internal server error", str(exc)),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=public_error_message("Analysis service is temporarily unavailable", str(exc)),
        ) from exc

    return AnalyzeResponse(
        analysis=analysis,
        records_processed=len(entries),
        similar_patterns_found=len(similar),
    )
