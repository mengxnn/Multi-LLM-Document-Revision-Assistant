from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


def create_app() -> FastAPI:
    app = FastAPI(title="多 Agent 办公文档修订助手")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <title>多 Agent 办公文档修订助手</title>
  </head>
  <body>
    <h1>多 Agent 办公文档修订助手</h1>
  </body>
</html>
"""

    return app
