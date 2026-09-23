import hashlib
import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz  # pymupdf
import pdfplumber
import xxhash

# Optional: layout-aware parsers (use one or more as needed)
import pymupdf4llm
from docling.document_converter import DocumentConverter
from unstructured.partition.pdf import partition_pdf

ROOT = Path(__file__).resolve().parents[1]
RAW_PDFS_DIR = ROOT / "data" / "raw_pdfs"
PARSED_DIR = ROOT / "data" / "parsed"

PARSED_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# Metadata model
# -----------------------------------------------------------------------------


@dataclass
class ChunkMetadata:
    # Core identity
    chunk_id: str
    doc_id: str
    doc_title: str
    doc_type: str  # e.g. "10-K", "code_of_conduct", "governance_principles"
    doc_year: Optional[int] = None
    version_date: Optional[str] = None
    source_file: str = ""
    source_url: str = ""

    # Location
    page_pdf: Optional[int] = None  # PDF page index (1-based)
    page_printed: Optional[int] = None  # Printed page number if available
    section_path: str = ""  # e.g. "Item 1A > Risk Factors > Cybersecurity Risk"
    section_title: str = ""
    item_number: str = ""  # e.g. "Item 1A", "Section 4.2"
    content_type: str = "text"  # text, table, list, footnote
    table_caption: Optional[str] = None
    table_id: Optional[str] = None

    # Structural / retrieval
    chunk_index: int = 0
    total_chunks: int = 0
    prev_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None
    parent_id: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    text_hash: str = ""

    # Governance / audit
    ingestion_date: str = ""
    parser_version: str = "1.0.0"
    effective_date: Optional[str] = None
    status: str = "current"  # current, superseded
    access_level: str = "public"  # public, internal

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def normalize_whitespace(text: str) -> str:
    # Fix hyphenated line breaks, collapse whitespace
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_repeated_headers_footers(lines: List[str]) -> List[str]:
    # Very simple heuristic: drop lines that repeat many times across pages
    # In production, you'd compute frequencies across all pages.
    freq: Dict[str, int] = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        freq[line] = freq.get(line, 0) + 1

    repeated = {line for line, count in freq.items() if count > 2 and len(line) < 80}

    cleaned = []
    for line in lines:
        s = line.strip()
        if s in repeated:
            continue
        cleaned.append(line)
    return cleaned


def is_toc_page(page_text: str, page_number: int, all_pages_text: List[str]) -> bool:
    """
    Heuristic TOC detection:
      - Page contains 'Table of Contents' or 'Contents' as a heading
      - Or: many short lines ending with numbers (like '2.4 Gifts and Business Hospitality .... 9')
    """
    text = page_text.lower()
    if "table of contents" in text or text.strip().startswith("contents"):
        return True

    lines = [l.strip() for l in page_text.splitlines() if l.strip()]
    if len(lines) < 5:
        return False

    # Count lines that look like "heading ... number"
    pattern = re.compile(r".+\s+\d{1,3}\s*$")
    toc_like = sum(1 for l in lines if pattern.match(l))
    if toc_like / len(lines) > 0.5:
        return True

    return False


def is_cover_or_signature_or_legal(page_text: str, page_number: int, total_pages: int) -> bool:
    text = page_text.lower()
    # Cover page heuristics
    if page_number == 1:
        if "annual report" in text or "form 10-k" in text or "corporate governance" in text:
            # Might still be content, but often cover-like
            pass

    # Signature / legal / copyright at end
    if page_number == total_pages or page_number == total_pages - 1:
        if "copyright" in text or "©" in text or "all rights reserved" in text:
            return True
        if "signed" in text and ("chief executive officer" in text or "chief financial officer" in text):
            return True

    # Very short last pages often are legal boilerplate
    if page_number >= total_pages - 2 and len(page_text.strip()) < 400:
        return True

    return False


def detect_doc_type_and_meta(filename: str) -> Tuple[str, str, Optional[int]]:
    """
    Infer doc_id, doc_type, doc_year from filename.
    Adjust patterns to your actual filenames.
    """
    name = filename.lower()

    doc_type = "other"
    doc_year = None

    if "10-k" in name or "10k" in name:
        doc_type = "10-K"
    elif "code of conduct" in name or "code_of_conduct" in name:
        doc_type = "code_of_conduct"
    elif "governance" in name and "principle" in name:
        doc_type = "governance_principles"
    elif "governance" in name:
        doc_type = "governance"

    # Try to extract year
    m = re.search(r"(19|20)\d{2}", filename)
    if m:
        doc_year = int(m.group())

    # Build doc_id
    base = re.sub(r"[^a-zA-Z0-9]+", "_", filename).strip("_").lower()
    doc_id = base[:64]

    doc_title = filename  # could be refined later

    return doc_id, doc_title, doc_type, doc_year


