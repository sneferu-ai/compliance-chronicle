"""PDF contract: valid file shape, and real selectable text (no page images)."""

import json
import os
import re

from compliance_chronicle import render_pdf
from compliance_chronicle.pdf import Line, build_pdf


def _extract_tj_text(pdf_bytes: bytes) -> str:
    """Extract the text shown by every ``Tj`` operator in a PDF.

    A minimal parser sufficient for the uncompressed content streams this
    writer produces: find each ``(text) Tj`` operand, unescape it, and
    decode the bytes as WinAnsiEncoding (CP1252) — the encoding the fonts
    declare. This is the round-trip a real PDF reader performs.
    """

    raw = pdf_bytes.decode("latin-1")
    pieces = []
    for match in re.finditer(r"\(((?:[^)(]|\\[()])*)\)\s*Tj", raw):
        inner = match.group(1)
        inner = inner.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
        pieces.append(inner.encode("latin-1").decode("cp1252"))
    return " ".join(pieces)


def _xref_offsets(pdf_bytes: bytes):
    """Parse the xref table and return [(obj_number, offset), ...].

    Verifies every offset points at the matching ``N 0 obj`` header —
    the structural integrity guarantee that lets a reader seek directly
    to any object.
    """

    text = pdf_bytes.decode("latin-1")
    xref_pos_match = re.search(r"startxref\n(\d+)\n", text)
    xref_pos = int(xref_pos_match.group(1))
    xref_section = text[xref_pos:]
    count_match = re.match(r"xref\n0 (\d+)\n", xref_section)
    count = int(count_match.group(1))
    entries = []
    pos = count_match.end()
    for i in range(count):
        line = xref_section[pos : pos + 20].strip()
        parts = line.split()
        entries.append((i, int(parts[0]), parts[1], parts[2]))
        pos += 20
    return entries


class TestPdfWriter:
    def test_valid_pdf_shape(self, sample_issue):
        data = render_pdf.render_issue_pdf_bytes(sample_issue)
        assert data.startswith(b"%PDF-1.4")
        assert data.rstrip().endswith(b"%%EOF")
        assert b"xref" in data and b"trailer" in data
        assert b"/Type /Catalog" in data

    def test_text_is_selectable(self, sample_issue):
        """Content streams are uncompressed text operators — the bytes of
        the issue text appear verbatim, which is what makes the PDF
        text-selectable and searchable in every reader."""
        data = render_pdf.render_issue_pdf_bytes(sample_issue)
        assert b"(The Compliance Chronicle)" in data
        assert b"Tj ET" in data  # real text operators
        # the citation must be selectable text in the PDF
        assert b"437" in data

    def test_escapes_special_characters(self):
        data = build_pdf("t", [Line("parens (and) backslash \\ ok")])
        assert b"\\(and\\)" in data
        assert b"\\\\" in data

    def test_multipage_pagination(self):
        lines = [Line(f"line {i}") for i in range(500)]
        data = build_pdf("big", lines)
        assert data.count(b"/Type /Page ") > 1

    def test_empty_document_still_valid(self):
        data = build_pdf("empty", [])
        assert data.startswith(b"%PDF-1.4") and data.rstrip().endswith(b"%%EOF")

    def test_xref_offsets_point_at_correct_objects(self):
        """Every xref entry's byte offset must land on the matching
        ``N 0 obj`` header — a reader uses the xref to seek directly to
        objects, so a stale offset makes the file unreadable."""
        data = build_pdf("integrity", [Line("one"), Line("two"), Line("three")])
        text = data.decode("latin-1")
        entries = _xref_offsets(data)
        # entry 0 is the free object (65535 f); the rest are in-use
        assert entries[0] == (0, 0, "65535", "f")
        for obj_number, offset, _, flag in entries[1:]:
            assert flag == "n"
            header = text[offset : offset + 12]
            assert header.startswith(f"{obj_number} 0 obj"), (
                f"xref says object {obj_number} is at offset {offset} "
                f"but found {header!r}"
            )

    def test_startxref_matches_xref_position(self):
        data = build_pdf("sx", [Line("hi")])
        text = data.decode("latin-1")
        startxref = int(re.search(r"startxref\n(\d+)\n", text).group(1))
        assert text[startxref:startxref + 4] == "xref"

    def test_fonts_declare_winansi_encoding(self):
        """WinAnsiEncoding is what makes em-dashes and curly quotes
        render as real glyphs instead of the Latin-1 fallback '?'."""
        data = build_pdf("enc", [Line("ok")])
        assert b"/Encoding /WinAnsiEncoding" in data
        assert data.count(b"/Encoding /WinAnsiEncoding") == 2  # both fonts

    def test_em_dash_round_trips_as_selectable_text(self):
        """The issue header uses an em-dash (U+2014). It must survive the
        PDF encode/decode round-trip as a real character, not degrade to
        '?' — that is the difference between a selectable archive and a
        corrupted one."""
        data = build_pdf("dash", [Line("Issue #1 — covering 2026-08")])
        extracted = _extract_tj_text(data)
        assert "\u2014" in extracted
        assert "?" not in extracted.split("covering")[0]  # no '?' before "covering"

    def test_text_extraction_recovers_issue_content(self, sample_issue):
        """A reader extracting text from the content streams recovers the
        issue's real content — title, citation, deadline — verbatim."""
        data = render_pdf.render_issue_pdf_bytes(sample_issue)
        extracted = _extract_tj_text(data)
        assert "The Compliance Chronicle" in extracted
        assert "Tex. Health & Safety Code ch. 437" in extracted
        assert "Deadline: 2026-10-01" in extracted
        # the em-dash in the header line survives the round-trip
        assert "Issue #1 — covering 2026-08" in extracted


class TestIssueRendering:
    def test_issue_content_present(self, quiet_issue):
        data = render_pdf.render_issue_pdf_bytes(quiet_issue)
        assert b"NO MATERIAL CHANGES THIS MONTH" in data
        assert b"VERIFICATION LEDGER" in data
        assert b"SEARCH LOG" in data

    def test_write_to_disk(self, sample_issue, tmp_path):
        out = render_pdf.render_issue_pdf(sample_issue, str(tmp_path / "issue.pdf"))
        with open(out, "rb") as handle:
            assert handle.read(8) == b"%PDF-1.4"


class TestArchive:
    def test_archive_builds_pdfs_and_index(self, sample_issue, quiet_issue, tmp_path):
        out_dir = str(tmp_path / "archive")
        index_path = render_pdf.build_archive([quiet_issue, sample_issue], out_dir)
        assert os.path.exists(os.path.join(out_dir, "issue-001.pdf"))
        assert os.path.exists(os.path.join(out_dir, "issue-002.pdf"))
        with open(index_path, "r", encoding="utf-8") as handle:
            html = handle.read()
        assert "issue-001.pdf" in html and "issue-002.pdf" in html
        assert "quiet month" in html
        with open(os.path.join(out_dir, "index.json"), "r", encoding="utf-8") as handle:
            index = json.load(handle)
        assert [i["issue_number"] for i in index["issues"]] == [1, 2]  # sorted

    def test_archive_pdfs_are_selectable(self, sample_issue, tmp_path):
        render_pdf.build_archive([sample_issue], str(tmp_path))
        with open(os.path.join(str(tmp_path), "issue-001.pdf"), "rb") as handle:
            data = handle.read()
        assert b"Tj ET" in data
