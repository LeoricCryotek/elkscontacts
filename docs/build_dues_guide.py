"""Build the Reception Dues-Payment Quick Guide PDF.

A 4-5 page printable guide for front-desk staff explaining how to record
an Elks member's dues payment in Odoo. The goal of recording in Odoo is
to signal the Secretary to post the payment into CLMS, so the member
doesn't keep getting renewal notices after they've already paid.

Reception's job ends at "Post Payment". They do NOT click "Mark as
Processed in CLMS" — that's the Secretary's responsibility.

Mockup illustrations are drawn directly with ReportLab primitives,
modeled on the six screenshots captured from the live system.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
    KeepTogether,
    Flowable,
)

# --------------------------------------------------------------------------- #
# Color palette taken from Odoo + the user's live screenshots                 #
# --------------------------------------------------------------------------- #
ODOO_PURPLE = colors.HexColor("#714B67")
DEEP_PURPLE = colors.HexColor("#5B3F58")  # app header
ACCENT_GREEN = colors.HexColor("#36B96E")  # avatar/toggles ON
ACCENT_PINK = colors.HexColor("#D03C9C")   # large avatar block
DRAFT_AMBER = colors.HexColor("#F2B233")   # "Pending CLMS Entry" badge
POSTED_BLUE = colors.HexColor("#017E84")   # Posted state badge
SOFT_GREY = colors.HexColor("#F4F4F4")
BORDER_GREY = colors.HexColor("#D0D0D0")
LIGHT_BORDER = colors.HexColor("#E5E5E5")
TEXT_DARK = colors.HexColor("#2D2D2D")
TEXT_MUTED = colors.HexColor("#777777")
HIGHLIGHT_YELLOW = colors.HexColor("#FFF3C7")
HIGHLIGHT_RED = colors.HexColor("#C03030")


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _arrow_down(c, x, y_top, length=0.22 * inch):
    """Draw a red downward arrow whose tip is at (x, y_top - length)."""
    c.setStrokeColor(HIGHLIGHT_RED)
    c.setLineWidth(1.6)
    y_tip = y_top - length
    c.line(x, y_top, x, y_tip)
    c.line(x - 0.05 * inch, y_tip + 0.05 * inch, x, y_tip)
    c.line(x + 0.05 * inch, y_tip + 0.05 * inch, x, y_tip)


def _arrow_left(c, x_right, y, length=0.22 * inch):
    """Red arrow whose tip is at (x_right - length, y), pointing right."""
    c.setStrokeColor(HIGHLIGHT_RED)
    c.setLineWidth(1.6)
    x_tip = x_right - length
    c.line(x_right, y, x_tip, y)
    c.line(x_tip + 0.05 * inch, y + 0.04 * inch, x_tip, y)
    c.line(x_tip + 0.05 * inch, y - 0.04 * inch, x_tip, y)


# --------------------------------------------------------------------------- #
# Mockup flowables — each redraws one of the six live screens                 #
# --------------------------------------------------------------------------- #
class MockAppsMenu(Flowable):
    """Step 1 — Odoo apps menu, vertical list (Discuss is current, Contacts
    is the target). Modeled on the user's first screenshot."""

    def __init__(self, width=2.6 * inch, height=2.2 * inch):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        # Purple header strip with waffle icon + "Discuss" (current app)
        c.setFillColor(DEEP_PURPLE)
        c.rect(0, self.height - 0.40 * inch, self.width, 0.40 * inch, fill=1, stroke=0)
        # Waffle icon = 3x3 grid of squares
        c.setFillColor(colors.white)
        ox, oy = 0.12 * inch, self.height - 0.30 * inch
        for r in range(3):
            for col in range(3):
                c.rect(ox + col * 0.07 * inch, oy + r * 0.07 * inch,
                       0.045 * inch, 0.045 * inch, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(0.42 * inch, self.height - 0.27 * inch, "Discuss")

        # Body: white panel with menu items
        c.setFillColor(colors.white)
        c.setStrokeColor(LIGHT_BORDER)
        c.rect(0, 0, self.width, self.height - 0.40 * inch, fill=1, stroke=1)

        items = ["Discuss", "Calendar", "To-do", "Contacts"]
        item_h = (self.height - 0.55 * inch) / len(items)
        y = self.height - 0.40 * inch - item_h
        for label in items:
            if label == "Discuss":
                c.setFillColor(SOFT_GREY)
                c.rect(0, y, self.width, item_h, fill=1, stroke=0)
            c.setFillColor(TEXT_DARK)
            c.setFont("Helvetica", 11)
            c.drawString(0.20 * inch, y + item_h / 2 - 0.06 * inch, label)
            if label == "Contacts":
                c.setStrokeColor(HIGHLIGHT_RED)
                c.setLineWidth(1.5)
                c.rect(0.14 * inch, y + 0.02 * inch,
                       self.width - 0.28 * inch, item_h - 0.04 * inch,
                       fill=0, stroke=1)
                _arrow_left(c, self.width + 0.20 * inch, y + item_h / 2)
                c.setFillColor(HIGHLIGHT_RED)
                c.setFont("Helvetica-Bold", 9)
                c.drawString(self.width + 0.25 * inch,
                             y + item_h / 2 - 0.06 * inch, "Click")
            y -= item_h


class MockSearchTyped(Flowable):
    """Step 2a — search bar with 'Daniel' typed and the
    'Search Name for: Daniel' dropdown chip."""

    def __init__(self, width=5.0 * inch, height=0.9 * inch):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        # Search input
        c.setFillColor(colors.white)
        c.setStrokeColor(BORDER_GREY)
        c.setLineWidth(1.0)
        c.roundRect(0, self.height - 0.42 * inch,
                    self.width, 0.40 * inch, 3, fill=1, stroke=1)
        # Magnifying glass
        c.setStrokeColor(TEXT_MUTED)
        c.setLineWidth(1.2)
        c.circle(0.20 * inch, self.height - 0.22 * inch, 0.06 * inch, fill=0, stroke=1)
        c.line(0.25 * inch, self.height - 0.27 * inch,
               0.30 * inch, self.height - 0.32 * inch)
        # Typed value
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica", 11)
        c.drawString(0.40 * inch, self.height - 0.27 * inch, "Daniel")

        # Dropdown chip below
        c.setFillColor(SOFT_GREY)
        c.setStrokeColor(BORDER_GREY)
        c.rect(0, 0, self.width, 0.32 * inch, fill=1, stroke=1)
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica", 10)
        c.drawString(0.15 * inch, 0.10 * inch, "Search ")
        c.setFont("Helvetica-Bold", 10)
        c.drawString(0.15 * inch + c.stringWidth("Search ", "Helvetica", 10),
                     0.10 * inch, "Name")
        nbw = c.stringWidth("Search Name", "Helvetica-Bold", 10)
        c.setFont("Helvetica", 10)
        c.drawString(0.15 * inch + nbw, 0.10 * inch, " for: ")
        c.setFillColor(ODOO_PURPLE)
        c.setFont("Helvetica-BoldOblique", 10)
        c.drawString(
            0.15 * inch + nbw + c.stringWidth(" for: ", "Helvetica", 10),
            0.10 * inch, "Daniel",
        )


class MockSearchResult(Flowable):
    """Step 2b — matched contact row with green 'D' avatar."""

    def __init__(self, width=4.0 * inch, height=0.55 * inch):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        c.setFillColor(colors.white)
        c.setStrokeColor(LIGHT_BORDER)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=1)
        # Checkbox
        c.setStrokeColor(TEXT_MUTED)
        c.rect(0.10 * inch, self.height / 2 - 0.07 * inch,
               0.14 * inch, 0.14 * inch, fill=0, stroke=1)
        # Green avatar
        c.setFillColor(ACCENT_GREEN)
        c.roundRect(0.34 * inch, self.height / 2 - 0.15 * inch,
                    0.30 * inch, 0.30 * inch, 3, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(0.49 * inch, self.height / 2 - 0.06 * inch, "D")
        # Name
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica", 11)
        c.drawString(0.78 * inch, self.height / 2 - 0.05 * inch,
                     "Daniel L Santiago")


class MockContactCard(Flowable):
    """Step 3 — the contact form for Daniel L Santiago. Smart-button bar
    with Pay Dues at the front, body with toggles, name, email, phone."""

    def __init__(self, width=6.4 * inch, height=2.9 * inch):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        c.setFillColor(colors.white)
        c.setStrokeColor(LIGHT_BORDER)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=1)

        # Top breadcrumb strip
        c.setFillColor(colors.HexColor("#FAFAFA"))
        c.rect(0, self.height - 0.34 * inch, self.width, 0.34 * inch, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setStrokeColor(BORDER_GREY)
        c.roundRect(0.10 * inch, self.height - 0.27 * inch,
                    0.32 * inch, 0.20 * inch, 2, fill=1, stroke=1)
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica", 8)
        c.drawCentredString(0.26 * inch, self.height - 0.20 * inch, "New")
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 8)
        c.drawString(0.50 * inch, self.height - 0.13 * inch, "Contacts")
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(0.50 * inch, self.height - 0.25 * inch, "Daniel L Santiago")

        # Smart-button bar — Pay Dues (purple) is first
        bar_y = self.height - 0.85 * inch
        bar_h = 0.45 * inch
        pay_x, pay_w = 0.10 * inch, 0.92 * inch
        c.setFillColor(ODOO_PURPLE)
        c.setStrokeColor(ODOO_PURPLE)
        c.roundRect(pay_x, bar_y, pay_w, bar_h, 3, fill=1, stroke=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 9)
        # tiny money icon
        c.rect(pay_x + 0.08 * inch, bar_y + 0.13 * inch,
               0.18 * inch, 0.13 * inch, fill=0, stroke=1)
        c.circle(pay_x + 0.17 * inch, bar_y + 0.20 * inch, 0.03 * inch, fill=0, stroke=1)
        c.drawString(pay_x + 0.32 * inch, bar_y + 0.17 * inch, "Pay Dues")

        # red callout box
        c.setStrokeColor(HIGHLIGHT_RED)
        c.setLineWidth(1.6)
        c.rect(pay_x - 0.04 * inch, bar_y - 0.04 * inch,
               pay_w + 0.08 * inch, bar_h + 0.08 * inch, fill=0, stroke=1)
        _arrow_down(c, pay_x + pay_w / 2, bar_y + bar_h + 0.30 * inch,
                    length=0.22 * inch)
        c.setFillColor(HIGHLIGHT_RED)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawCentredString(pay_x + pay_w / 2,
                            bar_y + bar_h + 0.34 * inch, "Click here")

        # Other smart buttons (greyed)
        others = [
            ("Invoiced", "$ 0.00"),
            ("Meetings", "0"),
            ("Tasks", "0"),
            ("Purchases", "0"),
            ("Mark RTS", ""),
            ("Drop Member", ""),
            ("More v", ""),
        ]
        x = pay_x + pay_w + 0.05 * inch
        for label, val in others:
            w = 0.74 * inch
            c.setFillColor(colors.white)
            c.setStrokeColor(LIGHT_BORDER)
            c.setLineWidth(0.5)
            c.roundRect(x, bar_y, w, bar_h, 3, fill=1, stroke=1)
            c.setFillColor(TEXT_DARK)
            c.setFont("Helvetica-Bold", 7.5)
            c.drawCentredString(x + w / 2, bar_y + 0.28 * inch, label)
            if val:
                c.setFont("Helvetica", 7)
                c.setFillColor(TEXT_MUTED)
                c.drawCentredString(x + w / 2, bar_y + 0.13 * inch, val)
            x += w + 0.04 * inch

        # Body: pink avatar block + toggles + details
        body_y = 0.10 * inch
        body_h = bar_y - 0.10 * inch - 0.10 * inch

        # Pink avatar square
        av_w = 0.78 * inch
        c.setFillColor(ACCENT_PINK)
        c.rect(0.10 * inch, body_y + body_h - av_w,
               av_w, av_w, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 36)
        c.drawCentredString(0.10 * inch + av_w / 2,
                            body_y + body_h - av_w / 2 - 0.12 * inch, "D")

        # Person / Company radio
        x = av_w + 0.30 * inch
        y = body_y + body_h - 0.18 * inch
        c.setStrokeColor(ODOO_PURPLE)
        c.setFillColor(ODOO_PURPLE)
        c.circle(x, y, 0.05 * inch, fill=1, stroke=1)
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica", 8.5)
        c.drawString(x + 0.10 * inch, y - 0.03 * inch, "Person")
        c.setFillColor(colors.white)
        c.setStrokeColor(BORDER_GREY)
        c.circle(x + 0.70 * inch, y, 0.05 * inch, fill=1, stroke=1)
        c.setFillColor(TEXT_DARK)
        c.drawString(x + 0.80 * inch, y - 0.03 * inch, "Company")

        # Toggle row
        y -= 0.30 * inch
        toggle_labels = [
            ("Elk", True),
            ("Volunteer", True),
            ("Customer", True),
            ("Initiate", False),
            ("Guest", False),
        ]
        tx = x
        for label, on in toggle_labels:
            c.setFillColor(TEXT_DARK)
            c.setFont("Helvetica", 8)
            c.drawString(tx, y, label)
            lw = c.stringWidth(label, "Helvetica", 8)
            sw_x = tx + lw + 0.06 * inch
            if on:
                c.setFillColor(ACCENT_GREEN)
            else:
                c.setFillColor(colors.HexColor("#CCCCCC"))
            c.roundRect(sw_x, y - 0.02 * inch, 0.24 * inch, 0.12 * inch,
                        0.06 * inch, fill=1, stroke=0)
            c.setFillColor(colors.white)
            knob_x = sw_x + 0.14 * inch if on else sw_x + 0.02 * inch
            c.circle(knob_x + 0.04 * inch, y + 0.04 * inch, 0.05 * inch,
                     fill=1, stroke=0)
            tx = sw_x + 0.32 * inch

        # "Linked to employee" + Merge Duplicates link
        y -= 0.22 * inch
        c.setFillColor(ACCENT_GREEN)
        c.setFont("Helvetica", 7.5)
        c.drawString(x, y, "✓ Linked to employee.")
        c.setFillColor(ODOO_PURPLE)
        c.drawString(x + 1.0 * inch, y, "↔ Merge Duplicates")

        # Big name
        y -= 0.34 * inch
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(x, y, "Daniel L Santiago")

        # Email + phone
        y -= 0.22 * inch
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 8.5)
        c.drawString(x, y, "✉  dslewiston@gmail.com")
        y -= 0.16 * inch
        c.drawString(x, y, "☎  208 792-7021")


