from dateutil.relativedelta import relativedelta
from odoo import api, fields, models

class ResPartner(models.Model):
    _inherit = "res.partner"

    # already have this, shown here for context
    x_detail_dues_paid_to_date = fields.Date("DetailDuesPaidToDate")

    # NEW: stored flag you can filter/group by
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



    def action_copy_core_from_elks(self, overwrite=False):
        for rec in self:
            vals = {}

            def set_if(value, target_field, current_value):
                if not value:
                    return
                if overwrite or not (current_value or "").strip():
                    vals[target_field] = value

            # Address
            set_if(rec.x_detail_active_address_line1, "street", rec.street)
            set_if(rec.x_detail_active_address_line2, "street2", rec.street2)
            set_if(rec.x_detail_active_city, "city", rec.city)
            set_if(rec.x_detail_active_zip, "zip", rec.zip)

            # Country & State
            country = rec._find_country(rec.x_detail_active_country) if rec.x_detail_active_country else False
            if country and (overwrite or not rec.country_id):
                vals["country_id"] = country.id

            state = rec._find_state(rec.x_detail_active_state, country or rec.country_id) if rec.x_detail_active_state else False
            if state and (overwrite or not rec.state_id):
                vals["state_id"] = state.id

            # Email
            set_if((rec.x_detail_email_address or "").strip(), "email", rec.email or "")

            # Phones
            home = rec._compose_phone(rec.x_detail_home_area_code, rec.x_detail_home_phone, rec.x_detail_home_phone_ext)
            if home and (overwrite or not (rec.phone or "").strip()):
                vals["phone"] = home

            mobile = rec._compose_phone(rec.x_detail_cell_area_code, rec.x_detail_cell_phone, None)
            if mobile and (overwrite or not (rec.mobile or "").strip()):
                vals["mobile"] = mobile

            if vals:
                rec.write(vals)
