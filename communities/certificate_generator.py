"""
Certificate PDF generation for BridgeCare health programs.

Supports three modes:
  - builtin: fully generated via ReportLab (Classic, Professional, Modern, Elegant)
  - image_overlay: org-uploaded background image with ReportLab text overlay
  - pdf_placeholder: org-uploaded PDF with {{placeholder}} fields filled via pypdf + ReportLab overlay
"""

import hashlib
import hmac
import io
import os
import string
import secrets
from datetime import datetime

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

import qrcode
from qrcode.image.pil import PilImage
from PIL import Image as PILImage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PAGE_W, PAGE_H = landscape(A4)  # 841.9 x 595.3 pts


def _hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return r / 255, g / 255, b / 255


def _make_qr_image(data: str) -> io.BytesIO:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img: PilImage = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _render_body_text(c: rl_canvas.Canvas, text: str, x: float, y: float,
                      width: float, line_height: float = 14,
                      font_name: str = "Helvetica", font_size: float = 11,
                      color=(0.2, 0.2, 0.2), align: str = "center"):
    """Word-wrap body text within a given width."""
    c.setFont(font_name, font_size)
    c.setFillColorRGB(*color)
    words = text.split()
    line = ""
    lines = []
    for word in words:
        test = f"{line} {word}".strip()
        if c.stringWidth(test, font_name, font_size) <= width:
            line = test
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)

    total_height = len(lines) * line_height
    cur_y = y + total_height / 2  # vertically center the block around y

    for ln in lines:
        w = c.stringWidth(ln, font_name, font_size)
        if align == "center":
            c.drawString(x + (width - w) / 2, cur_y, ln)
        elif align == "left":
            c.drawString(x, cur_y, ln)
        else:
            c.drawString(x + width - w, cur_y, ln)
        cur_y -= line_height


def _draw_qr_and_code(c: rl_canvas.Canvas, verification_url: str,
                      verification_code: str, x: float, y: float,
                      size: float = 55):
    qr_buf = _make_qr_image(verification_url)
    c.drawImage(ImageReader(qr_buf), x, y, width=size, height=size,
                preserveAspectRatio=True)
    c.setFont("Helvetica", 6)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    code_w = c.stringWidth(verification_code, "Helvetica", 6)
    c.drawString(x + (size - code_w) / 2, y - 8, verification_code)


def _draw_logo(c: rl_canvas.Canvas, logo_path_or_url, x, y, w, h):
    """Draw a logo image; gracefully skip if unavailable."""
    if not logo_path_or_url:
        return
    try:
        if hasattr(logo_path_or_url, "path"):
            src = logo_path_or_url.path
        else:
            src = str(logo_path_or_url)
        if not os.path.exists(src):
            return
        c.drawImage(ImageReader(src), x, y, width=w, height=h,
                    preserveAspectRatio=True, mask="auto")
    except Exception:
        pass


def _draw_signature(c: rl_canvas.Canvas, sig_path, x, y, w=80, h=30):
    if not sig_path:
        return
    try:
        if hasattr(sig_path, "path"):
            src = sig_path.path
        else:
            src = str(sig_path)
        if not os.path.exists(src):
            return
        c.drawImage(ImageReader(src), x, y, width=w, height=h,
                    preserveAspectRatio=True, mask="auto")
    except Exception:
        pass


def _resolve_colors(template):
    primary = _hex_to_rgb(template.primary_color or "#009EDB")
    secondary = _hex_to_rgb(template.secondary_color or "#00c7a6")
    accent = _hex_to_rgb(template.accent_color or "#7733FF")
    return primary, secondary, accent


# ---------------------------------------------------------------------------
# Built-in Template: Classic
# ---------------------------------------------------------------------------