class MockPayDuesForm(Flowable):
    """Step 4 — Pay Dues form in Draft state with Payment Type dropdown
    open showing all five options."""

    def __init__(self, width=6.4 * inch, height=4.5 * inch):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        c.setFillColor(colors.white)
        c.setStrokeColor(LIGHT_BORDER)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=1)

        # Top breadcrumb
        c.setFillColor(colors.HexColor("#FAFAFA"))
        c.rect(0, self.height - 0.34 * inch, self.width, 0.34 * inch, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setStrokeColor(BORDER_GREY)
        c.roundRect(0.10 * inch, self.height - 0.27 * inch,
                    0.32 * inch, 0.20 * inch, 2, fill=1, stroke=1)
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica", 8)
        c.drawCentredString(0.26 * inch, self.height - 0.20 * inch, "New")
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 7.5)
        c.drawString(0.50 * inch, self.height - 0.13 * inch,
                     "Contacts / Daniel L Santiago")
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(0.50 * inch, self.height - 0.25 * inch,
                     "Daniel L Santiago / One Year Dues Payment / 2026-05-13")

        # Post Payment button
        btn_y = self.height - 0.68 * inch
        c.setFillColor(ODOO_PURPLE)
        c.roundRect(0.10 * inch, btn_y, 0.90 * inch, 0.26 * inch, 3,
                    fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(0.55 * inch, btn_y + 0.09 * inch, "Post Payment")
        # red callout
        c.setStrokeColor(HIGHLIGHT_RED)
        c.setLineWidth(1.6)
        c.rect(0.07 * inch, btn_y - 0.04 * inch,
               0.96 * inch, 0.34 * inch, fill=0, stroke=1)
        _arrow_down(c, 0.55 * inch, btn_y + 0.34 * inch + 0.20 * inch,
                    length=0.20 * inch)
        c.setFillColor(HIGHLIGHT_RED)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString(0.55 * inch, btn_y + 0.58 * inch, "Step 5: Click")

        # Cancel button
        c.setFillColor(colors.white)
        c.setStrokeColor(BORDER_GREY)
        c.roundRect(1.10 * inch, btn_y, 0.60 * inch, 0.26 * inch, 3,
                    fill=1, stroke=1)
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica", 9)
        c.drawCentredString(1.40 * inch, btn_y + 0.09 * inch, "Cancel")

        # Draft / Posted state pill
        sx = self.width - 1.7 * inch
        c.setFillColor(SOFT_GREY)
        c.roundRect(sx, btn_y, 1.5 * inch, 0.26 * inch, 13, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.roundRect(sx, btn_y, 0.7 * inch, 0.26 * inch, 13, fill=1, stroke=0)
        c.setStrokeColor(ODOO_PURPLE)
        c.setLineWidth(1)
        c.roundRect(sx, btn_y, 0.7 * inch, 0.26 * inch, 13, fill=0, stroke=1)
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawCentredString(sx + 0.35 * inch, btn_y + 0.09 * inch, "Draft")
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(sx + 1.10 * inch, btn_y + 0.09 * inch, "Posted")

        # Section headers
        sec_y = btn_y - 0.30 * inch
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(0.15 * inch, sec_y, "MEMBER & PAYMENT")
        c.drawString(self.width / 2 + 0.05 * inch, sec_y, "DETAILS")
        c.setStrokeColor(LIGHT_BORDER)
        c.line(0.15 * inch, sec_y - 0.03 * inch,
               self.width / 2 - 0.15 * inch, sec_y - 0.03 * inch)
        c.line(self.width / 2 + 0.05 * inch, sec_y - 0.03 * inch,
               self.width - 0.15 * inch, sec_y - 0.03 * inch)

        # Left column rows
        rows_left = [
            ("Member", "Daniel L Santiago", False),
            ("Member No.", "013767", False),
            ("Currently Paid To", "Apr 1, 2027", False),
            ("Payment Type", "One Year Dues Payment", True),
        ]
        y = sec_y - 0.20 * inch
        for label, val, highlight in rows_left:
            c.setFillColor(TEXT_MUTED)
            c.setFont("Helvetica", 8)
            c.drawString(0.20 * inch, y, label)
            if highlight:
                c.setFillColor(colors.HexColor("#DCE9FA"))
                c.rect(1.20 * inch, y - 0.03 * inch,
                       1.80 * inch, 0.18 * inch, fill=1, stroke=0)
            c.setFillColor(TEXT_DARK)
            c.setFont("Helvetica", 8.5)
            c.drawString(1.22 * inch, y, val)
            if highlight:
                c.setFillColor(TEXT_MUTED)
                c.setFont("Helvetica", 7)
                c.drawString(2.95 * inch, y, "v")
                c.setStrokeColor(HIGHLIGHT_RED)
                c.setLineWidth(1.5)
                c.rect(1.18 * inch, y - 0.05 * inch,
                       1.85 * inch, 0.22 * inch, fill=0, stroke=1)
                c.setFillColor(HIGHLIGHT_RED)
                c.setFont("Helvetica-Bold", 7.5)
                c.drawString(3.10 * inch, y + 0.02 * inch, "Step 4: pick type")
            y -= 0.20 * inch

        # Dropdown menu
        menu_x = 1.20 * inch
        menu_w = 1.95 * inch
        menu_items = [
            "One Year Dues Payment",
            "Life Member Dues Payment",
            "Six Months Dues Payment",
            "Pro-Rated Dues Payment",
            "Custom / Misc. Payment",
        ]
        menu_h = len(menu_items) * 0.16 * inch + 0.06 * inch
        menu_top = y + 0.10 * inch
        c.setFillColor(colors.white)
        c.setStrokeColor(BORDER_GREY)
        c.rect(menu_x, menu_top - menu_h, menu_w, menu_h, fill=1, stroke=1)
        for i, mi in enumerate(menu_items):
            mi_y = menu_top - 0.16 * inch - i * 0.16 * inch
            if i == 0:
                c.setFillColor(SOFT_GREY)
                c.rect(menu_x, mi_y - 0.03 * inch,
                       menu_w, 0.16 * inch, fill=1, stroke=0)
                c.setFillColor(TEXT_DARK)
                c.setFont("Helvetica-Bold", 8.5)
            else:
                c.setFillColor(TEXT_DARK)
                c.setFont("Helvetica", 8.5)
            c.drawString(menu_x + 0.05 * inch, mi_y, mi)

        # Right column rows
        rx = self.width / 2 + 0.10 * inch
        rows_right = [
            ("Transaction Date", "May 13"),
            ("Check Number", ""),
            ("Daily Batch", ""),
            ("Lodge Year", "2026-2027"),
            ("Total Paid", "161.50"),
            ("Journal Entry", ""),
        ]
        y2 = sec_y - 0.20 * inch
        for label, val in rows_right:
            c.setFillColor(TEXT_MUTED)
            c.setFont("Helvetica", 8)
            c.drawString(rx, y2, label)
            c.setFillColor(TEXT_DARK if val else TEXT_MUTED)
            c.setFont("Helvetica-Bold" if label == "Total Paid" else "Helvetica", 8.5)
            c.drawString(rx + 1.20 * inch, y2, val or "—")
            y2 -= 0.20 * inch

        # CLMS PROCESSING strip
        clms_y = 1.40 * inch
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(0.15 * inch, clms_y, "CLMS PROCESSING")
        c.setStrokeColor(LIGHT_BORDER)
        c.line(0.15 * inch, clms_y - 0.03 * inch,
               self.width - 0.15 * inch, clms_y - 0.03 * inch)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 8)
        c.drawString(0.20 * inch, clms_y - 0.22 * inch, "CLMS Status")
        c.setFillColor(DRAFT_AMBER)
        c.roundRect(1.20 * inch, clms_y - 0.28 * inch,
                    1.20 * inch, 0.20 * inch, 8, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(1.80 * inch, clms_y - 0.22 * inch,
                            "Pending CLMS Entry")

        # Line items header
        li_y = 0.85 * inch
        c.setFillColor(SOFT_GREY)
        c.rect(0.15 * inch, li_y - 0.02 * inch,
               self.width - 0.30 * inch, 0.20 * inch, fill=1, stroke=0)
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawString(0.20 * inch, li_y + 0.04 * inch, "Rate / Fee")
        c.drawString(2.10 * inch, li_y + 0.04 * inch, "Description")
        c.drawString(4.10 * inch, li_y + 0.04 * inch, "Default")
        c.drawString(4.85 * inch, li_y + 0.04 * inch, "Amount Paid")

        # Line items
        items = [
            ("[19] Regular - GL Insurance", "23.00", "23.00"),
            ("[20] Regular - GL Per Capita", "6.50", "6.50"),
            ("[21] Regular - State Fees 1", "6.50", "6.50"),
            ("[5F] Regular - Dues 12 Mos", "120.00", "120.00"),
            ("[5G] Regular - The Elks Magazine", "5.50", "5.50"),
            ("[5H] Regular - ENH Per Capita", "0.00", "0.00"),
        ]
        for i, (label, default, paid) in enumerate(items):
            row_y = li_y - 0.18 * inch - i * 0.13 * inch
            c.setFillColor(TEXT_DARK)
            c.setFont("Helvetica", 7.5)
            c.drawString(0.20 * inch, row_y, label)
            c.drawString(2.10 * inch, row_y, label.split(" ", 1)[1])
            c.drawRightString(4.65 * inch, row_y, default)
            c.drawRightString(5.55 * inch, row_y, paid)


class MockPayDuesPosted(Flowable):
    """Step 5 — Posted state with the prominent "Reception: DO NOT CLICK"
    warning over the Mark as Processed in CLMS button."""

    def __init__(self, width=6.4 * inch, height=3.4 * inch):
        super().__init__()
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        c.setFillColor(colors.white)
        c.setStrokeColor(LIGHT_BORDER)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=1)

        # Top breadcrumb
        c.setFillColor(colors.HexColor("#FAFAFA"))
        c.rect(0, self.height - 0.34 * inch, self.width, 0.34 * inch, fill=1, stroke=0)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 7.5)
        c.drawString(0.10 * inch, self.height - 0.13 * inch,
                     "Contacts / Daniel L Santiago")
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(0.10 * inch, self.height - 0.25 * inch,
                     "Daniel L Santiago / One Year Dues Payment / 2026-05-13")

        # Button row
        btn_y = self.height - 0.68 * inch
        # Reset to Draft
        c.setFillColor(colors.white)
        c.setStrokeColor(BORDER_GREY)
        c.roundRect(0.10 * inch, btn_y, 0.90 * inch, 0.26 * inch, 3,
                    fill=1, stroke=1)
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(0.55 * inch, btn_y + 0.09 * inch, "Reset to Draft")

        # Mark as Processed in CLMS button
        c.setFillColor(colors.white)
        c.setStrokeColor(BORDER_GREY)
        c.roundRect(1.10 * inch, btn_y, 1.55 * inch, 0.26 * inch, 3,
                    fill=1, stroke=1)
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(1.87 * inch, btn_y + 0.09 * inch,
                            "Mark as Processed in CLMS")
        # Red X over it
        c.setStrokeColor(HIGHLIGHT_RED)
        c.setLineWidth(2.5)
        c.line(1.10 * inch, btn_y, 2.65 * inch, btn_y + 0.26 * inch)
        c.line(1.10 * inch, btn_y + 0.26 * inch, 2.65 * inch, btn_y)
        c.setFillColor(HIGHLIGHT_RED)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString(1.87 * inch, btn_y - 0.10 * inch,
                            "Reception: DO NOT CLICK")

        # Posted pill
        sx = self.width - 1.7 * inch
        c.setFillColor(SOFT_GREY)
        c.roundRect(sx, btn_y, 1.5 * inch, 0.26 * inch, 13, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setStrokeColor(POSTED_BLUE)
        c.setLineWidth(1)
        c.roundRect(sx + 0.7 * inch, btn_y, 0.8 * inch, 0.26 * inch, 13,
                    fill=1, stroke=1)
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 8.5)
        c.drawCentredString(sx + 0.35 * inch, btn_y + 0.09 * inch, "Draft")
        c.setFillColor(POSTED_BLUE)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawCentredString(sx + 1.10 * inch, btn_y + 0.09 * inch, "Posted")
        _arrow_down(c, sx + 1.10 * inch, btn_y + 0.55 * inch, length=0.20 * inch)
        c.setFillColor(POSTED_BLUE)
        c.setFont("Helvetica-Bold", 7.5)
        c.drawCentredString(sx + 1.10 * inch, btn_y + 0.58 * inch,
                            "Now Posted ✓")

        # Detail rows
        y = btn_y - 0.35 * inch
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(0.15 * inch, y, "DETAILS  (after posting)")
        c.setStrokeColor(LIGHT_BORDER)
        c.line(0.15 * inch, y - 0.03 * inch,
               self.width - 0.15 * inch, y - 0.03 * inch)

        rows = [
            ("Journal Entry", "EJE/2026/0011 / 2026-05-13"),
            ("Total Paid", "161.50"),
            ("Dues Paid-To Before Payment", "Apr 1, 2027"),
            ("Dues Paid-To After Payment", "Apr 1, 2028   <- advanced one year"),
            ("CLMS Status", "Pending CLMS Entry  <- Secretary works from here"),
        ]
        y -= 0.18 * inch
        for label, val in rows:
            c.setFillColor(TEXT_MUTED)
            c.setFont("Helvetica", 8)
            c.drawString(0.20 * inch, y, label)
            c.setFillColor(TEXT_DARK)
            c.setFont("Helvetica", 8)
            c.drawString(2.20 * inch, y, val)
            y -= 0.16 * inch

        # Chatter line
        y -= 0.06 * inch
        c.setFillColor(SOFT_GREY)
        c.rect(0.15 * inch, y - 0.20 * inch,
               self.width - 0.30 * inch, 0.30 * inch, fill=1, stroke=0)
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(0.25 * inch, y - 0.08 * inch,
                     "Activity log:  Administrator - Draft -> Posted   "
                     "Payment Posted: One Year Dues Payment")


