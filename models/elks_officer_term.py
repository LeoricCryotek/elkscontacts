# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


def _lodge_year_selections(self):
    """Generate selection list of lodge years (10 back, 5 forward).
    Lodge year runs April 1 - March 31."""
    import datetime
    today = datetime.date.today()
    current_start = today.year if today.month >= 4 else today.year - 1
    years = []
    for y in range(current_start - 10, current_start + 6):
        label = f"{y}-{y + 1}"
        years.append((label, label))
    return years


def _default_lodge_year(self):
    """Return the current lodge year string, e.g. '2025-2026'."""
    import datetime
    today = datetime.date.today()
    if today.month >= 4:
        return f"{today.year}-{today.year + 1}"
    else:
        return f"{today.year - 1}-{today.year}"


OFFICER_POSITIONS = [
    # ----- Elected Officers -----
    ('exalted_ruler', 'Exalted Ruler'),
    ('leading_knight', 'Leading Knight'),
    ('loyal_knight', 'Loyal Knight'),
    ('lecturing_knight', 'Lecturing Knight'),
    ('secretary', 'Secretary'),
    ('treasurer', 'Treasurer'),
    ('tiler', 'Tiler'),

    # ----- Board of Trustees -----
    ('boardchair', 'Board Chair'),
    ('trustee1y', '1 Year Trustee'),
    ('trustee2y', '2 Year Trustee'),
    ('trustee3y', '3 Year Trustee'),
    ('trustee4y', '4 Year Trustee'),
    ('trustee5y', '5 Year Trustee'),

    # ----- Appointed Officers -----
    ('esquire', 'Esquire'),
    ('chaplain', 'Chaplain'),
    ('inner_guard', 'Inner Guard'),
    ('organist', 'Organist'),
    ('pianist', 'Pianist'),
    ('sergeant_at_arms', 'Sergeant-at-Arms'),
    ('presiding_justice', 'Presiding Justice'),

    # ----- Staff / Administrative -----
    ('assistant_secretary', 'Assistant Secretary'),
    ('assistant_treasurer', 'Assistant Treasurer'),
    ('house_chair', 'House Committee Chair'),
    ('activities_chair', 'Activities Chair'),
    ('membership_chair', 'Membership Chair'),
    ('lodge_advisor', 'Lodge Advisor'),

    # ----- Past Officers (honorifics) -----
    ('past_exalted_ruler', 'Past Exalted Ruler (PER)'),
    ('per_of_year', 'PER of the Year (PEY)'),
    ('elk_of_the_year', 'Elk of the Year (EOY)'),
    ('officer_of_year', 'Officer of the Year (POY)'),
    ('citizen_of_year', 'Citizen of the Year'),

    # ----- Convention / Delegates -----
    ('delegate_grand', 'Grand Lodge Delegate'),
    ('delegate_state', 'State Convention Delegate'),
    ('alternate_grand', 'Alternate Grand Delegate'),
    ('alternate_state', 'Alternate State Delegate'),
]


