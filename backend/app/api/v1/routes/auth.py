from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.security import create_access_token

router = APIRouter()
bearer_scheme = HTTPBearer()

DEMO_USERS = {
    "teacher@academix.app": {
        "id": "demo-teacher",
        "name": "Demo Teacher",
        "role": "teacher",
        "password": "password123",
    },
    "student@academix.app": {
        "id": "demo-student",
        "name": "Demo Student",
        "role": "student",
        "password": "password123",
    },
}


class LoginRequest(BaseModel):
    email: str
    password: str


class UserPublic(BaseModel):
    id: str
    name: str
    email: str
    role: str


class LoginResponse(BaseModel):
    token: str
    user: UserPublic


def _current_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UserPublic:
    settings = get_settings()
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as error:
        raise unauthorized from error

    email = payload.get("sub")
    role = payload.get("role")
    if not isinstance(email, str) or not email:
        raise unauthorized
    if not isinstance(role, str) or not role:
        role = "student"

    demo_user = DEMO_USERS.get(email.lower())
    if demo_user is not None:
        return UserPublic(
            id=demo_user["id"],
            name=demo_user["name"],
            email=email,
            role=demo_user["role"],
        )

    return UserPublic(
        id=email,
        name=email.split("@")[0].title(),
        email=email,
        role=role,
    )


def require_role(role: str):
    def _require_role(
        current_user: UserPublic = Depends(_current_user_from_token),
    ) -> UserPublic:
        if current_user.role != role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires the {role} role.",
            )
        return current_user

    return _require_role


@router.post("/auth/login", response_model=LoginResponse)
def login_user(payload: LoginRequest) -> LoginResponse:
    email = payload.email.strip().lower()
    password = payload.password

    demo_user = DEMO_USERS.get(email)
    if demo_user is not None and demo_user["password"] == password:
        token = create_access_token(subject=email, role=demo_user["role"])
        return LoginResponse(
            token=token,
            user=UserPublic(
                id=demo_user["id"],
                name=demo_user["name"],
                email=email,
                role=demo_user["role"],
            ),
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
    )


@router.get("/auth/me", response_model=UserPublic)
def get_current_user(
    current_user: UserPublic = Depends(_current_user_from_token),
) -> UserPublic:
    return current_user


@router.get("/teacher/dashboard")
def teacher_dashboard(
    current_user: UserPublic = Depends(require_role("teacher")),
    db: Session = Depends(get_db), offset: int = Query(0,ge=0), limit: int = Query(25,ge=1,le=100),
    timezone_offset_minutes: int = Query(0,ge=-840,le=840),
) -> dict:
    from app.services.dashboard import dashboard
    return dashboard(db,current_user,offset,limit,timezone_offset_minutes)


@router.get("/student/dashboard")
def student_dashboard(
    current_user: UserPublic = Depends(require_role("student")),
    db: Session = Depends(get_db), offset: int = Query(0,ge=0), limit: int = Query(25,ge=1,le=100),
    timezone_offset_minutes: int = Query(0,ge=-840,le=840),
) -> dict:
    from app.services.dashboard import dashboard
    return dashboard(db,current_user,offset,limit,timezone_offset_minutes)
