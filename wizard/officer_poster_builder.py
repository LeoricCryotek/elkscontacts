# -*- coding: utf-8 -*-
"""Officer Photo Poster builder.

Pure Pillow image-compositing logic with **no Odoo imports** so it can be
unit-tested standalone.  Produces a print-ready PDF of the lodge officers
laid out as a photo board:

    Header band ....... Elks emblem (top-left) + gold lodge title + year
    Row 1 ............. Treasurer  |  EXALTED RULER (large)  |  Secretary
    Row 2 ............. Leading Knight | Loyal Knight | Lecturing Knight
    Row 3 ............. Trustees (Board Chair + 1y..5y, whatever exists)
    Row 4 ............. Everyone else (appointed officers, tiler, etc.)

Each photo gets a translucent black bar across its lower edge with the
officer's name (gold, bold) and title (white).

The default canvas is 47" x 29" at 150 DPI (7050 x 4350 px), saved as a
single-page PDF whose physical page size is exactly 47" x 29".
"""
import io
import os

from PIL import Image, ImageDraw, ImageFont

# ----------------------------------------------------------------------
# Palette
# ----------------------------------------------------------------------
BLACK = (12, 12, 14)
GOLD = (201, 162, 39)          # lodge gold
GOLD_BRIGHT = (224, 188, 70)
WHITE = (245, 245, 245)
BAR_RGBA = (0, 0, 0, 170)      # translucent title bar
PLACEHOLDER_BG = (38, 42, 54)
PLACEHOLDER_FG = (120, 128, 145)

# Position grouping ----------------------------------------------------
KNIGHTS = ['leading_knight', 'loyal_knight', 'lecturing_knight']
TRUSTEES = ['boardchair', 'trustee1y', 'trustee2y',
            'trustee3y', 'trustee4y', 'trustee5y']
# Positions that are placed explicitly; everything else falls to "the rest".
TOP_ROW = ['treasurer', 'exalted_ruler', 'secretary']


def _load_font(font_dir, filename, size):
    """Load a bundled TrueType font; fall back to PIL default on failure."""
    try:
        return ImageFont.truetype(os.path.join(font_dir, filename), size)
    except Exception:
        try:
            return ImageFont.truetype(filename, size)
        except Exception:
            return ImageFont.load_default()


def _open_photo(photo_bytes):
    """Return an RGB PIL image from raw bytes, or None."""
    if not photo_bytes:
        return None
    try:
        img = Image.open(io.BytesIO(photo_bytes))
        img.load()
        return img.convert('RGB')
    except Exception:
        return None


