from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..connection_test import ConnectionCheckResult, check_all_connections
from .contracts import ModelConnectionStatus, RevisionApplicationError
from .model_profiles import ModelProfileService, load_active_role_settings, profile_to_settings


class ModelConnectionService:
    def __init__(
        self,
        config_path: str | Path = "config/settings.env",
        *,
        model_profiles_path: str | Path = "config/model_profiles.json",
        checker: Callable[[list], list[ConnectionCheckResult]] = check_all_connections,
    ) -> None:
        self.config_path = Path(config_path)
        self.model_profiles_path = Path(model_profiles_path)
        self.checker = checker

    def check_model_connections(self) -> tuple[ModelConnectionStatus, ...]:
        settings = [
            load_active_role_settings(
                config_path=self.config_path,
                profile_path=self.model_profiles_path,
                role="WRITER",
                default_model="gpt-4.1",
            ),
            load_active_role_settings(
                config_path=self.config_path,
                profile_path=self.model_profiles_path,
                role="REVIEWER",
                default_model="gpt-4.1",
            ),
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

    def check_model_profile_connection(self, profile_id: str) -> ModelConnectionStatus:
        profiles = ModelProfileService(self.model_profiles_path).list_model_profiles()
        profile = next((item for item in profiles if item.profile_id == profile_id), None)
        if profile is None:
            raise RevisionApplicationError(f"model profile not found: {profile_id}")
        settings = profile_to_settings(profile, "PROFILE")
        result = self.checker([settings])[0]
        return ModelConnectionStatus(
            role=result.role,
            model=result.model,
            ok=result.ok,
            message=result.message,
            elapsed_seconds=result.elapsed_seconds,
        )