class ElksOfficerTerm(models.Model):
    """Track officer positions held by lodge members each lodge year.

    Each record represents one member holding one position for one lodge year
    (April 1 – March 31).  Partial-year terms are supported via the
    ``partial_year`` flag, allowing two members to share the same position
    in a single year.  The ``officer_type`` is auto-computed from the
    position but can be manually overridden (e.g. an appointed officer
    who was later elected).
    """
    _name = "elks.officer.term"
    _description = "Elks Officer Term"
    _order = "lodge_year desc, position"
    _rec_name = "display_name"

    partner_id = fields.Many2one(
        "res.partner", string="Member", required=True,
        ondelete="cascade", index=True,
    )
    position = fields.Selection(
        OFFICER_POSITIONS, string="Position", required=True, index=True,
    )
    lodge_year = fields.Selection(
        selection=_lodge_year_selections,
        string="Lodge Year", required=True, index=True,
        default=_default_lodge_year,
        help="Lodge year (April 1 - March 31). Select from the list.",
    )
    partial_year = fields.Boolean(
        string="Partial Year",
        help="Check if this member served only part of the lodge year. "
             "When checked, another member may also hold the same position "
             "for the same year.",
    )
    officer_type = fields.Selection([
        ('elected', 'Elected Officer'),
        ('appointed', 'Appointed Officer'),
        ('trustee', 'Trustee'),
        ('staff', 'Staff / Administrative'),
        ('honorific', 'Past / Honorific'),
        ('delegate', 'Delegate'),
    ], string="Officer Type", compute="_compute_officer_type",
       store=True, readonly=False,
       help="Auto-set from Position but can be changed. Use this to mark "
            "an appointed officer who was later elected, or vice versa.")
    notes = fields.Text(string="Notes")

    display_name = fields.Char(
        compute="_compute_display_name", store=True,
    )

    # ── Computed ─────────────────────────────────────────────
    @api.depends('position')
    def _compute_officer_type(self):
        elected = {
            'exalted_ruler', 'leading_knight', 'loyal_knight',
            'lecturing_knight', 'secretary', 'treasurer', 'tiler',
        }
        trustees = {
            'boardchair', 'trustee1y', 'trustee2y',
            'trustee3y', 'trustee4y', 'trustee5y',
        }
        staff = {
            'assistant_secretary', 'assistant_treasurer',
            'house_chair', 'activities_chair', 'membership_chair',
            'lodge_advisor',
        }
        honorific = {
            'past_exalted_ruler', 'per_of_year', 'elk_of_the_year',
            'officer_of_year', 'citizen_of_year',
        }
        delegate = {
            'delegate_grand', 'delegate_state',
            'alternate_grand', 'alternate_state',
        }
        for rec in self:
            if rec.position in elected:
                rec.officer_type = 'elected'
            elif rec.position in trustees:
                rec.officer_type = 'trustee'
            elif rec.position in staff:
                rec.officer_type = 'staff'
            elif rec.position in honorific:
                rec.officer_type = 'honorific'
            elif rec.position in delegate:
                rec.officer_type = 'delegate'
            elif rec.position:
                rec.officer_type = 'appointed'
            else:
                rec.officer_type = False

    @api.depends('partner_id.name', 'position', 'lodge_year')
    def _compute_display_name(self):
        labels = dict(OFFICER_POSITIONS)
        for rec in self:
            pos = labels.get(rec.position, rec.position or '')
            name = rec.partner_id.name or ''
            rec.display_name = f"{pos} - {name} ({rec.lodge_year})"

    # ── Constraints ──────────────────────────────────────────
    @api.constrains('position', 'lodge_year', 'partial_year')
    def _check_unique_position_per_year(self):
        """Prevent two holders of the same position in the same lodge year
        unless at least one of them is flagged as a partial-year term."""
        for rec in self:
            if not rec.position or not rec.lodge_year:
                continue
            others = self.search([
                ('id', '!=', rec.id),
                ('position', '=', rec.position),
                ('lodge_year', '=', rec.lodge_year),
            ])
            if not others:
                continue
            # If this record is partial, all others must also be partial
            # If this record is NOT partial, no others are allowed
            if not rec.partial_year:
                label = dict(OFFICER_POSITIONS).get(rec.position, rec.position)
                raise ValidationError(_(
                    "The position '%s' already has a holder for lodge year %s: %s. "
                    "If this was a partial year served, check the 'Partial Year' box "
                    "on both records."
                ) % (label, rec.lodge_year, others[0].partner_id.display_name))
            # If we're partial, check that existing ones are also partial
            non_partial = others.filtered(lambda o: not o.partial_year)
            if non_partial:
                label = dict(OFFICER_POSITIONS).get(rec.position, rec.position)
                raise ValidationError(_(
                    "The position '%s' for lodge year %s is held by %s as a full term. "
                    "To add a partial-year entry, first mark the existing record as "
                    "'Partial Year' as well."
                ) % (label, rec.lodge_year, non_partial[0].partner_id.display_name))

    @api.constrains('partner_id', 'position', 'lodge_year')
    def _check_no_duplicate_member_position(self):
        """Prevent the same member from being assigned the same position
        twice in the same lodge year (regardless of partial_year flag)."""
        for rec in self:
            if not (rec.partner_id and rec.position and rec.lodge_year):
                continue
            dupes = self.search([
                ('partner_id', '=', rec.partner_id.id),
                ('position', '=', rec.position),
                ('lodge_year', '=', rec.lodge_year),
                ('id', '!=', rec.id),
            ])
            if dupes:
                label = dict(OFFICER_POSITIONS).get(rec.position, rec.position)
                raise ValidationError(_(
                    "%(member)s already holds the position of "
                    "%(pos)s for lodge year %(yr)s."
                ) % {
                    'member': rec.partner_id.display_name,
                    'pos': label,
                    'yr': rec.lodge_year,
                })
