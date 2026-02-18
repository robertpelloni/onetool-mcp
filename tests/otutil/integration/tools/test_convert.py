"""Integration tests for document conversion tools.

Creates real documents using each library and verifies the conversion
produces meaningful Markdown output. Each test skips gracefully if
the required library is not installed.

Markers: @pytest.mark.integration, @pytest.mark.tools
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Temporary directory for conversion output files."""
    d = tmp_path / "output"
    d.mkdir()
    return d


@pytest.mark.integration
@pytest.mark.tools
class TestConvertPdf:
    """Integration tests for convert.pdf()."""

    def test_pdf_to_markdown(self, tmp_path: Path, output_dir: Path) -> None:
        """Create a minimal PDF with fitz and verify text is extracted."""
        fitz = pytest.importorskip("fitz", reason="pymupdf not installed")

        # Create a minimal PDF with known text
        doc: Any = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 100), "Hello PDF World")
        page.insert_text((50, 120), "Second line of content")
        pdf_path = tmp_path / "test.pdf"
        doc.save(str(pdf_path))
        doc.close()

        from otutil.tools.convert import pdf

        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = pdf(pattern=str(pdf_path), output_dir=str(output_dir))
        finally:
            os.chdir(old_cwd)

        assert "Error" not in result or "0 failed" in result
        assert "test.pdf" in result

        # Verify output file was created
        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) >= 1, "Expected at least one .md output file"

        all_content = "\n".join(f.read_text() for f in output_files)
        assert "Hello PDF World" in all_content or "Second line" in all_content


@pytest.mark.integration
@pytest.mark.tools
class TestConvertWord:
    """Integration tests for convert.word()."""

    def test_word_to_markdown(self, tmp_path: Path, output_dir: Path) -> None:
        """Create a DOCX with python-docx and verify content is extracted."""
        docx = pytest.importorskip("docx", reason="python-docx not installed")

        doc = docx.Document()
        doc.add_heading("Test Document", level=1)
        doc.add_paragraph("This is the first paragraph.")
        doc.add_paragraph("This is the second paragraph.")
        docx_path = tmp_path / "test.docx"
        doc.save(str(docx_path))

        from otutil.tools.convert import word

        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = word(pattern=str(docx_path), output_dir=str(output_dir))
        finally:
            os.chdir(old_cwd)

        assert "Error" not in result or "0 failed" in result
        assert "test.docx" in result

        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) >= 1, "Expected at least one .md output file"

        all_content = "\n".join(f.read_text() for f in output_files)
        assert "Test Document" in all_content or "first paragraph" in all_content


@pytest.mark.integration
@pytest.mark.tools
class TestConvertPptx:
    """Integration tests for convert.powerpoint()."""

    def test_pptx_to_markdown(self, tmp_path: Path, output_dir: Path) -> None:
        """Create a PPTX with python-pptx and verify slides are extracted."""
        pptx = pytest.importorskip("pptx", reason="python-pptx not installed")

        prs = pptx.Presentation()
        slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(slide_layout)
        title = slide.shapes.title
        if title:
            title.text = "Slide One Title"
        pptx_path = tmp_path / "test.pptx"
        prs.save(str(pptx_path))

        from otutil.tools.convert import powerpoint

        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = powerpoint(pattern=str(pptx_path), output_dir=str(output_dir))
        finally:
            os.chdir(old_cwd)

        assert "Error" not in result or "0 failed" in result
        assert "test.pptx" in result

        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) >= 1, "Expected at least one .md output file"

        all_content = "\n".join(f.read_text() for f in output_files)
        assert "Slide" in all_content or "slide" in all_content.lower() or len(all_content) > 10


@pytest.mark.integration
@pytest.mark.tools
class TestConvertExcel:
    """Integration tests for convert.excel()."""

    def test_excel_to_markdown(self, tmp_path: Path, output_dir: Path) -> None:
        """Create an XLSX with openpyxl and verify sheet data is extracted."""
        openpyxl = pytest.importorskip("openpyxl", reason="openpyxl not installed")

        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.title = "Data"
        ws["A1"] = "Name"
        ws["B1"] = "Score"
        ws["A2"] = "Alice"
        ws["B2"] = 95
        ws["A3"] = "Bob"
        ws["B3"] = 87
        xlsx_path = tmp_path / "test.xlsx"
        wb.save(str(xlsx_path))
        wb.close()

        from otutil.tools.convert import excel

        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = excel(pattern=str(xlsx_path), output_dir=str(output_dir))
        finally:
            os.chdir(old_cwd)

        assert "Error" not in result or "0 failed" in result
        assert "test.xlsx" in result

        output_files = list(output_dir.glob("*.md"))
        assert len(output_files) >= 1, "Expected at least one .md output file"

        all_content = "\n".join(f.read_text() for f in output_files)
        assert "Alice" in all_content or "Name" in all_content or "Score" in all_content