# --------------------------------------------------------------------------- #
# Document content                                                            #
# --------------------------------------------------------------------------- #
def build_pdf(out_path):
    doc = SimpleDocTemplate(
        out_path,
        pagesize=LETTER,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        title="Reception - Dues Payment Quick Guide",
        author="Elks Lodge",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"],
                        textColor=ODOO_PURPLE, spaceAfter=4, fontSize=18)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"],
                        textColor=ODOO_PURPLE, spaceBefore=10, spaceAfter=4,
                        fontSize=12.5)
    body = ParagraphStyle("body", parent=styles["BodyText"],
                          fontSize=10, leading=13, textColor=TEXT_DARK)
    caption = ParagraphStyle("caption", parent=styles["BodyText"],
                             fontSize=8.5, leading=11,
                             textColor=TEXT_MUTED,
                             alignment=TA_CENTER, spaceAfter=8)
    callout_yellow = ParagraphStyle("callout_yellow", parent=body,
                                    fontSize=9.5, leading=12,
                                    backColor=HIGHLIGHT_YELLOW,
                                    borderColor=colors.HexColor("#B89500"),
                                    borderWidth=0.5,
                                    borderPadding=6,
                                    spaceBefore=4, spaceAfter=8)
    callout_red = ParagraphStyle("callout_red", parent=body,
                                 fontSize=10, leading=13,
                                 backColor=colors.HexColor("#FBE2E2"),
                                 borderColor=HIGHLIGHT_RED,
                                 borderWidth=1,
                                 borderPadding=8,
                                 spaceBefore=6, spaceAfter=10,
                                 textColor=HIGHLIGHT_RED)

    story = []

    # COVER
    story.append(Paragraph("Reception - Dues Payment Quick Guide", h1))
    story.append(Paragraph(
        "How to record a member's dues payment in Odoo so the Secretary can post "
        "it into CLMS - preventing the member from getting renewal notices "
        "for dues they've already paid.",
        body))
    story.append(Spacer(1, 0.10 * inch))
    story.append(Paragraph(
        "<b>What you do:</b> open the member, click <b>Pay Dues</b>, pick the "
        "payment type, click <b>Post Payment</b>.  <b>That's it.</b><br/>"
        "<b>What you do NOT do:</b> click \"Mark as Processed in CLMS.\"  "
        "That button is for the Secretary only.",
        body))
    story.append(Spacer(1, 0.10 * inch))
    story.append(Paragraph(
        "<b>Audience:</b> Reception, front desk, on-duty volunteer.  "
        "<b>Time:</b> ~1 minute per payment.  "
        "<b>You do NOT need to:</b> calculate the dues amount - Odoo fills it in.",
        callout_yellow))

    # BEFORE YOU START
    story.append(Paragraph("Before you start", h2))
    bullets = [
        "Confirm the member's name (last name is fine for search).",
        "Ask how they're paying: cash, check, or card.",
        "If by check, jot the check number - you'll enter it on the form.",
        "If by card, run it on the Clover terminal AFTER you post the payment.",
    ]
    bullet_data = [[Paragraph("&bull;", body), Paragraph(b, body)] for b in bullets]
    bt = Table(bullet_data, colWidths=[0.20 * inch, 6.85 * inch])
    bt.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(bt)

    # STEP 1
    story.append(Paragraph("Step 1 - Open the Contacts app", h2))
    story.append(Paragraph(
        "Click the <b>waffle icon</b> (top-left, nine little squares) to open the "
        "apps menu. From the dropdown, click <b>Contacts</b>.",
        body))
    story.append(Spacer(1, 0.06 * inch))
    story.append(KeepTogether([
        MockAppsMenu(),
        Spacer(1, 0.04 * inch),
        Paragraph("Figure 1 - Apps menu. Click Contacts.", caption),
    ]))

    # STEP 2
    story.append(Paragraph("Step 2 - Find the member", h2))
    story.append(Paragraph(
        "Type the member's first or last name in the search bar and press "
        "<b>Enter</b>. Odoo shows a dropdown chip like \"Search Name for: Daniel.\"  "
        "Press Enter or click the chip.",
        body))
    story.append(Spacer(1, 0.06 * inch))
    story.append(MockSearchTyped())
    story.append(Spacer(1, 0.06 * inch))
    story.append(Paragraph(
        "Then click the matching member in the results list.", body))
    story.append(Spacer(1, 0.04 * inch))
    story.append(MockSearchResult())
    story.append(Paragraph(
        "Figure 2 - Search by name, then click the matching contact.", caption))

    story.append(Paragraph(
        "<b>Two members with the same name?</b>  The Member # column tells you "
        "which is which. Member numbers are unique. Confirm with the member if "
        "you're unsure.",
        callout_yellow))

    story.append(PageBreak())

    # STEP 3
    story.append(Paragraph("Step 3 - Click Pay Dues", h2))
    story.append(Paragraph(
        "The smart-button bar at the top of the contact has <b>Pay Dues</b> in "
        "purple at the very front (only visible when the <b>Elk</b> toggle is "
        "green). Click it.",
        body))
    story.append(Spacer(1, 0.06 * inch))
    story.append(KeepTogether([
        MockContactCard(),
        Spacer(1, 0.04 * inch),
        Paragraph("Figure 3 - Pay Dues sits at the front of the smart-button "
                  "bar.", caption),
    ]))
    story.append(Paragraph(
        "<b>Pay Dues not visible?</b>  The <b>Elk</b> toggle (top-left, just "
        "below the name) is OFF. Reception cannot flip this toggle - flag the "
        "Secretary.",
        callout_yellow))

    story.append(PageBreak())

    # STEP 4
    story.append(Paragraph("Step 4 - Pick the payment type", h2))
    story.append(Paragraph(
        "Odoo opens a draft payment record pre-filled for this member. The "
        "amount and line items are already calculated. You only need to "
        "confirm the <b>Payment Type</b> and, for checks, enter the "
        "<b>Check Number</b>.",
        body))

    pt_data = [
        [Paragraph("<b>Payment Type</b>", body),
         Paragraph("<b>When to pick it</b>", body),
         Paragraph("<b>Typical total</b>", body)],
        [Paragraph("One Year Dues Payment", body),
         Paragraph("Annual renewal - the default. Most payments.", body),
         Paragraph("$161.50", body)],
        [Paragraph("Life Member Dues Payment", body),
         Paragraph("Member is on the Life roster (reduced annual rate).", body),
         Paragraph("$50.00", body)],
        [Paragraph("Six Months Dues Payment", body),
         Paragraph("Half-year payment - rare; only if member asks.", body),
         Paragraph("~$80.75", body)],
        [Paragraph("Pro-Rated Dues Payment", body),
         Paragraph("New member joining mid-lodge-year. Secretary usually "
                   "handles these.", body),
         Paragraph("varies", body)],
        [Paragraph("Custom / Misc. Payment", body),
         Paragraph("Anything else - corrections, fees, etc. Ask Secretary "
                   "first.", body),
         Paragraph("varies", body)],
    ]
    pt_tbl = Table(pt_data, colWidths=[1.55 * inch, 4.0 * inch, 1.0 * inch])
    pt_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ODOO_PURPLE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT_GREY]),
    ]))
    story.append(Spacer(1, 0.06 * inch))
    story.append(pt_tbl)
    story.append(Spacer(1, 0.08 * inch))
    story.append(KeepTogether([
        MockPayDuesForm(),
        Spacer(1, 0.04 * inch),
        Paragraph("Figure 4 - Pay Dues form (Draft). Pick the type from the "
                  "dropdown, then click Post Payment.", caption),
    ]))

    story.append(PageBreak())

    # STEP 5
    story.append(Paragraph("Step 5 - Click Post Payment", h2))
    story.append(Paragraph(
        "After picking the type, click the purple <b>Post Payment</b> button at "
        "the top-left. The state changes from <b>Draft</b> to <b>Posted</b>:",
        body))
    bullets5 = [
        "<b>Total Paid</b> is finalized (e.g. $161.50 for a Regular One Year).",
        "<b>Journal Entry</b> gets a number (e.g. EJE/2026/0011) - Odoo has "
        "recorded the income.",
        "<b>Dues Paid-To After Payment</b> jumps forward (e.g. Apr 1 2027 -> "
        "Apr 1 2028). The member is now current.",
        "<b>CLMS Status</b> stays <b>\"Pending CLMS Entry\"</b> - that's the "
        "Secretary's signal to do their part.",
    ]
    bullet_data5 = [[Paragraph("&bull;", body), Paragraph(b, body)] for b in bullets5]
    bt5 = Table(bullet_data5, colWidths=[0.20 * inch, 6.85 * inch])
    bt5.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(bt5)

    story.append(Spacer(1, 0.06 * inch))
    story.append(KeepTogether([
        MockPayDuesPosted(),
        Spacer(1, 0.04 * inch),
        Paragraph("Figure 5 - Posted state. State pill flipped to Posted, "
                  "Dues Paid-To advanced one year, Journal Entry created.",
                  caption),
    ]))

    story.append(Paragraph(
        "<b>STOP HERE.</b>  Do NOT click \"Mark as Processed in CLMS.\"  "
        "That button is the Secretary's checkmark, used after they enter the "
        "payment at Grand Lodge. If Reception clicks it, the Secretary loses "
        "the signal that this payment needs CLMS attention - and the member "
        "may keep getting renewal notices.",
        callout_red))

    story.append(PageBreak())

    # STEP 6
    story.append(Paragraph("Step 6 - Take the money, hand off the member", h2))
    handoff = [
        "<b>Cash:</b> put it in the reception lockbox.",
        "<b>Check:</b> the Check Number you entered on the form is the audit "
        "trail; put the physical check in the lockbox.",
        "<b>Card:</b> run it on the Clover terminal now. Clover syncs back to "
        "Odoo automatically - no extra entry.",
        "Hand the member a receipt if your lodge issues one (print or email "
        "from the Pay Dues form).",
    ]
    handoff_data = [[Paragraph("&bull;", body), Paragraph(b, body)] for b in handoff]
    ht = Table(handoff_data, colWidths=[0.20 * inch, 6.85 * inch])
    ht.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(ht)

    # WHAT HAPPENS NEXT
    story.append(Paragraph("What happens next", h2))
    story.append(Paragraph(
        "The Secretary's CLMS queue shows every Posted payment with "
        "<b>CLMS Status = Pending CLMS Entry</b>. The Secretary logs into the "
        "Grand Lodge CLMS website, records the payment there, then comes back "
        "to Odoo and clicks <b>Mark as Processed in CLMS</b> - which is what "
        "stops the renewal notices to the member.",
        body))
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph(
        "Your job is done at <b>Post Payment</b>. If you accidentally close "
        "the form without posting, the payment is lost - the member still owes. "
        "When in doubt, re-open the contact and check the <b>Dues Paid Through</b> "
        "date.",
        body))

    # TROUBLESHOOTING
    story.append(Paragraph("Quick troubleshooting", h2))
    trouble = [
        ("<b>Pay Dues button missing</b>",
         "The <b>Elk</b> toggle is OFF on this contact. Flag the Secretary."),
        ("<b>\"The Elks FRS module must be installed\"</b>",
         "elksfrs is disabled. Call the Secretary or system admin. The "
         "payment did NOT save - do not retry until elksfrs is back."),
        ("<b>Total Paid shows $0.00</b>",
         "Wrong Payment Type, or no line items pulled in. Cancel, re-open "
         "the form, double-check the type. If still $0, flag the Secretary."),
        ("<b>Member is suspended or dropped</b>",
         "Red <b>Suspended</b> or <b>Dropped</b> ribbon on the contact. Do "
         "NOT collect dues. Direct them to the Secretary or a Trustee."),
        ("<b>I clicked Mark as Processed in CLMS by mistake</b>",
         "Tell the Secretary right away. They can reverse it from the "
         "Secretary dashboard."),
        ("<b>Wrong amount</b>",
         "If Total Paid looks completely wrong (e.g. $0 for Regular, $161 "
         "for Life), STOP - do not Post. Flag the Secretary."),
    ]
    trouble_data = [
        [Paragraph("<b>Symptom</b>", body), Paragraph("<b>What to do</b>", body)]
    ]
    for sym, fix in trouble:
        trouble_data.append([Paragraph(sym, body), Paragraph(fix, body)])
    tt = Table(trouble_data, colWidths=[2.4 * inch, 4.65 * inch])
    tt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ODOO_PURPLE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tt)

    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(
        "<i>Document version: 2026-05-13.  Source: ElksContacts v19.0.3.9 + "
        "elksfrs.  Update when the Pay Dues workflow changes.</i>",
        ParagraphStyle("footer", parent=body, fontSize=8,
                       textColor=TEXT_MUTED, alignment=TA_CENTER)))

    doc.build(story)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "Reception_Dues_Payment_Guide.pdf"
    build_pdf(out)
    print(f"Wrote {out}")
