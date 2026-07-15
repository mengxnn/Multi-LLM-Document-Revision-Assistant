from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .config import load_env_file


def read_pdf_text_with_ocr(path: str | Path, language: str = "chi_sim+eng") -> str:
    try:
        import fitz
        import pytesseract
    except ImportError as exc:
        raise RuntimeError(
            "OCR 依赖未安装，请重新运行 启动.bat 安装 PyMuPDF 和 pytesseract。"
        ) from exc
    _configure_tesseract_command(pytesseract)

    document = fitz.open(str(path))
    pages: list[str] = []
    try:
        for index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as image_file:
                pixmap.save(image_file.name)
                try:
                    text = pytesseract.image_to_string(image_file.name, lang=language).strip()
                except pytesseract.TesseractNotFoundError as exc:
                    raise RuntimeError(
                        "未找到 Tesseract OCR 程序。请确认 tesseract.exe 已加入 PATH，"
                        "或在 config/settings.env 添加 TESSERACT_CMD=D:\\Tesseract-OCR\\tesseract.exe。"
                    ) from exc
                except pytesseract.TesseractError as exc:
                    raise RuntimeError(f"Tesseract OCR 运行失败：{exc}") from exc
            if text:
                pages.append(f"<!-- OCR page {index} -->\n\n{text}")
    finally:
        document.close()

    if not pages:
        raise ValueError("OCR did not extract any text from this PDF.")
    return "\n\n".join(pages)


def _configure_tesseract_command(pytesseract_module) -> None:
    configured = getattr(pytesseract_module.pytesseract, "tesseract_cmd", "")
    if configured and Path(configured).exists():
        return
    for command in _candidate_tesseract_commands():
        if command.exists():
            pytesseract_module.pytesseract.tesseract_cmd = str(command)
            return


def _candidate_tesseract_commands() -> list[Path]:
    load_env_file("config/settings.env")
    configured = os.environ.get("TESSERACT_CMD")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured))
    candidates.append(Path("tools") / "tesseract" / "tesseract.exe")
    candidates.extend(
        [
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        ]
    )
    candidates.extend(
        Path(f"{letter}:\\Tesseract-OCR\\tesseract.exe")
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ"
    )
    return _deduplicate_paths(candidates)


def _deduplicate_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique
