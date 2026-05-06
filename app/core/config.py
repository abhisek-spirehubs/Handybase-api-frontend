from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    # --------------------------------------------------
    # Application
    # --------------------------------------------------
    APP_NAME: str = "Handybase API"
    ENV: str = Field(default="local", env="ENV")
    DEBUG: bool = Field(default=True, env="DEBUG")
    API_V1_STR: str = "/api/v1"

    # --------------------------------------------------
    # MongoDB
    # --------------------------------------------------
    MONGO_URI: str = Field(..., env="MONGO_URI")
    DATABASE_NAME: str = Field(..., env="DATABASE_NAME")

# --------------------------------------------------
    # Redis Configuration
    # --------------------------------------------------
    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    REDIS_DB: int = Field(default=0, env="REDIS_DB")
    REDIS_PASSWORD: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")
    
    @property
    def redis_url(self) -> str:
        if self.REDIS_URL:
            return self.REDIS_URL
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    

    # --------------------------------------------------
    # JWT Security
    # --------------------------------------------------
    JWT_SECRET: str = Field(..., env="JWT_SECRET")
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60,
        env="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    # --------------------------------------------------
    # CORS
    # --------------------------------------------------
    CORS_ORIGINS: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "https://app.handybase.com",
        ],
        env="CORS_ORIGINS",
    )

    # --------------------------------------------------
    # File Uploads
    # --------------------------------------------------
    ENABLE_UPLOADS: bool = Field(default=False, env="ENABLE_UPLOADS")
    UPLOAD_DIR: str = Field(default="uploads", env="UPLOAD_DIR")


    # --------------------------------------------------
    # Logging
    # --------------------------------------------------
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FILE_PATH: str = Field(default="logs/app.log", env="LOG_FILE_PATH")

        # Email
    SMTP_HOST: str = Field(..., env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USER: str = Field(..., env="SMTP_USER")
    SMTP_PASSWORD: str = Field(..., env="SMTP_PASSWORD")
    SMTP_FROM: str = Field(..., env="SMTP_FROM")


    # --------------------------------------------------
    # Firebase
    # --------------------------------------------------
    FIREBASE_CREDENTIALS_PATH: str = Field(
        default="firebase-credentials.json",
        env="FIREBASE_CREDENTIALS_PATH",
    )

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
