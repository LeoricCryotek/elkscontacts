# -*- coding: utf-8 -*-
# Copyright (C) 2025
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html)

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


def _current_lodge_year_start(today=None):
    """Return April 1 of the current lodge year.

    The Elks lodge year runs April 1 – March 31.
    If today is Jan–Mar, we're still in the previous lodge year
    (started April 1 of last calendar year).
    If today is Apr–Dec, the current lodge year started April 1 of this year.
    """
    if today is None:
        today = date.today()
    if today.month >= 4:
        return date(today.year, 4, 1)
    else:
        return date(today.year - 1, 4, 1)


class ResPartner(models.Model):
    """Extend res.partner with Elks Lodge membership fields.

    Adds lodge membership data (member number, dues, officer positions),
    CLMS import/export fields, volunteer ↔ HR employee sync, and
    lodge-specific local fields (keys, door codes, etc.).
    """
    _inherit = "res.partner"

    # ----------------------------
    # Contact type tags (multi-select)
    # ----------------------------
    x_is_volunteer = fields.Boolean("Volunteer", index=True)
    x_is_customer = fields.Boolean("Customer", index=True)
    x_is_guest = fields.Boolean("Guest", index=True)
    x_is_initiate = fields.Boolean(
        "Initiate", index=True,
        help="Applicant who has been proposed for membership but not yet "
             "initiated. Cleared automatically when the member is initiated.",
    )

    # Link to the HR employee record created for volunteers
    x_volunteer_employee_id = fields.Many2one(
        'hr.employee', string='Volunteer Employee Record',
        ondelete='set null', copy=False,
        help='Automatically created HR employee record when marked as a volunteer.',
    )

    # ----------------------------
    # Local (chapter-specific) data
    # ----------------------------
    x_local_door_code = fields.Char("Door Code", help="Local building or door access code.")
    x_local_has_key = fields.Boolean("Has Key")
    x_local_key_numbers = fields.Char(
        "Key Number(s)",
        help="Key number(s) issued to this person, e.g. '101, 102'.",
    )
    x_local_card_delivery = fields.Selection([
        ('not_delivered', 'Not Delivered'),
        ('hand', 'Delivered by Hand'),
        ('mailed', 'Mailed'),
    ], string="Membership Card", default='not_delivered',
        help="How the membership card was delivered to this member.",
    )
    x_local_card_delivery_date = fields.Date(
        "Card Delivery Date",
        help="Date the membership card was delivered or mailed.",
    )
    x_local_volunteer_active = fields.Boolean("Volunteer Active")
    x_local_bartender = fields.Boolean("Bartender")
    x_local_kitchen = fields.Boolean("Kitchen")
    x_local_sanitation = fields.Boolean("Sanitation")

    # ----------------------------
    # Membership / Lodge
    # ----------------------------
    x_is_not_member = fields.Boolean("Is not an Elks Member", default=True, index=True)
    x_is_member = fields.Boolean(
        "Is Elks Member",
        compute='_compute_x_is_member',
        inverse='_inverse_x_is_member',
        store=True,
        index=True,
    )
    x_detail_id = fields.Char("DetailID", index=True)
    x_detail_lodge_id = fields.Char("DetailLodgeID")
    x_detail_lodge_num = fields.Char("DetailLodgeNum")
    x_detail_member_num = fields.Char("DetailMemberNum", index=True)
    x_lodge_report_lodge_name = fields.Char("LodgeReportLodgeName")

    # ----------------------------
    # Name components / salutation
    # ----------------------------
    x_detail_name_prefix = fields.Char("DetailNamePrefix")
    x_detail_first_name = fields.Char("DetailFirstName")
    x_detail_name_salutation = fields.Char("DetailNameSalutation")  # maps to title
    x_detail_middle_name = fields.Char("DetailMiddleName")
    x_detail_last_name = fields.Char("DetailLastName")
    x_detail_name_suffix = fields.Char("DetailNameSuffix")

    # ----------------------------
    # Elks specifics / accounting
    # ----------------------------
    x_detail_elk_title = fields.Char("DetailElkTitle")
    x_detail_delinquent_months = fields.Integer("DetailDelinquentMonths")
    x_detail_dues_paid_to_date = fields.Date("DetailDuesPaidToDate")

    # ----------------------------
    # Address (source) + USPS/CASS
    # ----------------------------
    x_detail_active_address_line1 = fields.Char("DetailActiveAddressLine1")
    x_detail_active_address_line2 = fields.Char("DetailActiveAddressLine2")
    x_detail_active_city = fields.Char("DetailActiveCity")
    x_detail_active_state = fields.Char("DetailActiveState")
    x_detail_active_zip = fields.Char("DetailActiveZip")
    x_detail_active_country = fields.Char("DetailActiveCountry")

    x_detail_active_carrier_code = fields.Char("DetailActiveCarrierCode")
    x_detail_active_dpc = fields.Char("DetailActiveDPC")
    x_detail_active_postal_lot = fields.Char("DetailActivePostalLOT")
    x_detail_active_usps_type = fields.Char("DetailActiveUSPStype")
    x_detail_active_cass_result_code = fields.Char("DetailActiveCASSResultCode")

    x_detail_active_send_no_mail = fields.Boolean("DetailActiveSendNoMail")
    x_detail_active_is_undeliverable = fields.Boolean("DetailActiveIsUndeliverable")
    x_detail_active_send_no_magazine = fields.Boolean("DetailActiveSendNoMagazine")

    # ----------------------------
    # Household
    # ----------------------------
    x_detail_spouse_first_name = fields.Char("DetailSpouseFirstName")
    x_detail_spouse_last_name = fields.Char("DetailSpouseLastName")
    x_detail_head_of_household_num = fields.Char("DetailHeadOfHouseholdNum")
    x_detail_is_head_of_household = fields.Boolean("DetailIsHeadOfHousehold")

    # ----------------------------
    # Phones / Email (raw)
    # ----------------------------
    x_detail_home_area_code = fields.Char("DetailHomeAreaCode")
    x_detail_home_phone = fields.Char("DetailHomePhone")
    x_detail_home_phone_ext = fields.Char("DetailHomePhoneExt")

    x_detail_work_area_code = fields.Char("DetailWorkAreaCode")
    x_detail_work_phone = fields.Char("DetailWorkPhone")
    x_detail_work_phone_ext = fields.Char("DetailWorkPhoneExt")

    x_detail_cell_area_code = fields.Char("DetailCellAreaCode")
    x_detail_cell_phone = fields.Char("DetailCellPhone")

    x_detail_fax_area_code = fields.Char("DetailFaxAreaCode")
    x_detail_fax_phone = fields.Char("DetailFaxPhone")

    x_detail_email_address = fields.Char("DetailEmailAddress")

    # ----------------------------
    # User values
    # ----------------------------
    x_detail_user_value_001 = fields.Char("DetailUserValue001")
    x_detail_user_value_002 = fields.Char("DetailUserValue002")
    x_detail_user_value_003 = fields.Char("DetailUserValue003")
    x_detail_user_value_004 = fields.Char("DetailUserValue004")
    x_detail_user_value_005 = fields.Char("DetailUserValue005")
    x_detail_user_value_006 = fields.Char("DetailUserValue006")
    x_detail_user_value_007 = fields.Char("DetailUserValue007")
    x_detail_user_value_008 = fields.Char("DetailUserValue008")
    x_detail_user_value_009 = fields.Char("DetailUserValue009")

    # ----------------------------
    # Dates / Years
    # ----------------------------
    x_last_life_date = fields.Date("LastLifeDate")
    x_last_hon_life_date = fields.Date("LastHonLifeDate")
    x_detail_pey_start_year = fields.Char(
        "PEY Start Year", size=4,
        help="Year this member first received PEY (PER of the Year) recognition.",
    )
    x_detail_per_start_year = fields.Char(
        "PER Start Year", size=4,
        help="Year this member first became a Past Exalted Ruler.",
    )
    x_detail_poy_start_year = fields.Char(
        "POY Start Year", size=4,
        help="Year this member first received POY (Officer of the Year) recognition.",
    )

    # Computed years of service for PER / PEY / POY
    # NOT stored — avoids DB column creation issues during upgrade
    # and these are trivial subtractions, no performance concern.
    x_years_as_per = fields.Integer(
        "Years as PER",
        compute="_compute_honor_years",
        help="Number of years since becoming a Past Exalted Ruler.",
    )
    x_years_as_pey = fields.Integer(
        "Years as PEY",
        compute="_compute_honor_years",
        help="Number of years since receiving PEY recognition.",
    )
    x_years_as_poy = fields.Integer(
        "Years as POY",
        compute="_compute_honor_years",
        help="Number of years since receiving POY recognition.",
    )

    # ----------------------------
    # Member history dates (populated from membership application)
    # ----------------------------
    x_date_proposed = fields.Date(
        "Date Proposed",
        help="Date this member's application was proposed to the lodge.",
    )
    x_date_elected = fields.Date(
        "Date Elected",
        help="Date this member was elected by ballot.",
    )
    x_date_initiated = fields.Date(
        "Date Initiated",
        help="Date this member was formally initiated.",
    )
    x_date_of_birth = fields.Date(
        "Date of Birth",
        help="Member's date of birth.",
    )
    x_birth_city = fields.Char("Birth City")
    x_birth_county = fields.Char("Birth County")
    x_birth_state_id = fields.Many2one(
        'res.country.state', string="Birth State",
        domain="[('country_id.code', '=', 'US')]",
    )
    x_birth_country_id = fields.Many2one(
        'res.country', string="Birth Country",
    )
    x_occupation = fields.Char("Occupation")
    x_employer = fields.Char("Employer / Business")

    # ----------------------------
    # Misc
    # ----------------------------
    x_maiden_name = fields.Char("MaidenName")
    x_enotices_ok = fields.Boolean("eNoticesOK")
    x_branch_of_service = fields.Char("branchOfService")
    x_discharge_type = fields.Char("dischargeType")
    x_discharge_date = fields.Date("dischargeDate")
    x_sortfield = fields.Char("Sortfield")
    x_original_index = fields.Char("OriginalIndex")

    # ----------------------------
    # Officer Term History
    # ----------------------------
    x_officer_term_ids = fields.One2many(
        'elks.officer.term', 'partner_id',
        string='Officer Term History',
    )

    # ----------------------------
    # Member History (CLMS Elk History)
    # ----------------------------
    x_member_history_ids = fields.One2many(
        'elks.member.history', 'partner_id',
        string='Elk History',
    )

    # ----------------------------
    # Membership Application History
    # ----------------------------
    x_membership_application_ids = fields.One2many(
        'elks.membership.application', 'applicant_partner_id',
        string='Membership Applications',
    )

    # ----------------------------
    # Committee Assignment History
    # ----------------------------
    x_committee_assignment_ids = fields.One2many(
        'elks.committee.assignment', 'partner_id',
        string='Committee Assignments',
    )

    # Dues Payment History is added by the elksfrs module if installed.

    # ----------------------------
    # Officers (current)
    # ----------------------------
    x_elks_officer_position = fields.Selection([
        ('exalted_ruler', 'Exalted Ruler'),
        ('leading_knight', 'Leading Knight'),
        ('loyal_knight', 'Loyal Knight'),
        ('lecturing_knight', 'Lecturing Knight'),
        ('secretary', 'Secretary'),
        ('treasurer', 'Treasurer'),
        ('tiler', 'Tiler'),
        ('boardchair', 'Board Chair'),
        ('trustee1y', '1 Year Trustee'),
        ('trustee2y', '2 Year Trustee'),
        ('trustee3y', '3 Year Trustee'),
        ('esquire', 'Esquire'),
        ('chaplain', 'Chaplain'),
        ('inner_guard', 'Inner Guard'),
        ('organist', 'Organist'),
    ], string='Elks Officer Position', index=True, help="Officer role held by this member.")

    x_elks_officer_type = fields.Selection(
        [('elected', 'Elected Officer'), ('appointed', 'Appointed Officer')],
        string='Officer Type', compute='_compute_x_elks_officer_type', store=True
    )
    x_is_elks_officer = fields.Boolean(
        string='Is Elks Officer', compute='_compute_x_is_elks_officer', store=True
    )

    @api.constrains('x_detail_member_num')
    def _check_unique_member_num(self):
        for rec in self:
            if not rec.x_detail_member_num:
                continue
            dupes = self.with_context(active_test=False).search([
                ('x_detail_member_num', '=', rec.x_detail_member_num),
                ('id', '!=', rec.id),
            ])
            if dupes:
                raise ValidationError(_(
                    "Another contact (%(other)s) already has Elks "
                    "Member Number %(num)s."
                ) % {
                    'other': dupes[0].name,
                    'num': rec.x_detail_member_num,
                })

    # ==========================================
    # Onchange: Elk / Guest mutual exclusion
    # ==========================================
    @api.onchange('x_is_member')
    def _onchange_x_is_member(self):
        if self.x_is_member and self.x_is_guest:
            self.x_is_guest = False

    @api.onchange('x_is_guest')
    def _onchange_x_is_guest(self):
        if self.x_is_guest and self.x_is_member:
            self.x_is_member = False

    @api.constrains('x_is_member', 'x_is_guest')
    def _check_member_guest_exclusive(self):
        for rec in self:
            if rec.x_is_member and rec.x_is_guest:
                raise ValidationError(
                    _('A contact cannot be both an Elk member and a Guest. '
                      'Please uncheck one before saving.')
                )

    # ==========================================
    # Helpers
    # ==========================================
    def _extract_pin_from_phone(self):
        """Extract the last 4 digits from the contact's phone for use as a PIN.

        Tries mobile first (native ``mobile`` field or cell parts from CLMS),
        then falls back to home phone.  Returns a 4-digit string or False if
        no phone has enough digits.
        """
        import re
        for source in [
            getattr(self, 'mobile', None),
            self._compose_phone(
                self.x_detail_cell_area_code, self.x_detail_cell_phone,
            ) if self.x_detail_cell_phone else None,
            self.phone,
            self._compose_phone(
                self.x_detail_home_area_code, self.x_detail_home_phone,
                self.x_detail_home_phone_ext,
            ) if self.x_detail_home_phone else None,
        ]:
            if not source:
                continue
            digits = re.sub(r'\D', '', source)
            if len(digits) >= 4:
                return digits[-4:]
        return False

    def _prepare_person_defaults(self, vals):
        """Force individual (person) flags for import/create/write."""
        vals = dict(vals)
        vals.setdefault('company_type', 'person')
        if vals.get('company_type') == 'person':
            vals['is_company'] = False
            vals.setdefault('type', 'contact')
            vals['company_name'] = False
        return vals

    def _elks_compose_name(self, vals=None):
        """Compose display name from Elks name parts."""
        if vals is None:
            first = (self.x_detail_first_name or "").strip()
            middle = (self.x_detail_middle_name or "").strip()
            last = (self.x_detail_last_name or "").strip()
        else:
            first = (vals.get("x_detail_first_name") or "").strip()
            middle = (vals.get("x_detail_middle_name") or "").strip()
            last = (vals.get("x_detail_last_name") or "").strip()
        parts = [p for p in (first, middle, last) if p]
        return " ".join(parts).strip()

    def _compose_phone(self, area, number, ext=None):
        """Compose a US-formatted phone number from area code + number parts.

        Examples:
            ('208', '5569598')  → '(208) 556-9598'
            ('208', '556-9598') → '(208) 556-9598'
            ('', '5569598')     → '556-9598'
        """
        import re
        area = (area or "").strip()
        number = (number or "").strip()
        ext = (ext or "").strip() if ext else ""
        if not area and not number:
            return False

        # Strip all non-digit characters to normalize
        area_digits = re.sub(r'\D', '', area)
        num_digits = re.sub(r'\D', '', number)

        # Combine all digits to determine formatting
        all_digits = area_digits + num_digits

        if len(all_digits) == 10:
            # Full 10-digit US number: (XXX) XXX-XXXX
            core = f"({all_digits[:3]}) {all_digits[3:6]}-{all_digits[6:]}"
        elif len(all_digits) == 7:
            # 7-digit local number: XXX-XXXX
            core = f"{all_digits[:3]}-{all_digits[4:]}" if len(all_digits) > 4 else all_digits
            core = f"{all_digits[:3]}-{all_digits[3:]}"
        elif area_digits and num_digits:
            # Non-standard length — best effort with parens
            core = f"({area_digits}) {num_digits}"
        else:
            core = area_digits or num_digits

        if ext:
            core = f"{core} x{ext}"
        return core

    def _find_country(self, val):
        if not val:
            return False
        value = val.strip()
        Country = self.env["res.country"]
        return Country.search([("code", "=ilike", value)], limit=1) or \
            Country.search([("name", "=ilike", value)], limit=1) or False

    def _find_state(self, val, country=False):
        if not val:
            return False
        value = val.strip()
        domain = [("country_id", "=", country.id)] if country else []
        State = self.env["res.country.state"]
        return State.search(domain + [("code", "=ilike", value)], limit=1) or \
            State.search(domain + [("name", "=ilike", value)], limit=1) or False

    def _find_title(self, val):
        if not val:
            return False
        # Guard: res.partner.title may not exist if contacts module
        # is not installed, and title field may not be on res.partner
        if "res.partner.title" not in self.env or "title" not in self._fields:
            return False
        name = val.strip()
        if not name:
            return False
        Title = self.env["res.partner.title"]
        title = Title.search([("name", "=ilike", name)], limit=1)
        if title:
            return title
        mapping = {"mr": "Mr", "mrs": "Mrs", "ms": "Ms", "dr": "Dr", "rev": "Rev"}
        key = name.replace(".", "").lower()
        if key in mapping:
            t = Title.search([("name", "=ilike", mapping[key])], limit=1)
            if t:
                return t
        return Title.create({"name": name})

    # ==========================================
    # Compute / Constraints
    # ==========================================
    @api.depends('x_is_not_member')
    def _compute_x_is_member(self):
        for rec in self:
            rec.x_is_member = not rec.x_is_not_member

    def _inverse_x_is_member(self):
        for rec in self:
            rec.x_is_not_member = not rec.x_is_member

    @api.depends('x_elks_officer_position')
    def _compute_x_elks_officer_type(self):
        elected = {
            'exalted_ruler', 'leading_knight', 'loyal_knight',
            'lecturing_knight', 'secretary', 'treasurer'
        }
        for rec in self:
            if rec.x_elks_officer_position in elected:
                rec.x_elks_officer_type = 'elected'
            elif rec.x_elks_officer_position:
                rec.x_elks_officer_type = 'appointed'
            else:
                rec.x_elks_officer_type = False

    @api.depends('x_detail_per_start_year', 'x_detail_pey_start_year',
                 'x_detail_poy_start_year')
    def _compute_honor_years(self):
        current_year = date.today().year
        for rec in self:
            for yr_field, count_field in [
                ('x_detail_per_start_year', 'x_years_as_per'),
                ('x_detail_pey_start_year', 'x_years_as_pey'),
                ('x_detail_poy_start_year', 'x_years_as_poy'),
            ]:
                raw = getattr(rec, yr_field) or ''
                try:
                    start = int(raw.strip())
                    setattr(rec, count_field, max(0, current_year - start))
                except (ValueError, AttributeError):
                    setattr(rec, count_field, 0)

    @api.depends('x_elks_officer_position')
    def _compute_x_is_elks_officer(self):
        for rec in self:
            rec.x_is_elks_officer = bool(rec.x_elks_officer_position)

    @api.constrains('x_elks_officer_position', 'active')
    def _check_unique_officer_position(self):
        """Friendly check before SQL constraint for clearer message."""
        for rec in self:
            pos = rec.x_elks_officer_position
            if not pos:
                continue
            other = self.search([
                ('id', '!=', rec.id),
                ('x_elks_officer_position', '=', pos),
            ], limit=1)
            if other:
                label = dict(self._fields['x_elks_officer_position'].selection).get(pos, pos)
                raise ValidationError(_(
                    "Only one member can be '%s'. Current holder: %s"
                ) % (label, other.display_name))

    # ==========================================
    # Volunteer ↔ HR Employee sync
    # ==========================================
    def _get_or_create_volunteer_department(self):
        """Return the 'Volunteers' HR department, creating it if needed."""
        Department = self.env['hr.department'].sudo()
        dept = Department.search([('name', '=', 'Volunteers')], limit=1)
        if not dept:
            dept = Department.create({'name': 'Volunteers'})
        return dept

    def _sync_volunteer_employee(self):
        """Sync HR employee records based on x_is_volunteer.

        New behavior:
          * If already linked via ``x_volunteer_employee_id`` → re-activate / update.
          * Otherwise search for a HIGH-confidence match (email exact, or
            already linked via ``work_contact_id``) and silently auto-link if
            found.
          * If no high-confidence match → DO NOT create a new employee.
            Instead post a chatter note prompting the user to run the
            "Link / Create Employee" wizard.  This prevents duplicate employee
            records from being created blindly.
          * When volunteer is unchecked → archive the linked employee.
        """
        Employee = self.env['hr.employee'].sudo()

        def _norm_email(s):
            return (s or '').strip().lower()

        for rec in self:
            if rec.x_is_volunteer:
                if rec.x_volunteer_employee_id:
                    # Re-activate if it was previously archived
                    if not rec.x_volunteer_employee_id.active:
                        rec.x_volunteer_employee_id.write({
                            'active': True,
                            'x_is_volunteer': True,
                        })
                    continue

                # 1. Try the existing work_contact_id link
                existing = Employee.with_context(active_test=False).search([
                    ('work_contact_id', '=', rec.id),
                ], limit=1)

                # 2. Try an exact email match
                if not existing and rec.email:
                    candidates = Employee.with_context(active_test=False).search([
                        '|',
                        ('work_email', '=ilike', _norm_email(rec.email)),
                        ('private_email', '=ilike', _norm_email(rec.email)),
                    ])
                    if len(candidates) == 1:
                        existing = candidates

                if existing:
                    dept = rec._get_or_create_volunteer_department()
                    existing.write({
                        'active': True,
                        'department_id': dept.id,
                        'x_is_volunteer': True,
                        'work_contact_id': rec.id,
                    })
                    rec.write({'x_volunteer_employee_id': existing.id})
                    rec.message_post(
                        body=(
                            f"<strong>Auto-linked to existing employee</strong><br/>"
                            f"Employee: {existing.name} (ID {existing.id})"
                        ),
                        message_type='comment', subtype_xmlid='mail.mt_note',
                    )
                    _logger.info(
                        'Auto-linked partner %s to existing employee %s',
                        rec.id, existing.id,
                    )
                else:
                    # No safe auto-match — prompt the user to use the wizard
                    rec.message_post(
                        body=(
                            "<strong>Volunteer flag set — employee record not created.</strong><br/>"
                            "No unambiguous match was found.  Click "
                            "<em>Link / Create Employee</em> on the contact form to "
                            "pick an existing employee or create a new one."
                        ),
                        message_type='comment', subtype_xmlid='mail.mt_note',
                    )
                    _logger.info(
                        'No safe employee match for volunteer partner %s '
                        '— awaiting wizard link',
                        rec.id,
                    )
            else:
                # Archive the employee record when volunteer is unchecked
                if rec.x_volunteer_employee_id and rec.x_volunteer_employee_id.active:
                    rec.x_volunteer_employee_id.write({'active': False})
                    rec.message_post(
                        body=(
                            f"<strong>Volunteer flag removed</strong><br/>"
                            f"Employee record {rec.x_volunteer_employee_id.name} "
                            f"(ID {rec.x_volunteer_employee_id.id}) archived."
                        ),
                        message_type='comment', subtype_xmlid='mail.mt_note',
                    )
                    _logger.info(
                        'Archived volunteer employee record %s for partner %s',
                        rec.x_volunteer_employee_id.id, rec.id,
                    )

    def action_open_volunteer_link_wizard(self):
        """Open the Link / Create Employee wizard for this contact."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Link Volunteer to Employee'),
            'res_model': 'elks.volunteer.link.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
            },
        }

    def action_open_employee_merge_wizard(self):
        """Open the Merge Duplicate Employees wizard for this contact."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Merge Duplicate Employees'),
            'res_model': 'elks.employee.merge.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
            },
        }

    # ==========================================
    # Create / Write
    # ==========================================
    @api.model_create_multi
    def create(self, vals_list):
        """
        Import-friendly create:
          - If x_detail_member_num matches an existing partner (even archived),
            update that record (merge) instead of creating a duplicate.
          - Always force created/updated records to be individuals (company_type=person, is_company=False).
          - Ensures a non-empty 'name' (built from x_ name parts, email or member num).
          - After processing, run `action_update_elk_members()` on touched records to sync core fields.
        """
        def norm(num):
            return str(num).strip() if num else ""

        # Prefetch all existing partners that match incoming member numbers
        nums = list({norm(v.get("x_detail_member_num")) for v in vals_list if v.get("x_detail_member_num")})
        existing = self.with_context(active_test=False).search(
            [("x_detail_member_num", "in", [n for n in nums if n])]
        ) if nums else self.browse()
        by_num = {rec.x_detail_member_num.strip(): rec for rec in existing if rec.x_detail_member_num}

        touched = self.browse()
        to_create = []

        for vals in vals_list:
            vals = dict(vals)  # copy per row

            # Force person flags and customer defaults
            vals = self._prepare_person_defaults(vals)
            # Default all new contacts as customers
            vals.setdefault('customer_rank', 1)
            vals.setdefault('x_is_customer', True)

            # Ensure 'name'
            if not (vals.get("name") and str(vals.get("name")).strip()):
                composed = self._elks_compose_name(vals)
                if composed:
                    vals["name"] = composed
                elif vals.get("x_detail_email_address"):
                    vals["name"] = vals["x_detail_email_address"]
                elif vals.get("x_detail_member_num"):
                    vals["name"] = f"Member {vals['x_detail_member_num']}"
                else:
                    vals["name"] = "Unnamed Contact"

            num = norm(vals.get("x_detail_member_num"))

            if num and num in by_num:
                # Update (merge) existing; keep the same member number
                rec = by_num[num]
                upd = dict(vals)
                upd.pop("x_detail_member_num", None)
                rec.write(upd)

                # Ensure it remains a person
                if rec.is_company or rec.company_type != "person":
                    rec.write({"is_company": False, "company_type": "person"})

                touched |= rec
            else:
                to_create.append(vals)

        if to_create:
            created = super(ResPartner, self).create(to_create)
            # Index newly created by member number for potential later use
            for r in created:
                if r.x_detail_member_num:
                    by_num[r.x_detail_member_num.strip()] = r
            touched |= created

        # Run post-import mapping on all touched records
        if touched:
            overwrite = bool(self.env.context.get("elks_overwrite", True))
            touched.action_update_elk_members(overwrite=overwrite, only_with_elks=False)

        # Sync volunteer → employee for any records flagged as volunteer
        volunteers = touched.filtered('x_is_volunteer')
        if volunteers:
            volunteers._sync_volunteer_employee()

        return touched

    def write(self, vals):
        """
        Keep Elks members as individuals even on later edits;
        backfill 'name' if user cleared it while editing name parts.
        """
        # Force person for any record that has a member number unless caller explicitly changes company fields
        if ("is_company" not in vals) and ("company_type" not in vals):
            if any(rec.x_detail_member_num for rec in self):
                vals = self._prepare_person_defaults(vals)

        # Capture old values for CLMS-tracked fields BEFORE the write,
        # so we can log the actual before/after to chatter and trigger
        # a sync activity for the Secretary.
        clms_old_values = self._capture_clms_old_values(vals)

        res = super().write(vals)

        # If name parts changed and 'name' is blank, repopulate it
        if any(k in vals for k in ("x_detail_first_name", "x_detail_middle_name", "x_detail_last_name")):
            for rec in self:
                if not (rec.name or "").strip():
                    composed = rec._elks_compose_name()
                    if composed:
                        super(ResPartner, rec).write({"name": composed})

        # Sync volunteer → employee when the volunteer flag changes
        if 'x_is_volunteer' in vals:
            self._sync_volunteer_employee()

        # Log CLMS-tracked changes to chatter and schedule a Secretary
        # to-do so the change gets pushed into CLMS at Grand Lodge.
        if clms_old_values:
            self._track_clms_changes(clms_old_values)

        return res

    # ==========================================
    # Mapping helpers / actions
    # ==========================================
    def action_apply_elks_mapping(self):
        """
        Copy Elks x_* fields into native partner fields (name/title/email/address/phones).
        This method is conservative: it sets values when x_* is present and different.
        """
        for rec in self:
            vals = {}

            # Combine name parts -> name
            parts = [rec.x_detail_first_name, rec.x_detail_middle_name, rec.x_detail_last_name]
            name_combined = " ".join([p.strip() for p in parts if p and p.strip()])
            if name_combined and name_combined != (rec.name or ""):
                vals["name"] = name_combined

            # Title from salutation (only if title field exists)
            if "title" in rec._fields:
                title = rec._find_title(rec.x_detail_name_salutation)
                if title and rec.title != title:
                    vals["title"] = title.id

            # Email
            x_email = (rec.x_detail_email_address or "").strip()
            if x_email and (rec.email or "").strip() != x_email:
                vals["email"] = x_email

            # Address
            if rec.x_detail_active_address_line1:
                vals["street"] = rec.x_detail_active_address_line1
            if rec.x_detail_active_address_line2:
                vals["street2"] = rec.x_detail_active_address_line2
            if rec.x_detail_active_city:
                vals["city"] = rec.x_detail_active_city
            if rec.x_detail_active_zip:
                vals["zip"] = rec.x_detail_active_zip

            country = rec._find_country(rec.x_detail_active_country)
            if country:
                vals["country_id"] = country.id
            state = rec._find_state(rec.x_detail_active_state, country or rec.country_id)
            if state:
                vals["state_id"] = state.id

            # Phones
            home = rec._compose_phone(rec.x_detail_home_area_code, rec.x_detail_home_phone, rec.x_detail_home_phone_ext)
            if home and (rec.phone or "").strip() != home:
                vals["phone"] = home
            mobile = rec._compose_phone(rec.x_detail_cell_area_code, rec.x_detail_cell_phone, None)
            if mobile and "mobile" in rec._fields:
                if (getattr(rec, "mobile", "") or "").strip() != mobile:
                    vals["mobile"] = mobile

            fax = rec._compose_phone(rec.x_detail_fax_area_code, rec.x_detail_fax_phone, None)
            if fax and "fax" in rec._fields:
                if (getattr(rec, "fax", "") or "").strip() != fax:
                    vals["fax"] = fax

            if vals:
                rec.write(vals)

    def action_copy_core_from_elks(self, overwrite=False):
        """
        Copy core contact fields from imported x_* fields to native res.partner fields:
        street, street2, city, state_id, zip, country_id, email, phone, mobile.

        If overwrite is False (default), only fill targets that are empty.
        If overwrite is True, replace existing values.
        """
        for rec in self:
            vals = {}

            def set_if(value, target_field, current_value):
                if not value:
                    return
                if overwrite or not (current_value or "").strip():
                    vals[target_field] = value

            # Address lines + city + zip
            set_if(rec.x_detail_active_address_line1, "street", rec.street)
            set_if(rec.x_detail_active_address_line2, "street2", rec.street2)
            set_if(rec.x_detail_active_city, "city", rec.city)
            set_if(rec.x_detail_active_zip, "zip", rec.zip)

            # Country & State
            country = rec._find_country(rec.x_detail_active_country) if rec.x_detail_active_country else False
            if country and (overwrite or not rec.country_id):
                vals["country_id"] = country.id

            state = rec._find_state(rec.x_detail_active_state, country or rec.country_id) if rec.x_detail_active_state else False
            if state and (overwrite or not rec.state_id):
                vals["state_id"] = state.id

            # Email
            set_if((rec.x_detail_email_address or "").strip(), "email", rec.email or "")

            # Phone (home) and Mobile (cell)
            home = rec._compose_phone(rec.x_detail_home_area_code, rec.x_detail_home_phone, rec.x_detail_home_phone_ext)
            if home and (overwrite or not (rec.phone or "").strip()):
                vals["phone"] = home

            mobile = rec._compose_phone(rec.x_detail_cell_area_code, rec.x_detail_cell_phone, None)
            if mobile and "mobile" in rec._fields:
                current_mobile = (getattr(rec, "mobile", "") or "").strip()
                if overwrite or not current_mobile:
                    vals["mobile"] = mobile

            if vals:
                rec.write(vals)

    def action_update_elk_members(self, overwrite=False, only_with_elks=True):
        """
        Apply both Elks mappings...
        """
        Partner = self.env['res.partner']

        if self:
            partners = self
        else:
            if only_with_elks:
                fields_to_check = [
                    'x_detail_active_address_line1', 'x_detail_active_address_line2',
                    'x_detail_active_city', 'x_detail_active_state', 'x_detail_active_zip',
                    'x_detail_active_country', 'x_detail_email_address',
                    'x_detail_home_area_code', 'x_detail_home_phone', 'x_detail_home_phone_ext',
                    'x_detail_cell_area_code', 'x_detail_cell_phone',
                    'x_detail_fax_area_code', 'x_detail_fax_phone',
                    'x_detail_work_area_code', 'x_detail_work_phone', 'x_detail_work_phone_ext',
                    'x_detail_first_name', 'x_detail_middle_name', 'x_detail_last_name',
                ]

                # Build a proper prefix-notation OR domain:
                # ['|','|', <t1>, <t2>, <t3>, ...]
                terms = [(f, '!=', False) for f in fields_to_check]
                domain = (['|'] * (len(terms) - 1)) + terms  # correct syntax
            else:
                domain = []

            partners = Partner.search(domain)

        if not partners:
            return 0

        partners.action_apply_elks_mapping()
        partners.action_copy_core_from_elks(overwrite=overwrite)
        return len(partners)

    # ------------------------------------------------------------------
    # Last-name first letter (drives the A-Z sidebar in Contacts)
    # Must be a Selection (or Many2one) for Odoo's search panel
    # category support; Char fields are rejected by the panel.
    # ------------------------------------------------------------------
    x_last_name_letter = fields.Selection(
        selection=[(c, c) for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'] + [('#', '#')],
        string="Last Name Letter",
        compute='_compute_last_name_letter',
        store=True, index=True,
        help="First letter of the last name (uppercase). Drives the "
             "A-Z sidebar in the Contacts view.",
    )

    @api.depends('x_detail_last_name', 'name')
    def _compute_last_name_letter(self):
        for rec in self:
            src = (rec.x_detail_last_name or rec.name or '').strip()
            letter = ''
            for ch in src:
                if ch.isalpha():
                    letter = ch.upper()
                    break
            rec.x_last_name_letter = letter or '#'

    # ══════════════════════════════════════════════════════════════════
    #  CLMS PARITY — fields added to mirror the CLMS member record.
    #  Tabs covered below: Contact (additions), ALT Info, Grand Lodge
    #  Mailing, Grand Lodge Shipping.
    # ══════════════════════════════════════════════════════════════════

    # ── CLMS Contact tab — additions ──────────────────────────────────
    x_detail_nickname = fields.Char("Nickname")
    x_detail_sex = fields.Selection(
        [('male', 'Male'), ('female', 'Female')],
        string="Sex",
    )
    x_detail_generational_suffix = fields.Char(
        "Generational Suffix",
        help="e.g. Jr., Sr., III. CLMS stores this separately from "
             "professional and military suffixes.",
    )
    x_detail_professional_suffix = fields.Char(
        "Professional Suffix",
        help="e.g. MD, PhD, Esq.",
    )
    x_detail_military_suffix = fields.Char(
        "Military Suffix",
        help="e.g. USA Ret., USMC.",
    )
    x_lost_years = fields.Integer(
        "Lost Years",
        help="Years the member lapsed between drop and reinstatement.",
    )
    x_age = fields.Integer(
        "Age", compute='_compute_age', store=False,
    )
    x_member_years = fields.Integer(
        "Member Years", compute='_compute_member_years', store=False,
    )
    x_email_is_undeliverable = fields.Boolean(
        "Email Undeliverable",
        help="Email bounced — flag set so notices skip this contact.",
    )
    x_elks_org_account = fields.Char(
        "Elks.org Account",
        help="Member's elks.org login (may be updated by the member only "
             "via elks.org).",
    )
    x_gl_enotices_ok = fields.Boolean(
        "GL eNotices OK",
        help="Authorizes Grand Lodge notices via email.",
    )
    x_elks_magazine_online = fields.Selection(
        [('online', 'Online — no print'),
         ('print', 'Postal mail — print copy')],
        string="Elks Magazine Delivery",
        default='print',
    )
    x_newsletter_preference = fields.Selection(
        [('email', 'Send Newsletter via Email'),
         ('postal', 'Send Newsletter via Postal Mail'),
         ('none', "Don't Send Newsletter")],
        string="Newsletter Delivery",
        default='email',
    )

    @api.depends('x_date_of_birth')
    def _compute_age(self):
        today = fields.Date.today()
        for rec in self:
            if rec.x_date_of_birth:
                yrs = today.year - rec.x_date_of_birth.year
                if (today.month, today.day) < (
                    rec.x_date_of_birth.month, rec.x_date_of_birth.day,
                ):
                    yrs -= 1
                rec.x_age = max(0, yrs)
            else:
                rec.x_age = 0

    @api.depends('x_date_initiated', 'x_lost_years')
    def _compute_member_years(self):
        today = fields.Date.today()
        for rec in self:
            if rec.x_date_initiated:
                yrs = today.year - rec.x_date_initiated.year
                if (today.month, today.day) < (
                    rec.x_date_initiated.month, rec.x_date_initiated.day,
                ):
                    yrs -= 1
                rec.x_member_years = max(0, yrs - (rec.x_lost_years or 0))
            else:
                rec.x_member_years = 0

    # ── CLMS ALT Info tab — Alternate Address ─────────────────────────
    x_alt_street = fields.Char("Alt Address 1")
    x_alt_street2 = fields.Char("Alt Address 2")
    x_alt_city = fields.Char("Alt City")
    x_alt_state_id = fields.Many2one(
        'res.country.state', string="Alt State",
        domain="[('country_id', '=', x_alt_country_id)]",
    )
    x_alt_zip = fields.Char("Alt ZIP")
    x_alt_country_id = fields.Many2one(
        'res.country', string="Alt Country",
        default=lambda self: self.env.ref('base.us', raise_if_not_found=False),
    )
    x_alt_carrier_code = fields.Char("Alt Carrier Route")
    x_alt_dpc = fields.Char("Alt DPC")
    x_alt_postal_lot = fields.Char("Alt LOT")
    x_alt_cass_result_code = fields.Char("Alt CASS Result")
    x_alt_is_undeliverable = fields.Boolean("Alt Undeliverable")
    x_alt_send_no_magazine = fields.Boolean("Alt: Do NOT Send Elks Magazine")
    x_alt_send_no_mail = fields.Boolean("Alt: Send No Mail")

    # ── CLMS Secy Contact tab — Grand Lodge Mailing Address ───────────
    x_gl_mail_street = fields.Char("GL Mailing Address 1")
    x_gl_mail_street2 = fields.Char("GL Mailing Address 2")
    x_gl_mail_city = fields.Char("GL Mailing City")
    x_gl_mail_state_id = fields.Many2one(
        'res.country.state', string="GL Mailing State",
        domain="[('country_id.code', '=', 'US')]",
    )
    x_gl_mail_zip = fields.Char("GL Mailing ZIP")

    # ── CLMS Secy Contact tab — Grand Lodge Shipping Address ──────────
    x_gl_ship_street = fields.Char(
        "GL Shipping Address 1",
        help="Shipping address must NOT be a P.O. Box.",
    )
    x_gl_ship_street2 = fields.Char("GL Shipping Address 2")
    x_gl_ship_city = fields.Char("GL Shipping City")
    x_gl_ship_state_id = fields.Many2one(
        'res.country.state', string="GL Shipping State",
        domain="[('country_id.code', '=', 'US')]",
    )
    x_gl_ship_zip = fields.Char("GL Shipping ZIP")

    # ── CLMS Spouse / Emergency tab ───────────────────────────────────
    x_spouse_has_id_card = fields.Boolean(
        "Spouse Has ID Card",
        help="The spouse has been issued an Elks ID card.",
    )
    x_spouse_birthday = fields.Date("Spouse Birthday")
    x_anniversary_date = fields.Date("Wedding Anniversary")
    x_emergency_contact_name = fields.Char("Emergency Contact Name")
    x_emergency_relationship = fields.Char("Emergency Relationship")
    x_emergency_phone = fields.Char("Emergency Contact Phone")

    # ── CLMS Roles tab — Lodge Status flags ───────────────────────────
    # HLM and LM booleans are bidirectionally synced with their date
    # counterparts (x_last_hon_life_date / x_last_life_date):
    #   • Setting/clearing the date updates the boolean automatically.
    #   • Toggling the boolean ON sets the date to today (if blank).
    #   • Toggling OFF leaves the date in place so historical records
    #     of when status was first conferred are preserved.
    x_is_honorary_life_member = fields.Boolean(
        "Honorary Life Member (HLM)",
        compute='_compute_is_honorary_life_member',
        inverse='_inverse_is_honorary_life_member',
        store=True,
        help="True whenever an HLM date is set on the member.",
    )
    x_is_life_member = fields.Boolean(
        "Life Member (LM)",
        compute='_compute_is_life_member',
        inverse='_inverse_is_life_member',
        store=True,
        help="True whenever a Life Member date is set on the member.",
    )

    @api.depends('x_last_hon_life_date')
    def _compute_is_honorary_life_member(self):
        for rec in self:
            rec.x_is_honorary_life_member = bool(rec.x_last_hon_life_date)

    def _inverse_is_honorary_life_member(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.x_is_honorary_life_member and not rec.x_last_hon_life_date:
                rec.x_last_hon_life_date = today
            # Don't auto-clear the date on toggle-off — preserve history.

    @api.depends('x_last_life_date')
    def _compute_is_life_member(self):
        for rec in self:
            rec.x_is_life_member = bool(rec.x_last_life_date)

    def _inverse_is_life_member(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.x_is_life_member and not rec.x_last_life_date:
                rec.x_last_life_date = today
            # Don't auto-clear on toggle-off — preserve history.
    x_is_life_eligible = fields.Boolean("Eligible for Life Membership")
    x_is_charter_member = fields.Boolean("Charter Member of this Lodge")
    x_is_assisted = fields.Boolean(
        "Assisted",
        help="Lodge is assisting the member with dues (per BPOE practice).",
    )
    x_dues_pay_cycle = fields.Selection(
        [('april', 'April Pay'), ('october', 'October Pay')],
        string="Dues Pay Cycle", default='april',
        help="When the member's dues come due each year.",
    )
    x_is_rejected = fields.Boolean(
        "Rejected",
        help="Candidate was rejected or chose not to join.",
    )

    # ── CLMS Roles tab — Donor Programs ───────────────────────────────
    x_is_enf_donor = fields.Boolean(
        "ENF Donor",
        help="Elks National Foundation donor.",
    )
    x_enf_donor_id = fields.Char("ENF Donor ID")
    x_is_smp_donor = fields.Boolean(
        "SMP Donor",
        help="State Major Project donor.",
    )

    # ── CLMS Roles tab — Veteran ──────────────────────────────────────
    # Synced with x_branch_of_service: if a branch is recorded the
    # member is by definition a veteran; toggling the boolean on
    # without a branch leaves branch blank (set the branch separately).
    x_is_veteran = fields.Boolean(
        "Veteran",
        compute='_compute_is_veteran',
        inverse='_inverse_is_veteran',
        store=True,
        help="True when a Branch of Service is recorded for this member.",
    )

    @api.depends('x_branch_of_service')
    def _compute_is_veteran(self):
        for rec in self:
            rec.x_is_veteran = bool(rec.x_branch_of_service)

    def _inverse_is_veteran(self):
        # Toggling the boolean is just a convenience marker — the
        # branch field is the authoritative source. We never auto-set
        # or auto-clear branch from the boolean.
        pass

    # ── CLMS Roles tab — PDD ──────────────────────────────────────────
    x_detail_pdd_start_year = fields.Char("PDD Year")
    x_years_as_pdd = fields.Integer("Years as PDD")

    # ── CLMS Misc tab ─────────────────────────────────────────────────
    x_original_init_lodge_name = fields.Char(
        "Original Init Lodge",
        help="Name and city of the lodge where the member was first "
             "initiated (e.g. 'Lewiston, ID No. 896').",
    )
    x_original_init_lodge_num = fields.Char("Original Init Lodge #")
    x_initiating_exalted_ruler = fields.Char(
        "Exalted Ruler at Initiation",
    )
    x_initiating_secretary = fields.Char(
        "Secretary at Initiation",
    )
    x_detail_memsysnamid = fields.Char(
        "MemSysNamID",
        help="Grand Lodge member system name identifier — the CLMS-side "
             "primary key for this person.",
    )
    x_dues_rate_code = fields.Char(
        "Dues Rate Code",
        help="The dues rate code the member is on (e.g. R1 = Regular).",
    )

    # ── CLMS Secy Contact tab — separate GL-routed contact info ──────
    x_gl_home_phone = fields.Char("GL: Home Phone")
    x_gl_work_phone = fields.Char("GL: Work Phone")
    x_gl_cell_phone = fields.Char("GL: Cell Phone")
    x_gl_fax = fields.Char("GL: Fax Number")
    x_gl_email = fields.Char(
        "GL: Email Address",
        help="Email used by GL Accounting Dept for invoices etc.",
    )
    x_elks_org_email = fields.Char("Elks.org Email")

    # ── CLMS export-import parity fields ──────────────────────────────
    # These three columns appear in the CLMS "All Active Members - Full
    # Directory" export and were missing from the model.  Adding them
    # so the CSV can be imported directly without manual column
    # mapping.
    x_detail_record_type_code = fields.Char(
        "Record Type Code",
        help="CLMS DetailRecordTypeCode — single-letter code "
             "identifying member category (M=Member, etc.).",
    )
    x_detail_record_status = fields.Char(
        "Record Status",
        help="CLMS DetailRecordStatus — single-letter status code "
             "(A=Active, D=Dropped, etc.).",
    )
    x_group = fields.Char(
        "CLMS Group",
        help="CLMS GROUP column — group identifier used in the CLMS "
             "directory export.",
    )

    # ------------------------------------------------------------------
    # Return to Sender
    # ------------------------------------------------------------------
    x_return_to_sender = fields.Boolean(
        "Return to Sender", default=False, tracking=True, index=True,
        help="Mail sent to this contact was returned as undeliverable.",
    )
    x_return_to_sender_date = fields.Date(
        "Return Notice Date", tracking=True,
        help="Date the return-to-sender notice was received.",
    )

    def action_mark_return_to_sender(self):
        """Flag this contact as Return to Sender with today's date."""
        today = fields.Date.context_today(self)
        for rec in self:
            rec.write({
                'x_return_to_sender': True,
                'x_return_to_sender_date': today,
            })
            rec.message_post(
                body=_(
                    "<b>Return to Sender</b> — mail returned as "
                    "undeliverable. Flagged by %s on %s.",
                    self.env.user.name, today,
                ),
                subtype_xmlid='mail.mt_note',
            )

    def action_clear_return_to_sender(self):
        """Remove the Return to Sender flag (e.g. address updated)."""
        for rec in self:
            rec.write({
                'x_return_to_sender': False,
                'x_return_to_sender_date': False,
            })
            rec.message_post(
                body=_(
                    "<b>Return to Sender cleared</b> — address updated "
                    "by %s.", self.env.user.name,
                ),
                subtype_xmlid='mail.mt_note',
            )

    # ------------------------------------------------------------------
    # Suspension
    # ------------------------------------------------------------------
    x_is_suspended = fields.Boolean(
        "Suspended", default=False, tracking=True, index=True,
        help="Member is currently under suspension.",
    )
    x_suspension_start_date = fields.Date(
        "Suspension Start Date", tracking=True,
        help="Date the suspension began.",
    )
    x_suspension_end_date = fields.Date(
        "Suspension End Date", tracking=True,
        help="Date the suspension is scheduled to end.",
    )
    x_suspension_notes = fields.Text(
        "Suspension Notes", tracking=True,
        help="Reason or notes regarding the suspension.",
    )

    def action_suspend_member(self):
        """Open the suspension wizard so the user can enter dates and reason."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Suspend Member'),
            'res_model': 'elks.suspension.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
            },
        }

    def action_lift_suspension(self):
        """Remove the suspension flag."""
        today = fields.Date.context_today(self)
        for rec in self:
            rec.write({
                'x_is_suspended': False,
                'x_suspension_end_date': today,
            })
            rec.message_post(
                body=_(
                    "<b>Suspension Lifted</b> — cleared by %s on %s.",
                    self.env.user.name, today,
                ),
                subtype_xmlid='mail.mt_note',
            )

    # ------------------------------------------------------------------
    # Dues
    # ------------------------------------------------------------------
    x_is_dues_paid = fields.Boolean(
        string="Dues Paid (Lodge Year)",
        compute="_compute_is_dues_paid",
        store=True,
        index=True,
        help="True when dues are paid through the current lodge year "
             "(April 1 – March 31).",
    )

    @api.depends('x_detail_dues_paid_to_date')
    def _compute_is_dues_paid(self):
        """Dues are DUE on April 1.  A ``dues_paid_to_date`` of April 1 means
        the member has paid *up to* that date but has NOT yet paid *for* the
        month of April, so they are past due.  The paid-to date must be
        strictly **after** the lodge-year start to count as current."""
        today = fields.Date.context_today(self)
        cutoff = _current_lodge_year_start(today)
        for rec in self:
            d = rec.x_detail_dues_paid_to_date
            rec.x_is_dues_paid = bool(d and d > cutoff)

    # ------------------------------------------------------------------
    # Drop / Undrop (replaces Archive/Unarchive for members)
    # ------------------------------------------------------------------
    x_drop_reason = fields.Selection([
        ('nonpayment', 'Non-Payment of Dues'),
        ('resigned', 'Resigned'),
        ('expelled', 'Expelled'),
        ('deceased', 'Deceased'),
        ('other', 'Other'),
    ], string="Drop Reason", tracking=True)
    x_drop_date = fields.Date(
        "Date Dropped", tracking=True,
        help="Date the member was dropped from the rolls.",
    )
    x_drop_notes = fields.Text(
        "Drop Notes", tracking=True,
        help="Additional details about why the member was dropped.",
    )

    # ------------------------------------------------------------------
    # Death of Member - CLMS processing flow
    # ------------------------------------------------------------------
    # When a death is recorded (x_drop_reason='deceased') the contact is
    # NOT archived immediately. Instead the record sits in the Secretary's
    # queue with x_death_clms_status='pending' until they:
    #   (a) read the death announcement on the lodge floor, and
    #   (b) push the record into CLMS at Grand Lodge.
    # Marking CLMS Processed is the action that actually archives the
    # contact - so the member remains searchable in the directory through
    # the floor-reading meeting and the CLMS push.
    x_date_of_death = fields.Date(
        "Date of Death", tracking=True,
        help="Date the member died. Captured at the time the Death of "
             "Member smart button is clicked.",
    )
    x_date_read_on_floor = fields.Date(
        "Date Read on Lodge Floor", tracking=True,
        help="Date the death announcement was read aloud at a regular "
             "lodge meeting. Captured by the Secretary.",
    )
    x_death_clms_status = fields.Selection(
        [
            ('pending', 'Pending CLMS Entry'),
            ('processed', 'Processed in CLMS'),
        ],
        string="Death CLMS Status", tracking=True, copy=False,
        help="Tracks the Secretary's CLMS workflow for a deceased "
             "member. Stays 'Pending' until the Secretary pushes the "
             "record into CLMS at Grand Lodge.",
    )
    x_death_clms_processed_date = fields.Date(
        "Death CLMS Processed On", tracking=True, readonly=True, copy=False,
    )
    x_death_clms_processed_by = fields.Many2one(
        'res.users', string="Death CLMS Processed By",
        tracking=True, readonly=True, copy=False,
    )

    def action_open_death_wizard(self):
        """Open the Drop Member wizard pre-configured for a death.

        Same wizard as Drop Member, but with the Deceased checkbox
        pre-checked. The wizard's confirm action knows to set the
        CLMS status to 'pending' and skip immediate archiving for
        the deceased path.
        """
        self.ensure_one()
        if not self.x_is_member:
            raise UserError(_(
                "Death of Member can only be recorded on an Elks "
                "member. The selected contact is not flagged as a member."
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Record Death of Member'),
            'res_model': 'elks.drop.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_reason_deceased': True,
            },
        }

    def action_mark_read_on_floor(self):
        """Record that the death announcement was read at a lodge meeting.

        Available to any lodge user (reception, officer, secretary).
        Sets x_date_read_on_floor to today; the Secretary can edit the
        date if the reading happened on a different night.
        """
        for rec in self:
            if rec.x_drop_reason != 'deceased':
                raise UserError(_(
                    "Mark Read on Floor is only available for members "
                    "flagged as deceased."
                ))
            today = fields.Date.context_today(self)
            rec.x_date_read_on_floor = today
            rec.message_post(
                body=_(
                    "<b>Death announcement read on lodge floor</b> "
                    "by %s on %s.",
                    self.env.user.name, today,
                ),
                subtype_xmlid='mail.mt_note',
            )

    def action_mark_death_processed_clms(self):
        """Secretary-only: mark death as processed in CLMS, then archive.

        This is the action that actually archives the deceased member.
        Reception staff posting the death only sets the pending state;
        the contact stays active and searchable until the Secretary
        completes the Grand Lodge CLMS push and clicks this button.
        """
        if not self.env.user.has_group('elkscontacts.group_elks_secretary'):
            raise AccessError(_(
                "Only the Lodge Secretary can mark a member's death as "
                "processed in CLMS. Reception staff should leave the "
                "record in 'Pending CLMS Entry' state - the Secretary "
                "will pick it up from there."
            ))
        today = fields.Date.context_today(self)
        for rec in self:
            if rec.x_drop_reason != 'deceased':
                raise UserError(_(
                    "Mark Death Processed in CLMS is only available "
                    "for members flagged as deceased."
                ))
            rec.write({
                'x_death_clms_status': 'processed',
                'x_death_clms_processed_date': today,
                'x_death_clms_processed_by': self.env.user.id,
            })
            rec.message_post(
                body=_(
                    "<b>Death processed in CLMS</b> by %s on %s. "
                    "Member is being archived from the active rolls.",
                    self.env.user.name, today,
                ),
                subtype_xmlid='mail.mt_note',
            )
            # Now actually archive the contact (bypass the Drop wizard
            # interception in action_archive by calling super directly).
            super(ResPartner, rec).action_archive()

    def action_unmark_death_processed_clms(self):
        """Secretary-only: undo the CLMS processed flag and unarchive.

        Lets the Secretary reverse a mistaken click. Same group check
        as the forward action.
        """
        if not self.env.user.has_group('elkscontacts.group_elks_secretary'):
            raise AccessError(_(
                "Only the Lodge Secretary can reverse a CLMS death entry."
            ))
        for rec in self:
            if rec.x_drop_reason != 'deceased':
                raise UserError(_(
                    "Unmark Death CLMS Processed is only available "
                    "for members flagged as deceased."
                ))
            rec.write({
                'x_death_clms_status': 'pending',
                'x_death_clms_processed_date': False,
                'x_death_clms_processed_by': False,
            })
            # Unarchive the contact so it returns to the active rolls
            # and the Secretary's CLMS queue.
            super(ResPartner, rec).action_unarchive()
            rec.message_post(
                body=_(
                    "<b>Death CLMS entry reversed</b> by %s. "
                    "Member returned to active rolls; CLMS status reset "
                    "to Pending.",
                    self.env.user.name,
                ),
                subtype_xmlid='mail.mt_note',
            )

    def action_archive(self):
        """Override archive to route members through the Drop wizard."""
        members = self.filtered(lambda r: r.x_is_member)
        non_members = self - members
        # Non-members get the standard archive behavior
        if non_members:
            super(ResPartner, non_members).action_archive()
        # Members must go through the Drop wizard
        if members:
            if len(members) > 1:
                return members[0].action_open_drop_wizard()
            return members.action_open_drop_wizard()
        return True

    def action_open_drop_wizard(self):
        """Open the Drop Member wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Drop Member'),
            'res_model': 'elks.drop.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
            },
        }

    def action_unarchive(self):
        """Override unarchive to log 'Restored' and clear drop fields."""
        result = super().action_unarchive()
        for rec in self:
            if rec.x_is_member or rec.x_drop_reason:
                rec.write({
                    'x_drop_reason': False,
                    'x_drop_date': False,
                    'x_drop_notes': False,
                })
                rec.message_post(
                    body=_(
                        "<b>Member Restored</b> — reactivated by %s. "
                        "Drop reason cleared.",
                        self.env.user.name,
                    ),
                    subtype_xmlid='mail.mt_note',
                )
        return result

    # ------------------------------------------------------------------
    # Soft dependency on elksfrs — Pay Dues
    # ------------------------------------------------------------------
    # The Pay Dues smart button in views/elks_contact_views.xml binds to
    # `action_pay_dues`. The *real* implementation lives in the elksfrs
    # module (Financial Reporting System), which extends res.partner with
    # invoice/payment workflow.
    #
    # We must define a stub here so that Odoo's view validator finds the
    # method on res.partner when elkscontacts loads — elksfrs is loaded
    # AFTER elkscontacts (it depends on us), so without this stub the view
    # validation fails with "action_pay_dues is not a valid action on
    # res.partner" and aborts the entire elkscontacts install/upgrade.
    #
    # When elksfrs is installed, its `_inherit = 'res.partner'` class is
    # registered after ours, so Python MRO resolves `action_pay_dues` to
    # the elksfrs implementation and this stub is never reached. When
    # elksfrs is NOT installed, clicking the button raises the friendly
    # error below instead of a generic "method does not exist" trace.
    def action_pay_dues(self):
        """Stub overridden by elksfrs. Raises UserError if elksfrs absent."""
        raise UserError(_(
            "The Elks FRS module must be installed to record dues "
            "payments. Install or enable the 'elksfrs' module, then "
            "try again."
        ))

    @api.model
    def cron_update_is_dues_paid(self):
        """Runs daily: keeps the stored boolean in sync as the lodge year rolls over."""
        today = fields.Date.context_today(self)
        cutoff = _current_lodge_year_start(today)
        Partner = self.env['res.partner'].sudo()

        to_true = Partner.search([
            ('active', '=', True),
            ('x_is_dues_paid', '=', False),
            ('x_detail_dues_paid_to_date', '!=', False),
            ('x_detail_dues_paid_to_date', '>', cutoff),
        ])
        if to_true:
            to_true.write({'x_is_dues_paid': True})

        to_false = Partner.search([
            ('active', '=', True),
            ('x_is_dues_paid', '=', True),
            '|', ('x_detail_dues_paid_to_date', '=', False),
            ('x_detail_dues_paid_to_date', '<=', cutoff),
        ])
        if to_false:
            to_false.write({'x_is_dues_paid': False})

        return len(to_true) + len(to_false)

    # ══════════════════════════════════════════════════════════════════
    #  CLMS sync — log CLMS-tracked field changes to chatter and
    #  schedule a Secretary to-do to push them into CLMS.
    #
    #  Skip via context: self.with_context(elks_skip_clms_sync=True)
    #  — useful for bulk imports / initial sync where the CLMS record
    #  is the SOURCE of the change, not the destination.
    # ══════════════════════════════════════════════════════════════════

    #: Set of technical field names that count as CLMS-syncable.
    #: A change to any of these on a member contact triggers chatter
    #: logging + a Secretary to-do.  Excludes computed fields (HLM/LM/
    #: Veteran booleans, computed addresses, x_last_name_letter, etc.)
    #: because those mirror authoritative sources that are already in
    #: this set.
    CLMS_SYNC_FIELDS = frozenset([
        # ─── Contact tab ───────────────────────────────────────────
        'x_detail_name_prefix',
        'x_detail_first_name', 'x_detail_middle_name', 'x_detail_last_name',
        'x_detail_generational_suffix', 'x_detail_professional_suffix',
        'x_detail_military_suffix', 'x_detail_name_suffix',
        'x_detail_sex', 'x_detail_nickname', 'x_detail_elk_title',
        'x_detail_member_num', 'x_detail_dues_paid_to_date',
        'x_date_initiated', 'x_lost_years',
        # Active address
        'street', 'street2', 'city', 'state_id', 'zip', 'country_id',
        'x_detail_active_carrier_code', 'x_detail_active_dpc',
        'x_detail_active_postal_lot', 'x_detail_active_cass_result_code',
        'x_detail_active_is_undeliverable', 'x_detail_active_send_no_mail',
        'x_detail_active_send_no_magazine',
        # Phones
        'x_detail_home_phone', 'x_detail_home_area_code',
        'x_detail_home_phone_ext',
        'x_detail_work_phone', 'x_detail_work_area_code',
        'x_detail_work_phone_ext',
        'x_detail_cell_phone', 'x_detail_cell_area_code',
        'x_detail_fax_phone', 'x_detail_fax_area_code',
        # Email / online prefs
        'x_detail_email_address', 'x_email_is_undeliverable',
        'x_elks_org_account', 'x_enotices_ok', 'x_gl_enotices_ok',
        'x_elks_magazine_online', 'x_newsletter_preference',
        # ─── ALT Info ───────────────────────────────────────────────
        'x_alt_street', 'x_alt_street2', 'x_alt_city',
        'x_alt_state_id', 'x_alt_zip', 'x_alt_country_id',
        'x_alt_carrier_code', 'x_alt_dpc', 'x_alt_postal_lot',
        'x_alt_cass_result_code', 'x_alt_is_undeliverable',
        'x_alt_send_no_magazine', 'x_alt_send_no_mail',
        # ─── GL Mailing / Shipping ─────────────────────────────────
        'x_gl_mail_street', 'x_gl_mail_street2', 'x_gl_mail_city',
        'x_gl_mail_state_id', 'x_gl_mail_zip',
        'x_gl_ship_street', 'x_gl_ship_street2', 'x_gl_ship_city',
        'x_gl_ship_state_id', 'x_gl_ship_zip',
        # ─── Spouse / Emergency ────────────────────────────────────
        'x_detail_spouse_first_name', 'x_detail_spouse_last_name',
        'x_spouse_has_id_card', 'x_spouse_birthday', 'x_anniversary_date',
        'x_emergency_contact_name', 'x_emergency_relationship',
        'x_emergency_phone',
        # ─── History ───────────────────────────────────────────────
        'x_date_of_birth', 'x_date_of_death',
        # ─── Roles ─────────────────────────────────────────────────
        'x_last_hon_life_date', 'x_last_life_date',
        'x_is_life_eligible', 'x_is_charter_member', 'x_is_assisted',
        'x_dues_pay_cycle', 'x_is_rejected',
        'x_is_enf_donor', 'x_enf_donor_id', 'x_is_smp_donor',
        'x_branch_of_service', 'x_discharge_type', 'x_discharge_date',
        'x_detail_per_start_year', 'x_detail_pdd_start_year',
        'x_detail_poy_start_year', 'x_detail_pey_start_year',
        # ─── Misc ──────────────────────────────────────────────────
        'x_occupation', 'x_employer',
        'x_birth_city', 'x_birth_county', 'x_birth_state_id',
        'x_birth_country_id', 'x_maiden_name',
        'x_original_init_lodge_name', 'x_original_init_lodge_num',
        'x_initiating_exalted_ruler', 'x_initiating_secretary',
        'x_detail_memsysnamid', 'x_dues_rate_code',
        # ─── Secy Contact ──────────────────────────────────────────
        'x_gl_home_phone', 'x_gl_work_phone', 'x_gl_cell_phone',
        'x_gl_fax', 'x_gl_email', 'x_elks_org_email',
    ])

    def _capture_clms_old_values(self, vals):
        """Snapshot current values of CLMS-tracked fields about to be
        written. Returns {partner_id: {field_name: old_value}} or {}
        when nothing relevant is changing / when sync is suppressed.

        Suppressed automatically when any of these are true:
          * Explicit opt-out: ctx['elks_skip_clms_sync']
          * Module install / data load: ctx['install_mode']
          * Standard Odoo CSV import: ctx['import_file']
          * Tracking disabled: ctx['tracking_disable']
        """
        ctx = self.env.context
        if (
            not vals
            or ctx.get('elks_skip_clms_sync')
            or ctx.get('install_mode')
            or ctx.get('import_file')
            or ctx.get('tracking_disable')
        ):
            return {}
        changing = set(vals.keys()) & self.CLMS_SYNC_FIELDS
        if not changing:
            return {}
        snapshot = {}
        for rec in self:
            # Only members are tracked. Initiates haven't been added
            # to CLMS yet, non-members are out of scope.
            if not rec.x_is_member or rec.x_is_initiate:
                continue
            snapshot[rec.id] = {f: rec[f] for f in changing}
        return snapshot

    def _track_clms_changes(self, old_values_by_partner):
        """For each member where CLMS-tracked fields actually changed,
        post a chatter message with the diff AND (re)schedule a
        Secretary to-do."""
        for rec in self:
            old_vals = old_values_by_partner.get(rec.id)
            if not old_vals:
                continue
            changes = {}
            for f, old in old_vals.items():
                new = rec[f]
                # Compare cleanly across recordsets / scalars
                if isinstance(old, models.BaseModel):
                    if old.id != new.id:
                        changes[f] = (old, new)
                elif old != new:
                    changes[f] = (old, new)
            if changes:
                rec._log_clms_field_changes(changes)
                rec._schedule_clms_record_update_activity(changes)

    @staticmethod
    def _format_clms_value(val):
        """Render a value for the chatter table / activity note."""
        if val is False or val is None or val == '':
            return '<em>empty</em>'
        if isinstance(val, models.BaseModel):
            return val.display_name or '<em>empty</em>'
        return str(val)

    def _log_clms_field_changes(self, changes):
        """Post an internal-note chatter message with a tidy diff of
        CLMS-tracked fields that just changed on this member."""
        self.ensure_one()
        descriptions = self.fields_get(list(changes.keys()))
        rows = []
        for fname in sorted(changes.keys()):
            old, new = changes[fname]
            label = descriptions.get(fname, {}).get('string', fname)
            rows.append(
                "<tr><td><strong>%s</strong></td>"
                "<td style='color:#aa3333'>%s</td>"
                "<td>&#8594;</td>"
                "<td style='color:#1f7a1f'>%s</td></tr>"
                % (label, self._format_clms_value(old),
                   self._format_clms_value(new))
            )
        html = (
            "<p><strong>CLMS-tracked fields changed</strong> "
            "(awaiting push to CLMS):</p>"
            "<table style='border-collapse:collapse;font-size:12px;'>"
            "<thead><tr>"
            "<th align='left'>Field</th>"
            "<th align='left'>Was</th><th></th>"
            "<th align='left'>Now</th>"
            "</tr></thead><tbody>%s</tbody></table>"
        ) % ''.join(rows)
        self.message_post(
            body=html,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

    def _clms_secretary_user(self):
        """Find a user in the Lodge Secretary group, falling back to
        the current user if the group is empty / undefined."""
        sec_group = self.env.ref(
            'elkscontacts.group_elks_secretary',
            raise_if_not_found=False,
        )
        if sec_group:
            users = self.env['res.users'].search(
                [('group_ids', 'in', sec_group.id)], limit=1,
            )
            if users:
                return users
        return self.env.user

    def _schedule_clms_record_update_activity(self, changes):
        """Schedule (or accumulate into) a CLMS-update To-Do for the
        Secretary. Dedupes by reusing the open To-Do whose summary
        matches our pattern, so the secretary sees ONE actionable
        task per member with a running list of pending changes."""
        self.ensure_one()
        Activity = self.env['mail.activity']
        todo_type = self.env.ref(
            'mail.mail_activity_data_todo', raise_if_not_found=False,
        )
        if not todo_type:
            return

        descriptions = self.fields_get(list(changes.keys()))
        labels = sorted(
            descriptions.get(f, {}).get('string', f) for f in changes
        )
        fields_html = ''.join('<li>%s</li>' % l for l in labels)
        summary_prefix = "CLMS: Update record for"

        existing = Activity.search([
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', self.id),
            ('activity_type_id', '=', todo_type.id),
            ('summary', '=like', summary_prefix + ' %'),
        ], limit=1)

        if existing:
            existing.note = (existing.note or '') + (
                "<p><strong>Additional fields changed:</strong></p>"
                "<ul>%s</ul>" % fields_html
            )
            return

        secretary = self._clms_secretary_user()
        deadline = fields.Date.context_today(self) + relativedelta(days=3)
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            date_deadline=deadline,
            user_id=secretary.id,
            summary="%s %s" % (
                summary_prefix, self.display_name or 'member',
            ),
            note=_(
                "<p>The following CLMS-tracked fields were changed on "
                "this member and need to be pushed into the CLMS "
                "record at Grand Lodge:</p>"
                "<ul>%(fields)s</ul>"
                "<p>Mark this activity Done after you've updated CLMS.</p>"
            ) % {'fields': fields_html},
        )
