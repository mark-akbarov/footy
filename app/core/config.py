import json
import os
from enum import Enum
from functools import lru_cache
from typing import Optional, Set, List

from pydantic import AnyHttpUrl, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvironmentEnum(str, Enum):
    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOP = "develop"
    TEST = "test"


class GlobalSettings(BaseSettings):
    PROJECT_NAME: str = "FastAPI Template"
    API_V1_STR: str = "/v1"

    DOCS_USERNAME: str = "admin"
    DOCS_PASSWORD: str = "admin"

    TRUSTED_HOSTS: Set[str] = {"app", "localhost", "0.0.0.0", "127.0.0.1"}
    BACKEND_CORS_ORIGINS: List[str] = []

    ENVIRONMENT: EnvironmentEnum
    DEBUG: bool = True

    DATABASE_URL: Optional[PostgresDsn] = None
    DB_ECHO_LOG: bool = True

    REDIS_URL: Optional[RedisDsn] = None

    BREVO_API_KEY: str
    MAIL_SMTP_PORT: str
    MAIL_FROM: str
    MAIL_FROM_NAME: str

    TWILIO_ACCOUNT_SID: str = ''
    TWILIO_AUTH_TOKEN: str = ''
    TWILIO_MESSAGING_SERVICE_SID: str = ''

    # JWT Configuration
    JWT_SECRET_KEY: str = ''
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Stripe Configuration
    STRIPE_PUBLIC_KEY: str = ''
    STRIPE_SECRET_KEY: str = ''
    STRIPE_WEBHOOK_SECRET: str = ''

    # File Upload Configuration
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB

    @property
    def async_database_url(self) -> Optional[str]:
        return (
            str(self.DATABASE_URL).replace("postgresql://", "postgresql+asyncpg://")
            if self.DATABASE_URL
            else str(self.DATABASE_URL)
        )

    @property
    def cors_origins(self):
        if isinstance(self.BACKEND_CORS_ORIGINS, str):
            return json.loads(self.BACKEND_CORS_ORIGINS)
        return self.BACKEND_CORS_ORIGINS

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True)


class TestSettings(GlobalSettings):
    DEBUG: bool = True
    ENVIRONMENT: EnvironmentEnum = EnvironmentEnum.TEST


class DevelopSettings(GlobalSettings):
    DEBUG: bool = True
    ENVIRONMENT: EnvironmentEnum = EnvironmentEnum.DEVELOP


class StagingSettings(GlobalSettings):
    DEBUG: bool = False
    ENVIRONMENT: EnvironmentEnum = EnvironmentEnum.STAGING


class ProductionSettings(GlobalSettings):
    DEBUG: bool = False
    ENVIRONMENT: EnvironmentEnum = EnvironmentEnum.PRODUCTION


class FactoryConfig:
    def __init__(self, environment: Optional[str]):
        self.environment = environment

    def __call__(self) -> GlobalSettings:
        match self.environment:
            case EnvironmentEnum.PRODUCTION:
                return ProductionSettings()
            case EnvironmentEnum.STAGING:
                return StagingSettings()
            case EnvironmentEnum.TEST:
                return TestSettings()
            case _:
                return DevelopSettings()


@lru_cache()
def get_configuration() -> GlobalSettings:
    return FactoryConfig(os.environ.get("ENVIRONMENT"))()


settings = get_configuration()
