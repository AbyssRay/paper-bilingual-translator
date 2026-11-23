#!/usr/bin/env python3
"""
Extract text blocks from an academic PDF in two-column reading order with
normalized bounding-box coordinates for bilingual synchronized reading.

Output formats:
  - md:   Markdown-ready blocks with `<!-- sync: {"id": ..., "page": ..., "bbox": [...]} -->`
  - json: Structured JSON array of blocks
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    import pymupdf as fitz  # PyMuPDF >= 1.24
except ImportError:
    import fitz


def clean_block_text(raw_text: str) -> str:
    """Clean PDF line breaks and hyphenation while preserving paragraph text."""
    # Rejoin words hyphenated across line breaks (ASCII hyphen or soft hyphen U+00AD)
    text = re.sub(r"([A-Za-z])[-\u00ad]\s*\n\s*([A-Za-z])", r"\1\2", raw_text)
    # Remove any remaining standalone soft hyphens
    text = text.replace("\u00ad", "")
    # Collapse internal newlines and redundant whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_cell_text(raw_text: str) -> str:
    """Clean text inside a table cell and escape pipe characters for Markdown."""
    text = clean_block_text(raw_text)
    return text.replace("|", "\\|")


def is_header_continuation(header: List[str], row: List[str]) -> bool:
    """Detect whether a row is a wrapped second line of the table header."""
    non_empty = [c for c in row if c]
    if not non_empty:
        return False
    # If any header cell has an unclosed parenthesis or trailing hyphen/slash
    has_unclosed = any(
        c.count("(") > c.count(")") or c.endswith(("-", "–", "/"))
        for c in header
        if c
    )
    if has_unclosed and len(non_empty) < len(row):
        return True
    # Common wrapped header pattern: first column is empty (or single lowercase word like "solvent")
    # and all cells are short unit/label fragments rather than data citations
    if (
        len(non_empty) < len(row)
        and all(len(c) <= 35 for c in non_empty)
        and not any(re.search(r"\b(?:et al\.|19\d\d|20\d\d)\b", c) for c in non_empty)
        and (
            row[0] == ""
            or (row[0][0].islower() and not any(ch.isdigit() for ch in row[0]))
        )
    ):
        # Avoid mistaking a numeric data row with empty first column as a header continuation
        if not any(re.fullmatch(r"[\d.\-–+%]+", c) for c in non_empty):
            return True
    return False


def table_to_markdown(page: Any, table: Any) -> str:
    """Convert a PyMuPDF detected table into a clean GitHub-Flavored Markdown table."""
    raw_rows: List[List[str]] = []
    col_count = int(getattr(table, "col_count", 0) or 0)

    for row in table.rows:
        cells: List[str] = []
        for cell in row.cells:
            if cell is None:
                cells.append("")
            else:
                rect = fitz.Rect(cell)
                txt = page.get_text("text", clip=rect)
                cells.append(clean_cell_text(txt))
        if any(cells):
            raw_rows.append(cells)

    if len(raw_rows) < 2:
        return ""

    # Normalize column count across rows
    num_cols = max(col_count, max(len(r) for r in raw_rows))
    if num_cols < 2:
        return ""
    for r in raw_rows:
        if len(r) < num_cols:
            r.extend([""] * (num_cols - len(r)))

    # Merge wrapped header continuation rows into row 0
    header = list(raw_rows[0])
    body_start = 1
    while body_start < len(raw_rows) and is_header_continuation(header, raw_rows[body_start]):
        cont = raw_rows[body_start]
        for idx in range(num_cols):
            if cont[idx]:
                header[idx] = f"{header[idx]} {cont[idx]}".strip() if header[idx] else cont[idx]
        body_start += 1

    # Merge wrapped body continuation rows (empty first column) into previous data row
    body_rows: List[List[str]] = []
    for row in raw_rows[body_start:]:
        if row[0] == "" and body_rows and body_rows[-1][0] != "":
            prev = body_rows[-1]
            for idx in range(num_cols):
                if row[idx]:
                    prev[idx] = f"{prev[idx]} {row[idx]}".strip() if prev[idx] else row[idx]
        else:
            body_rows.append(list(row))

    if not body_rows:
        return ""

    # Mark empty visual/structure columns (e.g., chemical structure diagrams)
    for col_idx in range(num_cols):
        col_header = header[col_idx].lower()
        if any(k in col_header for k in ("structure", "diagram", "scheme", "image", "figure", "圖")):
            if all(r[col_idx] == "" for r in body_rows):
                for r in body_rows:
                    r[col_idx] = "（見原文圖示）"

    md_lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * num_cols) + " |",
    ]
    for r in body_rows:
        md_lines.append("| " + " | ".join(r) + " |")
    return "\n".join(md_lines)


def bbox_overlap_ratio(inner: List[float], outer: List[float], pad: float = 0.004) -> float:
    """Return fraction of `inner` bbox area covered by `outer` bbox (with small padding)."""
    ix0 = max(inner[0], outer[0] - pad)
    iy0 = max(inner[1], outer[1] - pad)
    ix1 = min(inner[2], outer[2] + pad)
    iy1 = min(inner[3], outer[3] + pad)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter_area = (ix1 - ix0) * (iy1 - iy0)
    inner_area = max(1e-9, (inner[2] - inner[0]) * (inner[3] - inner[1]))
    return inter_area / inner_area


def extract_page_tables(
    page: Any,
    page_num: int,
    w: float,
    h: float,
) -> List[Dict[str, Any]]:
    """Detect tables on a page and convert each into a single unified Markdown block."""
    if not hasattr(page, "find_tables"):
        return []

    table_blocks: List[Dict[str, Any]] = []
    try:
        found = page.find_tables()
    except Exception:
        return []

    for tbl in getattr(found, "tables", []):
        md_table = table_to_markdown(page, tbl)
        if not md_table:
            continue
        x0, y0, x1, y1 = tbl.bbox
        nx0 = round(max(0.0, min(1.0, x0 / w)), 4)
        ny0 = round(max(0.0, min(1.0, y0 / h)), 4)
        nx1 = round(max(0.0, min(1.0, x1 / w)), 4)
        ny1 = round(max(0.0, min(1.0, y1 / h)), 4)
        table_blocks.append(
            {
                "page": page_num,
                "bbox": [nx0, ny0, nx1, ny1],
                "text": md_table,
                "is_table": True,
            }
        )
    return table_blocks


def is_header_or_footer(
    text: str,
    ny0: float,
    ny1: float,
    header_margin: float,
    footer_margin: float,
) -> bool:
    """Heuristically filter running headers, footers, and page numbers."""
    # Pure page number near top or bottom
    if (ny0 < 0.10 or ny1 > 0.90) and re.fullmatch(
        r"[-–—\s]*(?:page\s*)?\d{1,4}[-–—\s]*", text, flags=re.IGNORECASE
    ):
        return True
    # Short running header at top margin
    if ny1 <= header_margin and len(text) < 140:
        return True
    # Short running footer / copyright / DOI line at bottom margin
    if ny0 >= footer_margin and len(text) < 140:
        return True
    return False


def is_full_width(nx0: float, nx1: float) -> bool:
    """Determine whether a block spans across both columns."""
    width = nx1 - nx0
    crosses_center = nx0 < 0.42 and nx1 > 0.58
    return crosses_center or width > 0.55


def sort_two_column_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort blocks on a page in reading order:
    Full-width blocks (title, abstract, wide tables/figures) act as vertical
    band separators. Within each band, left-column blocks come top-to-bottom,
    followed by right-column blocks top-to-bottom.
    """
    if not blocks:
        return []

    left_candidates = [
        b
        for b in blocks
        if not b.get("force_full_width")
        and not is_full_width(*b["bbox"][0::2])
        and b["bbox"][2] < 0.54
    ]
    right_candidates = [
        b
        for b in blocks
        if not b.get("force_full_width")
        and not is_full_width(*b["bbox"][0::2])
        and b["bbox"][0] > 0.46
    ]
    has_vertical_overlap = any(
        min(l["bbox"][3], r["bbox"][3]) > max(l["bbox"][1], r["bbox"][1])
        for l in left_candidates
        for r in right_candidates
    )
    is_two_col = (len(left_candidates) >= 2 and len(right_candidates) >= 2) or (
        len(left_candidates) >= 1 and len(right_candidates) >= 1 and has_vertical_overlap
    )

    if not is_two_col:
        return sorted(blocks, key=lambda b: (round(b["bbox"][1], 3), b["bbox"][0]))

    # Sort vertically first, then partition by full-width blocks
    blocks_by_y = sorted(blocks, key=lambda b: (b["bbox"][1], b["bbox"][0]))
    ordered: List[Dict[str, Any]] = []
    band_left: List[Dict[str, Any]] = []
    band_right: List[Dict[str, Any]] = []

    def flush_band() -> None:
        band_left.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
        band_right.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
        ordered.extend(band_left)
        ordered.extend(band_right)
        band_left.clear()
        band_right.clear()

    for blk in blocks_by_y:
        nx0, _, nx1, _ = blk["bbox"]
        if blk.get("force_full_width") or is_full_width(nx0, nx1):
            flush_band()
            ordered.append(blk)
        else:
            center_x = (nx0 + nx1) / 2.0
            if center_x < 0.5:
                band_left.append(blk)
            else:
                band_right.append(blk)

    flush_band()
    return ordered


