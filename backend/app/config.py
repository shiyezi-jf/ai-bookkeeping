from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./app.db"

    llm_api_key: SecretStr = SecretStr("")   # 关键：用 SecretStr
    llm_base_url: str = ""
    llm_model: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,   # LLM_API_KEY ↔ llm_api_key 自动对上
        extra="ignore",
    )

    @property
    def llm_ready(self) -> bool:
        return bool(self.llm_api_key.get_secret_value())

settings = Settings()