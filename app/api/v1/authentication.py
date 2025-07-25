import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Optional, Annotated
import random
import string

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db_session, DbSessionDep
from api.dependencies.user import get_current_active_user, get_current_user
from api.v1.application import require_team_role
from api.v1.membership import MEMBERSHIP_PRICES
from db.crud.membership import MembershipCrud
from db.crud.user import UsersCrud
from db.tables.membership import MembershipStatus, MembershipPlan
from db.tables.user import UserRole
from schemas.user import (
    CandidateRegistrationSchema,
    TeamRegistrationSchema,
    OutUserSchema,
    UpdateUserSchema,
    ResetPasswordSchema,
    ChangePasswordSchema,
)
from core.config import settings
from utils.redis_manager import RedisManager, RedisCacheDep
from tasks.notifications.send_email import send_email_task
from utils.s3 import delete_file_from_s3, upload_cv_to_s3, generate_presigned_url

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

# Security
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Token(BaseModel):
    access_token: str
    token_type: str


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


GetUserDep = Annotated[OutUserSchema, Depends(get_current_user)]

GetActiveUserDep = Annotated[OutUserSchema, Depends(get_current_active_user)]


@router.post("/register-candidate", response_model=OutUserSchema, status_code=status.HTTP_201_CREATED)
async def register_candidate(
    candidate_data: CandidateRegistrationSchema,
    db: AsyncSession = Depends(get_db_session)
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

    # Create user data from the schema
    user_data = candidate_data.model_dump()
    user_data["hashed_password"] = hashed_password
    del user_data["password"]

    try:
        # Create user but don't commit yet
        user = await user_crud.create(user_data)

        membership_crud = MembershipCrud(db)
        membership_data = {
            "user_id": user.id,
            "plan_type": MembershipPlan.BASIC.value,  # ✅ .value returns 'basic'
            "status": MembershipStatus.PENDING.value,  # ✅ 'pending'
            "price": MEMBERSHIP_PRICES[MembershipPlan.BASIC],
            "start_date": datetime.utcnow(),
            "renewal_date": datetime.utcnow() + timedelta(days=30),
        }

        await membership_crud.create(membership_data)

        # Commit both user and membership together
        await membership_crud.commit_session()

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Failed to register candidate.") from e

    # Send email verification
    verification_code = generate_verification_code()
    redis_key = f"email_verification:{candidate_data.email}:{user.id}"
    await RedisManager.set(redis_key, verification_code, ex=300)  # 5 minutes

    send_email_task.delay(
        to_email=candidate_data.email,
        subject="Verify Your Footy Account",
        template="verification",
        context={
            "first_name": candidate_data.first_name,
            "verification_code": verification_code
        }
    )

    return OutUserSchema.model_validate(user)


@router.post("/register-team", response_model=OutUserSchema, status_code=status.HTTP_201_CREATED)
async def register_team(
    team_data: TeamRegistrationSchema,
    db: AsyncSession = Depends(get_db_session),
):
    """Register a new team."""
    user_crud = UsersCrud(db)

    # Check if user already exists
    existing_user = await user_crud.get_by_email(team_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Ensure password is provided
    if not team_data.password or team_data.password.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required",
        )

    # Debug password before hashing
    print(f"Original password: {team_data.password}")

    hashed_password = get_password_hash(team_data.password)

    # Create user data from the schema
    user_data = team_data.model_dump()
    user_data["hashed_password"] = hashed_password
    del user_data["password"]

    # Debug hashed password
    print(f"Hashed password: {hashed_password}")

    if not hashed_password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password hashing failed.",
        )

    print("!!!!!! DEBUG: Data before creating team:", user_data)  # DEBUG STATEMENT
    print(f"User data being inserted: {user_data}")

    # Create user
    user = await user_crud.create(user_data)
    await user_crud.commit_session()

    # Send email verification
    verification_code = generate_verification_code()
    redis_key = f"email_verification:{team_data.email}:{user.id}"
    await RedisManager.set(redis_key, verification_code, ex=300)  # 5 minutes

    send_email_task.delay(
        to_email=user.email,
        subject="Verify Your Footy Account",
        template="verification",
        context={
            "first_name": user.first_name,
            "verification_code": verification_code,
        },
    )

    return OutUserSchema.model_validate(user)


@router.post("/login", response_model=Token)
async def login(
    db: DbSessionDep,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """Login user with email and password."""
    user_crud = UsersCrud(db)
    user = await user_crud.get_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is not active. Please verify your email first."
        )

    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please verify your email address before logging in."
        )

    # For teams, check if they are approved
    if user.role == UserRole.TEAM and not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your team account is pending approval."
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


