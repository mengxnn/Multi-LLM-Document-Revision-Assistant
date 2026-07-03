from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..config import ModelSettings, load_env_file, load_role_settings, merged_env_values
from .contracts import (
    ActiveModelProfile,
    ModelProfile,
    ModelProfileRequest,
    RevisionApplicationError,
)


VALID_ROLES = {"WRITER", "REVIEWER"}


class ModelProfileService:
    def __init__(self, profile_path: str | Path = "config/model_profiles.json") -> None:
        self.profile_path = Path(profile_path)

    def list_model_profiles(self) -> tuple[ModelProfile, ...]:
        data = self._read()
        profiles = [self._profile_from_dict(value) for value in data["profiles"].values()]
        profiles.sort(key=lambda item: (item.provider, item.name, item.profile_id))
        return tuple(profiles)

    def save_model_profile(self, request: ModelProfileRequest) -> ModelProfile:
        self._validate_request(request)
        data = self._read()
        profile = ModelProfile(**asdict(request))
        data["profiles"][profile.profile_id] = asdict(profile)
        self._write(data)
        return profile

    def delete_model_profile(self, profile_id: str) -> bool:
        data = self._read()
        if profile_id not in data["profiles"]:
            return False
        del data["profiles"][profile_id]
        data["active"] = {
            role: active_profile_id
            for role, active_profile_id in data["active"].items()
            if active_profile_id != profile_id
        }
        self._write(data)
        return True

    def activate_model_profile(self, role: str, profile_id: str) -> ActiveModelProfile:
        role = self._normalize_role(role)
        data = self._read()
        raw_profile = data["profiles"].get(profile_id)
        if raw_profile is None:
            raise RevisionApplicationError(f"model profile not found: {profile_id}")
        data["active"][role] = profile_id
        self._write(data)
        profile = self._profile_from_dict(raw_profile)
        return ActiveModelProfile(role=role, profile_id=profile_id, profile=profile)

    def get_active_model_profile(self, role: str) -> ModelProfile | None:
        role = self._normalize_role(role)
        data = self._read()
        profile_id = data["active"].get(role)
        if not profile_id:
            return None
        raw_profile = data["profiles"].get(profile_id)
        return self._profile_from_dict(raw_profile) if raw_profile else None

    def settings_for_role(
        self,
        *,
        config_path: str | Path,
        role: str,
        default_model: str,
    ) -> ModelSettings:
        role = self._normalize_role(role)
        profile = self.get_active_model_profile(role)
        if profile is not None:
            return profile_to_settings(profile, role)
        values = merged_env_values(load_env_file(config_path))
        return load_role_settings(values, role, default_model=default_model)

    def _read(self) -> dict[str, Any]:
        if not self.profile_path.exists():
            return {"profiles": {}, "active": {}}
        try:
            data = json.loads(self.profile_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RevisionApplicationError(
                f"failed to read model profiles: {exc}",
                stage="model_profiles",
            ) from exc
        if not isinstance(data, dict):
            data = {}
        profiles = data.get("profiles") if isinstance(data.get("profiles"), dict) else {}
        active = data.get("active") if isinstance(data.get("active"), dict) else {}
        return {"profiles": profiles, "active": active}

    def _write(self, data: dict[str, Any]) -> None:
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.profile_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _profile_from_dict(value: dict[str, Any]) -> ModelProfile:
        defaults = asdict(
            ModelProfileRequest(profile_id="", name="", model="")
        )
        defaults.update(value)
        return ModelProfile(**{key: defaults[key] for key in ModelProfile.__dataclass_fields__})

    @staticmethod
    def _validate_request(request: ModelProfileRequest) -> None:
        if not request.profile_id.strip():
            raise RevisionApplicationError("profile_id is required")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", request.profile_id):
            raise RevisionApplicationError("profile_id can only contain letters, numbers, dot, dash, and underscore")
        if not request.name.strip():
            raise RevisionApplicationError("profile name is required")
        if not request.model.strip():
            raise RevisionApplicationError("model is required")
        if request.timeout_seconds <= 0:
            raise RevisionApplicationError("timeout_seconds must be greater than 0")
        if request.max_retries < 0:
            raise RevisionApplicationError("max_retries cannot be negative")

    @staticmethod
    def _normalize_role(role: str) -> str:
        normalized = role.upper()
        if normalized not in VALID_ROLES:
            raise RevisionApplicationError("role must be WRITER or REVIEWER")
        return normalized


def profile_to_settings(profile: ModelProfile, role: str) -> ModelSettings:
    return ModelSettings(
        role=role.upper(),
        api_key=profile.api_key,
        base_url=profile.base_url,
        model=profile.model,
        enable_search=profile.enable_search,
        model_family=profile.model_family,
        vision=profile.vision,
        function_calling=profile.function_calling,
        json_output=profile.json_output,
        structured_output=profile.structured_output,
        timeout_seconds=profile.timeout_seconds,
        max_retries=profile.max_retries,
    )


def load_active_role_settings(
    *,
    config_path: str | Path,
    profile_path: str | Path,
    role: str,
    default_model: str,
) -> ModelSettings:
    return ModelProfileService(profile_path).settings_for_role(
        config_path=config_path,
        role=role,
        default_model=default_model,
    )
