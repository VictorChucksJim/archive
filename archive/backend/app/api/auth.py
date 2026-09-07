from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.api.deps import COOKIE_NAME, client_ip, get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import UserLogin, UserOut, UserRegister
from app.services.audit import log_action

settings = get_settings()
router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

COOKIE_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
IS_PROD = settings.APP_ENV == "production"


def _set_session_cookie(response: Response, user_id: str) -> None:
    token = create_access_token(subject=user_id)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=IS_PROD,
        samesite="lax",
        path="/",
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.AUTH_RATE_LIMIT)
def register(request: Request, payload: UserRegister, response: Response, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        # Do not reveal whether the account exists beyond a generic message.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Registration failed")

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        quota_bytes=settings.DEFAULT_QUOTA_BYTES,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    _set_session_cookie(response, str(user.id))
    log_action(db, user.id, "REGISTER", "user", str(user.id), client_ip(request), request.headers.get("user-agent"))
    return user


@router.post("/login", response_model=UserOut)
@limiter.limit(settings.AUTH_RATE_LIMIT)
def login(request: Request, payload: UserLogin, response: Response, db: Session = Depends(get_db)):
    generic_error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise generic_error
    if not user.is_active:
        raise generic_error

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    _set_session_cookie(response, str(user.id))
    log_action(db, user.id, "LOGIN", "user", str(user.id), client_ip(request), request.headers.get("user-agent"))
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    response.delete_cookie(COOKIE_NAME, path="/")
    log_action(db, user.id, "LOGOUT", "user", str(user.id), client_ip(request), request.headers.get("user-agent"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