def extract_pdf_blocks(
    pdf_path: Path,
    header_margin: float = 0.062,
    footer_margin: float = 0.935,
    min_chars: int = 2,
    detect_tables: bool = True,
) -> List[Dict[str, Any]]:
    """Extract normalized, reading-order text and table blocks from all pages of a PDF."""
    doc = fitz.open(str(pdf_path))
    all_blocks: List[Dict[str, Any]] = []

    try:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_num = page_idx + 1
            w = float(page.rect.width) or 1.0
            h = float(page.rect.height) or 1.0

            table_blocks = (
                extract_page_tables(page, page_num, w, h) if detect_tables else []
            )
            full_width_tables = [
                tb for tb in table_blocks if is_full_width(tb["bbox"][0], tb["bbox"][2])
            ]

            raw_blocks = page.get_text("blocks")
            page_blocks: List[Dict[str, Any]] = []

            for rb in raw_blocks:
                # rb: (x0, y0, x1, y1, text, block_no, block_type)
                x0, y0, x1, y1, raw_text, _, block_type = rb
                if block_type != 0:  # 0 = text, 1 = image
                    continue

                text = clean_block_text(raw_text)
                if len(text) < min_chars:
                    continue

                nx0 = round(max(0.0, min(1.0, x0 / w)), 4)
                ny0 = round(max(0.0, min(1.0, y0 / h)), 4)
                nx1 = round(max(0.0, min(1.0, x1 / w)), 4)
                ny1 = round(max(0.0, min(1.0, y1 / h)), 4)
                bbox = [nx0, ny0, nx1, ny1]

                if is_header_or_footer(text, ny0, ny1, header_margin, footer_margin):
                    continue

                # Skip text blocks already absorbed into a detected table
                if any(bbox_overlap_ratio(bbox, tb["bbox"]) >= 0.4 for tb in table_blocks):
                    continue

                # Keep a "Table N" caption attached as full-width right above a full-width table
                force_full_width = False
                if full_width_tables and re.match(r"^(?:Table|Tab\.)\s+\d+", text, flags=re.IGNORECASE):
                    if any(0.0 <= (tb["bbox"][1] - ny1) <= 0.045 for tb in full_width_tables):
                        force_full_width = True

                page_blocks.append(
                    {
                        "page": page_num,
                        "bbox": bbox,
                        "text": text,
                        "force_full_width": force_full_width,
                    }
                )

            ordered_blocks = sort_two_column_blocks(page_blocks + table_blocks)
            for idx, blk in enumerate(ordered_blocks, start=1):
                blk_id = f"p{page_num}_b{idx}"
                all_blocks.append(
                    {
                        "id": blk_id,
                        "page": page_num,
                        "bbox": blk["bbox"],
                        "text": blk["text"],
                    }
                )
    finally:
        doc.close()

    return all_blocks


