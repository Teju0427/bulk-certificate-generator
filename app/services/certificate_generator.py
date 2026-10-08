"""Draws one certificate PDF with ReportLab (a single predefined template)."""
from datetime import date
from pathlib import Path
from uuid import UUID

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)  # 842 x 595 points
CENTER_X = PAGE_WIDTH / 2
NAVY = colors.HexColor("#1F3A5F")
GOLD = colors.HexColor("#B8923A")
GREY = colors.HexColor("#555555")
MAX_TEXT_WIDTH = PAGE_WIDTH - 160


def _fit_font_size(text: str, font: str, max_size: int, min_size: int = 8) -> int:
    """Shrink the font until the text fits between the margins (long names)."""
    size = max_size
    while size > min_size and stringWidth(text, font, size) > MAX_TEXT_WIDTH:
        size -= 1
    return size


def _draw_centered(pdf: canvas.Canvas, text: str, y: float, font: str, max_size: int, color) -> None:
    pdf.setFillColor(color)
    pdf.setFont(font, _fit_font_size(text, font, max_size))
    pdf.drawCentredString(CENTER_X, y, text)


def _draw_border(pdf: canvas.Canvas) -> None:
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(4)
    pdf.rect(25, 25, PAGE_WIDTH - 50, PAGE_HEIGHT - 50)
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1)
    pdf.rect(36, 36, PAGE_WIDTH - 72, PAGE_HEIGHT - 72)


def generate_certificate_pdf(
    output_path: Path,
    *,
    certificate_id: UUID,
    recipient_name: str,
    event_name: str,
    certificate_title: str,
    organization_name: str,
    issue_date: date,
) -> Path:
    """Create the PDF at output_path and return that path. Raises on any problem."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(output_path), pagesize=landscape(A4))
    pdf.setTitle(f"{certificate_title} - {recipient_name}")

    _draw_border(pdf)
    _draw_centered(pdf, organization_name.upper(), 490, "Helvetica-Bold", 22, NAVY)
    _draw_centered(pdf, certificate_title, 430, "Times-Bold", 38, GOLD)
    _draw_centered(pdf, "This certificate is proudly presented to", 370, "Helvetica-Oblique", 14, GREY)
    _draw_centered(pdf, recipient_name, 315, "Times-BoldItalic", 40, NAVY)

    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1)
    pdf.line(CENTER_X - 200, 298, CENTER_X + 200, 298)

    _draw_centered(pdf, "for successfully participating in", 262, "Helvetica", 14, GREY)
    _draw_centered(pdf, event_name, 230, "Helvetica-Bold", 20, NAVY)
    _draw_centered(pdf, f"Issued on {issue_date:%d %B %Y}", 170, "Helvetica", 13, GREY)
    _draw_centered(pdf, f"Certificate ID: {certificate_id}", 60, "Helvetica", 9, GREY)

    pdf.showPage()
    pdf.save()
    return output_path
