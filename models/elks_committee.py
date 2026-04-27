# -*- coding: utf-8 -*-
"""Committee tracking for the Elks Lodge.

A committee is a group of members assigned to a specific lodge function
(House, Membership, Scholarship, Veterans, etc.).  Each committee has a
chair, optional officer liaison, and member assignments per lodge year.

Statutory committees are mandated by the Grand Lodge and must have at
least one member assigned each year.  Subcommittees fall under a parent
statutory committee.  Lodge committees are created at the discretion of
the individual lodge.
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


COMMITTEE_TYPES = [
    ('statutory', 'Statutory'),
    ('subcommittee', 'Subcommittee'),
    ('lodge', 'Lodge'),
]


class ElksCommittee(models.Model):
    _name = "elks.committee"
    _description = "Elks Lodge Committee"
    _order = "sort_code, name"

    name = fields.Char(
        "Committee Name", required=True, index=True,
    )
    code = fields.Char(
        "Short Code",
        help="Optional abbreviation, e.g. 'HOUSE', 'MEM', 'SCHOL'.",
    )
    sort_code = fields.Char(
        "Committee Code",
        help="Numeric sort code from the Grand Lodge committee list "
             "(e.g. 1000, 2010, X250).",
        index=True,
    )
    committee_type = fields.Selection(
        COMMITTEE_TYPES, string="Type", default='lodge', required=True,
    )
    is_required = fields.Boolean(
        "Required",
        compute="_compute_is_required", store=True,
        help="Statutory committees are required by the Grand Lodge "
             "and must have at least one member assigned each year.",
    )
    parent_committee_id = fields.Many2one(
        "elks.committee", string="Parent Committee",
        domain="[('committee_type', '=', 'statutory')]",
        help="The statutory committee this subcommittee falls under.",
        ondelete="set null",
    )
    child_committee_ids = fields.One2many(
        "elks.committee", "parent_committee_id",
        string="Subcommittees",
    )
    description = fields.Text("Purpose / Description")
    active = fields.Boolean(default=True)

    # Leadership
    chair_id = fields.Many2one(
        "res.partner", string="Chair",
        domain="[('x_is_member', '=', True)]",
    )
    officer_liaison_id = fields.Many2one(
        "res.partner", string="Officer Liaison",
        domain="[('x_is_elks_officer', '=', True)]",
    )

    # Current-year assignments (computed)
    member_ids = fields.One2many(
        "elks.committee.assignment", "committee_id",
        string="Assignments",
    )
    current_member_count = fields.Integer(
        "Active Members", compute="_compute_current_member_count",
    )

    budget_amount = fields.Monetary(
        "Annual Budget", currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id,
    )

    notes = fields.Text("Notes")

    @api.depends("committee_type")
    def _compute_is_required(self):
        for rec in self:
            rec.is_required = rec.committee_type == 'statutory'

    @api.depends("member_ids", "member_ids.is_current")
    def _compute_current_member_count(self):
        for rec in self:
            rec.current_member_count = len(
                rec.member_ids.filtered('is_current')
            )


class ElksCommitteeAssignment(models.Model):
    _name = "elks.committee.assignment"
    _description = "Committee Membership Assignment"
    _order = "lodge_year desc, role, partner_id"

    committee_id = fields.Many2one(
        "elks.committee", string="Committee", required=True,
        ondelete="cascade", index=True,
    )
    partner_id = fields.Many2one(
        "res.partner", string="Member", required=True,
        domain="[('x_is_member', '=', True)]",
        ondelete="cascade", index=True,
    )
    role = fields.Selection([
        ('chair', 'Chair'),
        ('vice_chair', 'Vice Chair'),
        ('secretary', 'Secretary'),
        ('member', 'Member'),
        ('liaison', 'Officer Liaison'),
    ], default='member', required=True)
    lodge_year = fields.Char(
        "Lodge Year", required=True, index=True,
        help="YYYY-YYYY format, e.g. 2025-2026.",
    )
    date_appointed = fields.Date(
        "Appointed On", default=fields.Date.context_today,
    )
    date_ended = fields.Date("Ended On")
    is_current = fields.Boolean(
        "Currently Active", compute="_compute_is_current", store=True,
    )
    notes = fields.Char("Notes")

    @api.depends("date_ended", "date_appointed")
    def _compute_is_current(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.date_ended and rec.date_ended < today:
                rec.is_current = False
            else:
                rec.is_current = True

    @api.constrains("partner_id", "committee_id", "lodge_year")
    def _check_unique_assignment(self):
        for rec in self:
            if not (rec.partner_id and rec.committee_id and rec.lodge_year):
                continue
            dupes = self.search([
                ('partner_id', '=', rec.partner_id.id),
                ('committee_id', '=', rec.committee_id.id),
                ('lodge_year', '=', rec.lodge_year),
                ('id', '!=', rec.id),
            ])
            if dupes:
                raise ValidationError(_(
                    "%(name)s is already assigned to %(com)s for %(yr)s."
                ) % {
                    'name': rec.partner_id.name,
                    'com': rec.committee_id.name,
                    'yr': rec.lodge_year,
                })
