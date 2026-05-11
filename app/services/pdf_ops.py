from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Tuple

from pypdf import PdfReader, PdfWriter


@dataclass(frozen=True)
class PdfPageRef:
    path: str
    index: int  # 0-based


def merge_pdfs(file_paths: Iterable[str], output_path: str) -> None:
    writer = PdfWriter()
    for file_path in file_paths:
        reader = PdfReader(file_path)
        for page in reader.pages:
            writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)


def split_pdf_every_page(input_path: str, output_dir: str, base_name: str) -> None:
    reader = PdfReader(input_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, page in enumerate(reader.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)
        out_path = out_dir / f"{base_name}_{i}.pdf"
        with open(out_path, "wb") as f:
            writer.write(f)


def split_pdf_ranges(
    input_path: str, ranges: List[Tuple[int, int]], output_dir: str, base_name: str
) -> None:
    reader = PdfReader(input_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, (start, end) in enumerate(ranges, start=1):
        writer = PdfWriter()
        for page_index in range(start - 1, end):
            writer.add_page(reader.pages[page_index])
        out_path = out_dir / f"{base_name}_{i}.pdf"
        with open(out_path, "wb") as f:
            writer.write(f)


def parse_page_ranges(text: str, max_page: int) -> List[Tuple[int, int]]:
    ranges: List[Tuple[int, int]] = []
    text = text.strip()
    if not text:
        return ranges

    parts = [p.strip() for p in text.split(",") if p.strip()]
    for part in parts:
        if "-" in part:
            start_s, end_s = [x.strip() for x in part.split("-", 1)]
            if not start_s or not end_s:
                raise ValueError(f"Invalid range: {part}")
            start = int(start_s)
            end = int(end_s)
            if start <= 0 or end <= 0 or start > end:
                raise ValueError(f"Invalid range: {part}")
        else:
            start = int(part)
            end = start
            if start <= 0:
                raise ValueError(f"Invalid page: {part}")

        if end > max_page:
            raise ValueError(f"Page out of bounds: {part}")

        ranges.append((start, end))

    return ranges


def build_page_list_from_pdfs(file_paths: Iterable[str]) -> List[PdfPageRef]:
    pages: List[PdfPageRef] = []
    for file_path in file_paths:
        reader = PdfReader(file_path)
        for i in range(len(reader.pages)):
            pages.append(PdfPageRef(path=file_path, index=i))
    return pages


def export_ordered_pages(pages: Iterable[PdfPageRef], output_path: str) -> None:
    writer = PdfWriter()
    readers = {}

    for page_ref in pages:
        if page_ref.path not in readers:
            readers[page_ref.path] = PdfReader(page_ref.path)
        reader = readers[page_ref.path]
        writer.add_page(reader.pages[page_ref.index])

    with open(output_path, "wb") as f:
        writer.write(f)
