import socket
from unittest import TestCase
from unittest.mock import patch

import run_gui


class RunGuiTests(TestCase):
    def test_main_starts_server_when_port_is_available(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

        with patch("run_gui.webbrowser.open") as open_browser, patch(
            "run_gui.uvicorn.run"
        ) as run_server:
            run_gui.main(port=port)

        open_browser.assert_called_once_with(f"http://127.0.0.1:{port}")
        run_server.assert_called_once_with(
            "office_revision.web.app:create_app",
            host="127.0.0.1",
            port=port,
            factory=True,
        )

    def test_main_opens_existing_url_when_port_is_already_in_use(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            port = listener.getsockname()[1]

            with patch("run_gui.webbrowser.open") as open_browser, patch(
                "run_gui.uvicorn.run"
            ) as run_server, patch("builtins.print"):
                run_gui.main(port=port)

        open_browser.assert_called_once_with(f"http://127.0.0.1:{port}")
        run_server.assert_not_called()