def compute_text_hash(text: str) -> str:
    return xxhash.xxh64(text.encode("utf-8")).hexdigest()


def build_chunk_id(doc_id: str, page_pdf: int, chunk_index: int) -> str:
    return f"{doc_id}_p{page_pdf:03d}_c{chunk_index:03d}"


# -----------------------------------------------------------------------------
# Structure detection (sections, items)
# -----------------------------------------------------------------------------


def detect_section_headings(text: str) -> List[Tuple[int, str]]:
    """
    Detect section headings and return list of (line_index, heading_text).
    This is simplistic; you can enhance with font size info from pymupdf if needed.
    """
    lines = text.splitlines()
    headings = []

    # Patterns for 10-K items
    item_pattern = re.compile(r"^\s*(Item\s+\d+[A-Z]?)\b", re.IGNORECASE)
    # Patterns for numbered sections like "2.4", "Section 4.2", "Principle 7"
    section_pattern = re.compile(r"^\s*((Section|Principle|Article)\s*\d+(\.\d+)?)\b", re.IGNORECASE)
    # All-caps short lines as headings
    caps_pattern = re.compile(r"^\s*([A-Z][A-Z\s]{3,})\s*$")

    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        if item_pattern.match(s) or section_pattern.match(s) or caps_pattern.match(s):
            headings.append((i, s))

    return headings


def build_section_path_for_line(
    line_index: int,
    headings: List[Tuple[int, str]],
) -> Tuple[str, str, str]:
    """
    Given a line index and list of detected headings, return:
      - section_path (hierarchical)
      - section_title (current heading)
      - item_number (e.g. 'Item 1A', 'Section 4.2')
    This is a simple stack-based approach.
    """
    stack: List[str] = []
    current_heading = ""
    current_item = ""

    next_heading_idx = 0
    for i in range(line_index + 1):
        # Push new headings when we reach them
        while next_heading_idx < len(headings) and headings[next_heading_idx][0] <= i:
            h_text = headings[next_heading_idx][1].strip()
            stack.append(h_text)
            current_heading = h_text
            # Detect item_number
            m = re.match(r"^\s*(Item\s+\d+[A-Z]?)\b", h_text, re.IGNORECASE)
            if m:
                current_item = m.group(1)
            else:
                m2 = re.match(r"^\s*((Section|Principle|Article)\s*\d+(\.\d+)?)\b", h_text, re.IGNORECASE)
                if m2:
                    current_item = m2.group(1)
            next_heading_idx += 1

    section_path = " > ".join(stack)
    return section_path, current_heading, current_item


# -----------------------------------------------------------------------------
# Table extraction
# -----------------------------------------------------------------------------


def _cell_to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").replace("|", "\\|").strip()


def table_rows_to_markdown(rows: List[List[Any]]) -> str:
    """Convert pdfplumber extract() rows (list of lists) to a markdown table."""
    if not rows:
        return ""

    header = [_cell_to_str(c) for c in rows[0]]
    body = rows[1:] if len(rows) > 1 else []

    if not any(header):
        ncols = max((len(r) for r in rows), default=0)
        header = [f"col_{i + 1}" for i in range(ncols)]
        body = rows

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in body:
        padded = list(row) + [None] * max(0, len(header) - len(row))
        cells = [_cell_to_str(c) for c in padded[: len(header)]]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def extract_tables_from_page_pdfplumber(page) -> List[Dict[str, Any]]:
    """
    Extract tables from a pdfplumber page as list of:
      {
        "table_index": int,
        "caption": str,
        "markdown": str,
        "bbox": tuple,
      }
    """
    tables = page.find_tables()
    result = []
    for idx, table in enumerate(tables):
        rows = table.extract() or []
        markdown = table_rows_to_markdown(rows)
        caption = f"Table {idx + 1}"
        result.append({
            "table_index": idx,
            "caption": caption,
            "markdown": markdown,
            "bbox": table.bbox,
        })
    return result


# -----------------------------------------------------------------------------
# Main parsing logic
# -----------------------------------------------------------------------------


