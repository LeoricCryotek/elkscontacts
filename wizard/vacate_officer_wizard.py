# -*- coding: utf-8 -*-
"""Vacate Officer wizard.

Used from an elks.officer.term record to mark that the officer has
left the position mid-term (resigned, retired, deceased, removed).
Sets the x_vacated_* fields on the term (preserving the historical
record of who held the seat) so the roster report and public website
render the position as Vacant.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ElksOfficerVacateWizard(models.TransientModel):
    _name = 'elks.officer.vacate.wizard'
    _description = 'Vacate Officer Wizard'

    term_id = fields.Many2one(
        'elks.officer.term', string='Officer Term', required=True,
    )
    term_display = fields.Char(
        related='term_id.display_name', readonly=True,
        string='Position',
    )
    partner_id = fields.Many2one(
        related='term_id.partner_id', readonly=True,
        string='Current Officer',
    )
    vacated_date = fields.Date(
        'Vacated On', required=True,
        default=fields.Date.context_today,
        help="Date the officer stopped serving. Defaults to today.",
    )
    reason = fields.Selection([
        ('resigned', 'Resigned'),
        ('retired', 'Retired'),
        ('removed', 'Removed'),
        ('deceased', 'Deceased'),
        ('other', 'Other'),
    ], string='Reason', required=True, default='resigned')
    notes = fields.Text(
        'Notes',
        help="Optional detail — visible on the term record's chatter.",
    )
    fill_immediately = fields.Boolean(
        "Open 'Fill Vacant Position' after saving",
        default=False,
        help="Check to jump straight into creating a replacement term "
             "for someone else to serve the balance of the year. Leave "
             "unchecked to just mark the position vacant for now.",
    )

    def action_confirm_vacate(self):
        self.ensure_one()
        if not self.term_id:
            raise UserError(_("No officer term selected."))
        if self.term_id.x_is_vacated:
            raise UserError(_(
                "This officer term is already marked as vacated."
            ))

        vals = {
            'x_vacated_date': self.vacated_date,
            'x_vacated_reason': self.reason,
            'x_vacated_notes': self.notes or False,
        }
        # If date_end isn't set, use the vacated date so downstream
        # reports and cutoff checks pick it up too.
        if not self.term_id.date_end:
            vals['date_end'] = self.vacated_date
        self.term_id.write(vals)

        reason_label = dict(self._fields['reason'].selection).get(
            self.reason, self.reason,
        )
        note_line = ('<br/>Notes: ' + self.notes) if self.notes else ''
        # elks.officer.term doesn't currently inherit mail.thread, so
        # message_post isn't available on it. Guard the call so future
        # additions of mail.thread inheritance keep working, and drop
        # to a plain log line otherwise. The contact record DOES
        # inherit mail.thread so that side always logs.
        if hasattr(self.term_id, 'message_post'):
            self.term_id.message_post(
                body=_(
                    "<b>Position vacated</b> by %(user)s.<br/>"
                    "Officer: %(officer)s<br/>"
                    "Date: %(date)s<br/>"
                    "Reason: %(reason)s"
                    "%(notes)s"
                    "<br/><i>This position will now display as "
                    "<b>Vacant</b> on the roster report and the public "
                    "website. The term record is preserved as history.</i>"
                ) % {
                    'user': self.env.user.name,
                    'officer': (self.partner_id.name if self.partner_id
                                else '—'),
                    'date': self.vacated_date,
                    'reason': reason_label,
                    'notes': note_line,
                },
                subtype_xmlid='mail.mt_note',
            )
        # Log to the officer's contact chatter — res.partner has
        # mail.thread so this always works — so the member's own
        # record reflects that they left mid-term.
        if self.partner_id and hasattr(self.partner_id, 'message_post'):
            self.partner_id.message_post(
                body=_(
                    "<b>Left officer position</b>: %(position)s "
                    "(%(year)s) as of %(date)s — <i>%(reason)s</i>."
                ) % {
                    'position': self.term_id.display_name or '',
                    'year': self.term_id.lodge_year or '',
                    'date': self.vacated_date,
                    'reason': reason_label,
                },
                subtype_xmlid='mail.mt_note',
            )

        if self.fill_immediately:
            return self.term_id.action_open_fill_vacant_position()
        return {'type': 'ir.actions.act_window_close'}
