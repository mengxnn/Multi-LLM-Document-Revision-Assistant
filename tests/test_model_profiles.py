import json
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from office_revision.application import (
    ModelProfileRequest,
    RevisionApplication,
    RevisionApplicationError,
    StartProjectRequest,
)
from office_revision.application.model_connections import ModelConnectionService
from office_revision.application.model_profiles import (
    ModelProfileService,
    load_active_role_settings,
)
from office_revision.application.new_projects import NewProjectService
from office_revision.connection_test import ConnectionCheckResult
from office_revision.workflow import RevisionPass, RevisionResult


@contextmanager
def clean_model_environment():
    keys = [
        key
        for key in os.environ
        if key.startswith("WRITER_")
        or key.startswith("REVIEWER_")
        or key.startswith("OPENAI_")
    ]
    old_values = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ.pop(key, None)
        yield
    finally:
        for key in keys:
            if old_values[key] is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_values[key]


class ModelProfileTests(unittest.TestCase):
    def test_saves_lists_and_activates_model_profiles_per_role(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "model_profiles.json"
            service = ModelProfileService(path)

            profile = service.save_model_profile(
                ModelProfileRequest(
                    profile_id="qwen-max",
                    name="Qwen Max",
                    provider="dashscope",
                    api_key="secret",
                    base_url="https://dashscope.example/v1",
                    model="qwen-max",
                    enable_search=True,
                    timeout_seconds=120,
                    max_retries=2,
                )
            )
            activated = service.activate_model_profile("writer", "qwen-max")

            self.assertEqual(profile.profile_id, "qwen-max")
            self.assertEqual(activated.role, "WRITER")
            self.assertEqual(activated.profile_id, "qwen-max")
            self.assertEqual(service.get_active_model_profile("WRITER"), profile)
            self.assertEqual(service.list_model_profiles(), (profile,))
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["active"]["WRITER"], "qwen-max")

    def test_rejects_activating_missing_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ModelProfileService(Path(temp_dir) / "model_profiles.json")

            with self.assertRaises(RevisionApplicationError):
                service.activate_model_profile("reviewer", "missing")

    def test_active_profile_overrides_env_settings_for_role(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with clean_model_environment():
                profiles_path = Path(temp_dir) / "model_profiles.json"
                env_path = Path(temp_dir) / "settings.env"
                env_path.write_text(
                    "WRITER_API_KEY=env-writer\nWRITER_MODEL=env-writer-model\n"
                    "REVIEWER_API_KEY=env-reviewer\nREVIEWER_MODEL=env-reviewer-model\n",
                    encoding="utf-8",
                )
                service = ModelProfileService(profiles_path)
                service.save_model_profile(
                    ModelProfileRequest(
                        profile_id="writer-profile",
                        name="Writer Profile",
                        api_key="profile-key",
                        base_url="https://profile.example/v1",
                        model="profile-model",
                        model_family="r1",
                        enable_search=True,
                    )
                )
                service.activate_model_profile("writer", "writer-profile")

                writer = load_active_role_settings(
                    config_path=env_path,
                    profile_path=profiles_path,
                    role="WRITER",
                    default_model="default",
                )
                reviewer = load_active_role_settings(
                    config_path=env_path,
                    profile_path=profiles_path,
                    role="REVIEWER",
                    default_model="default",
                )

                self.assertEqual(writer.api_key, "profile-key")
                self.assertEqual(writer.model, "profile-model")
                self.assertEqual(writer.model_family, "r1")
                self.assertTrue(writer.enable_search)
                self.assertEqual(reviewer.api_key, "env-reviewer")
                self.assertEqual(reviewer.model, "env-reviewer-model")

    def test_revision_application_exposes_model_profile_facade(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = RevisionApplication(
                config_path=Path(temp_dir) / "settings.env",
                model_profiles_path=Path(temp_dir) / "model_profiles.json",
            )
            profile = app.save_model_profile(
                ModelProfileRequest(
                    profile_id="reviewer-profile",
                    name="Reviewer Profile",
                    api_key="key",
                    model="reviewer-model",
                )
            )

            active = app.activate_model_profile("reviewer", profile.profile_id)

            self.assertEqual(active.role, "REVIEWER")
            self.assertEqual(app.get_active_model_profile("reviewer"), profile)
            self.assertEqual(app.list_model_profiles(), (profile,))

    def test_connection_check_uses_active_profiles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with clean_model_environment():
                profiles_path = Path(temp_dir) / "model_profiles.json"
                env_path = Path(temp_dir) / "settings.env"
                env_path.write_text(
                    "WRITER_API_KEY=env-writer\nWRITER_MODEL=env-writer-model\n"
                    "REVIEWER_API_KEY=env-reviewer\nREVIEWER_MODEL=env-reviewer-model\n",
                    encoding="utf-8",
                )
                profile_service = ModelProfileService(profiles_path)
                profile_service.save_model_profile(
                    ModelProfileRequest(
                        profile_id="writer-profile",
                        name="Writer Profile",
                        api_key="profile-key",
                        model="profile-writer-model",
                        timeout_seconds=180,
                        max_retries=3,
                    )
                )
                profile_service.activate_model_profile("writer", "writer-profile")
                seen = []

                def checker(settings_items):
                    seen.extend(settings_items)
                    return [
                        ConnectionCheckResult(item.role, item.model, True, "ok", 0.1)
                        for item in settings_items
                    ]

                service = ModelConnectionService(
                    env_path,
                    model_profiles_path=profiles_path,
                    checker=checker,
                )

                statuses = service.check_model_connections()

                self.assertEqual(statuses[0].model, "profile-writer-model")
                self.assertEqual(statuses[1].model, "env-reviewer-model")
                self.assertEqual(seen[0].api_key, "profile-key")
                self.assertEqual(seen[1].api_key, "env-reviewer")

    def test_connection_check_can_target_single_profile(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_path = Path(temp_dir) / "model_profiles.json"
            profile_service = ModelProfileService(profiles_path)
            profile_service.save_model_profile(
                ModelProfileRequest(
                    profile_id="qwen-plus",
                    name="Qwen Plus",
                    api_key="profile-key",
                    base_url="https://dashscope.example/v1",
                    model="qwen-plus",
                    timeout_seconds=180,
                    max_retries=3,
                )
            )
            seen = []

            def checker(settings_items):
                seen.extend(settings_items)
                return [
                    ConnectionCheckResult(item.role, item.model, True, "ok", 0.2)
                    for item in settings_items
                ]

            service = ModelConnectionService(
                model_profiles_path=profiles_path,
                checker=checker,
            )

            status = service.check_model_profile_connection("qwen-plus")

            self.assertEqual(status.role, "PROFILE")
            self.assertEqual(status.model, "qwen-plus")
            self.assertTrue(status.ok)
            self.assertEqual(seen[0].api_key, "profile-key")
            self.assertEqual(seen[0].timeout_seconds, 180)
            self.assertEqual(seen[0].max_retries, 3)

    def test_start_new_project_uses_active_profiles_for_real_runner(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with clean_model_environment():
                root = Path(temp_dir)
                profiles_path = root / "model_profiles.json"
                env_path = root / "settings.env"
                env_path.write_text(
                    "WRITER_API_KEY=env-writer\nWRITER_MODEL=env-writer-model\n"
                    "REVIEWER_API_KEY=env-reviewer\nREVIEWER_MODEL=env-reviewer-model\n",
                    encoding="utf-8",
                )
                profile_service = ModelProfileService(profiles_path)
                profile_service.save_model_profile(
                    ModelProfileRequest(
                        profile_id="writer-profile",
                        name="Writer Profile",
                        api_key="profile-key",
                        model="profile-writer-model",
                        timeout_seconds=180,
                        max_retries=3,
                    )
                )
                profile_service.activate_model_profile("writer", "writer-profile")
                seen = {}

                def real_runner(request, *, writer_settings, reviewer_settings, **kwargs):
                    seen["writer"] = writer_settings
                    seen["reviewer"] = reviewer_settings
                    return RevisionResult(
                        request=request,
                        passes=[
                            RevisionPass(
                                cycle_index=1,
                                draft="final draft",
                                review="是否继续修改：否",
                                review_continue=False,
                            )
                        ],
                        stopped_early=True,
                        stop_reason="reviewer_requested_stop",
                    )

                service = NewProjectService(
                    root / "projects",
                    env_path,
                    model_profiles_path=profiles_path,
                    real_runner=real_runner,
                    title_generator=lambda **kwargs: "Profile Test",
                )

                service.start_new_project(
                    StartProjectRequest(
                        requirements_text="Write a plan.",
                        cycles=1,
                        dry_run=False,
                    )
                )

                self.assertEqual(seen["writer"].model, "profile-writer-model")
                self.assertEqual(seen["writer"].api_key, "profile-key")
                self.assertEqual(seen["writer"].timeout_seconds, 180)
                self.assertEqual(seen["writer"].max_retries, 3)
                self.assertEqual(seen["reviewer"].model, "env-reviewer-model")


if __name__ == "__main__":
    unittest.main()