def format_as_markdown(blocks: List[Dict[str, Any]]) -> str:
    """Format extracted blocks with HTML sync comments for bilingual translation."""
    lines: List[str] = []
    for blk in blocks:
        meta = {
            "id": blk["id"],
            "page": blk["page"],
            "bbox": blk["bbox"],
        }
        lines.append(f"<!-- sync: {json.dumps(meta, ensure_ascii=False)} -->")
        lines.append(blk["text"])
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract two-column PDF text and table blocks with normalized sync coordinates."
    )
    parser.add_argument("pdf_path", type=Path, help="Path to the input PDF file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Optional output file path (defaults to stdout)",
    )
    parser.add_argument(
        "--format",
        choices=["md", "json"],
        default="md",
        help="Output format: 'md' (with sync comments) or 'json' (default: md)",
    )
    parser.add_argument(
        "--header-margin",
        type=float,
        default=0.062,
        help="Normalized top margin threshold for filtering running headers (default: 0.062)",
    )
    parser.add_argument(
        "--footer-margin",
        type=float,
        default=0.935,
        help="Normalized bottom margin threshold for filtering footers (default: 0.935)",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=2,
        help="Minimum character length for a text block (default: 2)",
    )
    parser.add_argument(
        "--no-tables",
        action="store_true",
        help="Disable automatic table detection and Markdown table merging",
    )

    args = parser.parse_args()
    if not args.pdf_path.exists():
        print(f"Error: PDF file not found: {args.pdf_path}", file=sys.stderr)
        return 1

    blocks = extract_pdf_blocks(
        args.pdf_path,
        header_margin=args.header_margin,
        footer_margin=args.footer_margin,
        min_chars=args.min_chars,
        detect_tables=not args.no_tables,
    )

    if args.format == "json":
        output_text = json.dumps(blocks, ensure_ascii=False, indent=2) + "\n"
    else:
        output_text = format_as_markdown(blocks)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_text, encoding="utf-8")
        print(
            f"Extracted {len(blocks)} blocks from {args.pdf_path.name} -> {args.output}",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(output_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
