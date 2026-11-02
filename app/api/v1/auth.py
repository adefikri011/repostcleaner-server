from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import (
    SESSION_COOKIE_NAME,
    get_authenticated_session,
    require_csrf,
    require_trusted_browser_request,
)
from app.core.security import create_csrf_token, verify_csrf_token
from app.db.session import get_db
from app.models.session import UserSession
from app.models.user import User
from app.schemas.auth import (
    ApiResponse,
    AuthData,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.services.auth_service import (
    DuplicateEmailError,
    InvalidCredentialsError,
    LoginBlockedError,
    authenticate_user,
    load_session,
    register_user,
    revoke_session,
    update_last_active,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=ApiResponse[AuthData],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_browser_request)],
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[AuthData]:
    try:
        user = register_user(
            db,
            email=str(payload.email),
            display_name=payload.display_name,
            password=payload.password,
        )
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None

    return ApiResponse(
        success=True,
        message="Account created. Sign in to continue.",
        data=AuthData(user=UserResponse.model_validate(user)),
    )


@router.post(
    "/login",
    response_model=ApiResponse[AuthData],
    dependencies=[Depends(require_trusted_browser_request)],
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> ApiResponse[AuthData]:
    client_host = request.client.host if request.client else "unknown"
    try:
        user, token = authenticate_user(
            db,
            email=str(payload.email),
            password=payload.password,
            client_host=client_host,
        )
    except LoginBlockedError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sign-in attempts. Try again in 15 minutes.",
            headers={"Retry-After": "900"},
        ) from None
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Cookie"},
        ) from None

    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.session_expire_hours * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    return ApiResponse(
        success=True,
        message="Login successful",
        data=AuthData(
            user=UserResponse.model_validate(user),
            csrf_token=create_csrf_token(token),
        ),
    )


@router.get(
    "/me",
    response_model=ApiResponse[AuthData],
)
def current_user(
    db: Session = Depends(get_db),
    authenticated: tuple[UserSession, User, str] = Depends(
        get_authenticated_session
    ),
) -> ApiResponse[AuthData]:
    user_session, user, token = authenticated
    update_last_active(db, user_session)
    return ApiResponse(
        success=True,
        message="Current user loaded",
        data=AuthData(
            user=UserResponse.model_validate(user),
            csrf_token=create_csrf_token(token),
        ),
    )


@router.post(
    "/logout",
    response_model=ApiResponse[None],
    dependencies=[Depends(require_trusted_browser_request)],
)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        csrf_token = request.headers.get("x-csrf-token", "")
        if not verify_csrf_token(token, csrf_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Request could not be verified",
            )
        revoke_session(db, token)

    settings = get_settings()
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )
    return ApiResponse(success=True, message="Logout successful", data=None)
