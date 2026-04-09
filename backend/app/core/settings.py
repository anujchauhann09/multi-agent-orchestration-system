from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    REDIS_URL: str

    # Google / Gemini
    GOOGLE_API_KEY: str
    GOOGLE_API_MODEL: str = "gemini-2.5-flash"
    GOOGLE_EMBEDDING_MODEL: str = "models/gemini-embedding-001"

    # GitHub
    GITHUB_TOKEN: str

    # Pinecone
    PINECONE_API_KEY: str
    PINECONE_INDEX: str

    # Agent limits
    MAX_RETRIES: int = 2
    MAX_AGENT_STEPS: int = 5

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