def parse_pdf_to_chunks(pdf_path: Path) -> List[Dict[str, Any]]:
    doc_id, doc_title, doc_type, doc_year = detect_doc_type_and_meta(pdf_path.name)
    source_file = pdf_path.name
    source_url = ""  # fill if you track URLs

    ingestion_date = datetime.utcnow().isoformat() + "Z"

    # Open with pymupdf for text + layout
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    # Also open with pdfplumber for table extraction
    pdf_plumber_doc = pdfplumber.open(pdf_path)

    # Pre-pass: detect TOC and noise pages
    page_texts = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text")
        page_texts.append(text)

    toc_pages = set()
    noise_pages = set()

    for i, text in enumerate(page_texts, start=1):
        if is_toc_page(text, i, page_texts):
            toc_pages.add(i)
        if is_cover_or_signature_or_legal(text, i, total_pages):
            noise_pages.add(i)

    # For TOC-like inline blocks (e.g. 1.1–5.7 at top of governance doc),
    # we rely on the same heuristic: if a page is mostly TOC-like lines, skip it.

    chunks: List[Dict[str, Any]] = []
    global_chunk_index = 0

    # Headings detection per document (simple text-based)
    full_text = "\n".join(page_texts)
    doc_headings = detect_section_headings(full_text)

    # Map global line indices to (page, line_on_page) if needed; here we approximate.
    # For a more precise implementation, track line offsets per page.

    for page_idx, page in enumerate(doc, start=1):
        if page_idx in toc_pages or page_idx in noise_pages:
            continue

        text = page.get_text("text")
        lines = text.splitlines()

        # Clean repeated headers/footers
        cleaned_lines = strip_repeated_headers_footers(lines)
        cleaned_text = "\n".join(cleaned_lines)
        cleaned_text = normalize_whitespace(cleaned_text)

        if len(cleaned_text.strip()) < 50:
            # Almost empty page; could trigger OCR in a fuller implementation
            continue

        # Detect section path per line (approximate using whole-page text)
        section_path, section_title, item_number = build_section_path_for_line(
            0,  # simplified; in full version, compute per line
            doc_headings,
        )

        # Text chunk
        meta = ChunkMetadata(
            chunk_id="",  # set later
            doc_id=doc_id,
            doc_title=doc_title,
            doc_type=doc_type,
            doc_year=doc_year,
            source_file=source_file,
            source_url=source_url,
            page_pdf=page_idx,
            page_printed=page_idx,  # refine if you parse printed page numbers
            section_path=section_path,
            section_title=section_title,
            item_number=item_number,
            content_type="text",
            ingestion_date=ingestion_date,
        )

        meta.text_hash = compute_text_hash(cleaned_text)
        meta.chunk_index = global_chunk_index
        global_chunk_index += 1

        meta.chunk_id = build_chunk_id(doc_id, page_idx, meta.chunk_index)

        chunk_record = {
            "metadata": meta.to_dict(),
            "text": cleaned_text,
        }
        chunks.append(chunk_record)

        # Tables on this page (using pdfplumber)
        plumber_page = pdf_plumber_doc.pages[page_idx - 1]
        tables = extract_tables_from_page_pdfplumber(plumber_page)

        for t in tables:
            table_text = t["markdown"]
            if len(table_text.strip()) < 20:
                continue

            table_meta = ChunkMetadata(
                chunk_id="",
                doc_id=doc_id,
                doc_title=doc_title,
                doc_type=doc_type,
                doc_year=doc_year,
                source_file=source_file,
                source_url=source_url,
                page_pdf=page_idx,
                page_printed=page_idx,
                section_path=section_path,
                section_title=section_title,
                item_number=item_number,
                content_type="table",
                table_caption=t["caption"],
                table_id=f"{doc_id}_t{len(chunks)}",
                ingestion_date=ingestion_date,
            )
            table_meta.text_hash = compute_text_hash(table_text)
            table_meta.chunk_index = global_chunk_index
            global_chunk_index += 1
            table_meta.chunk_id = build_chunk_id(doc_id, page_idx, table_meta.chunk_index)

            table_record = {
                "metadata": table_meta.to_dict(),
                "text": table_text,
            }
            chunks.append(table_record)

    doc.close()
    pdf_plumber_doc.close()

    # Set total_chunks per section (here simplified as per doc)
    total = len(chunks)
    for i, c in enumerate(chunks):
        c["metadata"]["total_chunks"] = total
        if i > 0:
            c["metadata"]["prev_chunk_id"] = chunks[i - 1]["metadata"]["chunk_id"]
        if i < total - 1:
            c["metadata"]["next_chunk_id"] = chunks[i + 1]["metadata"]["chunk_id"]
        c["metadata"]["parent_id"] = c["metadata"].get("section_path", "")

    return chunks


def main():
    if not RAW_PDFS_DIR.exists():
        print(f"No directory: {RAW_PDFS_DIR}")
        return

    pdf_files = sorted(RAW_PDFS_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {RAW_PDFS_DIR}")
        return

    for pdf_path in pdf_files:
        print(f"Parsing: {pdf_path.name}")
        chunks = parse_pdf_to_chunks(pdf_path)

        out_name = pdf_path.with_suffix(".jsonl").name
        out_path = PARSED_DIR / out_name

        with out_path.open("w", encoding="utf-8") as f:
            for rec in chunks:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        print(f"  -> Wrote {len(chunks)} chunks to {out_path}")


if __name__ == "__main__":
    main()