# -*- coding: utf-8 -*-
"""Officer Photo Poster wizard.

Collects the lodge officers for a chosen lodge year, builds a large-format
(default 47" x 29" @ 150 DPI) photo-board PDF via the pure-Pillow
``officer_poster_builder`` module, and hands back a print-ready PDF plus
ready-to-send instructions for a print shop (Staples).
"""
import base64
import os

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..models.elks_officer_term import (
    OFFICER_POSITIONS,
    _lodge_year_selections,
    _default_lodge_year,
)
from . import officer_poster_builder as builder

_FONT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'static', 'fonts')
)


class ElksOfficerPosterWizard(models.TransientModel):
    _name = "elks.officer.poster.wizard"
    _description = "Officer Photo Poster Generator"

    lodge_year = fields.Selection(
        selection=_lodge_year_selections,
        string="Lodge Year", required=True,
        default=_default_lodge_year,
        help="Officers from this lodge year are placed on the poster.",
    )
    width_in = fields.Float("Width (inches)", default=47.0, required=True)
    height_in = fields.Float("Height (inches)", default=29.0, required=True)
    dpi = fields.Integer(
        "Resolution (DPI)", default=150, required=True,
        help="150 DPI is ideal for large-format prints viewed from a "
             "distance. Higher values make far larger files with little "
             "visible benefit at poster size.",
    )
    include_inactive = fields.Boolean(
        "Include Archived Terms", default=False,
        help="Normally only active officer terms are shown.",
    )

    # Results
    poster_pdf = fields.Binary("Poster PDF", readonly=True, attachment=True)
    poster_filename = fields.Char("Filename", readonly=True)
    poster_preview = fields.Binary(
        "Preview", readonly=True, attachment=True,
        help="On-screen preview of the generated poster (downscaled). "
             "The downloaded PDF is full resolution.",
    )
    officer_count = fields.Integer("Officers Found", readonly=True)
    staples_instructions = fields.Text("Print Shop Instructions", readonly=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('done', 'Generated')],
        default='draft',
    )

    # ------------------------------------------------------------------
    def _collect_officers(self):
        """Return an ordered list of officer dicts for the builder."""
        self.ensure_one()
        Term = self.env['elks.officer.term']
        domain = [('lodge_year', '=', self.lodge_year)]
        if not self.include_inactive:
            domain.append(('active', '=', True))
        terms = Term.with_context(active_test=not self.include_inactive).search(domain)

        labels = dict(OFFICER_POSITIONS)
        # Position display order for "the rest" row stability.
        order_index = {key: i for i, (key, _lbl) in enumerate(OFFICER_POSITIONS)}

        officers = []
        seen = set()
        for term in terms:
            # one tile per position (skip duplicate partial-year extras)
            if term.position in seen:
                continue
            seen.add(term.position)

            photo = term.image_1920 or term.partner_id.image_1920 or False
            photo_bytes = base64.b64decode(photo) if photo else None

            officers.append({
                'position_key': term.position,
                'position_label': labels.get(term.position, term.position or ''),
                'name': term.partner_id.name or '',
                'photo': photo_bytes,
                'gender': term.gender or 'male',
                '_order': order_index.get(term.position, 999),
            })

        officers.sort(key=lambda o: o['_order'])
        return officers

    def _emblem_bytes(self):
        settings = self.env['elks.lodge.settings'].sudo().search([], limit=1)
        if not settings:
            return None, '', ''
        raw = (settings.officer_poster_emblem
               or settings.logo_lodge
               or settings.logo_primary)
        emblem = base64.b64decode(raw) if raw else None
        return emblem, settings.name or 'Lodge', settings.lodge_number or ''

    def _build_staples_instructions(self, lodge_name, lodge_number):
        return _(
            "PRINT SHOP ORDER — %(lodge)s #%(num)s Officer Board\n"
            "================================================================\n"
            "\n"
            "File: the attached PDF is print-ready at full size.\n"
            "\n"
            "  • Finished size:   %(w).0f in wide x %(h).0f in tall "
            "(landscape)\n"
            "  • Resolution:      %(dpi)s DPI at final size\n"
            "  • Color:           Full color (CMYK ok)\n"
            "  • Scaling:         Print at 100%% — do NOT 'fit to page' "
            "or 'shrink to fit'\n"
            "  • Bleed/margins:   No additional margins; print edge to edge "
            "(full bleed)\n"
            "  • Orientation:     Landscape\n"
            "\n"
            "Recommended media (pick one):\n"
            "  • Satin or matte photo paper (poster), or\n"
            "  • Mounted on 3/16\" foam board for a rigid display board, or\n"
            "  • Laminated poster if it will be handled often.\n"
            "\n"
            "Notes for the operator:\n"
            "  • The PDF page is already %(w).0f x %(h).0f inches — please "
            "confirm the page size reads 47 x 29 in before printing.\n"
            "  • Keep the black background solid; do not 'auto-enhance' or "
            "color-correct.\n"
        ) % {
            'lodge': lodge_name,
            'num': lodge_number,
            'w': self.width_in,
            'h': self.height_in,
            'dpi': self.dpi,
        }

    # ------------------------------------------------------------------
    def action_generate(self):
        self.ensure_one()
        if self.dpi < 72 or self.dpi > 300:
            raise UserError(_(
                "Please choose a DPI between 72 and 300. 150 is recommended "
                "for large-format posters."
            ))
        officers = self._collect_officers()
        if not officers:
            raise UserError(_(
                "No officer terms found for lodge year %s. Add officer "
                "terms (with photos) first, then generate the poster."
            ) % self.lodge_year)

        emblem, lodge_name, lodge_number = self._emblem_bytes()

        pdf_bytes, preview_png, _dims = builder.build_officer_poster(
            officers=officers,
            emblem_bytes=emblem,
            lodge_name=lodge_name,
            lodge_number=lodge_number,
            lodge_year=self.lodge_year,
            font_dir=_FONT_DIR,
            dpi=self.dpi,
            width_in=self.width_in,
            height_in=self.height_in,
        )

        fname = "Officer_Board_%s_%s.pdf" % (
            (lodge_number or 'lodge'),
            (self.lodge_year or '').replace('/', '-'),
        )
        self.write({
            'poster_pdf': base64.b64encode(pdf_bytes),
            'poster_preview': base64.b64encode(preview_png),
            'poster_filename': fname,
            'officer_count': len(officers),
            'staples_instructions': self._build_staples_instructions(
                lodge_name, lodge_number),
            'state': 'done',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
