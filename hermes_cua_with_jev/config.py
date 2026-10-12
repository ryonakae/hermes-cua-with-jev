from pathlib import Path
import yaml
from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    driver_binary: str = "cua-driver"
    driver_socket: str | None = None
    model: str = Field(default="jev-latest", min_length=1)


def load_settings(home):
    path = Path(home) / 'plugins/hermes-cua-with-jev/config.yaml'
    return Settings.model_validate(yaml.safe_load(path.read_text()) or {}) if path.exists() else Settings()
