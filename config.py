import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    data_dir: Path
    db_path: Path
    voyage_api_key: Optional[str]
    embedding_model: str
    openrouter_api_key: Optional[str]
    llm_model: str
    chunk_size: int = 1000
    chunk_overlap: int = 100
    default_limit: int = 10
    context_budget: int = 4000

    @classmethod
    def from_env(cls) -> "Config":
        data_dir = Path(os.getenv("COEUS_DATA", "~/.coeus")).expanduser()
        data_dir.mkdir(parents=True, exist_ok=True)
        load_dotenv(data_dir / ".env")

        return cls(
            data_dir=data_dir,
            db_path=data_dir / "coeus.db",
            voyage_api_key=os.getenv("VOYAGE_API_KEY"),
            embedding_model=os.getenv("COEUS_EMBED_MODEL", "voyage-3"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            llm_model=os.getenv("COEUS_LLM_MODEL", "anthropic/claude-3.5-sonnet"),
            chunk_size=int(os.getenv("COEUS_CHUNK_SIZE", "1000")),
            chunk_overlap=int(os.getenv("COEUS_CHUNK_OVERLAP", "100")),
            default_limit=int(os.getenv("COEUS_LIMIT", "10")),
            context_budget=int(os.getenv("COEUS_BUDGET", "4000")),
        )

    def is_valid(self) -> tuple[bool, list[str]]:
        errors = []

        if self.embedding_model == "voyage-3" and not self.voyage_api_key:
            errors.append("VOYAGE_API_KEY required for voyage-3 embeddings")

        return len(errors) == 0, errors


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def reset_config() -> None:
    global _config
    _config = None
