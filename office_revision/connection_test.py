from __future__ import annotations

from dataclasses import dataclass

from .config import ModelSettings


@dataclass(frozen=True)
class ConnectionCheckResult:
    role: str
    model: str
    ok: bool
    message: str


def validate_settings(settings: ModelSettings) -> ConnectionCheckResult | None:
    if not settings.api_key:
        return ConnectionCheckResult(
            role=settings.role,
            model=settings.model,
            ok=False,
            message=f"{settings.role}_API_KEY is empty.",
        )
    if not settings.model:
        return ConnectionCheckResult(
            role=settings.role,
            model=settings.model,
            ok=False,
            message=f"{settings.role}_MODEL is empty.",
        )
    return None


def check_openai_compatible_connection(settings: ModelSettings) -> ConnectionCheckResult:
    invalid = validate_settings(settings)
    if invalid is not None:
        return invalid

    try:
        from openai import OpenAI

        kwargs = {"api_key": settings.api_key}
        if settings.base_url:
            kwargs["base_url"] = settings.base_url
        client = OpenAI(**kwargs)
        create_kwargs = {
            "model": settings.model,
            "messages": [
                {
                    "role": "user",
                    "content": "请只回复：连接成功",
                }
            ],
            "max_tokens": 20,
        }
        if settings.enable_search:
            create_kwargs["extra_body"] = {"enable_search": True}
        response = client.chat.completions.create(**create_kwargs)
        content = response.choices[0].message.content or ""
        search_note = " search=on" if settings.enable_search else " search=off"
        return ConnectionCheckResult(
            role=settings.role,
            model=settings.model,
            ok=True,
            message=(content.strip() or "Connection succeeded.") + search_note,
        )
    except Exception as exc:
        return ConnectionCheckResult(
            role=settings.role,
            model=settings.model,
            ok=False,
            message=f"{type(exc).__name__}: {exc}",
        )


def check_all_connections(settings_items: list[ModelSettings]) -> list[ConnectionCheckResult]:
    return [check_openai_compatible_connection(settings) for settings in settings_items]