def _render_classic(c, template, ctx):
    primary, secondary, accent = _resolve_colors(template)
    W, H = PAGE_W, PAGE_H

    # Outer border
    c.setStrokeColorRGB(*accent)
    c.setLineWidth(2)
    c.rect(12 * mm, 12 * mm, W - 24 * mm, H - 24 * mm, stroke=1, fill=0)
    c.setLineWidth(0.5)
    c.rect(14 * mm, 14 * mm, W - 28 * mm, H - 28 * mm, stroke=1, fill=0)

    # Top header bar
    c.setFillColorRGB(*primary)
    c.rect(0, H - 22 * mm, W, 22 * mm, stroke=0, fill=1)

    # Header text
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 9)
    header_w = c.stringWidth("BRIDGECARE HEALTH PLATFORM", "Helvetica-Bold", 9)
    c.drawString((W - header_w) / 2, H - 10 * mm, "BRIDGECARE HEALTH PLATFORM")

    # Logo top-left in header
    logo = template.custom_logo or (
        template.organization.orgnaization_logo if template.organization else None
    )
    _draw_logo(c, logo, 18 * mm, H - 20 * mm, 18 * mm, 16 * mm)

    # Certificate title
    title = template.header_text or "Certificate of Participation"
    c.setFont("Helvetica-Bold", 26)
    c.setFillColorRGB(*primary)
    title_w = c.stringWidth(title, "Helvetica-Bold", 26)
    c.drawString((W - title_w) / 2, H - 50 * mm, title)

    # Decorative underline
    c.setStrokeColorRGB(*secondary)
    c.setLineWidth(1.5)
    line_x = (W - 120 * mm) / 2
    c.line(line_x, H - 53 * mm, line_x + 120 * mm, H - 53 * mm)

    # "This is to certify that"
    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    intro = "This is to certify that"
    intro_w = c.stringWidth(intro, "Helvetica", 10)
    c.drawString((W - intro_w) / 2, H - 63 * mm, intro)

    # Participant name
    c.setFont("Helvetica-Bold", 20)
    c.setFillColorRGB(*accent)
    name_w = c.stringWidth(ctx["participant_name"], "Helvetica-Bold", 20)
    c.drawString((W - name_w) / 2, H - 76 * mm, ctx["participant_name"])

    # Name underline
    c.setStrokeColorRGB(*accent)
    c.setLineWidth(1)
    nl = (W - name_w) / 2 - 5 * mm
    c.line(nl, H - 78 * mm, nl + name_w + 10 * mm, H - 78 * mm)

    # Body text
    body = ctx["body_text"]
    _render_body_text(c, body,
                      20 * mm, H - 96 * mm,
                      W - 40 * mm, line_height=14,
                      font_name="Helvetica", font_size=10,
                      color=(0.3, 0.3, 0.3))

    # Dates / org
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    prog_info = f"{ctx['program_name']}  ·  {ctx['start_date']} – {ctx['end_date']}"
    prog_w = c.stringWidth(prog_info, "Helvetica", 9)
    c.drawString((W - prog_w) / 2, H - 110 * mm, prog_info)

    # Signatory section
    sig_x = 30 * mm
    sig_y = 30 * mm
    _draw_signature(c, template.signatory_signature, sig_x, sig_y + 8 * mm)
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.setLineWidth(0.5)
    c.line(sig_x, sig_y + 6 * mm, sig_x + 70 * mm, sig_y + 6 * mm)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawString(sig_x, sig_y + 2 * mm, template.signatory_name or "")
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(sig_x, sig_y - 3 * mm, template.signatory_title or "")

    # Organization name bottom center
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    org_name = ctx["organization_name"]
    org_w = c.stringWidth(org_name, "Helvetica", 9)
    c.drawString((W - org_w) / 2, 32 * mm, org_name)
    c.setFillColorRGB(*primary)
    c.rect((W - org_w) / 2 - 2 * mm, 30 * mm,
           org_w + 4 * mm, 0.6 * mm, stroke=0, fill=1)

    # Footer text
    if template.footer_text:
        c.setFont("Helvetica", 7)
        c.setFillColorRGB(0.6, 0.6, 0.6)
        ft_w = c.stringWidth(template.footer_text, "Helvetica", 7)
        c.drawString((W - ft_w) / 2, 22 * mm, template.footer_text)

    # QR code
    if template.show_qr_code:
        _draw_qr_and_code(c, ctx["verification_url"], ctx["verification_code"],
                          W - 30 * mm - 12 * mm, 24 * mm, size=30 * mm)


