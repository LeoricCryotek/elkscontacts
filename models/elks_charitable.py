# -*- coding: utf-8 -*-
"""Charitable giving tracking.

The Elks Lodge reports charitable giving to the Grand Lodge annually.
This model tracks donations made BY the lodge to charitable causes
(scholarships, veterans programs, youth activities, disaster relief,
ENF, etc.) with hours and dollars separated.
"""
from odoo import api, fields, models


CHARITY_CATEGORIES = [
    ('scholarship', 'Scholarships'),
    ('veterans', 'Veterans Programs'),
    ('youth', 'Youth Activities'),
    ('drug_awareness', 'Drug Awareness'),
    ('hoop_shoot', 'Hoop Shoot'),
    ('soccer_shoot', 'Soccer Shoot'),
    ('disaster', 'Disaster Relief'),
    ('enf', 'Elks National Foundation (ENF)'),
    ('special_needs', 'Special Needs'),
    ('community', 'General Community'),
    ('other', 'Other'),
]


class ElksCharitableActivity(models.Model):
    _name = "elks.charitable.activity"
    _description = "Elks Charitable Activity / Donation"
    _order = "date desc, id desc"
    _inherit = ["mail.thread"]

    name = fields.Char(
        "Activity / Recipient", required=True, index=True,
        help="e.g. 'Clearwater Valley Scholarship Fund' or 'Idaho Food Bank Drive'.",
    )
    category = fields.Selection(
        CHARITY_CATEGORIES, string="Category", required=True, index=True,
        tracking=True,
    )
    date = fields.Date(
        "Activity Date", required=True,
        default=fields.Date.context_today, index=True, tracking=True,
    )
    lodge_year = fields.Char(
        "Lodge Year", compute="_compute_lodge_year", store=True, index=True,
    )

    # Financial
    cash_donated = fields.Monetary(
        "Cash Donated", currency_field='currency_id', tracking=True,
    )
    goods_value = fields.Monetary(
        "Value of Goods Donated", currency_field='currency_id', tracking=True,
        help="Fair value of physical donations (food, clothing, equipment).",
    )
    total_value = fields.Monetary(
        "Total Value", compute="_compute_totals", store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id,
    )

    # Volunteer effort
    volunteer_hours = fields.Float(
        "Volunteer Hours", tracking=True,
        help="Total member-hours donated to this activity.",
    )
    volunteer_count = fields.Integer(
        "Volunteer Count", tracking=True,
        help="Number of individual members who participated.",
    )
    people_served = fields.Integer(
        "People Served", tracking=True,
        help="Estimated number of people who benefited from this activity.",
    )

    # Tracking
    committee_id = fields.Many2one(
        "elks.committee", string="Committee",
        help="Committee responsible for this activity.",
    )
    lead_partner_id = fields.Many2one(
        "res.partner", string="Activity Lead",
        domain="[('x_is_member', '=', True)]",
    )
    recipient_org = fields.Char(
        "Recipient Organization",
        help="External organization or beneficiary, if any.",
    )
    notes = fields.Text("Notes")

    # FRS integration via optional reference — allows linking to an
    # elks.journal.entry without forcing elkscontacts to depend on elksfrs.
    # Users can still paste the entry reference manually; the elksfrs
    # module may extend this model to add a proper M2O if installed.
    journal_entry_ref = fields.Char(
        "Journal Entry Reference",
        help="Reference to an accounting journal entry for the cash "
             "donation portion (if any).",
    )

    @api.depends("date")
    def _compute_lodge_year(self):
        for rec in self:
            if rec.date:
                if rec.date.month >= 4:
                    start = rec.date.year
                else:
                    start = rec.date.year - 1
                rec.lodge_year = f"{start}-{start + 1}"
            else:
                rec.lodge_year = False

    @api.depends("cash_donated", "goods_value")
    def _compute_totals(self):
        for rec in self:
            rec.total_value = (rec.cash_donated or 0) + (rec.goods_value or 0)
