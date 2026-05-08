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

    active = fields.Boolean(
        default=True,
        help="Uncheck to archive this term.  Archived terms remain in the "
             "member's history but are hidden from the website and default "
             "list views.  When an officer is removed mid-year the record "
             "is archived rather than deleted.",
    )

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
    date_start = fields.Date(
        "Term Start",
        help="Date this officer began serving in this position.",
    )
    date_end = fields.Date(
        "Term End",
        help="Date this officer stopped serving.  Auto-set when the term "
             "is archived mid-year.",
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

    # ── Website Display Fields (NOT linked to contact) ──────
    image_1920 = fields.Image(
        "Photo", max_width=1920, max_height=1920,
        help="Officer photo for website display. Not linked to the contact record.",
    )
    officer_email = fields.Char(
        "Officer Email",
        help="Public email for this officer position (e.g. ER@lodge.com). "
             "Shown on the website officer page.",
    )
    officer_phone = fields.Char(
        "Officer Phone",
        help="Public phone for this officer position. "
             "Shown on the website officer page.",
    )
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
    ], string="Gender", default='male',
       help="Used for default Elk avatar if no photo is provided.",
    )
    message = fields.Text(
        "Message",
        help="Public message / bio displayed on the website officer page.",
    )
    show_on_website = fields.Boolean(
        "Show on Website", default=True,
        help="Uncheck to hide this officer from the public website page.",
    )
    # Backward-compatible alias so cached views referencing 'notes' still work
    notes = fields.Text(related='message', string="Notes (deprecated)")

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
    @api.constrains('position', 'lodge_year', 'partial_year', 'active')
    def _check_unique_position_per_year(self):
        """Only one *active*, non-partial holder per position per year.

        Multiple holders are allowed when:
        - one or more are archived (``active=False``), or
        - all are flagged as partial-year terms.
        """
        for rec in self:
            if not rec.position or not rec.lodge_year or not rec.active:
                continue
            # Only check against other active records
            others = self.with_context(active_test=True).search([
                ('id', '!=', rec.id),
                ('position', '=', rec.position),
                ('lodge_year', '=', rec.lodge_year),
                ('active', '=', True),
            ])
            if not others:
                continue
            if not rec.partial_year:
                label = dict(OFFICER_POSITIONS).get(rec.position, rec.position)
                raise ValidationError(_(
                    "The position '%s' already has an active holder for "
                    "lodge year %s: %s. If this was a partial year served, "
                    "check the 'Partial Year' box on both records, or "
                    "archive the previous holder first."
                ) % (label, rec.lodge_year, others[0].partner_id.display_name))
            non_partial = others.filtered(lambda o: not o.partial_year)
            if non_partial:
                label = dict(OFFICER_POSITIONS).get(rec.position, rec.position)
                raise ValidationError(_(
                    "The position '%s' for lodge year %s is held by %s as "
                    "a full term.  To add a partial-year entry, first mark "
                    "the existing record as 'Partial Year' as well."
                ) % (label, rec.lodge_year, non_partial[0].partner_id.display_name))

    @api.constrains('partner_id', 'position', 'lodge_year')
    def _check_no_duplicate_member_position(self):
        """Prevent the same member from being assigned the same position
        twice in the same lodge year (regardless of partial_year flag).
        Archived records are excluded from this check."""
        for rec in self:
            if not (rec.partner_id and rec.position and rec.lodge_year):
                continue
            if not rec.active:
                continue
            dupes = self.with_context(active_test=True).search([
                ('partner_id', '=', rec.partner_id.id),
                ('position', '=', rec.position),
                ('lodge_year', '=', rec.lodge_year),
                ('active', '=', True),
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

    # ── Sync current officer position to contact ────────────
    def _sync_officer_position_to_partner(self):
        """Update x_elks_officer_position on the partner based on the
        most recent *active* officer term for the current lodge year.
        If the partner has no active term for the current year, clear
        the position."""
        current_year = _default_lodge_year(self)
        partners = self.mapped('partner_id')
        for partner in partners:
            term = self.with_context(active_test=True).search([
                ('partner_id', '=', partner.id),
                ('lodge_year', '=', current_year),
                ('active', '=', True),
            ], order='id desc', limit=1)
            new_pos = term.position if term else False
            if partner.x_elks_officer_position != new_pos:
                partner.write({'x_elks_officer_position': new_pos})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_officer_position_to_partner()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'position' in vals or 'partner_id' in vals or 'lodge_year' in vals:
            self._sync_officer_position_to_partner()
        return res

    def action_archive_term(self):
        """Archive an officer term mid-year instead of deleting.

        Marks the record as partial year, sets the end date, hides from
        website, and deactivates it.  The record remains in the member's
        history for audit purposes.
        """
        today = fields.Date.today()
        self.write({
            'active': False,
            'partial_year': True,
            'show_on_website': False,
            'date_end': today,
        })
        self._sync_officer_position_to_partner()

    def unlink(self):
        """Prevent deletion of officer terms — archive them instead.

        This preserves history.  Only truly empty/erroneous records
        (created in the same session) can be deleted via the ORM.
        """
        for rec in self:
            if rec.create_date and rec.partner_id:
                # Archive instead of deleting
                rec.action_archive_term()
        # Filter out the ones we just archived
        remaining = self.filtered(lambda r: not r.partner_id)
        if remaining:
            partners = remaining.mapped('partner_id')
            res = super(ElksOfficerTerm, remaining).unlink()
            current_year = _default_lodge_year(self)
            for partner in partners:
                term = self.search([
                    ('partner_id', '=', partner.id),
                    ('lodge_year', '=', current_year),
                ], order='id desc', limit=1)
                new_pos = term.position if term else False
                if partner.x_elks_officer_position != new_pos:
                    partner.write({'x_elks_officer_position': new_pos})
            return res
        return True