# ---------------------------------------------------------------------------
# Built-in Template: Professional
# ---------------------------------------------------------------------------

def _render_professional(c, template, ctx):
    primary, secondary, accent = _resolve_colors(template)
    W, H = PAGE_W, PAGE_H
    panel_w = 0.28 * W

    # Left dark panel
    c.setFillColorRGB(*primary)
    c.rect(0, 0, panel_w, H, stroke=0, fill=1)

    # Accent stripe on left panel
    c.setFillColorRGB(*accent)
    c.rect(panel_w - 4, 0, 4, H, stroke=0, fill=1)

    # Logo in left panel
    logo = template.custom_logo or (
        template.organization.orgnaization_logo if template.organization else None
    )
    _draw_logo(c, logo, 8 * mm, H - 30 * mm, panel_w - 16 * mm, 22 * mm)

    # Organization name in left panel
    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(1, 1, 1)
    org_lines = _wrap_text(ctx["organization_name"], panel_w - 16 * mm,
                           "Helvetica-Bold", 10, c)
    org_y = H - 40 * mm
    for ln in org_lines:
        c.drawString(8 * mm, org_y, ln)
        org_y -= 13

    # Program name in left panel
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(*[min(v + 0.3, 1.0) for v in secondary])
    prog_lines = _wrap_text(ctx["program_name"], panel_w - 16 * mm,
                            "Helvetica", 8, c)
    prog_y = org_y - 6
    for ln in prog_lines:
        c.drawString(8 * mm, prog_y, ln)
        prog_y -= 11

    # Dates in left panel
    c.setFont("Helvetica", 7.5)
    c.setFillColorRGB(0.8, 0.9, 1.0)
    c.drawString(8 * mm, prog_y - 10, ctx["start_date"])
    c.drawString(8 * mm, prog_y - 21, f"to  {ctx['end_date']}")

    # Verification code in left panel
    if template.show_qr_code:
        _draw_qr_and_code(c, ctx["verification_url"], ctx["verification_code"],
                          8 * mm, 18 * mm, size=26 * mm)

    # Right content area
    rx = panel_w + 16 * mm
    rw = W - panel_w - 24 * mm

    # Top right thin border line
    c.setStrokeColorRGB(*secondary)
    c.setLineWidth(1)
    c.line(rx, H - 16 * mm, rx + rw, H - 16 * mm)

    # "CERTIFICATE" stamp
    c.setFont("Helvetica-Bold", 28)
    c.setFillColorRGB(*primary)
    stamp = "CERTIFICATE"
    c.drawString(rx, H - 36 * mm, stamp)

    c.setFont("Helvetica", 12)
    c.setFillColorRGB(*accent)
    sub = f"of  {template.header_text.replace('Certificate of', '').strip() or 'Participation'}"
    c.drawString(rx, H - 46 * mm, sub)

    # Divider
    c.setStrokeColorRGB(*secondary)
    c.setLineWidth(0.8)
    c.line(rx, H - 51 * mm, rx + rw, H - 51 * mm)

    # "Awarded to"
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(rx, H - 60 * mm, "Awarded to")

    # Participant name
    c.setFont("Helvetica-Bold", 22)
    c.setFillColorRGB(*accent)
    c.drawString(rx, H - 74 * mm, ctx["participant_name"])

    # Body paragraph
    _render_body_text(c, ctx["body_text"],
                      rx, H - 100 * mm, rw,
                      line_height=14, font_name="Helvetica", font_size=9.5,
                      color=(0.3, 0.3, 0.3), align="left")

    # Signatory
    sig_y = 32 * mm
    _draw_signature(c, template.signatory_signature, rx, sig_y + 8 * mm)
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.setLineWidth(0.5)
    c.line(rx, sig_y + 6 * mm, rx + 65 * mm, sig_y + 6 * mm)
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawString(rx, sig_y + 2 * mm, template.signatory_name or "")
    c.setFont("Helvetica", 7.5)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(rx, sig_y - 3 * mm, template.signatory_title or "")

    # Footer
    if template.footer_text:
        c.setFont("Helvetica", 7)
        c.setFillColorRGB(0.6, 0.6, 0.6)
        c.drawString(rx, 20 * mm, template.footer_text)

    # Bottom border line
    c.setStrokeColorRGB(*secondary)
    c.setLineWidth(1)
    c.line(rx, 16 * mm, rx + rw, 16 * mm)


