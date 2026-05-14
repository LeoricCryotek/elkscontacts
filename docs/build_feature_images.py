"""Generate mockup feature screenshots for the elkscontacts module
description page (static/description/).

Outputs:
  banner.png                  — wide hero (1024x512)
  feature_smart_buttons.png   — smart-button bar with Pay Dues at front
  feature_toggles.png         — Elk / Volunteer / Customer toggles row
  feature_clms_tab.png        — CLMS tab fields layout

Style matches the Odoo 19 purple theme and the live screenshots the
user provided. All images are pure PIL primitives, no external fonts.
"""

from PIL import Image, ImageDraw, ImageFont
import os
import sys

# Colors
PURPLE_DEEP = (91, 63, 88)        # app header
PURPLE = (113, 75, 103)           # primary
PURPLE_LIGHT = (236, 230, 240)    # selected row
GREEN = (54, 185, 110)            # toggle ON, avatar
PINK = (208, 60, 156)             # large avatar
AMBER = (242, 178, 51)            # pending CLMS badge
WHITE = (255, 255, 255)
SOFT_GREY = (244, 244, 244)
BORDER = (208, 208, 208)
LIGHT_BORDER = (229, 229, 229)
DARK = (45, 45, 45)
MUTED = (119, 119, 119)
RED = (192, 48, 48)
GOLD = (184, 149, 0)


def _font(size, bold=False):
    """Try a few common system fonts; fall back to default."""
    candidates_bold = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ]
    candidates_reg = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for p in (candidates_bold if bold else candidates_reg):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size, index=1 if bold and p.endswith(".ttc") else 0)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_toggle(d, x, y, on=True, w=28, h=14):
    """Pill-shaped toggle switch."""
    color = GREEN if on else (204, 204, 204)
    d.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=color)
    knob_r = (h - 2) // 2
    knob_cx = x + w - knob_r - 2 if on else x + knob_r + 2
    knob_cy = y + h // 2
    d.ellipse(
        (knob_cx - knob_r, knob_cy - knob_r, knob_cx + knob_r, knob_cy + knob_r),
        fill=WHITE,
    )


