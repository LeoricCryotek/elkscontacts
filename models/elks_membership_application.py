# -*- coding: utf-8 -*-
"""Membership Application / Proposal Tracking.

Tracks the full lifecycle of an Elks membership application:
  Proposed → Investigation → Balloting → Initiated → Member (or Rejected)

Each application links:
  - The applicant (may not yet be a res.partner with member status)
  - The proposer (an existing Elks member / res.partner)
  - Application details from the proposal form

On initiation the applicant is flagged as a full member and an initiation
dues payment can be created linking to the APP-001 / APP-002 rate codes.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta

import datetime
import logging

_logger = logging.getLogger(__name__)


def _reinstatement_year_selections(self):
    """Generate selection list of lodge years for reinstatement.
    Goes back 100 years and forward 10 years to cover long-lapsed members."""
    today = datetime.date.today()
    current_start = today.year if today.month >= 4 else today.year - 1
    years = []
    for y in range(current_start - 100, current_start + 11):
        label = f"{y}-{y + 1}"
        years.append((label, label))
    return years


APPLICATION_STAGES = [
    ('proposed', 'Proposed'),
    ('investigation', 'Under Investigation'),
    ('balloting', 'Balloting'),
    ('elected', 'Elected'),
    ('initiated', 'Initiated'),
    ('rejected', 'Rejected'),
    ('withdrawn', 'Withdrawn'),
]


class ElksMembershipApplication(models.Model):
    _name = "elks.membership.application"
    _description = "Elks Membership Application"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "date_proposed desc, id desc"

    # ------------------------------------------------------------------
    # Core fields
    # ------------------------------------------------------------------
    name = fields.Char(
        "Reference", required=True, readonly=True, copy=False,
        default=lambda self: _('New'),
    )
    stage = fields.Selection(
        APPLICATION_STAGES, string="Stage", default='proposed',
        required=True, tracking=True, index=True,
        help="Current stage in the membership application process.",
    )
    active = fields.Boolean(default=True)
    application_type = fields.Selection([
        ('new', 'New Member'),
        ('reinstatement', 'Reinstatement'),
        ('affiliation', 'Affiliation / Transfer'),
    ], string="Application Type", default='new', required=True, tracking=True,
    )

    # ------------------------------------------------------------------
    # Reinstatement / Affiliation / Transfer fields
    # ------------------------------------------------------------------
    # Per BPOE Code 561300 — Request Form for Transfer Dimit,
    # Certificate of Release, or Absolute Dimit.

    # Previous lodge information (the lodge they are coming FROM)
    reinstatement_previous_lodge = fields.Char(
        "Previous Lodge Name & No.",
        help="Lodge name and number where applicant was previously "
             "a member (e.g. 'Hoquiam 1082').",
    )
    reinstatement_previous_state = fields.Many2one(
        'res.country.state', string="Previous Lodge State",
        domain="[('country_id.code', '=', 'US')]",
    )
    reinstatement_previous_member_num = fields.Char(
        "Previous Member Number",
        help="Membership number at the previous lodge.",
    )
    reinstatement_previous_secretary = fields.Char(
        "Previous Lodge Secretary",
        help="Name of the Secretary at the previous lodge.",
    )

    # Dimit / Release type — how they left the previous lodge
    dimit_type = fields.Selection([
        ('transfer_dimit', 'Transfer Dimit'),
        ('certificate_of_release', 'Certificate of Release'),
        ('absolute_dimit', 'Absolute Dimit'),
    ], string="Dimit Type",
        help="Per BPOE Sections 14.110 (Transfer Dimit), "
             "14.180 (Certificate of Release), and "
             "14.120 (Absolute Dimit).",
    )
    dimit_date = fields.Date(
        "Dimit / Release Date",
        help="Date the Transfer Dimit, Certificate of Release, "
             "or Absolute Dimit was issued.",
    )
    certificate_of_release_fee_paid = fields.Boolean(
        "Release Fee Paid ($20)",
        help="The $20 Certificate of Release fee has been paid "
             "(per Section 14.180).",
    )

    # Reason for leaving (reinstatements — they didn't dimit)
    reinstatement_reason = fields.Selection([
        ('dropped_nonpayment', 'Dropped for Non-Payment'),
        ('transfer_dimit', 'Transfer Dimit (Sec. 14.110)'),
        ('certificate_of_release', 'Certificate of Release (Sec. 14.180)'),
        ('absolute_dimit', 'Absolute Dimit (Sec. 14.120)'),
        ('other', 'Other'),
    ], string="Reason for Leaving",
    )
    reinstatement_reason_other = fields.Char("Other Reason")

    # Timing
    reinstatement_last_year_good_standing = fields.Selection(
        selection=_reinstatement_year_selections,
        string="Last Year in Good Standing",
        help="The last lodge year the member was in good standing "
             "before dropping or dimitting.",
    )
    reinstatement_membership_ended = fields.Date(
        "When Membership Ended",
        help="Date the member's previous membership ended "
             "(dropped, dimitted, or transferred).",
    )

    # Fees
    reinstatement_fee = fields.Float("Reinstatement Fee")
    affiliation_fee = fields.Float("Affiliation Fee")
    certificate_of_release_fee = fields.Float(
        "Certificate of Release Fee",
        default=20.00,
        help="$20 fee per Section 14.180.",
    )
    prorated_dues = fields.Float("Prorated Dues")

    # ------------------------------------------------------------------
    # Applicant information
    # ------------------------------------------------------------------
    applicant_partner_id = fields.Many2one(
        'res.partner', string="Applicant Contact",
        help="If the applicant already exists as a contact, link here. "
             "Otherwise a new contact is created on initiation.",
        tracking=True,
    )
    applicant_first_name = fields.Char("First Name", required=True, tracking=True)
    applicant_middle_name = fields.Char("Middle Name")
    applicant_last_name = fields.Char("Last Name", required=True, tracking=True)
    applicant_suffix = fields.Char("Suffix")
    applicant_display_name = fields.Char(
        "Applicant Name", compute='_compute_applicant_display_name', store=True,
    )
    applicant_sex = fields.Selection(
        [('male', 'Male'), ('female', 'Female')],
        string="Sex",
    )
    applicant_date_of_birth = fields.Date("Date of Birth")
    applicant_birth_city = fields.Char("Birth City")
    applicant_birth_country_id = fields.Many2one(
        'res.country', string="Birth Country",
        default=lambda self: self.env.ref('base.us', raise_if_not_found=False),
    )
    applicant_birth_state_id = fields.Many2one(
        'res.country.state', string="Birth State",
        domain="[('country_id', '=', applicant_birth_country_id)]",
    )

    # Contact info
    applicant_street = fields.Char("Home Address")
    applicant_street2 = fields.Char("Home Address 2")
    applicant_city = fields.Char("City")
    applicant_state_id = fields.Many2one('res.country.state', string="State")
    applicant_zip = fields.Char("Zip")
    applicant_phone = fields.Char("Home Phone")
    applicant_mobile = fields.Char("Cell Phone")
    applicant_email = fields.Char("Email")

    # Business info
    applicant_occupation = fields.Char("Occupation")
    applicant_employer = fields.Char("Employer / Business")
    applicant_business_address = fields.Char("Business Address")
    applicant_business_phone = fields.Char("Business Phone")

    # Spouse
    applicant_spouse_name = fields.Char("Spouse Name")

    # Military
    applicant_military_branch = fields.Selection([
        ('army', 'U.S. Army'),
        ('navy', 'U.S. Navy'),
        ('air_force', 'U.S. Air Force'),
        ('marine_corps', 'U.S. Marine Corps'),
        ('coast_guard', 'U.S. Coast Guard'),
        ('space_force', 'U.S. Space Force'),
        ('army_reserve', 'U.S. Army Reserve'),
        ('navy_reserve', 'U.S. Navy Reserve'),
        ('air_force_reserve', 'U.S. Air Force Reserve'),
        ('marine_corps_reserve', 'U.S. Marine Corps Reserve'),
        ('coast_guard_reserve', 'U.S. Coast Guard Reserve'),
        ('army_national_guard', 'Army National Guard'),
        ('air_national_guard', 'Air National Guard'),
    ], string="Branch of Service")
    applicant_military_discharge_type = fields.Selection([
        ('honorable', 'Honorable'),
        ('general', 'General (Under Honorable Conditions)'),
        ('other_than_honorable', 'Other Than Honorable'),
        ('bad_conduct', 'Bad Conduct'),
        ('dishonorable', 'Dishonorable'),
        ('medical', 'Medical'),
        ('entry_level', 'Entry Level Separation'),
        ('other', 'Other'),
    ], string="Discharge Type")
    applicant_military_discharge_other = fields.Char("Discharge Type (Other)")
    applicant_military_discharge_date = fields.Date("Discharge Date")

    # ------------------------------------------------------------------
    # Proposer (must be an existing Elks member)
    # ------------------------------------------------------------------
    proposer_id = fields.Many2one(
        'res.partner', string="Proposed By", required=True,
        domain="[('x_is_member', '=', True)]",
        tracking=True,
        help="The Elks member who is proposing this applicant.",
    )
    proposer_member_num = fields.Char(
        related='proposer_id.x_detail_member_num',
        string="Proposer Member #", store=True,
    )
    proposer_lodge_num = fields.Char(
        related='proposer_id.x_detail_lodge_num',
        string="Proposer Lodge #", store=True,
    )

    # Second reference / endorser (optional)
    endorser_id = fields.Many2one(
        'res.partner', string="Endorsed By",
        domain="[('x_is_member', '=', True)]",
        help="Optional second member endorsing this application.",
    )

    # ------------------------------------------------------------------
    # Application questions (from the official proposal form)
    # ------------------------------------------------------------------
    q_belief_in_god = fields.Boolean(
        "Believes in God?", required=True,
        help="Do you believe in God and are you willing to attest to that belief?",
    )
    q_us_citizen = fields.Boolean(
        "Is a US Citizen?", required=True,
        help="Are you a citizen of the United States of America who will "
             "pledge allegiance to and salute our Flag?",
    )
    q_no_subversive_affiliation = fields.Boolean(
        "No Subversive Affiliation?", required=True,
        help="Applicant affirms they are not now a member of, or directly or "
             "indirectly participating in, any group or organization supporting "
             "the overthrow of the Government of the United States.",
    )
    q_never_convicted_felony = fields.Boolean(
        "No Felony or Moral Turpitude Conviction?", required=True,
        help="Has never pleaded guilty or been convicted of a felony or "
             "crime of moral turpitude.",
    )
    q_willing_to_assume_obligation = fields.Boolean(
        "Willing to Assume Obligation?", required=True,
        help="Willing to assume an obligation that will not conflict with "
             "duties to self, family, religious or political opinions, and "
             "will uphold the Constitution and laws of the United States.",
    )
    q_bona_fide_resident = fields.Boolean(
        "Bona Fide Resident?", required=True,
        help="Has been a bona fide resident within the jurisdiction of this "
             "Lodge immediately preceding the date of this application.",
    )
    q_authorize_electronic = fields.Boolean(
        "Authorizes Electronic Communications?",
        help="Authorizes receipt by electronic means of the Elks Magazine, "
             "Lodge newsletters, and any required notices.",
    )
    q_good_character = fields.Boolean(
        "Good Character Attested?", required=True,
    )
    # Previously proposed at another lodge
    q_previously_proposed = fields.Boolean(
        "Previously Proposed at Any Lodge?",
        help="Has the applicant ever been proposed for membership in any "
             "Elks Lodge before?",
    )
    q_previous_lodge = fields.Char("Previous Lodge")
    q_previous_lodge_date = fields.Date("Previous Proposal Date")
    q_previous_lodge_result = fields.Char("Previous Result")

    # Military service toggle (controls tab visibility)
    applicant_served_military = fields.Boolean(
        "Served in Armed Forces?",
        help="Has the applicant ever served in the armed forces of the "
             "United States of America?",
    )

    # ------------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------------
    date_proposed = fields.Date(
        "Date Proposed", default=fields.Date.context_today,
        required=True, tracking=True,
        help="The date the application was formally proposed to the "
             "lodge. Auto-set to today when creating a new application.",
    )
    date_read_onto_floor = fields.Date(
        "Read Onto Floor",
        help="The date the application was read onto the lodge floor "
             "at a regular session. Per BPOE statute, the application "
             "must be read at the first regular session after it is "
             "received by the Secretary.",
        tracking=True,
    )
    date_read_first = fields.Date(
        "First Reading",
        help="The date the application was first read aloud at a lodge "
             "meeting. Set this after the reading occurs (not in advance).",
    )
    date_investigation_assigned = fields.Date(
        "Investigation Assigned",
        help="Auto-populated when the application moves to the "
             "Investigation stage. Can be adjusted manually if the "
             "investigator was assigned on a different date.",
    )
    date_investigation_complete = fields.Date(
        "Investigation Complete",
        help="Enter the date the investigator finished their review. "
             "Set this after the investigation is done (not in advance).",
    )
    date_balloting = fields.Date(
        "Balloting Date",
        help="Auto-populated when the application moves to Balloting. "
             "Can be adjusted to the actual date the vote takes place.",
    )
    date_elected = fields.Date(
        "Date Elected",
        help="Auto-populated when the applicant is elected. Records "
             "the date of the successful ballot vote.",
    )
    date_initiated = fields.Date(
        "Date Initiated",
        help="Auto-populated when the Initiate action is used. Records "
             "the date the applicant completed the initiation ceremony.",
    )
    date_rejected = fields.Date(
        "Date Rejected",
        help="Auto-populated when the application is rejected. Records "
             "the date of the rejection decision.",
    )

    # ------------------------------------------------------------------
    # Investigation
    # ------------------------------------------------------------------
    investigator_id = fields.Many2one(
        'res.partner', string="Investigator",
        domain="[('x_is_member', '=', True),"
               " ('id', 'in', investigation_committee_member_ids)]",
        tracking=True,
        help="Select a member from the Investigation Committee to "
             "conduct the background review of the applicant.",
    )
    investigation_committee_member_ids = fields.Many2many(
        'res.partner', compute='_compute_investigation_committee_members',
        help="Technical field: current Investigation Committee members.",
    )
    investigation_notes = fields.Text(
        "Investigation Notes",
        help="Record findings from the investigation. Include details "
             "about the applicant's background, character references, "
             "and any concerns.",
    )
    investigation_result = fields.Selection([
        ('favorable', 'Favorable'),
        ('unfavorable', 'Unfavorable'),
    ], string="Investigation Result", tracking=True,
        help="The investigator's recommendation. 'Favorable' allows "
             "the application to proceed to balloting. 'Unfavorable' "
             "may lead to rejection.",
    )

    # ------------------------------------------------------------------
    # Balloting
    # ------------------------------------------------------------------
    ballot_all_in_favor = fields.Boolean(
        "All in Favor (Unanimous)",
        help="Check if the ballot was unanimous — all members voted in favor.",
    )
    ballot_result = fields.Selection([
        ('elected', 'Elected'),
        ('rejected', 'Rejected'),
    ], string="Ballot Result", tracking=True,
        help="Set automatically when using the Elected or Reject buttons. "
             "Can also be set manually here — changing the value will "
             "advance the application stage accordingly.",
    )
    ballot_votes_for = fields.Integer(
        "Votes For",
        help="Number of votes in favor of the applicant during the ballot.",
    )
    ballot_votes_against = fields.Integer(
        "Votes Against",
        help="Number of votes against the applicant during the ballot.",
    )

    # ------------------------------------------------------------------
    # Initiation / Fees
    # ------------------------------------------------------------------
    initiation_fee_paid = fields.Boolean("Initiation Fee Paid", tracking=True)
    dues_paid = fields.Boolean("Dues Paid", tracking=True)
    dues_payment_ref = fields.Char(
        "Dues Payment Ref",
        help="Reference to the dues payment record (e.g. payment name from elksfrs).",
    )
    member_number_assigned = fields.Char(
        "Member Number Assigned", tracking=True,
        help="The CLMS member number assigned upon initiation.",
    )

    # ------------------------------------------------------------------
    # Lodge year
    # ------------------------------------------------------------------
    lodge_year = fields.Char(
        "Lodge Year", compute='_compute_lodge_year', store=True,
        help="The lodge year (Apr-Mar) in which this application was proposed.",
    )

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------
    notes = fields.Html("Notes")

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    def _compute_investigation_committee_members(self):
        """Populate the investigator dropdown with current Investigation
        Committee members only."""
        Committee = self.env['elks.committee']
        inv_committee = Committee.search(
            [('name', 'ilike', 'investigation')], limit=1,
        )
        if inv_committee:
            current = inv_committee.member_ids.filtered('is_current')
            partner_ids = current.mapped('partner_id').ids
        else:
            # Fallback: if no Investigation committee exists yet, allow
            # any active member so the form doesn't block work.
            partner_ids = self.env['res.partner'].search(
                [('x_is_member', '=', True)],
            ).ids
        for rec in self:
            rec.investigation_committee_member_ids = partner_ids

    @api.depends('applicant_first_name', 'applicant_middle_name', 'applicant_last_name', 'applicant_suffix')
    def _compute_applicant_display_name(self):
        for rec in self:
            parts = [
                rec.applicant_first_name or '',
                rec.applicant_middle_name or '',
                rec.applicant_last_name or '',
            ]
            name = ' '.join(p.strip() for p in parts if p.strip())
            if rec.applicant_suffix:
                name = f"{name} {rec.applicant_suffix.strip()}"
            rec.applicant_display_name = name or _('New Applicant')

    @api.depends('date_proposed')
    def _compute_lodge_year(self):
        for rec in self:
            if rec.date_proposed:
                d = rec.date_proposed
                # Lodge year runs Apr 1 – Mar 31
                if d.month >= 4:
                    rec.lodge_year = f"{d.year}-{d.year + 1}"
                else:
                    rec.lodge_year = f"{d.year - 1}-{d.year}"
            else:
                rec.lodge_year = False

    # ------------------------------------------------------------------
    # Sequence
    # ------------------------------------------------------------------
    def _build_initiate_partner_vals(self):
        """Build partner values from the application for the initiate contact."""
        self.ensure_one()
        vals = {
            'name': self.applicant_display_name,
            'x_detail_first_name': self.applicant_first_name,
            'x_detail_middle_name': self.applicant_middle_name or False,
            'x_detail_last_name': self.applicant_last_name,
            'x_detail_name_suffix': self.applicant_suffix or False,
            'x_is_initiate': True,
            'x_is_not_member': True,  # not a member yet
            'x_is_guest': False,
            'street': self.applicant_street or False,
            'street2': self.applicant_street2 or False,
            'city': self.applicant_city or False,
            'state_id': self.applicant_state_id.id if self.applicant_state_id else False,
            'zip': self.applicant_zip or False,
            'phone': self.applicant_phone or False,
            'x_detail_cell_phone': self.applicant_mobile or False,
            'email': self.applicant_email or False,
            'x_detail_email_address': self.applicant_email or False,
            'x_detail_spouse_first_name': self.applicant_spouse_name or False,
            'x_branch_of_service': self.applicant_military_branch or False,
            'x_discharge_type': self.applicant_military_discharge_type or False,
            'x_discharge_date': self.applicant_military_discharge_date or False,
            'company_type': 'person',
            'is_company': False,
        }
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'elks.membership.application'
                ) or _('New')
        records = super().create(vals_list)
        for rec in records:
            # Auto-create an initiate contact if none is linked
            if not rec.applicant_partner_id and rec.applicant_first_name:
                partner_vals = rec._build_initiate_partner_vals()
                partner = self.env['res.partner'].with_context(
                    elks_overwrite=False,
                ).create(partner_vals)
                rec.applicant_partner_id = partner
                partner.message_post(
                    body=_(
                        "<strong>Initiate contact created</strong><br/>"
                        "From membership application: %(ref)s<br/>"
                        "Proposed by: %(proposer)s",
                        ref=rec.name,
                        proposer=rec.proposer_id.name if rec.proposer_id else 'N/A',
                    ),
                    message_type='comment', subtype_xmlid='mail.mt_note',
                )
            rec.message_post(
                body=_(
                    "<strong>Application proposed</strong><br/>"
                    "Applicant: %(name)s<br/>"
                    "Proposed by: %(proposer)s<br/>"
                    "Date: %(date)s",
                    name=rec.applicant_display_name,
                    proposer=rec.proposer_id.name,
                    date=rec.date_proposed,
                ),
                message_type='comment', subtype_xmlid='mail.mt_note',
            )
            rec._schedule_clms_activity('proposed')
        return records

    # ------------------------------------------------------------------
    # CLMS activity scheduling
    # ------------------------------------------------------------------
    CLMS_ACTIVITIES = {
        'proposed': "CLMS: Enter new proposed member — %s",
        'investigation': "CLMS: Update investigation status — %s",
        'balloting': "CLMS: Record ballot scheduled — %s",
        'elected': "CLMS: Record election result — %s",
        'initiated': "CLMS: Complete new member initiation entry — %s",
        'rejected': "CLMS: Record application rejection — %s",
    }

    def _schedule_clms_activity(self, stage_key):
        """Schedule a to-do activity for the Secretary to update CLMS."""
        summary_tpl = self.CLMS_ACTIVITIES.get(stage_key)
        if not summary_tpl:
            return
        todo_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not todo_type:
            return
        for rec in self:
            deadline = fields.Date.context_today(self) + relativedelta(days=2)
            rec.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=deadline,
                summary=summary_tpl % rec.applicant_display_name,
                note=_(
                    "Update CLMS to reflect the new member process step.<br/>"
                    "Application: %(ref)s<br/>"
                    "Stage: %(stage)s<br/>"
                    "Applicant: %(name)s",
                    ref=rec.name,
                    stage=stage_key.replace('_', ' ').title(),
                    name=rec.applicant_display_name,
                ),
            )

    # ------------------------------------------------------------------
    # Ballot result ↔ stage sync
    # ------------------------------------------------------------------
    @api.onchange('ballot_result')
    def _onchange_ballot_result(self):
        """When the user manually changes the ballot result dropdown,
        advance the stage to keep the two in sync."""
        for rec in self:
            if rec.ballot_result == 'elected' and rec.stage == 'balloting':
                rec.stage = 'elected'
                if not rec.date_elected:
                    rec.date_elected = fields.Date.context_today(self)
            elif rec.ballot_result == 'rejected' and rec.stage in ('balloting', 'proposed', 'investigation'):
                rec.stage = 'rejected'
                if not rec.date_rejected:
                    rec.date_rejected = fields.Date.context_today(self)

    # ------------------------------------------------------------------
    # Wizard-based actions for Elect and Initiate
    # ------------------------------------------------------------------
    def action_open_ballot_wizard(self):
        """Open the ballot recording wizard as a popup."""
        self.ensure_one()
        if self.stage != 'balloting':
            raise UserError(_("Only applications in balloting can be elected."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Record Ballot Result'),
            'res_model': 'elks.ballot.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_application_id': self.id},
        }

    def action_open_initiate_wizard(self):
        """Open the initiation wizard as a popup."""
        self.ensure_one()
        if self.stage != 'elected':
            raise UserError(_("Only elected applicants can be initiated."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Initiate New Member'),
            'res_model': 'elks.initiate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_application_id': self.id,
                'default_member_number': self.member_number_assigned or '',
                'default_initiation_fee_paid': self.initiation_fee_paid,
                'default_dues_paid': self.dues_paid,
            },
        }

    # ------------------------------------------------------------------
    # Stage transitions
    # ------------------------------------------------------------------
    def action_start_investigation(self):
        """Move to Investigation stage."""
        for rec in self:
            if rec.stage != 'proposed':
                raise UserError(_("Only proposed applications can move to investigation."))
            vals = {'stage': 'investigation'}
            if not rec.date_investigation_assigned:
                vals['date_investigation_assigned'] = fields.Date.context_today(self)
            rec.write(vals)
            rec.message_post(
                body=_("<strong>Investigation started</strong>%s",
                       f"<br/>Investigator: {rec.investigator_id.name}" if rec.investigator_id else ""),
                message_type='comment', subtype_xmlid='mail.mt_note',
            )
            rec._schedule_clms_activity('investigation')

    def action_move_to_balloting(self):
        """Move to Balloting stage."""
        for rec in self:
            if rec.stage not in ('proposed', 'investigation'):
                raise UserError(_("Only proposed or investigated applications can move to balloting."))
            vals = {'stage': 'balloting'}
            if not rec.date_balloting:
                vals['date_balloting'] = fields.Date.context_today(self)
            rec.write(vals)
            rec.message_post(
                body=_("<strong>Moved to balloting</strong><br/>Applicant: %s", rec.applicant_display_name),
                message_type='comment', subtype_xmlid='mail.mt_note',
            )
            rec._schedule_clms_activity('balloting')

    def action_elect(self, votes_for=0, votes_against=0):
        """Record a successful ballot — Elected."""
        for rec in self:
            if rec.stage != 'balloting':
                raise UserError(_("Only applications in balloting can be elected."))
            vals = {
                'stage': 'elected',
                'ballot_result': 'elected',
            }
            if votes_for:
                vals['ballot_votes_for'] = votes_for
            if votes_against:
                vals['ballot_votes_against'] = votes_against
            if not rec.date_elected:
                vals['date_elected'] = fields.Date.context_today(self)
            rec.write(vals)
            rec.message_post(
                body=_("<strong>Elected by ballot</strong><br/>Applicant: %s<br/>"
                       "Votes For: %s / Against: %s",
                       rec.applicant_display_name,
                       rec.ballot_votes_for, rec.ballot_votes_against),
                message_type='comment', subtype_xmlid='mail.mt_note',
            )
            rec._schedule_clms_activity('elected')

    def action_reject(self):
        """Record a rejected ballot or withdrawal."""
        for rec in self:
            vals = {
                'stage': 'rejected',
                'ballot_result': 'rejected',
            }
            if not rec.date_rejected:
                vals['date_rejected'] = fields.Date.context_today(self)
            rec.write(vals)
            rec.message_post(
                body=_("<strong>Application rejected</strong><br/>Applicant: %s", rec.applicant_display_name),
                message_type='comment', subtype_xmlid='mail.mt_note',
            )
            rec._schedule_clms_activity('rejected')

    def action_withdraw(self):
        """Applicant or lodge withdraws the application."""
        for rec in self:
            if rec.stage in ('initiated',):
                raise UserError(_("Cannot withdraw an application that has already been initiated."))
            rec.write({'stage': 'withdrawn'})
            rec.message_post(
                body=_("<strong>Application withdrawn</strong><br/>Applicant: %s", rec.applicant_display_name),
                message_type='comment', subtype_xmlid='mail.mt_note',
            )

    def action_initiate(self):
        """Initiate the elected applicant — create or update the member contact.

        This:
          1. Creates a res.partner if applicant_partner_id is not set, or
             updates the existing partner to flag as member.
          2. Sets the member number if provided.
          3. Advances the dues paid-to date by one year from initiation.
          4. Logs everything to chatter on both the application and the contact.
        """
        for rec in self:
            if rec.stage != 'elected':
                raise UserError(_("Only elected applicants can be initiated."))

            partner = rec.applicant_partner_id
            if not partner:
                # Should not normally happen (contact is created at proposal),
                # but handle gracefully — create a member contact now.
                partner_vals = rec._build_initiate_partner_vals()
                partner_vals['x_is_initiate'] = False
                partner_vals['x_is_not_member'] = False  # makes x_is_member = True
                if rec.member_number_assigned:
                    partner_vals['x_detail_member_num'] = rec.member_number_assigned
                partner = self.env['res.partner'].with_context(
                    elks_overwrite=False,
                ).create(partner_vals)
                rec.applicant_partner_id = partner
            else:
                # Promote initiate → full member
                update_vals = {
                    'x_is_initiate': False,
                    'x_is_not_member': False,  # makes x_is_member = True
                }
                if rec.member_number_assigned and not partner.x_detail_member_num:
                    update_vals['x_detail_member_num'] = rec.member_number_assigned
                # Sync any fields updated on the application since proposal
                if rec.applicant_email and not partner.email:
                    update_vals['email'] = rec.applicant_email
                if rec.applicant_phone and not partner.phone:
                    update_vals['phone'] = rec.applicant_phone
                if rec.applicant_mobile and not partner.x_detail_cell_phone:
                    update_vals['x_detail_cell_phone'] = rec.applicant_mobile
                partner.write(update_vals)

            # Advance dues paid-to date by one year from initiation
            initiation_date = rec.date_initiated or fields.Date.context_today(self)
            current_paid_to = partner.x_detail_dues_paid_to_date
            if current_paid_to and current_paid_to > initiation_date:
                new_paid_to = current_paid_to + relativedelta(years=1)
            else:
                # New member — set to end of current lodge year (Mar 31)
                if initiation_date.month >= 4:
                    new_paid_to = initiation_date.replace(year=initiation_date.year + 1, month=3, day=31)
                else:
                    new_paid_to = initiation_date.replace(month=3, day=31)
            partner.write({'x_detail_dues_paid_to_date': new_paid_to})

            vals = {
                'stage': 'initiated',
            }
            if not rec.date_initiated:
                vals['date_initiated'] = initiation_date
            rec.write(vals)

            # Chatter on the application
            rec.message_post(
                body=_(
                    "<strong>Member Initiated</strong><br/>"
                    "Contact: <a href='/odoo/contacts/%(pid)s'>%(pname)s</a><br/>"
                    "Member #: %(mnum)s<br/>"
                    "Dues Paid Through: %(paid_to)s",
                    pid=partner.id,
                    pname=partner.name,
                    mnum=rec.member_number_assigned or 'Not yet assigned',
                    paid_to=new_paid_to,
                ),
                message_type='comment', subtype_xmlid='mail.mt_note',
            )

            # Chatter on the member contact
            partner.message_post(
                body=_(
                    "<strong>Initiated as new Elks Member</strong><br/>"
                    "Application: %(ref)s<br/>"
                    "Proposed by: %(proposer)s<br/>"
                    "Date Initiated: %(date)s<br/>"
                    "Dues Paid Through: %(paid_to)s",
                    ref=rec.name,
                    proposer=rec.proposer_id.name,
                    date=rec.date_initiated,
                    paid_to=new_paid_to,
                ),
                message_type='comment', subtype_xmlid='mail.mt_note',
            )

            _logger.info(
                'Application %s: initiated %s as member (partner %s)',
                rec.name, rec.applicant_display_name, partner.id,
            )
            rec._schedule_clms_activity('initiated')

    def action_create_initiation_payment(self):
        """Open a new dues payment pre-filled for initiation fees.

        Requires the elksfrs module to be installed.
        """
        self.ensure_one()
        if not self.applicant_partner_id:
            raise UserError(_(
                "Please initiate the applicant first (creates the member contact) "
                "before creating the initiation payment."
            ))
        # Check that elksfrs is installed
        if 'elks.dues.payment' not in self.env:
            raise UserError(_(
                "The Elks FRS module must be installed to create dues payments."
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Initiation Payment'),
            'res_model': 'elks.dues.payment',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': self.applicant_partner_id.id,
                'default_payment_type': 'custom',
                'default_application_id': self.id,
            },
        }

    def action_reset_to_proposed(self):
        """Reset a rejected/withdrawn application back to proposed (for corrections)."""
        for rec in self:
            if rec.stage not in ('rejected', 'withdrawn'):
                raise UserError(_("Only rejected or withdrawn applications can be reset."))
            rec.write({'stage': 'proposed'})
            rec.message_post(
                body=_("<strong>Application reset to Proposed</strong>"),
                message_type='comment', subtype_xmlid='mail.mt_note',
            )
