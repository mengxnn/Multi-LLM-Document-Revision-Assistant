from __future__ import annotations

import re
from pathlib import Path

from docx import Document


HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$")


def read_source_text(path: str | Path) -> str:
    source_path = Path(path)
    suffix = source_path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return source_path.read_text(encoding="utf-8")
    if suffix == ".docx":
        return read_docx_text(source_path)
    if suffix == ".doc":
        raise ValueError(".doc is not supported yet. Please convert it to .docx first.")
    raise ValueError(f"Unsupported source file type: {source_path.suffix}")


def read_docx_text(path: str | Path) -> str:
    document = Document(path)
    blocks: list[str] = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        heading_level = _heading_level(paragraph.style.name)
        if heading_level:
            blocks.append(f"{'#' * heading_level} {text}")
        else:
            blocks.append(text)

    for table in document.tables:
        for row in table.rows:
            cells = [_clean_cell_text(cell.text) for cell in row.cells]
            if any(cells):
                blocks.append("| " + " | ".join(cells) + " |")

    return "\n\n".join(blocks)


def write_final_docx(text: str, output_path: str | Path, reference_path: str | Path | None = None) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    document = Document(reference_path) if reference_path else Document()
    if reference_path:
        _clear_body(document)

    pending_table: list[list[str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            _flush_table(document, pending_table)
            pending_table = []
            continue
        if _is_horizontal_rule(line):
            _flush_table(document, pending_table)
            pending_table = []
            continue
        if _is_table_row(line):
            pending_table.append(_parse_table_row(line))
            continue

        _flush_table(document, pending_table)
        pending_table = []
        heading = HEADING_PATTERN.match(line)
        if heading:
            level = min(len(heading.group(1)), 6)
            paragraph = document.add_heading("", level=level)
            _add_markdown_runs(paragraph, heading.group(2).strip())
        else:
            paragraph = document.add_paragraph()
            _add_markdown_runs(paragraph, line)

    _flush_table(document, pending_table)
    document.save(output)


def _heading_level(style_name: str) -> int | None:
    match = re.search(r"Heading\s+([1-6])", style_name, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _clean_cell_text(text: str) -> str:
    return " ".join(text.split())


def _is_table_row(line: str) -> bool:
    return line.startswith("|") and line.endswith("|") and line.count("|") >= 2


def _is_horizontal_rule(line: str) -> bool:
    return bool(re.fullmatch(r"[-*_]{3,}", line.replace(" ", "")))


def _parse_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip("|").split("|")]


def _flush_table(document, rows: list[list[str]]) -> None:
    if not rows:
        return
    rows = [row for row in rows if not _is_separator_row(row)]
    if not rows:
        return
    column_count = max(len(row) for row in rows)
    table = document.add_table(rows=len(rows), cols=column_count)
    table.style = "Table Grid"
    for row_index, row in enumerate(rows):
        for col_index in range(column_count):
            cell = table.cell(row_index, col_index)
            cell.text = ""
            paragraph = cell.paragraphs[0]
            _add_markdown_runs(paragraph, row[col_index] if col_index < len(row) else "")


def _is_separator_row(row: list[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in row if cell.strip())


def _add_markdown_runs(paragraph, text: str) -> None:
    parts = re.split(r"(\*\*[^*]+\*\*|<br\s*/?>)", text, flags=re.IGNORECASE)
    for part in parts:
        if not part:
            continue
        if re.fullmatch(r"<br\s*/?>", part, flags=re.IGNORECASE):
            paragraph.add_run().add_break()
            continue
        if part.startswith("**") and part.endswith("**") and len(part) >= 4:
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            paragraph.add_run(part.replace("\\n", "\n"))


def _clear_body(document) -> None:
    body = document._body._element
    for child in list(body):
        if child.tag.endswith("}sectPr"):
            continue
        body.remove(child)
