from datetime import datetime, timedelta
from typing import Optional
import random
import string

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel

from api.dependencies.database import DbSessionDep
from db.crud.user import UsersCrud
from db.tables.user import UserRole
from schemas.user import (
    CandidateRegistrationSchema,
    TeamRegistrationSchema,
    UserLoginSchema,
    OutUserSchema
)
from core.config import settings
from utils.redis_manager import redis_client
from tasks.notifications.send_email import send_email_task

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

# Security
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


class EmailVerificationSchema(BaseModel):
    email: str
    code: str


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme), db=DbSessionDep) -> OutUserSchema:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    user_crud = UsersCrud(db)
    user = await user_crud.get_by_email(email=token_data.email)
    if user is None:
        raise credentials_exception
    return OutUserSchema.model_validate(user)


async def get_current_active_user(current_user: OutUserSchema = Depends(get_current_user)) -> OutUserSchema:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@router.post("/register-candidate", response_model=OutUserSchema, status_code=status.HTTP_201_CREATED)
async def register_candidate(
    candidate_data: CandidateRegistrationSchema,
    db: DbSessionDep
):
    """Register a new candidate."""
    user_crud = UsersCrud(db)

    # Check if user already exists
    existing_user = await user_crud.get_by_email(candidate_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Hash password
    hashed_password = get_password_hash(candidate_data.password)

    # Create user data
    user_data = candidate_data.model_dump()
    user_data["hashed_password"] = hashed_password
    user_data["role"] = UserRole.CANDIDATE
    del user_data["password"]

    # Create user
    user = await user_crud.create(user_data)
    await user_crud.commit_session()

    # Send email verification
    verification_code = generate_verification_code()
    redis_key = f"email_verification:{candidate_data.email}:{user.id}"
    await redis_client.set(redis_key, verification_code, ex=300)  # 5 minutes

    # Send verification email
    email_context = {
        "first_name": candidate_data.first_name,
        "verification_code": verification_code
    }
    send_email_task.delay(
        candidate_data.email,
        "Verify Your Footy Account",
        "verification",
        email_context
    )

    return OutUserSchema.model_validate(user)


@router.post("/register-team", response_model=OutUserSchema, status_code=status.HTTP_201_CREATED)
async def register_team(
    team_data: TeamRegistrationSchema,
    db: DbSessionDep
):
    print(111111111111111111111111111111111111111111111111111)
    """Register a new team."""
    user_crud = UsersCrud(db)

    # Check if user already exists
    existing_user = await user_crud.get_by_email(team_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Hash password
    hashed_password = get_password_hash(team_data.password)

    # Create user data
    user_data = team_data.model_copy(update={
        "hashed_password": hashed_password,
        "role": UserRole.TEAM
    })
    user_dict = user_data.model_dump(exclude={"password"})

    # Create user
    user = await user_crud.create(user_dict)
    await user_crud.commit_session()

    # Send email verification
    verification_code = generate_verification_code()
    redis_key = f"email_verification:{team_data.email}:{user.id}"
    await redis_client.set(redis_key, verification_code, ex=300)  # 5 minutes

    # Send verification email
    email_context = {
        "first_name": team_data.first_name,
        "verification_code": verification_code
    }
    send_email_task.delay(
        team_data.email,
        "Verify Your Footy Account",
        "verification",
        email_context
    )

    return OutUserSchema.model_validate(user)


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db=DbSessionDep
):
    """Login user."""
    user_crud = UsersCrud(db)
    user = await user_crud.get_by_email(form_data.username)

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is not active. Please verify your email first."
        )

    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please verify your email address before logging in."
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=OutUserSchema)
async def read_users_me(current_user: OutUserSchema = Depends(get_current_active_user)):
    """Get current user information."""
    return current_user


@router.post("/resend-verification")
async def resend_verification(email: str, db: DbSessionDep):
    """Resend verification email."""
    user_crud = UsersCrud(db)
    user = await user_crud.get_by_email(email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified"
        )

    # Generate new verification code
    verification_code = generate_verification_code()
    redis_key = f"email_verification:{email}:{user.id}"
    await redis_client.set(redis_key, verification_code, ex=300)  # 5 minutes

    # Send verification email
    email_context = {
        "first_name": user.first_name,
        "verification_code": verification_code
    }
    send_email_task.delay(
        email,
        "Verify Your Footy Account",
        "verification",
        email_context
    )

    return {"message": "Verification email sent successfully"}


def generate_verification_code() -> str:
    """Generate a 6-digit verification code."""
    return ''.join(random.choices(string.digits, k=6))


@router.post("/send-email-verification")
async def send_email_verification(
    email: str,
    user_id: int,
    db: DbSessionDep
):
    """Send email verification code."""
    # Generate verification code
    verification_code = generate_verification_code()

    # Store code in Redis with 5-minute expiry
    redis_key = f"email_verification:{email}:{user_id}"
    await redis_client.set(redis_key, verification_code, ex=300)  # 5 minutes

    # Send verification email
    email_context = {
        "verification_code": verification_code
    }
    send_email_task.delay(
        email,
        "Verify Your Footy Account",
        "verification",
        email_context
    )

    return {"message": "Verification code sent successfully"}


@router.post("/verify-email")
async def verify_email(
    verification_data: EmailVerificationSchema,
    db: DbSessionDep
):
    """Verify email code and activate user."""
    user_crud = UsersCrud(db)

    # Get user by email
    user = await user_crud.get_by_email(verification_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check verification code
    redis_key = f"email_verification:{verification_data.email}:{user.id}"
    stored_code = await redis_client.get(redis_key)

    if not stored_code or stored_code != verification_data.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code"
        )

    # Verify email and activate user
    user.email_verified = True
    user.is_active = True
    await user_crud.commit_session()

    # Delete verification code
    await redis_client.delete(redis_key)

    return {"message": "Email verified successfully, account activated"}
