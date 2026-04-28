# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ElksSuspensionWizard(models.TransientModel):
    _name = 'elks.suspension.wizard'
    _description = 'Suspend Member Wizard'

    partner_id = fields.Many2one(
        'res.partner', string='Member', required=True,
    )
    suspension_start_date = fields.Date(
        'Start Date', required=True,
        default=fields.Date.context_today,
    )
    suspension_end_date = fields.Date('End Date')
    suspension_notes = fields.Text('Reason / Notes')

    def action_confirm_suspension(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('No member selected.'))
        self.partner_id.write({
            'x_is_suspended': True,
            'x_suspension_start_date': self.suspension_start_date,
            'x_suspension_end_date': self.suspension_end_date or False,
            'x_suspension_notes': self.suspension_notes or False,
        })
        self.partner_id.message_post(
            body=_(
                "<b>Member Suspended</b> by %s.<br/>"
                "Start: %s<br/>"
                "%s"
                "%s",
                self.env.user.name,
                self.suspension_start_date,
                f"End: {self.suspension_end_date}<br/>" if self.suspension_end_date else "",
                f"Reason: {self.suspension_notes}" if self.suspension_notes else "",
            ),
            subtype_xmlid='mail.mt_note',
        )
        return {'type': 'ir.actions.act_window_close'}
