from __future__ import annotations

import os
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path

from .config import load_env_file
from .document_io import (
    PositionedTextLine,
    join_positioned_text_lines,
    order_positioned_text_lines,
)


def check_ocr_environment(pytesseract_module=None) -> dict[str, object]:
    if pytesseract_module is None:
        try:
            import pytesseract as pytesseract_module
        except ImportError:
            return {
                "ok": False,
                "path": None,
                "version": None,
                "languages": [],
                "missing_languages": ["chi_sim", "eng"],
                "message": "OCR Python 依赖未安装，请重新运行启动.bat 安装依赖。",
            }

    _configure_tesseract_command(pytesseract_module)
    configured = str(pytesseract_module.pytesseract.tesseract_cmd or "tesseract")
    resolved = _resolve_tesseract_command(configured)
    if resolved is None:
        return {
            "ok": False,
            "path": None,
            "version": None,
            "languages": [],
            "missing_languages": ["chi_sim", "eng"],
            "message": "未找到 Tesseract OCR 程序，请检查安装位置或 TESSERACT_CMD 配置。",
        }

    pytesseract_module.pytesseract.tesseract_cmd = str(resolved)
    try:
        version = str(pytesseract_module.get_tesseract_version()).splitlines()[0]
        languages = sorted(pytesseract_module.get_languages(config=""))
    except Exception as exc:
        return {
            "ok": False,
            "path": str(resolved),
            "version": None,
            "languages": [],
            "missing_languages": ["chi_sim", "eng"],
            "message": f"Tesseract OCR 检测失败：{exc}",
        }

    required_languages = ("chi_sim", "eng")
    missing_languages = [item for item in required_languages if item not in languages]
    if missing_languages:
        message = f"Tesseract 已安装，但缺少语言包：{', '.join(missing_languages)}。"
    else:
        message = "OCR 环境可用，中文和英文语言包均已安装。"
    return {
        "ok": not missing_languages,
        "path": str(resolved),
        "version": version,
        "languages": languages,
        "missing_languages": missing_languages,
        "message": message,
    }


def read_pdf_text_with_ocr(
    path: str | Path,
    language: str = "chi_sim+eng",
    *,
    pytesseract_module=None,
) -> str:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "OCR 依赖未安装，请重新运行 启动.bat 安装 PyMuPDF 和 pytesseract。"
        ) from exc
    if pytesseract_module is None:
        try:
            import pytesseract as pytesseract_module
        except ImportError as exc:
            raise RuntimeError(
                "OCR 依赖未安装，请重新运行 启动.bat 安装 PyMuPDF 和 pytesseract。"
            ) from exc
    _configure_tesseract_command(pytesseract_module)

    document = fitz.open(str(path))
    pages: list[str] = []
    try:
        for index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as image_file:
                pixmap.save(image_file.name)
                try:
                    data = pytesseract_module.image_to_data(
                        image_file.name,
                        lang=language,
                        output_type=pytesseract_module.Output.DICT,
                    )
                except pytesseract_module.TesseractNotFoundError as exc:
                    raise RuntimeError(
                        "未找到 Tesseract OCR 程序。请确认 tesseract.exe 已加入 PATH，"
                        "或在 config/settings.env 添加 TESSERACT_CMD=D:\\Tesseract-OCR\\tesseract.exe。"
                    ) from exc
                except pytesseract_module.TesseractError as exc:
                    raise RuntimeError(f"Tesseract OCR 运行失败：{exc}") from exc
            lines = _ocr_data_to_lines(data, page_width=float(pixmap.width))
            ordered, two_column = order_positioned_text_lines(
                lines,
                page_width=float(pixmap.width),
                page_height=float(pixmap.height),
            )
            text = join_positioned_text_lines(ordered)
            if text:
                layout = "two-column" if two_column else "single-column"
                pages.append(f"<!-- OCR page {index}; layout: {layout} -->\n\n{text}")
    finally:
        document.close()

    if not pages:
        raise ValueError("OCR did not extract any text from this PDF.")
    return "\n\n".join(pages)


def _ocr_data_to_lines(
    data: dict[str, list],
    *,
    page_width: float,
) -> list[PositionedTextLine]:
    grouped: dict[tuple[int, int, int], list[tuple[float, float, float, float, str]]] = (
        defaultdict(list)
    )
    texts = data.get("text") or []
    for index, raw_text in enumerate(texts):
        text = str(raw_text or "").strip()
        if not text:
            continue
        left = _ocr_number(data, "left", index)
        top = _ocr_number(data, "top", index)
        width = _ocr_number(data, "width", index)
        height = _ocr_number(data, "height", index)
        key = (
            _ocr_integer(data, "block_num", index),
            _ocr_integer(data, "par_num", index),
            _ocr_integer(data, "line_num", index),
        )
        grouped[key].append((left, top, left + width, top + height, text))

    lines: list[PositionedTextLine] = []
    split_gap = max(page_width * 0.04, 24.0)
    for words in grouped.values():
        ordered_words = sorted(words, key=lambda item: item[0])
        segments: list[list[tuple[float, float, float, float, str]]] = []
        for word in ordered_words:
            if segments and word[0] - segments[-1][-1][2] >= split_gap:
                segments.append([])
            if not segments:
                segments.append([])
            segments[-1].append(word)
        lines.extend(_ocr_segment_to_line(segment) for segment in segments if segment)
    return lines


def _ocr_segment_to_line(
    words: list[tuple[float, float, float, float, str]],
) -> PositionedTextLine:
    text = words[0][4]
    for previous, current in zip(words, words[1:]):
        separator = "" if _cjk_boundary(previous[4], current[4]) else " "
        text += separator + current[4]
    return PositionedTextLine(
        x0=min(word[0] for word in words),
        y0=min(word[1] for word in words),
        x1=max(word[2] for word in words),
        y1=max(word[3] for word in words),
        text=text,
    )


def _cjk_boundary(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return _is_cjk(left[-1]) and _is_cjk(right[0])


def _is_cjk(character: str) -> bool:
    return "\u3400" <= character <= "\u9fff"


def _ocr_number(data: dict[str, list], key: str, index: int) -> float:
    values = data.get(key) or []
    try:
        return float(values[index])
    except (IndexError, TypeError, ValueError):
        return 0.0


def _ocr_integer(data: dict[str, list], key: str, index: int) -> int:
    return int(_ocr_number(data, key, index))


def _configure_tesseract_command(pytesseract_module) -> None:
    configured = getattr(pytesseract_module.pytesseract, "tesseract_cmd", "")
    if configured and Path(configured).exists():
        return
    for command in _candidate_tesseract_commands():
        if command.exists():
            pytesseract_module.pytesseract.tesseract_cmd = str(command)
            return


def _resolve_tesseract_command(command: str) -> Path | None:
    command_path = Path(command)
    if command_path.exists():
        return command_path.resolve()
    discovered = shutil.which(command)
    if discovered:
        return Path(discovered).resolve()
    return None


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
