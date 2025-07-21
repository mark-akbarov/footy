from fastapi import Depends, HTTPException
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from fastapi.security import OAuth2PasswordBearer

from api.dependencies.database import get_db_session
from core.config import settings
from db.crud.user import UsersCrud
from schemas.user import OutUserSchema

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db_session)
) -> OutUserSchema:
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
    except JWTError:
        raise credentials_exception

    user_crud = UsersCrud(db)
    user = await user_crud.get_by_email(email=email)
    if user is None:
        raise credentials_exception
    return OutUserSchema.model_validate(user)


async def get_current_active_user(current_user: OutUserSchema = Depends(get_current_user)) -> OutUserSchema:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
