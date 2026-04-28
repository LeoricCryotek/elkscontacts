# -*- coding: utf-8 -*-
# Copyright (C) 2025
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html)

from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)


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
    x_is_not_member = fields.Boolean("Is not an Elks Member", index=True)
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
