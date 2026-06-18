from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..config import load_env_file, load_role_settings, merged_env_values
from ..connection_test import ConnectionCheckResult, check_all_connections
from .contracts import ModelConnectionStatus


class ModelConnectionService:
    def __init__(
        self,
        config_path: str | Path = "config/settings.env",
        *,
        checker: Callable[[list], list[ConnectionCheckResult]] = check_all_connections,
    ) -> None:
        self.config_path = Path(config_path)
        self.checker = checker

    def check_model_connections(self) -> tuple[ModelConnectionStatus, ...]:
        loaded = load_env_file(self.config_path)
        values = merged_env_values(loaded)
        settings = [
            load_role_settings(values, "WRITER", default_model="gpt-4.1"),
            load_role_settings(values, "REVIEWER", default_model="gpt-4.1"),
        ]
        return tuple(
            ModelConnectionStatus(
                role=result.role,
                model=result.model,
                ok=result.ok,
                message=result.message,
                elapsed_seconds=result.elapsed_seconds,
            )
            for result in self.checker(settings)
        )
