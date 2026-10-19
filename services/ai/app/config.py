"""Runtime configuration (environment variables prefixed ``AI_``)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_", env_file=".env", extra="ignore")

    # Bearer token the core API presents; this service is internal and never exposed publicly.
    service_token: SecretStr = Field(min_length=24)
    # Models prepared by fetch_models.py (one directory per capability, each with manifest.json).
    models_dir: Path = Path("/models")
    device: Literal["auto", "cpu", "cuda"] = "auto"
    # int8 on CPU, float16 on GPU when "auto".
    compute_type: str = "auto"
    cpu_threads: int = 0

    # Media are read through short-lived pre-signed links built by the API; only this prefix is accepted.
    media_url_prefix: str = "http://seaweedfs:8333/"
    max_media_bytes: int = 300 * 1024 * 1024
    max_audio_s: float = 600.0

    whisper_beam_size: int = 5
    # Vocabulary hint for Tunisian Arabic and emergency terms (improves spelling of dialect words).
    whisper_prompt_ar: str = (
        "بلاغ طوارئ في تونس: حريق، دخان، نار، فيضان، غرق، حادث مرور، "
        "كرهبة، برشا، فما، عالقين، مجروحين، الحماية المدنية."
    )

    ollama_url: str = "http://ollama:11434"
    llm_model: str = "qwen3:8b"
    llm_timeout_s: float = 120.0
    llm_num_ctx: int = 4096

    # Concurrent requests per model (inference is CPU/GPU bound).
    concurrency: int = 1
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
