"""Build an offline HTML textbook search from a PDF file."""

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

try:
    import pymupdf  # noqa: F401
except ImportError:
    raise SystemExit(
        "PyMuPDF is required. Install it with: python -m pip install PyMuPDF"
    ) from None

import build_app
import extract_pdf


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an offline HTML search page from a textbook PDF."
    )
    parser.add_argument("pdf", type=Path, help="text-based textbook PDF")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output HTML path (default: next to the PDF, with .html extension)",
    )
    args = parser.parse_args()

    pdf = args.pdf.expanduser().resolve()
    if not pdf.is_file():
        parser.error(f"PDF file not found: {pdf}")
    if pdf.suffix.lower() != ".pdf":
        parser.error("input file must have a .pdf extension")

    output = args.output.expanduser().resolve() if args.output else pdf.with_suffix(".html")

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="textbook-cheatsheet-") as temp_dir:
        temp = Path(temp_dir)
        extract_pdf.OUT = temp / "pages.json"

        previous_argv = sys.argv
        try:
            sys.argv = [str(extract_pdf.__file__), str(pdf)]
            extract_pdf.main()
        finally:
            sys.argv = previous_argv

        pages = json.loads(extract_pdf.OUT.read_text(encoding="utf-8"))
        build_app.SRC = extract_pdf.OUT
        build_app.RAW_JSON = temp / "fragments.json"
        build_app.OUT = output
        build_app.SKIP_PAGE_FROM = len(pages) + 1
        build_app.SKIP_PAGES = set()
        build_app.main()

    html = output.read_text(encoding="utf-8")
    html = html.replace(
        "История Нового времени — поиск по учебнику", "Офлайн-поиск по учебнику"
    )
    html = html.replace("История Нового времени, 7 класс", "Поиск по учебнику")
    html = html.replace(
        "Мединский, Чубарьян. Поиск по тексту учебника, без интернета",
        "Поиск по тексту PDF · работает без интернета",
    )
    html = html.replace(
        "Спроси, например: что такое меркантилизм",
        "Введите термин, событие или имя из учебника",
    )
    html = html.replace(
        "Отвечает только тем, что есть в учебнике. У каждого ответа указана страница.",
        "Ищет только в тексте PDF. У каждого найденного фрагмента указана страница.",
    )
    html = re.sub(
        r'const EXAMPLES=\[.*?\];', "const EXAMPLES=[];", html, count=1, flags=re.S
    )
    output.write_text(html, encoding="utf-8")
    print(f"Open this file in a browser: {output}")


if __name__ == "__main__":
    main()
