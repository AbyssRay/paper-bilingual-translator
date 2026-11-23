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
    # Rejoin words hyphenated across line breaks (e.g., "electro-\nchemical" -> "electrochemical")
    text = re.sub(r"([A-Za-z])-\s*\n\s*([A-Za-z])", r"\1\2", raw_text)
    # Collapse internal newlines and redundant whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


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
        b for b in blocks if not is_full_width(*b["bbox"][0::2]) and b["bbox"][2] < 0.54
    ]
    right_candidates = [
        b for b in blocks if not is_full_width(*b["bbox"][0::2]) and b["bbox"][0] > 0.46
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
        if is_full_width(nx0, nx1):
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
    header_margin: float = 0.055,
    footer_margin: float = 0.935,
    min_chars: int = 2,
) -> List[Dict[str, Any]]:
    """Extract normalized, reading-order text blocks from all pages of a PDF."""
    doc = fitz.open(str(pdf_path))
    all_blocks: List[Dict[str, Any]] = []

    try:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_num = page_idx + 1
            w = float(page.rect.width) or 1.0
            h = float(page.rect.height) or 1.0

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

                if is_header_or_footer(text, ny0, ny1, header_margin, footer_margin):
                    continue

                page_blocks.append(
                    {
                        "page": page_num,
                        "bbox": [nx0, ny0, nx1, ny1],
                        "text": text,
                    }
                )

            ordered_blocks = sort_two_column_blocks(page_blocks)
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
        description="Extract two-column PDF text blocks with normalized sync coordinates."
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
        default=0.055,
        help="Normalized top margin threshold for filtering running headers (default: 0.055)",
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

    args = parser.parse_args()
    if not args.pdf_path.exists():
        print(f"Error: PDF file not found: {args.pdf_path}", file=sys.stderr)
        return 1

    blocks = extract_pdf_blocks(
        args.pdf_path,
        header_margin=args.header_margin,
        footer_margin=args.footer_margin,
        min_chars=args.min_chars,
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
