from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class ModelSettings:
    role: str
    api_key: str
    base_url: str
    model: str
    enable_search: bool = False
    model_family: str = "unknown"
    vision: bool = False
    function_calling: bool = False
    json_output: bool = False
    structured_output: bool = False
    timeout_seconds: int = 60
    max_retries: int = 1


def load_env_file(path: str | Path) -> dict[str, str]:
    config_path = Path(path)
    if not config_path.exists():
        return {}

    loaded: dict[str, str] = {}
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or not value:
            continue
        loaded[key] = value
        os.environ.setdefault(key, value)
    return loaded


def merged_env_values(loaded: dict[str, str]) -> dict[str, str]:
    values = dict(loaded)
    values.update(os.environ)
    return values


def load_role_settings(
    values: dict[str, str],
    role: str,
    *,
    default_model: str,
) -> ModelSettings:
    role = role.upper()
    api_key = values.get(f"{role}_API_KEY") or values.get("OPENAI_API_KEY") or ""
    base_url = values.get(f"{role}_BASE_URL") or values.get("OPENAI_BASE_URL") or ""
    model = values.get(f"{role}_MODEL") or default_model
    return ModelSettings(
        role=role,
        api_key=api_key,
        base_url=base_url,
        model=model,
        enable_search=_env_bool(values, f"{role}_ENABLE_SEARCH", fallback_key="OPENAI_ENABLE_SEARCH", default=False),
        model_family=values.get(f"{role}_MODEL_FAMILY") or values.get("OPENAI_MODEL_FAMILY") or "unknown",
        vision=_env_bool(values, f"{role}_VISION", fallback_key="OPENAI_VISION", default=False),
        function_calling=_env_bool(
            values,
            f"{role}_FUNCTION_CALLING",
            fallback_key="OPENAI_FUNCTION_CALLING",
            default=False,
        ),
        json_output=_env_bool(values, f"{role}_JSON_OUTPUT", fallback_key="OPENAI_JSON_OUTPUT", default=False),
        structured_output=_env_bool(
            values,
            f"{role}_STRUCTURED_OUTPUT",
            fallback_key="OPENAI_STRUCTURED_OUTPUT",
            default=False,
        ),
        timeout_seconds=_env_int(values, f"{role}_TIMEOUT_SECONDS", fallback_key="OPENAI_TIMEOUT_SECONDS", default=60),
        max_retries=_env_int(values, f"{role}_MAX_RETRIES", fallback_key="OPENAI_MAX_RETRIES", default=1),
    )


def _env_bool(
    values: dict[str, str],
    key: str,
    *,
    fallback_key: str,
    default: bool,
) -> bool:
    raw = values.get(key)
    if raw is None:
        raw = values.get(fallback_key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(
    values: dict[str, str],
    key: str,
    *,
    fallback_key: str,
    default: int,
) -> int:
    raw = values.get(key)
    if raw is None:
        raw = values.get(fallback_key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def read_optional_text(path: str | Path, default: str) -> str:
    text_path = Path(path)
    if not text_path.exists():
        return default
    text = text_path.read_text(encoding="utf-8").strip()
    return text or default
