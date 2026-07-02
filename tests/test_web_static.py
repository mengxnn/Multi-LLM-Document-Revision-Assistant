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
        self.assertIn("/api/model-profiles/active/writer", response.text)
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

    def test_model_profile_form_exposes_advanced_fields(self):
        client = TestClient(create_app())

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("profile-timeout-seconds", response.text)
        self.assertIn("profile-max-retries", response.text)
        self.assertIn("profile-model-family", response.text)
        self.assertIn("profile-enable-search", response.text)
        self.assertIn("profile-vision", response.text)
        self.assertIn("profile-function-calling", response.text)
        self.assertIn("profile-json-output", response.text)
        self.assertIn("profile-structured-output", response.text)

    def test_model_profile_page_shows_active_role_slots(self):
        client = TestClient(create_app())

        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("active-profiles", response.text)
        self.assertIn("active-writer-profile", response.text)
        self.assertIn("active-reviewer-profile", response.text)

    def test_run_gui_module_imports(self):
        import run_gui

        self.assertTrue(callable(run_gui.main))
