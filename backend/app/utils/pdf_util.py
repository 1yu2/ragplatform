from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader, PdfWriter


def split_pdf_bytes(pdf_bytes: bytes, chunk_pages: int) -> tuple[list[tuple[int, bytes]], int]:
    if chunk_pages <= 0:
        raise ValueError("chunk_pages must be > 0")

    reader = PdfReader(BytesIO(pdf_bytes))
    total_pages = len(reader.pages)
    chunks: list[tuple[int, bytes]] = []

    for start in range(0, total_pages, chunk_pages):
        end = min(start + chunk_pages, total_pages)
        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])

        out = BytesIO()
        writer.write(out)
        chunks.append((start + 1, out.getvalue()))

    return chunks, total_pages


def split_pdf_bytes_range(
    pdf_bytes: bytes,
    chunk_pages: int,
    start_page: int = 1,
    end_page: int | None = None,
) -> tuple[list[tuple[int, bytes]], int]:
    if chunk_pages <= 0:
        raise ValueError("chunk_pages must be > 0")

    reader = PdfReader(BytesIO(pdf_bytes))
    total_pages = len(reader.pages)
    if total_pages <= 0:
        return [], 0

    start = max(1, int(start_page))
    end = total_pages if end_page is None else min(total_pages, int(end_page))
    if start > end:
        return [], total_pages

    chunks: list[tuple[int, bytes]] = []
    cur = start - 1
    end_idx = end - 1

    while cur <= end_idx:
        nxt = min(cur + chunk_pages - 1, end_idx)
        writer = PdfWriter()
        for i in range(cur, nxt + 1):
            writer.add_page(reader.pages[i])
        out = BytesIO()
        writer.write(out)
        chunks.append((cur + 1, out.getvalue()))
        cur = nxt + 1

    return chunks, total_pages