def _wrap_text(text, max_width, font_name, font_size, c):
    words = text.split()
    lines, line = [], ""
    for w in words:
        test = f"{line} {w}".strip()
        if c.stringWidth(test, font_name, font_size) <= max_width:
            line = test
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


# ---------------------------------------------------------------------------
# Built-in Template: Modern
# ---------------------------------------------------------------------------

def _render_modern(c, template, ctx):
    primary, secondary, accent = _resolve_colors(template)
    W, H = PAGE_W, PAGE_H

    # Full light grey background
    c.setFillColorRGB(0.97, 0.97, 0.98)
    c.rect(0, 0, W, H, stroke=0, fill=1)

    # Top header band with primary color
    header_h = 0.22 * H
    c.setFillColorRGB(*primary)
    c.rect(0, H - header_h, W, header_h, stroke=0, fill=1)

    # Secondary wave accent (simulated with overlapping rounded rect)
    c.setFillColorRGB(*secondary)
    c.roundRect(W * 0.55, H - header_h - 8 * mm,
                W * 0.5, header_h * 0.55, 30, stroke=0, fill=1)

    # Accent dot cluster top-right
    c.setFillColorRGB(*accent, )
    for i in range(3):
        c.circle(W - (10 + i * 7) * mm, H - (8 + i * 5) * mm, 3 - i * 0.5, stroke=0, fill=1)

    # Logo in header
    logo = template.custom_logo or (
        template.organization.orgnaization_logo if template.organization else None
    )
    _draw_logo(c, logo, 12 * mm, H - header_h + 8 * mm, 22 * mm, header_h - 16 * mm)

    # Platform name in header
    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(1, 1, 1)
    c.drawString(38 * mm, H - 12 * mm, "BRIDGECARE")
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.85, 0.95, 1.0)
    c.drawString(38 * mm, H - 19 * mm, ctx["organization_name"])

    # Certificate header
    title = template.header_text or "Certificate of Participation"
    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(1, 1, 1)
    title_w = c.stringWidth(title.upper(), "Helvetica-Bold", 10)
    c.drawString((W - title_w) / 2, H - header_h + 10 * mm, title.upper())

    # Content area
    content_y = H - header_h - 12 * mm

    # Awarded to
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.55, 0.55, 0.55)
    awarded = "presented to"
    aw_w = c.stringWidth(awarded, "Helvetica", 9)
    c.drawString((W - aw_w) / 2, content_y, awarded)

    # Name
    c.setFont("Helvetica-Bold", 24)
    c.setFillColorRGB(*primary)
    name_w = c.stringWidth(ctx["participant_name"], "Helvetica-Bold", 24)
    c.drawString((W - name_w) / 2, content_y - 15 * mm, ctx["participant_name"])

    # Name underline
    c.setStrokeColorRGB(*secondary)
    c.setLineWidth(2)
    c.line((W - name_w) / 2 - 5 * mm, content_y - 17 * mm,
           (W + name_w) / 2 + 5 * mm, content_y - 17 * mm)

    # Body text
    _render_body_text(c, ctx["body_text"],
                      20 * mm, content_y - 34 * mm,
                      W - 40 * mm, line_height=13,
                      font_name="Helvetica", font_size=9.5,
                      color=(0.3, 0.3, 0.3))

    # Program & date strip
    strip_y = 38 * mm
    c.setFillColorRGB(*[min(v + 0.85, 1.0) for v in primary])
    c.roundRect(16 * mm, strip_y - 3 * mm, W - 32 * mm, 12 * mm, 4, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColorRGB(*primary)
    info = f"{ctx['program_name']}    ·    {ctx['start_date']} – {ctx['end_date']}"
    info_w = c.stringWidth(info, "Helvetica-Bold", 8)
    c.drawString((W - info_w) / 2, strip_y + 1 * mm, info)

    # Signatory
    sig_x = 22 * mm
    _draw_signature(c, template.signatory_signature, sig_x, 16 * mm)
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.setLineWidth(0.5)
    c.line(sig_x, 14 * mm, sig_x + 60 * mm, 14 * mm)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawString(sig_x, 10 * mm, template.signatory_name or "")
    c.setFont("Helvetica", 7.5)
    c.setFillColorRGB(0.55, 0.55, 0.55)
    c.drawString(sig_x, 5.5 * mm, template.signatory_title or "")

    # QR code
    if template.show_qr_code:
        _draw_qr_and_code(c, ctx["verification_url"], ctx["verification_code"],
                          W - 28 * mm - 12 * mm, 5 * mm, size=28 * mm)


# ---------------------------------------------------------------------------
# Built-in Template: Elegant
# ---------------------------------------------------------------------------

def _render_elegant(c, template, ctx):
    primary, secondary, accent = _resolve_colors(template)
    W, H = PAGE_W, PAGE_H

    # Cream background
    c.setFillColorRGB(0.99, 0.98, 0.95)
    c.rect(0, 0, W, H, stroke=0, fill=1)

    # Corner decorations (4 corners)
    corner = 18 * mm
    for cx, cy, dx, dy in [
        (0, H - corner, 1, -1),    # top-left
        (W - corner, H - corner, -1, -1),  # top-right
        (0, 0, 1, 1),              # bottom-left
        (W - corner, 0, -1, 1),   # bottom-right
    ]:
        c.setStrokeColorRGB(*accent)
        c.setLineWidth(1.5)
        c.line(cx, cy, cx + dx * corner, cy)
        c.line(cx, cy, cx, cy + dy * corner)
        c.setLineWidth(0.5)
        c.line(cx + dx * 3 * mm, cy + dy * 3 * mm,
               cx + dx * (corner - 1 * mm), cy + dy * 3 * mm)
        c.line(cx + dx * 3 * mm, cy + dy * 3 * mm,
               cx + dx * 3 * mm, cy + dy * (corner - 1 * mm))

    # Double border
    c.setStrokeColorRGB(*primary)
    c.setLineWidth(0.8)
    c.rect(8 * mm, 8 * mm, W - 16 * mm, H - 16 * mm, stroke=1, fill=0)
    c.setLineWidth(0.3)
    c.rect(10 * mm, 10 * mm, W - 20 * mm, H - 20 * mm, stroke=1, fill=0)

    # Top ornament band
    c.setFillColorRGB(*primary)
    c.rect(8 * mm, H - 20 * mm, W - 16 * mm, 0.5 * mm, stroke=0, fill=1)
    c.setFillColorRGB(*accent)
    c.rect(8 * mm, H - 21.5 * mm, W - 16 * mm, 0.5 * mm, stroke=0, fill=1)

    # Logo
    logo = template.custom_logo or (
        template.organization.orgnaization_logo if template.organization else None
    )
    _draw_logo(c, logo, (W - 20 * mm) / 2, H - 38 * mm, 20 * mm, 16 * mm)

    # Certificate title
    title = template.header_text or "Certificate of Participation"
    c.setFont("Helvetica-Bold", 22)
    c.setFillColorRGB(*primary)
    title_w = c.stringWidth(title, "Helvetica-Bold", 22)
    c.drawString((W - title_w) / 2, H - 50 * mm, title)

    # Ornamental divider
    div_y = H - 54 * mm
    c.setStrokeColorRGB(*accent)
    c.setLineWidth(0.7)
    dw = 100 * mm
    c.line((W - dw) / 2, div_y, (W - 20 * mm) / 2, div_y)
    c.circle(W / 2, div_y, 1.5 * mm, stroke=0, fill=1)
    c.setFillColorRGB(*accent)
    c.circle(W / 2, div_y, 1.5 * mm, stroke=0, fill=1)
    c.setStrokeColorRGB(*accent)
    c.line((W + 20 * mm) / 2, div_y, (W + dw) / 2, div_y)

    # "Proudly awarded to"
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    sub = "Proudly awarded to"
    sub_w = c.stringWidth(sub, "Helvetica", 9)
    c.drawString((W - sub_w) / 2, H - 63 * mm, sub)

    # Participant name
    c.setFont("Helvetica-Bold", 21)
    c.setFillColorRGB(*accent)
    name_w = c.stringWidth(ctx["participant_name"], "Helvetica-Bold", 21)
    c.drawString((W - name_w) / 2, H - 76 * mm, ctx["participant_name"])

    # Body text
    _render_body_text(c, ctx["body_text"],
                      22 * mm, H - 96 * mm,
                      W - 44 * mm, line_height=13,
                      font_name="Helvetica", font_size=10,
                      color=(0.3, 0.3, 0.3))

    # Program info
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.55, 0.55, 0.55)
    prog = f"{ctx['program_name']}   ·   {ctx['start_date']} — {ctx['end_date']}"
    prog_w = c.stringWidth(prog, "Helvetica", 9)
    c.drawString((W - prog_w) / 2, H - 112 * mm, prog)

    # Bottom ornament band
    c.setFillColorRGB(*primary)
    c.rect(8 * mm, 20.5 * mm, W - 16 * mm, 0.5 * mm, stroke=0, fill=1)
    c.setFillColorRGB(*accent)
    c.rect(8 * mm, 19 * mm, W - 16 * mm, 0.5 * mm, stroke=0, fill=1)

    # Signatory left
    sig_x = 22 * mm
    _draw_signature(c, template.signatory_signature, sig_x, 26 * mm)
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.setLineWidth(0.5)
    c.line(sig_x, 25 * mm, sig_x + 60 * mm, 25 * mm)
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawString(sig_x, 21 * mm, template.signatory_name or "")
    c.setFont("Helvetica", 7.5)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(sig_x, 16.5 * mm, template.signatory_title or "")

    # Footer text center
    if template.footer_text:
        c.setFont("Helvetica", 7)
        c.setFillColorRGB(0.6, 0.6, 0.6)
        ft_w = c.stringWidth(template.footer_text, "Helvetica", 7)
        c.drawString((W - ft_w) / 2, 15 * mm, template.footer_text)

    # QR code bottom right
    if template.show_qr_code:
        _draw_qr_and_code(c, ctx["verification_url"], ctx["verification_code"],
                          W - 30 * mm - 10 * mm, 14 * mm, size=28 * mm)