def _draw_smart_button(d, x, y, w, h, label, value=None, highlight=False, icon=None):
    """One smart button in the button bar."""
    if highlight:
        d.rounded_rectangle((x, y, x + w, y + h), radius=4, fill=PURPLE)
        text_color = WHITE
    else:
        d.rounded_rectangle((x, y, x + w, y + h), radius=4,
                            outline=LIGHT_BORDER, width=1, fill=WHITE)
        text_color = DARK

    # Icon area on the left
    if icon == "money":
        d.rectangle((x + 8, y + h // 2 - 4, x + 24, y + h // 2 + 6),
                    outline=text_color, width=1)
        d.ellipse((x + 13, y + h // 2 - 2, x + 19, y + h // 2 + 4),
                  outline=text_color, width=1)
    elif icon == "doc":
        d.rectangle((x + 10, y + h // 2 - 6, x + 22, y + h // 2 + 6),
                    outline=text_color, width=1)
        d.line((x + 12, y + h // 2 - 2, x + 20, y + h // 2 - 2),
               fill=text_color, width=1)
        d.line((x + 12, y + h // 2 + 1, x + 20, y + h // 2 + 1),
               fill=text_color, width=1)

    # Text
    label_x = x + 30 if icon else x + 8
    f_label = _font(11, bold=True)
    f_value = _font(10)
    if value:
        d.text((label_x, y + 6), label, fill=text_color, font=f_label)
        d.text((label_x, y + 22), value, fill=text_color, font=f_value)
    else:
        # center vertically
        d.text((label_x, y + h // 2 - 7), label, fill=text_color, font=f_label)


# --------------------------------------------------------------------------- #
def make_banner(out_path):
    """Wide hero banner: 1024x512.

    Shows the elkscontacts logo + tagline + a compact preview of the
    contact form with smart buttons.
    """
    W, H = 1024, 512
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    # Left half: purple panel with logo, title, subtitle
    d.rectangle((0, 0, W // 2, H), fill=PURPLE_DEEP)
    # Decorative "elk antler" symbol — stylized
    cx, cy = W // 4, 160
    d.ellipse((cx - 70, cy - 70, cx + 70, cy + 70), outline=WHITE, width=4)
    # Crown of antlers using lines
    for ang in [(-50, -30), (-30, -10), (-10, 10), (10, 30), (30, 50)]:
        a1, a2 = ang
        import math
        x1 = cx + 60 * math.cos(math.radians(a1 - 90))
        y1 = cy + 60 * math.sin(math.radians(a1 - 90))
        x2 = cx + 90 * math.cos(math.radians(a2 - 90))
        y2 = cy + 90 * math.sin(math.radians(a2 - 90))
        d.line((x1, y1, x2, y2), fill=WHITE, width=3)

    d.text((W // 4 - 130, 250), "Elks Contacts", fill=WHITE, font=_font(36, bold=True))
    d.text((W // 4 - 215, 295), "Smarter member records for Odoo 19",
           fill=(230, 220, 235), font=_font(16))
    d.text((W // 4 - 175, 340), "CLMS-aware  •  Officer tracking",
           fill=(200, 180, 215), font=_font(13))
    d.text((W // 4 - 175, 360), "Volunteer / HR sync  •  Dues & Drop",
           fill=(200, 180, 215), font=_font(13))
    d.text((W // 4 - 175, 380), "Membership applications & ballots",
           fill=(200, 180, 215), font=_font(13))

    # Right half: preview of the contact form
    panel_x = W // 2 + 40
    panel_w = W - panel_x - 40
    panel_y = 50
    panel_h = H - 100

    # Card background
    d.rounded_rectangle((panel_x, panel_y, panel_x + panel_w, panel_y + panel_h),
                        radius=8, fill=WHITE, outline=BORDER, width=1)

    # Header strip
    d.rectangle((panel_x + 1, panel_y + 1, panel_x + panel_w - 1, panel_y + 36),
                fill=(250, 250, 250))
    d.text((panel_x + 12, panel_y + 10), "Daniel L Santiago",
           fill=DARK, font=_font(13, bold=True))

    # Smart-button bar
    bar_y = panel_y + 50
    bar_h = 50
    btn_x = panel_x + 12
    _draw_smart_button(d, btn_x, bar_y, 90, bar_h,
                       "Pay Dues", highlight=True, icon="money")
    btn_x += 96
    for label, val in [("Invoiced", "$ 0.00"), ("Meetings", "0"),
                       ("Tasks", "0"), ("Mark RTS", None)]:
        _draw_smart_button(d, btn_x, bar_y, 88, bar_h, label, value=val)
        btn_x += 94

    # Avatar + name + toggles in body
    body_y = bar_y + 70
    d.rectangle((panel_x + 12, body_y, panel_x + 80, body_y + 68), fill=PINK)
    d.text((panel_x + 35, body_y + 12), "D", fill=WHITE, font=_font(36, bold=True))

    # Toggles
    tog_x = panel_x + 92
    tog_y = body_y + 8
    for i, (label, on) in enumerate(
        [("Elk", True), ("Volunteer", True), ("Customer", True),
         ("Initiate", False), ("Guest", False)]
    ):
        d.text((tog_x, tog_y), label, fill=DARK, font=_font(10, bold=True))
        tw = d.textlength(label, font=_font(10, bold=True))
        _draw_toggle(d, tog_x + int(tw) + 4, tog_y + 2, on=on)
        tog_x += int(tw) + 42

    d.text((panel_x + 92, body_y + 30), "Daniel L Santiago",
           fill=DARK, font=_font(18, bold=True))
    d.text((panel_x + 92, body_y + 54), "Member No. 013767  •  Dues paid through Apr 1, 2028",
           fill=MUTED, font=_font(10))

    img.save(out_path, "PNG", optimize=True)


def make_smart_buttons_feature(out_path):
    """800x220 image showing the smart-button bar with Pay Dues highlighted."""
    W, H = 900, 220
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    # Header
    d.text((20, 16), "Smart-button bar — quick actions on every member",
           fill=PURPLE, font=_font(15, bold=True))
    d.text((20, 38), "Reception clicks Pay Dues to record a renewal. Secretary uses Mark RTS, "
                    "Drop Member, etc.", fill=MUTED, font=_font(11))

    # Frame
    frame_y = 80
    d.rounded_rectangle((20, frame_y, W - 20, frame_y + 110),
                        radius=6, fill=(252, 252, 252),
                        outline=LIGHT_BORDER, width=1)

    # Buttons
    bar_y = frame_y + 22
    bar_h = 64
    btn_x = 36

    items = [
        ("Pay Dues", None, True, "money"),
        ("Invoiced", "$ 0.00", False, None),
        ("Meetings", "0", False, None),
        ("Tasks", "0", False, None),
        ("Purchases", "0", False, None),
        ("Mark RTS", None, False, None),
        ("Drop Member", None, False, None),
        ("More v", None, False, None),
    ]
    for label, val, hi, icon in items:
        w = 100 if hi else 95
        _draw_smart_button(d, btn_x, bar_y, w, bar_h, label,
                           value=val, highlight=hi, icon=icon)
        btn_x += w + 6

    # Red callout under Pay Dues
    d.rectangle((33, bar_y - 4, 33 + 104, bar_y + bar_h + 4),
                outline=RED, width=2)
    d.line((85, bar_y + bar_h + 8, 85, bar_y + bar_h + 22), fill=RED, width=2)
    d.polygon([(80, bar_y + bar_h + 18), (90, bar_y + bar_h + 18),
               (85, bar_y + bar_h + 22)], fill=RED)

    img.save(out_path, "PNG", optimize=True)


def make_toggles_feature(out_path):
    """800x180 image showing the contact-type toggle row."""
    W, H = 900, 180
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    d.text((20, 16), "Contact-type toggles — one contact, many roles",
           fill=PURPLE, font=_font(15, bold=True))
    d.text((20, 38), "Tag any contact as Elk, Volunteer, Customer, Initiate, or Guest. "
                    "Toggles unlock the related views, smart buttons, and tabs.",
           fill=MUTED, font=_font(11))

    # Frame
    d.rounded_rectangle((20, 75, W - 20, 165), radius=6,
                        fill=(252, 252, 252), outline=LIGHT_BORDER, width=1)

    # Person/Company radio
    d.ellipse((40, 110, 56, 126), outline=PURPLE, width=2)
    d.ellipse((44, 114, 52, 122), fill=PURPLE)
    d.text((60, 110), "Person", fill=DARK, font=_font(12, bold=True))
    d.ellipse((130, 110, 146, 126), outline=BORDER, width=2)
    d.text((150, 110), "Company", fill=DARK, font=_font(12))

    # Toggles row
    tog_x = 240
    for label, on in [("Elk", True), ("Volunteer", True), ("Customer", True),
                      ("Initiate", False), ("Guest", False)]:
        d.text((tog_x, 112), label, fill=DARK, font=_font(12, bold=True))
        tw = d.textlength(label, font=_font(12, bold=True))
        _draw_toggle(d, tog_x + int(tw) + 6, 113, on=on, w=32, h=16)
        tog_x += int(tw) + 70

    img.save(out_path, "PNG", optimize=True)


def make_clms_tab_feature(out_path):
    """900x320 image showing the CLMS tab on a contact."""
    W, H = 900, 320
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    d.text((20, 16), "CLMS tab — every Grand Lodge field on one contact",
           fill=PURPLE, font=_font(15, bold=True))
    d.text((20, 38), "Member number, dues paid-through date, address (CASS-validated), suspension/drop "
                    "history, member-history events.", fill=MUTED, font=_font(11))

    # Tab strip
    tab_y = 78
    d.line((20, tab_y + 28, W - 20, tab_y + 28), fill=LIGHT_BORDER, width=1)
    # CLMS tab (selected)
    d.text((40, tab_y + 8), "CLMS", fill=PURPLE, font=_font(12, bold=True))
    d.line((36, tab_y + 28, 86, tab_y + 28), fill=PURPLE, width=3)
    # Other tabs (faded)
    d.text((110, tab_y + 8), "Elks History", fill=MUTED, font=_font(12))
    d.text((220, tab_y + 8), "Lodge Records", fill=MUTED, font=_font(12))
    d.text((340, tab_y + 8), "Contacts & Addresses", fill=MUTED, font=_font(12))
    d.text((500, tab_y + 8), "Sales & Purchase", fill=MUTED, font=_font(12))

    # Content panel
    panel_y = tab_y + 40
    d.rounded_rectangle((20, panel_y, W - 20, H - 20), radius=4,
                        fill=(252, 252, 252), outline=LIGHT_BORDER, width=1)

    # Two columns of fields
    fields_left = [
        ("Membership", None),
        ("Record ID", "1234567"),
        ("Member Number", "013767"),
        ("Lodge Number", "2756"),
        ("Lodge Name", "Lewiston Elks #896"),
        ("Dues Paid To", "Apr 1, 2028"),
        ("Delinquent Months", "0"),
    ]
    fields_right = [
        ("Name", None),
        ("First Name", "Daniel"),
        ("Middle Name", "L"),
        ("Last Name", "Santiago"),
        ("Date of Birth", "Apr 22, 1972"),
        ("Date Initiated", "Aug 15, 2018"),
        ("E-Notices OK", "Yes"),
    ]
    fy = panel_y + 14
    col_w = (W - 60) // 2
    for col_x, fields in [(40, fields_left), (40 + col_w, fields_right)]:
        y = fy
        for label, val in fields:
            if val is None:
                # Section header
                d.text((col_x, y), label, fill=PURPLE, font=_font(11, bold=True))
                d.line((col_x, y + 18, col_x + col_w - 60, y + 18),
                       fill=LIGHT_BORDER, width=1)
                y += 26
            else:
                d.text((col_x + 4, y), label, fill=MUTED, font=_font(10))
                d.text((col_x + 130, y), val, fill=DARK, font=_font(10, bold=True))
                y += 22

    img.save(out_path, "PNG", optimize=True)


if __name__ == "__main__":
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out_dir, exist_ok=True)
    make_banner(os.path.join(out_dir, "banner.png"))
    make_smart_buttons_feature(
        os.path.join(out_dir, "feature_smart_buttons.png"))
    make_toggles_feature(os.path.join(out_dir, "feature_toggles.png"))
    make_clms_tab_feature(os.path.join(out_dir, "feature_clms_tab.png"))
    print("Wrote:")
    for f in ("banner.png", "feature_smart_buttons.png",
              "feature_toggles.png", "feature_clms_tab.png"):
        print(" ", os.path.join(out_dir, f))
