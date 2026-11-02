from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.auth import router as auth_router
from app.core.config import get_settings
from app.schemas.auth import ApiResponse


settings = get_settings()
app = FastAPI(
    title="Repost Cleaner API",
    description="Backend API for Repost Cleaner",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Repost-Request"],
)


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    del request
    response = ApiResponse[None](
        success=False,
        message=str(exc.detail),
        data=None,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(mode="json"),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    del request, exc
    response = ApiResponse[None](
        success=False,
        message="Invalid request data",
        data=None,
    )
    return JSONResponse(
        status_code=422,
        content=response.model_dump(mode="json"),
    )


app.include_router(auth_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "message": "Welcome to Repost Cleaner API",
        "status": "running"
    }


@app.get("/api/v1/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "repost-cleaner-api"
    }