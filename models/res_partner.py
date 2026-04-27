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
