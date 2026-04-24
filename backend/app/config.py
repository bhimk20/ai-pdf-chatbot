from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    google_api_key: str = Field(alias="GOOGLE_API_KEY")
    supabase_url: str = Field(alias="SUPABASE_URL")
    supabase_service_role_key: str = Field(alias="SUPABASE_SERVICE_ROLE_KEY")
    gemini_chat_model: str = Field(
        default="gemini-2.5-flash",
        alias="GEMINI_CHAT_MODEL",
    )
    gemini_embedding_model: str = Field(
        default="gemini-embedding-001",
        alias="GEMINI_EMBEDDING_MODEL",
    )
    gemini_embedding_dimensions: int = Field(
        default=3072,
        alias="GEMINI_EMBEDDING_DIMENSIONS",
    )
    retrieval_k: int = Field(default=5, alias="RETRIEVAL_K")
    chunk_size: int = Field(default=1500, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=250, alias="CHUNK_OVERLAP")
    max_files: int = Field(default=5, alias="MAX_FILES")
    max_file_size_mb: int = Field(default=10, alias="MAX_FILE_SIZE_MB")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
