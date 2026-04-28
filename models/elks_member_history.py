# -*- coding: utf-8 -*-
"""Elk Member History — mirrors CLMS "Elk History" records.

Tracks the chronological membership lifecycle events for a member:
Proposed, Applied, Investigated, Orientation, Elected, Initiated,
Paid-to date changes, transfers, reinstatements, suspensions, drops, etc.

Records can be auto-created by the membership application workflow or
imported from CLMS, and can also be manually edited by the Secretary.
"""
from odoo import api, fields, models, _

import logging

_logger = logging.getLogger(__name__)

HISTORY_TYPES = [
    ('proposed', 'Proposed'),
    ('applied', 'Applied'),
    ('investigated', 'Investigated'),
    ('orientation', 'Orientation'),
    ('elected', 'Elected'),
    ('initiated', 'Initiated'),
    ('paid_to', 'Paid to'),
    ('transfer_dimit', 'Transfer Dimit'),
    ('certificate_of_release', 'Certificate of Release'),
    ('absolute_dimit', 'Absolute Dimit'),
    ('reinstatement', 'Reinstatement'),
    ('affiliation', 'Affiliation'),
    ('suspended', 'Suspended'),
    ('dropped', 'Dropped'),
    ('deceased', 'Deceased'),
    ('life_member', 'Life Member'),
    ('honorary_life', 'Honorary Life'),
    ('other', 'Other'),
]


class ElksMemberHistory(models.Model):
    _name = "elks.member.history"
    _description = "Elk Member History"
    _order = "event_date desc, id desc"

    partner_id = fields.Many2one(
        'res.partner', string="Member", required=True,
        ondelete='cascade', index=True,
    )
    event_type = fields.Selection(
        HISTORY_TYPES, string="Type", required=True, index=True,
    )
    event_date = fields.Date("Date", required=True)

    # CLMS fields — mirror the Elk History table columns
    lodge_num_1 = fields.Char(
        "LodgeNum1",
        help="Lodge number for the primary lodge involved in this event.",
    )
    number_1 = fields.Char(
        "Number1",
        help="Member number (at LodgeNum1) at the time of this event.",
    )
    comment_1 = fields.Char(
        "Comment1",
        help="Primary comment — e.g. lodge location, application type (NM), "
             "or proposer/investigator name.",
    )
    comment_2 = fields.Char(
        "Comment2",
        help="Secondary comment — e.g. proposer name, endorser, or note.",
    )
    lodge_num_2 = fields.Char(
        "LodgeNum2",
        help="Second lodge number — used for transfers, affiliations, "
             "or when a proposer is from a different lodge.",
    )
    number_2 = fields.Char(
        "Number2",
        help="Member number at the second lodge (LodgeNum2).",
    )
    lost_years = fields.Integer(
        "LostYears", default=0,
        help="Number of years of membership lost due to drop/dimit. "
             "CLMS tracks this for seniority calculations.",
    )
    chg = fields.Char(
        "Chg",
        help="Change indicator from CLMS — e.g. '+1' for membership gain, "
             "'-1' for loss. Affects lodge membership totals.",
    )
    chg_year = fields.Char(
        "ChgYear",
        help="Lodge year in which the membership change was counted.",
    )

    # Source tracking
    source = fields.Selection([
        ('manual', 'Manual Entry'),
        ('application', 'Application Workflow'),
        ('clms_import', 'CLMS Import'),
    ], string="Source", default='manual', readonly=True,
        help="How this history entry was created.",
    )
    application_id = fields.Many2one(
        'elks.membership.application', string="Application",
        ondelete='set null',
        help="Link to the membership application that generated this entry.",
    )
