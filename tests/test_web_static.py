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

    def test_static_css_is_served(self):
        client = TestClient(create_app())

        response = client.get("/static/styles.css")

        self.assertEqual(response.status_code, 200)
        self.assertIn(".layout", response.text)

    def test_run_gui_module_imports(self):
        import run_gui

        self.assertTrue(callable(run_gui.main))
