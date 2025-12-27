"""Configuration module for Vanna 2.0 Text-to-SQL application."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    # Azure OpenAI Configuration
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_API_VERSION: str = "2025-01-01-preview"
    AZURE_OPENAI_DEPLOYMENT_NAME: str = "gpt-5.1"
    
    # Embedding Model Configuration
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str = "text-embedding-3-large-2"
    AZURE_OPENAI_EMBEDDINGS_API_VERSION: str = "2023-05-15"
    
    # Data Source - AdventureWorksDW (PostgreSQL)
    DATA_SOURCE_HOST: str
    DATA_SOURCE_PORT: int = 5432
    DATA_SOURCE_DB: str
    DATA_SOURCE_USER: str
    DATA_SOURCE_PASSWORD: str
    
    # pgvector (Local Vector Store)
    PGVECTOR_HOST: str = "pgvector-db"
    PGVECTOR_PORT: int = 5432
    PGVECTOR_DB: str = "vanna_vectors"
    PGVECTOR_USER: str = "vanna"
    PGVECTOR_PASSWORD: str
    
    # Application Settings
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def data_source_connection_string(self) -> str:
        """Build PostgreSQL connection string for data source."""
        return (
            f"postgresql://{self.DATA_SOURCE_USER}:{self.DATA_SOURCE_PASSWORD}"
            f"@{self.DATA_SOURCE_HOST}:{self.DATA_SOURCE_PORT}/{self.DATA_SOURCE_DB}"
        )
    
    @property
    def pgvector_connection_string(self) -> str:
        """Build PostgreSQL connection string for pgvector."""
        return (
            f"postgresql://{self.PGVECTOR_USER}:{self.PGVECTOR_PASSWORD}"
            f"@{self.PGVECTOR_HOST}:{self.PGVECTOR_PORT}/{self.PGVECTOR_DB}"
        )


# Global settings instance
settings = Settings()
