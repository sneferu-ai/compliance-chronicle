"""A minimal, dependency-free, text-selectable PDF writer.

The archive contract requires real, selectable text — not page images.
Rather than take a dependency, this module writes simple, valid
PDF 1.4 documents directly: one Catalog, a Pages tree, one Page per
sheet, a content stream per page using ``BT ... Tj ... ET`` text
operators, and the standard 14 Helvetica / Helvetica-Bold fonts.

What this deliberately does not do: compression (streams stay plain so
audits can read them), embedding fonts (standard 14 are guaranteed by
every conforming reader), images, or metadata beyond a title. It is a
document archive writer, not a layout engine.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import List, Sequence, Tuple

PAGE_WIDTH = 612  # US Letter, points
PAGE_HEIGHT = 792
MARGIN = 54
BODY_SIZE = 10.0

# Rough average character widths (fraction of font size) for Helvetica.
# Used only for wrapping — cosmetic, never semantic.
_AVG_CHAR_WIDTH = 0.5


def _escape_text(text: str) -> str:
    """Escape a string for a PDF text-showing operator (Tj).

    Text is encoded to CP1252 (WinAnsiEncoding) and re-decoded as
    Latin-1 so the raw bytes survive the final Latin-1 content-stream
    encode unchanged. The fonts declare ``/Encoding /WinAnsiEncoding``
    so a conforming reader maps those bytes back to the correct glyphs
    (em-dash, en-dash, curly quotes, the section sign, etc.). Anything
    outside CP1252 — extremely rare in this corpus — degrades to '?'
    rather than corrupting the stream.
    """

    out = (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )
    return out.encode("cp1252", errors="replace").decode("latin-1")


def _wrap_for_width(text: str, size: float, indent: int = 0) -> List[str]:
    usable = PAGE_WIDTH - 2 * MARGIN - indent
    max_chars = max(20, int(usable / (size * _AVG_CHAR_WIDTH)))
    if not text.strip():
        return [""]
    wrapped = textwrap.wrap(text, width=max_chars)
    return wrapped or [""]


@dataclass
class Line:
    """One logical line of the document."""

    text: str
    size: float = BODY_SIZE
    bold: bool = False
    indent: int = 0
    space_after: float = 0.0


def _paginate(lines: Sequence[Line]) -> List[List[Tuple[str, float, bool, int]]]:
    """Split wrapped lines into pages of drawn text rows."""

    pages: List[List[Tuple[str, float, bool, int]]] = []
    current: List[Tuple[str, float, bool, int]] = []
    y = PAGE_HEIGHT - MARGIN
    for line in lines:
        for piece in _wrap_for_width(line.text, line.size, line.indent):
            height = line.size + 4.0
            if y - height < MARGIN:
                pages.append(current)
                current = []
                y = PAGE_HEIGHT - MARGIN
            current.append((piece, line.size, line.bold, line.indent))
            y -= height
        if line.space_after:
            y -= line.space_after
    if current or not pages:
        pages.append(current)
    return pages


def _content_stream(page_rows: List[Tuple[str, float, bool, int]]) -> bytes:
    parts: List[str] = []
    y = PAGE_HEIGHT - MARGIN
    for text, size, bold, indent in page_rows:
        font = "F2" if bold else "F1"
        x = MARGIN + indent
        y -= size + 4.0
        if text:
            parts.append(f"BT /{font} {size:.1f} Tf {x:.1f} {y:.1f} Td ({_escape_text(text)}) Tj ET")
    return "\n".join(parts).encode("latin-1")


def build_pdf(title: str, lines: Sequence[Line]) -> bytes:
    """Build a complete PDF document from logical lines."""

    pages = _paginate(lines)
    objects: List[bytes] = []

    # Object numbering: 1=Catalog, 2=Pages, 3=Font F1, 4=Font F2,
    # then per page: page object + content stream object.
    n_pages = len(pages)
    page_obj_ids = [5 + 2 * i for i in range(n_pages)]
    content_obj_ids = [6 + 2 * i for i in range(n_pages)]

    kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(
        f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode("latin-1")
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")

    for page_id, content_id, rows in zip(page_obj_ids, content_obj_ids, pages):
        stream = _content_stream(rows)
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("latin-1")
        )
        objects.append(
            b"<< /Length "
            + str(len(stream)).encode("latin-1")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )

    # Info object (document title) as the last object.
    info_id = 5 + 2 * n_pages
    objects.append(f"<< /Title ({_escape_text(title)}) >>".encode("latin-1"))

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: List[int] = []
    for obj_number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{obj_number} 0 obj\n".encode("latin-1"))
        out.extend(body)
        out.extend(b"\nendobj\n")

    xref_pos = len(out)
    total_objects = len(objects) + 1  # including the free object 0
    out.extend(f"xref\n0 {total_objects}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        out.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        (
            f"trailer\n<< /Size {total_objects} /Root 1 0 R /Info {info_id} 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        ).encode("latin-1")
    )
    return bytes(out)


def write_pdf(title: str, lines: Sequence[Line], path: str) -> None:
    with open(path, "wb") as handle:
        handle.write(build_pdf(title, lines))