# ---------------------------------------------------------------------------
# Image overlay
# ---------------------------------------------------------------------------

def _render_image_overlay(c, template, ctx):
    """Draw text over a user-supplied background image."""
    W, H = PAGE_W, PAGE_H

    # Draw background image
    if template.background_image:
        try:
            bg_path = template.background_image.path
            if os.path.exists(bg_path):
                c.drawImage(ImageReader(bg_path), 0, 0, width=W, height=H,
                            preserveAspectRatio=False)
        except Exception:
            pass

    primary, secondary, accent = _resolve_colors(template)

    # Semi-transparent overlay strip for readability
    c.setFillColorRGB(1, 1, 1)
    c.setStrokeColorRGB(1, 1, 1)
    # No transparency in ReportLab without special setup — we use a solid white band
    c.setFillAlpha(0.7)
    c.rect(0, H * 0.25, W, H * 0.5, stroke=0, fill=1)
    c.setFillAlpha(1.0)

    # Title
    title = template.header_text or "Certificate of Participation"
    c.setFont("Helvetica-Bold", 20)
    c.setFillColorRGB(*primary)
    title_w = c.stringWidth(title, "Helvetica-Bold", 20)
    c.drawString((W - title_w) / 2, H * 0.68, title)

    # Participant name
    c.setFont("Helvetica-Bold", 22)
    c.setFillColorRGB(*accent)
    name_w = c.stringWidth(ctx["participant_name"], "Helvetica-Bold", 22)
    c.drawString((W - name_w) / 2, H * 0.56, ctx["participant_name"])

    # Body text
    _render_body_text(c, ctx["body_text"],
                      20 * mm, H * 0.47,
                      W - 40 * mm, line_height=13,
                      font_name="Helvetica", font_size=9.5,
                      color=(0.2, 0.2, 0.2))

    # Program info
    c.setFont("Helvetica", 8.5)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    prog = f"{ctx['program_name']}   ·   {ctx['start_date']} — {ctx['end_date']}"
    prog_w = c.stringWidth(prog, "Helvetica", 8.5)
    c.drawString((W - prog_w) / 2, H * 0.36, prog)

    # Signatory
    sig_x = 22 * mm
    _draw_signature(c, template.signatory_signature, sig_x, H * 0.14)
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.setLineWidth(0.5)
    c.line(sig_x, H * 0.13, sig_x + 60 * mm, H * 0.13)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawString(sig_x, H * 0.10, template.signatory_name or "")
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(sig_x, H * 0.07, template.signatory_title or "")

    # QR code
    if template.show_qr_code:
        _draw_qr_and_code(c, ctx["verification_url"], ctx["verification_code"],
                          W - 30 * mm - 12 * mm, H * 0.06, size=28 * mm)


