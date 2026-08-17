from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    miner_base_urls: str = "https://telegraph-miner-node.onrender.com"
    miner_names: str = "Telegraph Groq LPU Miner"
    miner_chat_paths: str = "/chat,/v1/chat/completions"
    miner_timeout_seconds: float = 45.0
    host: str = "0.0.0.0"
    port: int = 8080

    def base_urls(self) -> List[str]:
        return [u.strip().rstrip("/") for u in self.miner_base_urls.split(",") if u.strip()]

    def names(self) -> List[str]:
        names = [n.strip() for n in self.miner_names.split(",") if n.strip()]
        urls = self.base_urls()
        while len(names) < len(urls):
            names.append(f"miner-{len(names) + 1}")
        return names[: len(urls)]

    def chat_paths(self) -> List[str]:
        return [p.strip() for p in self.miner_chat_paths.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
