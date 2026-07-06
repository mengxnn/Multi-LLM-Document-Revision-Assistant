import warnings
from unittest import TestCase

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
    category=Warning,
)

from fastapi.testclient import TestClient

from office_revision.web.app import create_app


class WebStaticTests(TestCase):
    def test_web_root_serves_html_page(self):
        client = TestClient(create_app())

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("多 Agent 办公文档修订助手", response.text)
        self.assertIn("/static/styles.css", response.text)
        self.assertIn("/static/app.js", response.text)

    def test_static_javascript_is_served(self):
        client = TestClient(create_app())

        response = client.get("/static/app.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("loadProjects", response.text)
        self.assertIn("response.text()", response.text)
        self.assertIn("continueProject", response.text)
        self.assertIn("deleteProject", response.text)
        self.assertIn("clearProjectSelection", response.text)
        self.assertIn('"skip"', response.text)
        self.assertIn("permanent", response.text)
        self.assertIn("shortPath", response.text)
        self.assertIn("artifactDisplayPath", response.text)
        self.assertIn("inputDisplayPath", response.text)
        self.assertIn("openArtifact", response.text)
        self.assertIn("selectedBaseVersionPath", response.text)
        self.assertIn("chooseBaseVersion", response.text)
        self.assertIn("base_version_path", response.text)
        self.assertIn("checkModelProfile", response.text)
        self.assertIn("loadActiveModelProfiles", response.text)
        self.assertIn("activateModelProfile", response.text)
        self.assertIn("deleteModelProfile", response.text)
        self.assertIn("editModelProfile", response.text)
        self.assertIn("editingProfileId", response.text)
        self.assertIn("/api/model-profiles/active/writer", response.text)
        self.assertIn('method: "DELETE"', response.text)
        self.assertIn("/activate", response.text)
        self.assertIn("/check", response.text)
        self.assertIn("/api/artifacts/open", response.text)
        self.assertIn("打开文件", response.text)
        self.assertIn("文件位置", response.text)

    def test_static_css_is_served(self):
        client = TestClient(create_app())

        response = client.get("/static/styles.css")

        self.assertEqual(response.status_code, 200)
        self.assertIn(".layout", response.text)
        self.assertIn(".artifact-list", response.text)
        self.assertIn(".path-row", response.text)

    def test_project_detail_controls_are_present(self):
        client = TestClient(create_app())

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("continue-feedback-text", response.text)
        self.assertIn("continue-project", response.text)
        self.assertIn("delete-permanent", response.text)

    def test_new_project_form_accepts_source_requirement_and_meeting_files(self):
        client = TestClient(create_app())

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="requirements-file"', response.text)
        self.assertIn('id="source-file"', response.text)
        self.assertIn('id="meeting-notes-file"', response.text)
        self.assertIn('accept=".docx,.md,.pdf,.txt"', response.text)

    def test_start_project_javascript_submits_multipart_form_data(self):
        client = TestClient(create_app())

        response = client.get("/static/app.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("new FormData()", response.text)
        self.assertIn("/api/projects/start-upload", response.text)
        self.assertIn("requirements_file", response.text)
        self.assertIn("source_file", response.text)
        self.assertIn("meeting_notes_file", response.text)

    def test_project_versions_render_artifacts_in_collapsible_details(self):
        client = TestClient(create_app())

        response = client.get("/static/app.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn('document.createElement("details")', response.text)
        self.assertIn("version-artifacts", response.text)
        self.assertIn("版本详情", response.text)

    def test_project_inputs_label_pdf_extracted_text(self):
        client = TestClient(create_app())

        response = client.get("/static/app.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("inputDisplayLabel", response.text)
        self.assertIn("PDF提取文本", response.text)

    def test_project_detail_can_be_collapsed_from_javascript(self):
        client = TestClient(create_app())

        response = client.get("/static/app.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("if (selectedProjectId === projectId)", response.text)
        self.assertIn("clearProjectSelection()", response.text)
        self.assertIn("updateProjectDetailButtons", response.text)
        self.assertIn("折叠详情", response.text)

    def test_model_profile_form_uses_user_friendly_basic_fields(self):
        client = TestClient(create_app())

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("显示名称", response.text)
        self.assertIn("模型ID", response.text)
        self.assertIn("供应商类型", response.text)
        self.assertNotIn('id="profile-id"', response.text)
        self.assertNotIn('id="profile-model-family"', response.text)
        self.assertNotIn('value="openai-compatible"', response.text)

    def test_model_profile_form_collapses_advanced_fields(self):
        client = TestClient(create_app())

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="profile-advanced-settings"', response.text)
        self.assertIn("高级设置", response.text)
        self.assertIn("profile-timeout-seconds", response.text)
        self.assertIn("profile-max-retries", response.text)
        self.assertIn("profile-enable-search", response.text)
        self.assertIn("profile-vision", response.text)
        self.assertIn("profile-function-calling", response.text)
        self.assertIn("profile-json-output", response.text)
        self.assertIn("profile-structured-output", response.text)
        self.assertIn('placeholder="60"', response.text)
        self.assertIn('placeholder="1"', response.text)
        self.assertNotIn('id="profile-timeout-seconds" type="number" min="1" value="60"', response.text)
        self.assertNotIn('id="profile-max-retries" type="number" min="0" value="1"', response.text)

    def test_model_profile_page_shows_active_role_slots(self):
        client = TestClient(create_app())

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("active-profiles", response.text)
        self.assertIn("active-writer-profile", response.text)
        self.assertIn("active-reviewer-profile", response.text)

    def test_model_profile_sections_are_collapsible(self):
        client = TestClient(create_app())

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="existing-profiles-section"', response.text)
        self.assertIn('id="add-profile-section"', response.text)
        self.assertIn("现有配置", response.text)
        self.assertIn("添加配置", response.text)
        self.assertIn('id="profiles"', response.text)
        self.assertIn('id="profile-form"', response.text)

    def test_model_profile_javascript_supports_editing_existing_profile(self):
        client = TestClient(create_app())

        response = client.get("/static/app.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("createEditProfileButton", response.text)
        self.assertIn("editModelProfile", response.text)
        self.assertIn("editingProfileId", response.text)
        self.assertIn("profile_id: editingProfileId", response.text)
        self.assertIn("addProfileSectionEl.open = true", response.text)

    def test_run_gui_module_imports(self):
        import run_gui

        self.assertTrue(callable(run_gui.main))