# ---------------------------------------------------------------------------
# PDF placeholder filling
# ---------------------------------------------------------------------------

def _render_pdf_placeholder(template, ctx) -> bytes:
    """
    Replace {{placeholder}} tokens in a PDF template via text overlay.
    Strategy: render the original PDF page as background, then overlay text
    via ReportLab for each replacement. For simplicity we use ReportLab to
    overlay replacement text on top of the background PDF.
    """
    from pypdf import PdfReader, PdfWriter
    import io as _io

    if not template.pdf_template:
        return b""

    try:
        pdf_path = template.pdf_template.path
    except Exception:
        return b""

    replacements = {
        "{{participant_name}}": ctx["participant_name"],
        "{{program_name}}": ctx["program_name"],
        "{{organization_name}}": ctx["organization_name"],
        "{{start_date}}": ctx["start_date"],
        "{{end_date}}": ctx["end_date"],
        "{{issue_date}}": ctx["issue_date"],
        "{{verification_code}}": ctx["verification_code"],
    }

    reader = PdfReader(pdf_path)
    writer = PdfWriter()

    for page_idx, page in enumerate(reader.pages):
        # Get page dimensions
        media_box = page.mediabox
        pw = float(media_box.width)
        ph = float(media_box.height)

        # Build overlay with ReportLab
        overlay_buf = _io.BytesIO()
        c = rl_canvas.Canvas(overlay_buf, pagesize=(pw, ph))
        c.setFont("Helvetica", 12)
        c.setFillColorRGB(0.1, 0.1, 0.1)

        # Scan page for placeholder text positions — since PDF text extraction
        # doesn't give reliable positions, we embed replacements as annotations
        # at fixed y positions (center-area). Orgs are expected to leave blank
        # lines or use our placeholder positions defined below.
        # For a robust approach we scan extracted text and redact + replace.
        raw_text = page.extract_text() or ""

        # Build a simple overlay: write each replacement value centered
        # This works best when org marks their PDF with our standard placeholders.
        y_pos = ph * 0.55
        for placeholder, value in replacements.items():
            if placeholder in raw_text:
                c.setFont("Helvetica-Bold", 14)
                value_w = c.stringWidth(value, "Helvetica-Bold", 14)
                c.drawString((pw - value_w) / 2, y_pos, value)
                y_pos -= 20

        # QR code overlay if enabled
        if template.show_qr_code and page_idx == 0:
            qr_buf = _make_qr_image(ctx["verification_url"])
            qr_size = 50
            c.drawImage(ImageReader(qr_buf),
                        pw - qr_size - 10, 10,
                        width=qr_size, height=qr_size,
                        preserveAspectRatio=True)
            c.setFont("Helvetica", 6)
            code_w = c.stringWidth(ctx["verification_code"], "Helvetica", 6)
            c.drawString(pw - qr_size - 10 + (qr_size - code_w) / 2, 5,
                         ctx["verification_code"])

        c.save()
        overlay_buf.seek(0)

        from pypdf import PdfReader as _PR
        overlay_reader = _PR(overlay_buf)
        page.merge_page(overlay_reader.pages[0])
        writer.add_page(page)

    out = _io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out.read()


