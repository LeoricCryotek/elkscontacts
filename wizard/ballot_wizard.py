# -*- coding: utf-8 -*-
"""Ballot recording wizard — popup form for entering ballot results."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ElksBallotWizard(models.TransientModel):
    _name = "elks.ballot.wizard"
    _description = "Record Ballot Result"

    application_id = fields.Many2one(
        'elks.membership.application', string="Application",
        required=True, readonly=True,
    )
    applicant_name = fields.Char(
        related='application_id.applicant_display_name', readonly=True,
    )
    ballot_result = fields.Selection([
        ('elected', 'Elected'),
        ('rejected', 'Rejected'),
    ], string="Ballot Result", required=True, default='elected',
        help="Select 'Elected' if the vote passed or 'Rejected' if it failed.",
    )
    all_in_favor = fields.Boolean(
        "All in Favor (Unanimous)",
        help="Check if the ballot was unanimous.",
    )
    votes_for = fields.Integer(
        "Votes For",
        help="Number of votes in favor of the applicant.",
    )
    votes_against = fields.Integer(
        "Votes Against",
        help="Number of votes against the applicant.",
    )
    ballot_date = fields.Date(
        "Ballot Date", default=fields.Date.context_today,
        help="The date the ballot vote took place.",
    )

    def action_confirm(self):
        """Apply the ballot result to the application."""
        self.ensure_one()
        app = self.application_id
        if app.stage != 'balloting':
            raise UserError(_("This application is no longer in the balloting stage."))

        app.write({'ballot_all_in_favor': self.all_in_favor})

        if self.ballot_result == 'elected':
            app.action_elect(
                votes_for=self.votes_for,
                votes_against=self.votes_against,
            )
            if self.ballot_date and not app.date_elected:
                app.write({'date_elected': self.ballot_date})
        else:
            app.write({
                'ballot_votes_for': self.votes_for,
                'ballot_votes_against': self.votes_against,
            })
            app.action_reject()
            if self.ballot_date and not app.date_rejected:
                app.write({'date_rejected': self.ballot_date})

        return {'type': 'ir.actions.act_window_close'}
