from dateutil.relativedelta import relativedelta
from odoo import api, fields, models

class ResPartner(models.Model):
    _inherit = "res.partner"

    x_is_dues_paid = fields.Boolean(
        string="Dues Paid (last 12 months)",
        compute="_compute_is_dues_paid",
        store=True,
        index=True,
    )

    @api.depends('x_detail_dues_paid_to_date')
    def _compute_is_dues_paid(self):
        today = fields.Date.context_today(self)
        cutoff = today - relativedelta(months=12)
        for rec in self:
            d = rec.x_detail_dues_paid_to_date
            rec.x_is_dues_paid = bool(d and d >= cutoff)

    @api.model
    def cron_update_is_dues_paid(self):
        """Runs daily: keeps the stored boolean in sync as time passes."""
        today = fields.Date.context_today(self)
        cutoff = today - relativedelta(months=12)
        Partner = self.env['res.partner'].sudo()

        to_true = Partner.search([
            ('active', '=', True),
            ('x_is_dues_paid', '=', False),
            ('x_detail_dues_paid_to_date', '!=', False),
            ('x_detail_dues_paid_to_date', '>=', cutoff),
        ])
        if to_true:
            to_true.write({'x_is_dues_paid': True})

        to_false = Partner.search([
            ('active', '=', True),
            ('x_is_dues_paid', '=', True),
            '|', ('x_detail_dues_paid_to_date', '=', False),
            ('x_detail_dues_paid_to_date', '<', cutoff),
        ])
        if to_false:
            to_false.write({'x_is_dues_paid': False})

        return len(to_true) + len(to_false)
