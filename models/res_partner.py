import datetime

from odoo import _, api, fields, models


def _current_lodge_year_start(today=None):
    """Return April 1 of the current lodge year.

    The Elks lodge year runs April 1 – March 31.
    If today is Jan–Mar, we're still in the previous lodge year
    (started April 1 of last calendar year).
    If today is Apr–Dec, the current lodge year started April 1 of this year.
    """
    if today is None:
        today = datetime.date.today()
    if today.month >= 4:
        return datetime.date(today.year, 4, 1)
    else:
        return datetime.date(today.year - 1, 4, 1)


class ResPartner(models.Model):
    _inherit = "res.partner"

    # ------------------------------------------------------------------
    # Return to Sender
    # ------------------------------------------------------------------
    x_return_to_sender = fields.Boolean(
        "Return to Sender", default=False, tracking=True, index=True,
        help="Mail sent to this contact was returned as undeliverable.",
    )
    x_return_to_sender_date = fields.Date(
        "Return Notice Date", tracking=True,
        help="Date the return-to-sender notice was received.",
    )

    def action_mark_return_to_sender(self):
        """Flag this contact as Return to Sender with today's date."""
        today = fields.Date.context_today(self)
        for rec in self:
            rec.write({
                'x_return_to_sender': True,
                'x_return_to_sender_date': today,
            })
            rec.message_post(
                body=_(
                    "<b>Return to Sender</b> — mail returned as "
                    "undeliverable. Flagged by %s on %s.",
                    self.env.user.name, today,
                ),
                subtype_xmlid='mail.mt_note',
            )

    def action_clear_return_to_sender(self):
        """Remove the Return to Sender flag (e.g. address updated)."""
        for rec in self:
            rec.write({
                'x_return_to_sender': False,
                'x_return_to_sender_date': False,
            })
            rec.message_post(
                body=_(
                    "<b>Return to Sender cleared</b> — address updated "
                    "by %s.", self.env.user.name,
                ),
                subtype_xmlid='mail.mt_note',
            )

    # ------------------------------------------------------------------
    # Suspension
    # ------------------------------------------------------------------
    x_is_suspended = fields.Boolean(
        "Suspended", default=False, tracking=True, index=True,
        help="Member is currently under suspension.",
    )
    x_suspension_start_date = fields.Date(
        "Suspension Start Date", tracking=True,
        help="Date the suspension began.",
    )
    x_suspension_end_date = fields.Date(
        "Suspension End Date", tracking=True,
        help="Date the suspension is scheduled to end.",
    )
    x_suspension_notes = fields.Text(
        "Suspension Notes", tracking=True,
        help="Reason or notes regarding the suspension.",
    )

    def action_suspend_member(self):
        """Open the suspension wizard so the user can enter dates and reason."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Suspend Member'),
            'res_model': 'elks.suspension.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
            },
        }

    def action_lift_suspension(self):
        """Remove the suspension flag."""
        today = fields.Date.context_today(self)
        for rec in self:
            rec.write({
                'x_is_suspended': False,
                'x_suspension_end_date': today,
            })
            rec.message_post(
                body=_(
                    "<b>Suspension Lifted</b> — cleared by %s on %s.",
                    self.env.user.name, today,
                ),
                subtype_xmlid='mail.mt_note',
            )

    # ------------------------------------------------------------------
    # Dues
    # ------------------------------------------------------------------
    x_is_dues_paid = fields.Boolean(
        string="Dues Paid (Lodge Year)",
        compute="_compute_is_dues_paid",
        store=True,
        index=True,
        help="True when dues are paid through the current lodge year "
             "(April 1 – March 31).",
    )

    @api.depends('x_detail_dues_paid_to_date')
    def _compute_is_dues_paid(self):
        """Dues are DUE on April 1.  A ``dues_paid_to_date`` of April 1 means
        the member has paid *up to* that date but has NOT yet paid *for* the
        month of April, so they are past due.  The paid-to date must be
        strictly **after** the lodge-year start to count as current."""
        today = fields.Date.context_today(self)
        cutoff = _current_lodge_year_start(today)
        for rec in self:
            d = rec.x_detail_dues_paid_to_date
            rec.x_is_dues_paid = bool(d and d > cutoff)

    # ------------------------------------------------------------------
    # Drop / Undrop (replaces Archive/Unarchive for members)
    # ------------------------------------------------------------------
    x_drop_reason = fields.Selection([
        ('nonpayment', 'Non-Payment of Dues'),
        ('resigned', 'Resigned'),
        ('expelled', 'Expelled'),
        ('deceased', 'Deceased'),
        ('other', 'Other'),
    ], string="Drop Reason", tracking=True)
    x_drop_date = fields.Date(
        "Date Dropped", tracking=True,
        help="Date the member was dropped from the rolls.",
    )
    x_drop_notes = fields.Text(
        "Drop Notes", tracking=True,
        help="Additional details about why the member was dropped.",
    )

    def action_archive(self):
        """Override archive to route members through the Drop wizard."""
        members = self.filtered(lambda r: r.x_is_member)
        non_members = self - members
        # Non-members get the standard archive behavior
        if non_members:
            super(ResPartner, non_members).action_archive()
        # Members must go through the Drop wizard
        if members:
            if len(members) > 1:
                # For multi-select, open wizard for the first, archive the rest
                # (edge case — usually done one at a time)
                return members[0].action_open_drop_wizard()
            return members.action_open_drop_wizard()
        return True

    def action_open_drop_wizard(self):
        """Open the Drop Member wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Drop Member'),
            'res_model': 'elks.drop.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
            },
        }

    def action_unarchive(self):
        """Override unarchive to log 'Restored' and clear drop fields."""
        result = super().action_unarchive()
        for rec in self:
            if rec.x_is_member or rec.x_drop_reason:
                rec.write({
                    'x_drop_reason': False,
                    'x_drop_date': False,
                    'x_drop_notes': False,
                })
                rec.message_post(
                    body=_(
                        "<b>Member Restored</b> — reactivated by %s. "
                        "Drop reason cleared.",
                        self.env.user.name,
                    ),
                    subtype_xmlid='mail.mt_note',
                )
        return result

    @api.model
    def cron_update_is_dues_paid(self):
        """Runs daily: keeps the stored boolean in sync as the lodge year rolls over."""
        today = fields.Date.context_today(self)
        cutoff = _current_lodge_year_start(today)
        Partner = self.env['res.partner'].sudo()

        # paid-to date must be strictly AFTER the lodge-year start (April 1)
        # because April 1 means paid *up to* that date, NOT *for* that month.
        to_true = Partner.search([
            ('active', '=', True),
            ('x_is_dues_paid', '=', False),
            ('x_detail_dues_paid_to_date', '!=', False),
            ('x_detail_dues_paid_to_date', '>', cutoff),
        ])
        if to_true:
            to_true.write({'x_is_dues_paid': True})

        to_false = Partner.search([
            ('active', '=', True),
            ('x_is_dues_paid', '=', True),
            '|', ('x_detail_dues_paid_to_date', '=', False),
            ('x_detail_dues_paid_to_date', '<=', cutoff),
        ])
        if to_false:
            to_false.write({'x_is_dues_paid': False})

        return len(to_true) + len(to_false)