def _cover_crop(img, target_w, target_h):
    """Scale + center-crop an image to exactly fill target box (like CSS
    background-size: cover)."""
    target_w, target_h = int(target_w), int(target_h)
    src_w, src_h = img.size
    if src_w == 0 or src_h == 0:
        return Image.new('RGB', (target_w, target_h), PLACEHOLDER_BG)
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = max(1, int(src_w * scale)), max(1, int(src_h * scale))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def _contain_fit(img, box_w, box_h, bg=BLACK):
    """Scale an image to fit *inside* box_w x box_h without cropping
    (like CSS object-fit: contain), centered on a bg-filled canvas.
    Used for logos/emblems so the whole graphic always shows."""
    box_w, box_h = int(box_w), int(box_h)
    src_w, src_h = img.size
    out = Image.new('RGB', (box_w, box_h), bg)
    if src_w == 0 or src_h == 0:
        return out
    scale = min(box_w / src_w, box_h / src_h)
    new_w, new_h = max(1, int(src_w * scale)), max(1, int(src_h * scale))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    out.paste(img, ((box_w - new_w) // 2, (box_h - new_h) // 2))
    return out


def _initials(name):
    parts = [p for p in (name or '').replace('.', ' ').split() if p]
    if not parts:
        return '?'
    if len(parts) == 1:
        return parts[0][:1].upper()
    return (parts[0][:1] + parts[-1][:1]).upper()


def _placeholder(target_w, target_h, name, fonts):
    """Build a placeholder tile (initials in a circle) when no photo."""
    target_w, target_h = int(target_w), int(target_h)
    tile = Image.new('RGB', (target_w, target_h), PLACEHOLDER_BG)
    d = ImageDraw.Draw(tile)
    r = int(min(target_w, target_h) * 0.28)
    cx, cy = target_w // 2, int(target_h * 0.42)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=PLACEHOLDER_FG, width=max(3, r // 18))
    txt = _initials(name)
    f = fonts['placeholder']
    bbox = d.textbbox((0, 0), txt, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text((cx - tw / 2 - bbox[0], cy - th / 2 - bbox[1]), txt,
           fill=PLACEHOLDER_FG, font=f)
    return tile


def _fit_font(draw, text, base_font_path, font_dir, max_w, start_size, min_size=14):
    """Return a font sized so `text` fits within max_w (shrinks if needed)."""
    size = start_size
    while size > min_size:
        f = _load_font(font_dir, base_font_path, size)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return _load_font(font_dir, base_font_path, min_size)


def _draw_tile(canvas, box, officer, fonts, font_dir, emphasize=False):
    """Render one officer photo tile with title bar into `box` on canvas.

    box = (x, y, w, h).  officer = dict(name, position_label, photo, gender).
    """
    x, y, w, h = (int(v) for v in box)
    name = officer.get('name') or ''
    title = officer.get('position_label') or ''
    photo = _open_photo(officer.get('photo'))

    if photo is not None:
        tile = _cover_crop(photo, w, h)
    else:
        tile = _placeholder(w, h, name, fonts)

    # Gold frame
    frame = Image.new('RGB', (w, h), GOLD)
    pad = max(4, int(min(w, h) * 0.012))
    inner = tile.resize((w - 2 * pad, h - 2 * pad), Image.LANCZOS)
    frame.paste(inner, (pad, pad))
    tile = frame

    # Title bar across the lower edge
    bar_h = max(56, int(h * (0.20 if emphasize else 0.17)))
    bar = Image.new('RGBA', (w, bar_h), BAR_RGBA)
    tile_rgba = tile.convert('RGBA')
    tile_rgba.alpha_composite(bar, (0, h - bar_h))
    tile = tile_rgba.convert('RGB')

    d = ImageDraw.Draw(tile)
    inner_w = w - 2 * pad - int(w * 0.04)
    tx = pad + int(w * 0.02)

    name_size = int(bar_h * (0.42 if emphasize else 0.40))
    title_size = int(bar_h * (0.30 if emphasize else 0.30))
    name_font = _fit_font(d, name, 'DejaVuSans-Bold.ttf', font_dir,
                          inner_w, name_size)
    title_font = _fit_font(d, title, 'DejaVuSansCondensed-Bold.ttf', font_dir,
                           inner_w, title_size)

    name_y = h - bar_h + int(bar_h * 0.12)
    title_y = h - bar_h + int(bar_h * 0.56)
    d.text((tx, name_y), name, fill=GOLD_BRIGHT, font=name_font)
    d.text((tx, title_y), title, fill=WHITE, font=title_font)

    canvas.paste(tile, (x, y))


def _row_boxes(x0, x1, y, cell_h, count, gap):
    """Evenly spaced equal cells across [x0, x1] at vertical y."""
    if count <= 0:
        return []
    total_gap = gap * (count - 1)
    cell_w = (x1 - x0 - total_gap) / count
    boxes = []
    cx = x0
    for _ in range(count):
        boxes.append((cx, y, cell_w, cell_h))
        cx += cell_w + gap
    return boxes


def _fixed_row_boxes(canvas_w, y, count, tile_w, tile_h, gap):
    """A row of `count` fixed-size (tile_w x tile_h) tiles, centered
    horizontally on the full canvas width.  Leaves blank space on the
    sides rather than stretching the tiles."""
    if count <= 0:
        return []
    row_w = count * tile_w + (count - 1) * gap
    start_x = (canvas_w - row_w) / 2.0
    return [(start_x + i * (tile_w + gap), y, tile_w, tile_h)
            for i in range(count)]


def build_officer_poster(officers, emblem_bytes, lodge_name, lodge_number,
                         lodge_year, font_dir, dpi=150,
                         width_in=47.0, height_in=29.0):
    """Build the poster and return single-page PDF bytes.

    officers: list of dict(position_key, position_label, name, photo, gender)
    """
    W = int(round(width_in * dpi))
    H = int(round(height_in * dpi))
    canvas = Image.new('RGB', (W, H), BLACK)
    draw = ImageDraw.Draw(canvas)

    margin = int(W * 0.022)
    gap = int(W * 0.014)

    fonts = {
        'placeholder': _load_font(font_dir, 'DejaVuSans-Bold.ttf', int(H * 0.06)),
    }

    # ---- index officers by position ----
    by_pos = {}
    for o in officers:
        by_pos.setdefault(o.get('position_key'), []).append(o)

    def take(pos):
        lst = by_pos.get(pos)
        if lst:
            return lst[0]
        return None

    used_keys = set()

    # ================= HEADER BAND =================
    # Kept compact so four rows of 6"-tall photo tiles fit on a 29" sheet.
    header_h = int(H * 0.10)
    # Emblem in BOTH top corners — contain-fit (no crop) with clear
    # padding so the whole logo always shows and never touches the edge.
    if emblem_bytes:
        emb = _open_photo(emblem_bytes)
        if emb is not None:
            es = int(header_h * 0.78)
            emb = _contain_fit(emb, es, es)
            emb_y = int((header_h - es) / 2)
            pad = int(0.15 * dpi)
            canvas.paste(emb, (margin + pad, emb_y))                 # left
            canvas.paste(emb, (W - margin - pad - es, emb_y))        # right
    # Title centered
    title_text = (lodge_name or 'Lodge').upper() + ' OFFICERS'
    tfont = _fit_font(draw, title_text, 'DejaVuSans-Bold.ttf', font_dir,
                      W - 2 * margin - int(header_h * 1.8), int(header_h * 0.42))
    tw = draw.textlength(title_text, font=tfont)
    bbox = draw.textbbox((0, 0), title_text, font=tfont)
    th = bbox[3] - bbox[1]
    title_y = int(header_h * 0.20)
    draw.text(((W - tw) / 2, title_y), title_text, fill=GOLD, font=tfont)
    # Sub: lodge number + year
    sub = f"No. {lodge_number}    •    {lodge_year}"
    sfont = _load_font(font_dir, 'DejaVuSansCondensed-Bold.ttf', int(header_h * 0.20))
    sw = draw.textlength(sub, font=sfont)
    draw.text(((W - sw) / 2, title_y + th + int(header_h * 0.16)), sub,
              fill=WHITE, font=sfont)
    # Gold rule under header
    rule_y = header_h
    draw.rectangle([margin, rule_y, W - margin, rule_y + max(3, int(H * 0.0015))],
                   fill=GOLD)

    # ================= BODY GRID (hierarchical portrait tiles) ========
    # Tile sizes are scaled by rank, keeping the 3.5:6 portrait aspect.
    # Knights are the anchor at 3.5" x 6"; the other tiers scale from it:
    #   ER      = 1.35 x flanks  = 1.72125 x knights
    #   flanks  = 1.275 x knights      (Treasurer / Secretary, 25-30%)
    #   knights = 1.0   (anchor, 3.5 x 6)
    #   bottom  = knights / 1.20       (Trustees + everyone else)
    BASE_W = 3.5 * dpi
    BASE_H = 6.0 * dpi
    SCALE_ER = 1.35 * 1.275
    SCALE_FLANK = 1.275
    SCALE_KNIGHT = 1.0
    SCALE_BOTTOM = 1.0 / 1.20

    body_top = header_h + int(H * 0.02)
    body_bottom = H - margin
    body_h = body_bottom - body_top
    usable_w = W - 2 * margin

    # Wider in-row gap so rows spread across more of the sheet.
    row_gap = int(0.9 * dpi)
    vgap_min = int(0.30 * dpi)

    # Decide which positions exist, in hierarchical order.
    knights = [k for k in KNIGHTS if take(k)]
    trustees = [k for k in TRUSTEES if take(k)]
    rest = []
    explicit = set(TOP_ROW) | set(KNIGHTS) | set(TRUSTEES)
    for o in officers:
        if o.get('position_key') not in explicit:
            rest.append(o)

    er = take('exalted_ruler')
    treasurer = take('treasurer')
    secretary = take('secretary')

    # Build ordered rows. Each row = list of (officer, scale).
    rows = []
    top_row = []
    if treasurer:
        top_row.append((treasurer, SCALE_FLANK))
    if er:
        top_row.append((er, SCALE_ER))
    if secretary:
        top_row.append((secretary, SCALE_FLANK))
    if top_row:
        rows.append(top_row)
    if knights:
        rows.append([(take(k), SCALE_KNIGHT) for k in knights])
    # Bottom row = Trustees first (hierarchical), then everyone else.
    bottom = [(take(k), SCALE_BOTTOM) for k in trustees]
    bottom += [(o, SCALE_BOTTOM) for o in rest]
    if bottom:
        bw0 = BASE_W * SCALE_BOTTOM
        max_per_row = max(1, int((usable_w + row_gap) // (bw0 + row_gap)))
        bottom = bottom[:max_per_row]
        rows.append(bottom)

    if rows:
        n_rows = len(rows)
        # --- Auto-enlarge to fill the sheet ('enlarge + spread') -------
        # Vertical bound: stack of band heights + min gaps must fit body_h.
        stack_base = sum(max(BASE_H * s for _o, s in row) for row in rows)
        avail_tiles_h = body_h - vgap_min * (n_rows - 1)
        fill_v = avail_tiles_h / stack_base if stack_base else 1.0
        # Width bound: the widest row (at base) must fit usable width.
        fill_w = 1e9
        for row in rows:
            base_row_w = sum(BASE_W * s for _o, s in row)
            avail = usable_w - row_gap * (len(row) - 1)
            if base_row_w > 0:
                fill_w = min(fill_w, avail / base_row_w)
        # Enlarge as much as both bounds allow, capped so it never overflows.
        fill = min(fill_v, fill_w)
        fill = max(0.5, min(fill, 1.6))

        def tile_size(scale):
            return (int(round(BASE_W * scale * fill)),
                    int(round(BASE_H * scale * fill)))

        # Per-row band height = tallest tile in that row.
        band_heights = [max(tile_size(s)[1] for _o, s in row) for row in rows]
        stack_h = sum(band_heights)
        if n_rows > 1:
            vgap = (body_h - stack_h) / (n_rows - 1)
            vgap = max(vgap_min, vgap)
        else:
            vgap = 0

        cur_y = body_top
        for row, band_h in zip(rows, band_heights):
            sizes = [tile_size(s) for _o, s in row]
            total_w = sum(w for w, _h in sizes) + row_gap * (len(row) - 1)
            start_x = (W - total_w) / 2.0
            x = start_x
            for (officer, _scale), (tw, th) in zip(row, sizes):
                # vertically center each tile within the row band
                y = cur_y + (band_h - th) / 2.0
                _draw_tile(canvas, (x, y, tw, th), officer, fonts, font_dir)
                x += tw + row_gap
            cur_y += band_h + vgap

    # ================= EXPORT PDF + PREVIEW PNG =================
    out = io.BytesIO()
    canvas.save(out, format='PDF', resolution=float(dpi))

    # Downscaled PNG preview (keeps the wizard field light; faithful to
    # the printed layout since it's the same canvas).
    preview_w = 1600
    preview_h = max(1, int(H * (preview_w / W)))
    preview = canvas.resize((preview_w, preview_h), Image.LANCZOS)
    pout = io.BytesIO()
    preview.save(pout, format='PNG')

    return out.getvalue(), pout.getvalue(), (W, H)


# ----------------------------------------------------------------------
# Standalone smoke test
# ----------------------------------------------------------------------
if __name__ == '__main__':
    import random

    here = os.path.dirname(os.path.abspath(__file__))
    fdir = os.path.join(here, '..', 'static', 'fonts')
    fdir = os.path.abspath(fdir)

    def fake_photo(seed):
        random.seed(seed)
        im = Image.new('RGB', (600, 800),
                       (random.randint(30, 90), random.randint(30, 90),
                        random.randint(60, 140)))
        d = ImageDraw.Draw(im)
        for _ in range(40):
            d.line([(random.randint(0, 600), random.randint(0, 800)),
                    (random.randint(0, 600), random.randint(0, 800))],
                   fill=(200, 60, 60), width=8)
        b = io.BytesIO()
        im.save(b, 'PNG')
        return b.getvalue()

    sample_positions = [
        ('exalted_ruler', 'Exalted Ruler', 'Mike Gwinn'),
        ('treasurer', 'Treasurer', 'Michael Miltenberger'),
        ('secretary', 'Secretary', 'Danielle Johnson Sauve'),
        ('leading_knight', 'Leading Knight', 'Christopher Huddleston'),
        ('loyal_knight', 'Loyal Knight', 'Tammy Mathews'),
        ('lecturing_knight', 'Lecturing Knight', 'Samantha Musser'),
        ('boardchair', 'Board Chair', 'Gregory Lind'),
        ('trustee1y', '1 Year Trustee', 'Gregory Lind'),
        ('trustee3y', '3 Year Trustee', 'Danny Santiago'),
        ('chaplain', 'Chaplain', 'Alice Gwinn'),
        ('inner_guard', 'Inner Guard', 'Jim Scully'),
        ('organist', 'Lodge Organist', 'Dana Lohrey'),
        ('tiler', 'Tiler', 'No Photo Person'),
    ]
    officers = []
    for i, (k, lbl, nm) in enumerate(sample_positions):
        officers.append({
            'position_key': k, 'position_label': lbl, 'name': nm,
            'photo': fake_photo(i) if nm != 'No Photo Person' else None,
            'gender': 'male',
        })

    # fake emblem
    em = Image.new('RGB', (400, 400), (10, 10, 10))
    ed = ImageDraw.Draw(em)
    ed.ellipse([10, 10, 390, 390], fill=(20, 20, 20), outline=(150, 60, 160), width=10)
    ed.text((150, 180), 'Elks', fill=(190, 60, 180))
    emb = io.BytesIO(); em.save(emb, 'PNG')

    pdf, preview_png, dims = build_officer_poster(
        officers, emb.getvalue(), 'Lewiston Lodge', '896', '2025-2026', fdir)
    with open('/tmp/officer_poster_test.pdf', 'wb') as f:
        f.write(pdf)
    with open('/tmp/officer_poster_preview.png', 'wb') as f:
        f.write(preview_png)
    print('wrote /tmp/officer_poster_test.pdf', dims, 'pdf_bytes=', len(pdf),
          'preview_bytes=', len(preview_png))
