from __future__ import annotations

import webbrowser

import uvicorn


def main() -> None:
    host = "127.0.0.1"
    port = 8765
    url = f"http://{host}:{port}"
    webbrowser.open(url)
    uvicorn.run("office_revision.web.app:create_app", host=host, port=port, factory=True)


if __name__ == "__main__":
    main()
