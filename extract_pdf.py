import json
import re
import sys
from pathlib import Path

import pymupdf

SRC_DIR = Path(__file__).parent
OUT = SRC_DIR / "data" / "pages.json"

HYPHEN_BREAK = re.compile(r"([а-яёa-z])-\s*\n\s*([а-яёa-z])", re.IGNORECASE)
SPACED_HYPHEN = re.compile(r"([а-яёa-z]) +- +([а-яёa-z])", re.IGNORECASE)
MULTISPACE = re.compile(r"[ \t]{2,}")
SINGLE_LETTER_LINE = re.compile(r"^\s*[а-яёa-z]\s*$", re.IGNORECASE | re.MULTILINE)
SECTION_LINE = re.compile(r"^§\s*(\d+)\.?\s+(.+)$")
CHAPTER_LINE = re.compile(r"^ГЛАВА\s+([IVX]+)\b\s*(.*)$")
PAGE_NOISE = re.compile(r"^\s*\d{1,3}\s*(ГЛАВА\s+[IVX]+)?\s*$")


def clean(raw: str) -> str:
    text = raw.replace("\u00ad", "").replace("\u00a0", " ").replace("\u2009", " ")
    for glyph in ("ࡨ", "Ǖ", "ǳ", "ǖ", "\u2022", "\uf0b7"):
        text = text.replace(glyph, " ")
    text = HYPHEN_BREAK.sub(r"\1\2", text)
    text = SPACED_HYPHEN.sub(r"\1-\2", text)
    text = SINGLE_LETTER_LINE.sub("", text)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if PAGE_NOISE.match(stripped):
            continue
        lines.append(MULTISPACE.sub(" ", stripped))
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def find_pdf() -> Path:
    if len(sys.argv) > 1:
        given = Path(sys.argv[1])
        if not given.is_file():
            sys.exit(f"Файл не найден: {given}")
        return given
    pdfs = sorted(SRC_DIR.glob("*.pdf"))
    if not pdfs:
        sys.exit("В папке нет ни одного .pdf — положи файл рядом со скриптом.")
    return pdfs[0]


def main() -> None:
    src = find_pdf()
    doc = pymupdf.open(str(src))
    pages = []
    short = []
    for index, page in enumerate(doc, start=1):
        raw = page.get_text("text")
        text = clean(raw)
        if len(text) < 60:
            short.append(index)
        pages.append({"page": index, "text": text})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(pages, ensure_ascii=False, indent=0), encoding="utf-8")
    chars = sum(len(p["text"]) for p in pages)
    print(f"Файл: {src.name}")
    print(f"Страниц: {len(pages)}, символов: {chars}")
    print(f"Коротких страниц (<60 симв.): {len(short)} {short[:20]}")
    print(f"Записано: {OUT}")


if __name__ == "__main__":
    main()