@router.patch("/profile", response_model=OutUserSchema)
async def update_user_profile(
    current_user: GetActiveUserDep,
    profile_data: UpdateUserSchema,
    db_session: DbSessionDep
):
    users_crud = UsersCrud(db_session=db_session)
    await users_crud.update_by_id(current_user.id, profile_data)
    await users_crud.commit_session()
    result = await users_crud.get_by_id(current_user.id)
    return result


@router.post("/reset-password", )
async def reset_password_endpoint(
    current_user: GetActiveUserDep,
    db_session: DbSessionDep,
    cache: RedisCacheDep
):
    users_crud = UsersCrud(db_session)
    user = await users_crud.get_by_id(current_user.id)
    code = generate_verification_code()
    generated_hash = jwt.encode(
        {"code": code, "email": user.email},
        key=settings.RESET_PASSWORD_SECRET,
        algorithm="HS512"
    )
    reset_link = f"settings.BASE_URL/v1/auth/verify-otp/?info={generated_hash}"
    cache.setex(user.email, settings.REDIS_TTL, code)
    send_email_task.apply_async(kwargs={
        "to_email": user.email,
        "subject": "Reset Your Password",
        "template": "reset_password",
        "context": {
            "email": user.email,
            "reset_link": reset_link,
        }
    }
    )
    return


@router.post("/verify-otp", )
async def verify_otp_password_endpoint(
    cache: RedisCacheDep,
    info_hash: str
):
    try:
        data = jwt.decode(
            info_hash,
            key=settings.RESET_PASSWORD_SECRET,
            algorithm="HS512"
        )
    except Exception as exc:
        raise exc

    email = data['email']
    verification_code = data['code']
    code = cache.get(email)

    if verification_code != code:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")

    return {"success": True}


@router.post("/change-password", )
async def change_password_endpoint(
    db_session: DbSessionDep,
    current_user: GetActiveUserDep,
    payload: ChangePasswordSchema,
):
    if payload.new_password != payload.new_password_repeated:
        raise HTTPException(status_code=400, detail="Password don't match")

    try:
        users_crud = UsersCrud(db_session)
        hashed_password = get_password_hash(password=payload.new_password)
        await users_crud.update_by_id(current_user.id, {'hashed_password': hashed_password})
        await users_crud.commit_session()
        return {"success": True}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=exc)


def generate_verification_code() -> str:
    """Generate a 6-digit verification code."""
    return ''.join(random.choices(string.digits, k=6))


@router.post("/verify-email")
async def verify_email(
    email: str,
    code: int,
    db: AsyncSession = Depends(get_db_session)
):
    """Verify email code and activate user."""
    user_crud = UsersCrud(db)

    # Get user by email
    user = await user_crud.get_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check verification code
    redis_key = f"email_verification:{email}:{user.id}"
    stored_code = await RedisManager.get(redis_key)
    print(stored_code)

    if not stored_code or stored_code != code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code"
        )

    # Verify email and activate user
    user.email_verified = True
    user.is_active = True
    await user_crud.commit_session()

    # Delete verification code
    await RedisManager.delete(redis_key)

    return {"message": "Email verified successfully, account activated"}


@router.post("/upload-logo")
async def upload_logo(
    db: AsyncSession = Depends(get_db_session),
    current_user: OutUserSchema = Depends(require_team_role),
    file: UploadFile = File(...)
):
    user_crud = UsersCrud(db)

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file uploaded"
        )

    allowed_extensions = ['.png', '.jpg', '.jpeg', '.webp']
    file_extension = os.path.splitext(file.filename)[1].lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files (PNG, JPG, JPEG, WEBP) are allowed"
        )

    content = await file.read()

    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds {settings.MAX_FILE_SIZE // (1024 * 1024)}MB limit"
        )

    user = await user_crud.get_model_by_id(current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Delete previous logo if exists
    if user.logo_file_path:
        try:
            delete_file_from_s3(user.logo_file_path)
        except Exception as e:
            print(f"Warning: Failed to delete old logo: {e}")

    # Upload new logo
    try:
        s3_key = upload_cv_to_s3(
            file_obj=BytesIO(content),
            filename=file.filename,
            content_type=file.content_type,
            folder="logos"
        )
        user.logo_file_path = s3_key
        await user_crud.commit_session()
    except Exception as e:
        print(f"Error uploading logo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing file"
        )

    download_url = generate_presigned_url(s3_key)

    return {
        "message": "Logo uploaded successfully",
        "filename": file.filename,
        "file_size": len(content),
        "file_path": s3_key,
        "download_url": download_url
    }
