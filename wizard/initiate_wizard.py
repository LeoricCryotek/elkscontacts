# -*- coding: utf-8 -*-
"""Initiation wizard — popup form for completing the member initiation."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ElksInitiateWizard(models.TransientModel):
    _name = "elks.initiate.wizard"
    _description = "Initiate New Member"

    application_id = fields.Many2one(
        'elks.membership.application', string="Application",
        required=True, readonly=True,
    )
    applicant_name = fields.Char(
        related='application_id.applicant_display_name', readonly=True,
    )
    member_number = fields.Char(
        "CLMS Member Number",
        help="The member number to assign in CLMS. Leave blank if "
             "not yet assigned — you can update it later.",
    )
    initiation_date = fields.Date(
        "Initiation Date", default=fields.Date.context_today,
        required=True,
        help="The date the initiation ceremony took place.",
    )
    initiation_fee_paid = fields.Boolean(
        "Initiation Fee Paid",
        help="Check if the initiation fee has been collected.",
    )
    dues_paid = fields.Boolean(
        "Dues Paid",
        help="Check if the new member's dues have been collected.",
    )
    applicant_partner_id = fields.Many2one(
        related='application_id.applicant_partner_id',
        string="Linked Contact", readonly=True,
        help="If a contact record is already linked, it will be "
             "updated. Otherwise a new contact will be created.",
    )

    def action_confirm(self):
        """Apply the initiation to the application."""
        self.ensure_one()
        app = self.application_id
        if app.stage != 'elected':
            raise UserError(_("This application is no longer in the elected stage."))

        # Push wizard values to the application before initiating
        update_vals = {
            'initiation_fee_paid': self.initiation_fee_paid,
            'dues_paid': self.dues_paid,
        }
        if self.member_number:
            update_vals['member_number_assigned'] = self.member_number
        if self.initiation_date:
            update_vals['date_initiated'] = self.initiation_date
        app.write(update_vals)

        # Run the full initiation logic
        app.action_initiate()

        return {'type': 'ir.actions.act_window_close'}
