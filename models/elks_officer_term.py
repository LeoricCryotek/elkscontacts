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

    # ── Vacate / Resignation tracking ────────────────────────
    # When an officer resigns, retires, or is removed mid-term we
    # DON'T delete the term row (that would lose the historical
    # record of who held the seat). Instead we stamp these fields.
    # The roster report and public website check x_is_vacated and
    # render the position as "Vacant" while preserving the audit
    # trail here.
    # NB: no tracking=True on these — elks.officer.term does not
    # inherit mail.thread yet, and Odoo 19 warns about the flag on
    # non-mail models. Add mail.thread inheritance to the model if
    # you want a chatter audit trail (that also requires a small
    # schema migration).
    x_vacated_date = fields.Date(
        "Vacated On",
        help="Date the officer stopped serving in this position. "
             "When set, the roster report and public website will show "
             "this position as Vacant. The officer's name is preserved "
             "on this record for the audit trail.",
    )
    x_vacated_reason = fields.Selection([
        ('resigned', 'Resigned'),
        ('retired', 'Retired'),
        ('removed', 'Removed'),
        ('deceased', 'Deceased'),
        ('other', 'Other'),
    ], string="Vacate Reason")
    x_vacated_notes = fields.Text(
        "Vacate Notes",
        help="Optional detail on why the position was vacated.",
    )
    x_is_vacated = fields.Boolean(
        string="Position Vacant",
        compute='_compute_x_is_vacated', store=True, index=True,
        help="True when the officer has left this position mid-term. "
             "Report and website will render this seat as Vacant.",
    )

    @api.depends('x_vacated_date')
    def _compute_x_is_vacated(self):
        for rec in self:
            rec.x_is_vacated = bool(rec.x_vacated_date)

    def action_open_vacate_wizard(self):
        """Open the small wizard used to mark this officer as vacated.

        Prompts for date, reason, and optional notes so the Secretary
        never has to remember which fields to fill by hand. On confirm
        the wizard writes the fields, updates date_end if not already
        set, and posts a chatter note.
        """
        self.ensure_one()
        if self.x_is_vacated:
            raise ValidationError(_(
                "This term is already marked as vacated on %s. "
                "Clear the vacated date first if you need to change it."
            ) % self.x_vacated_date)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Mark Officer Vacated'),
            'res_model': 'elks.officer.vacate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_term_id': self.id,
            },
        }

    def action_open_fill_vacant_position(self):
        """Open the Officer Term create form pre-filled to backfill
        this vacant seat with a replacement.

        Defaults the new term to the same position + lodge year, with
        a start date the day after this term was vacated, and marks it
        partial_year so it doesn't collide with the vacated original
        on any lodge-year uniqueness checks.
        """
        self.ensure_one()
        if not self.x_is_vacated:
            raise ValidationError(_(
                "This position isn't marked as vacant. Use the "
                "'Mark Officer Vacated' button first to record the "
                "vacancy, then fill it."
            ))
        from datetime import timedelta
        new_start = (self.x_vacated_date + timedelta(days=1)) if \
            self.x_vacated_date else False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fill Vacant Position'),
            'res_model': 'elks.officer.term',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_position': self.position,
                'default_lodge_year': self.lodge_year,
                'default_officer_type': self.officer_type,
                'default_partial_year': True,
                'default_date_start': new_start,
            },
        }
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
    @api.constrains('position', 'lodge_year', 'partial_year', 'active',
                    'x_vacated_date', 'date_start', 'date_end')
    def _check_unique_position_per_year(self):
        """Only block a new term when its date range OVERLAPS an
        existing holder's for the same position and lodge year.

        Two terms for the same position + lodge year are allowed if:
        - one or more is archived (``active=False``),
        - one or more is vacated (``x_is_vacated=True``) — they held
          the seat historically but are no longer occupying it,
        - or their ``date_start``/``date_end`` windows don't overlap.

        A missing ``date_start`` defaults to April 1 of the lodge year
        and a missing ``date_end`` defaults to March 31 of the next
        year, so a term with no dates behaves as a full-year term.
        """
        import datetime as _dt

        def _bounds(term):
            """Return (start, end) date bounds for the term. Fills in
            April 1 -> March 31 defaults from lodge_year when either
            side is blank."""
            start = term.date_start
            end = term.date_end
            if not (start and end) and term.lodge_year:
                try:
                    y_start = int(term.lodge_year.split('-')[0])
                    start = start or _dt.date(y_start, 4, 1)
                    end = end or _dt.date(y_start + 1, 3, 31)
                except (ValueError, IndexError):
                    pass
            return start, end

        for rec in self:
            if not rec.position or not rec.lodge_year or not rec.active:
                continue
            # Vacated terms are not "currently holding" — skip.
            if rec.x_is_vacated:
                continue
            rec_start, rec_end = _bounds(rec)

            # Look at every other active, non-vacated term for the
            # same position + lodge year.
            others = self.with_context(active_test=True).search([
                ('id', '!=', rec.id),
                ('position', '=', rec.position),
                ('lodge_year', '=', rec.lodge_year),
                ('active', '=', True),
                ('x_is_vacated', '=', False),
            ])
            if not others:
                continue

            for other in others:
                other_start, other_end = _bounds(other)
                # Non-overlapping windows: rec ends before other starts
                # OR other ends before rec starts.
                if (rec_end and other_start and rec_end < other_start):
                    continue
                if (other_end and rec_start and other_end < rec_start):
                    continue
                # Overlap detected — block with a clear message that
                # names the conflicting date range.
                label = dict(OFFICER_POSITIONS).get(
                    rec.position, rec.position)
                raise ValidationError(_(
                    "The position '%(pos)s' for lodge year %(yr)s "
                    "overlaps an existing term held by %(other)s "
                    "(%(o_start)s - %(o_end)s). Adjust the Term Start "
                    "or Term End dates so the two windows don't "
                    "overlap, mark the previous holder as vacated, or "
                    "archive the previous term."
                ) % {
                    'pos': label,
                    'yr': rec.lodge_year,
                    'other': other.partner_id.display_name,
                    'o_start': other_start or _('(no start)'),
                    'o_end': other_end or _('(no end)'),
                })

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
        most recent *active, non-vacated* officer term for the current
        lodge year. Vacated terms are treated as "no longer holding"
        the position so the res.partner-side uniqueness constraint
        doesn't block backfilling the vacant seat."""
        current_year = _default_lodge_year(self)
        partners = self.mapped('partner_id')
        for partner in partners:
            term = self.with_context(active_test=True).search([
                ('partner_id', '=', partner.id),
                ('lodge_year', '=', current_year),
                ('active', '=', True),
                ('x_is_vacated', '=', False),
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
        # x_vacated_date drives x_is_vacated, so a vacate write needs
        # to re-sync the partner's officer position (clearing it, if
        # this was their only current term).
        if ('position' in vals or 'partner_id' in vals
                or 'lodge_year' in vals or 'x_vacated_date' in vals):
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