# ---------------------------------------------------------------------------
# Verification hash + code generation
# ---------------------------------------------------------------------------

def generate_verification_hash(cert_id: str, recipient_email: str, issued_at: str) -> str:
    key = (settings.SECRET_KEY or "bridgecare-cert-key").encode()
    msg = f"{cert_id}:{recipient_email}:{issued_at}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def generate_verification_code(length: int = 10) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

BUILTIN_RENDERERS = {
    "classic": _render_classic,
    "professional": _render_professional,
    "modern": _render_modern,
    "elegant": _render_elegant,
}


def generate_certificate_pdf(certificate) -> bytes:
    """
    Generate a PDF for the given IssuedCertificate instance.
    Returns raw PDF bytes.
    """
    template = certificate.template
    program = certificate.program
    org = program.organization

    start_date = program.start_date.strftime("%d %b %Y") if program.start_date else "—"
    end_date = program.end_date.strftime("%d %b %Y") if program.end_date else start_date

    frontend_url = getattr(settings, "FRONTEND_URL", "https://app.bridgecare.com")
    verification_url = f"{frontend_url}/verify/certificate/{certificate.verification_code}"

    body = template.body_text or ""
    body = (
        body
        .replace("{{participant_name}}", certificate.recipient_name)
        .replace("{{program_name}}", program.program_name)
        .replace("{{organization_name}}", org.organization_name if org else "BridgeCare")
        .replace("{{start_date}}", start_date)
        .replace("{{end_date}}", end_date)
        .replace("{{issue_date}}", certificate.issued_at.strftime("%d %b %Y")
                 if certificate.issued_at else datetime.now().strftime("%d %b %Y"))
        .replace("{{verification_code}}", certificate.verification_code)
    )

    ctx = {
        "participant_name": certificate.recipient_name,
        "program_name": program.program_name,
        "organization_name": org.organization_name if org else "BridgeCare",
        "start_date": start_date,
        "end_date": end_date,
        "issue_date": (certificate.issued_at.strftime("%d %b %Y")
                       if certificate.issued_at else datetime.now().strftime("%d %b %Y")),
        "verification_url": verification_url,
        "verification_code": certificate.verification_code,
        "body_text": body,
    }

    ttype = template.template_type

    if ttype == "pdf_placeholder":
        pdf_bytes = _render_pdf_placeholder(template, ctx)
        if pdf_bytes:
            return pdf_bytes
        # Fall through to classic if no PDF template

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=landscape(A4))

    if ttype == "image_overlay":
        _render_image_overlay(c, template, ctx)
    else:
        style = getattr(template, "builtin_style", "classic") or "classic"
        renderer = BUILTIN_RENDERERS.get(style, _render_classic)
        renderer(c, template, ctx)

    c.save()
    buf.seek(0)
    return buf.read()
