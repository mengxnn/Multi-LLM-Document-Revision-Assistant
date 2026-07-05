from __future__ import annotations

import socket
import webbrowser

import uvicorn


def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    url = f"http://{host}:{port}"
    if _port_in_use(host, port):
        print(f"Web app is already running: {url}")
        webbrowser.open(url)
        return

    webbrowser.open(url)
    uvicorn.run("office_revision.web.app:create_app", host=host, port=port, factory=True)


def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex((host, port)) == 0


if __name__ == "__main__":
    main()
