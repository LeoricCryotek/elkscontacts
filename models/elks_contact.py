# -*- coding: utf-8 -*-
# © 2025
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.en.html)
#
# Module: elkscontacts
#
# This file extends `res.partner` with Elks-specific fields and mapping logic.
# Highlights:
# - Import-friendly create() that de-duplicates by Elks Member Number.
# - Partners with a member number are always kept as individuals (not companies).
# - Two mapping helpers:
#     * action_apply_elks_mapping(): conservative sync (if x_* present and different)
#     * action_copy_core_from_elks(): copy x_* into native fields (optionally overwrite)
# - An action to run both mappings on any subset or all Elks-like contacts.
#
# Notes for Odoo 19:
# - _sql_constraints is deprecated in favor of model.Constraint API.
#   Here we provide robust ORM-level uniqueness checks; you can add real DB
#   constraints later with the new API if desired.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # -------------------------------------------------------------------------
    # Local (chapter-specific) data
    # -------------------------------------------------------------------------
    x_local_door_code = fields.Char("Door Code", help="Local building or door access code.")
    x_local_has_key = fields.Boolean("Has Key")
    x_local_volunteer_active = fields.Boolean("Volunteer Active")
    x_local_bartender = fields.Boolean("Bartender")
    x_local_kitchen = fields.Boolean("Kitchen")
    x_local_sanitation = fields.Boolean("Sanitation")

    # -------------------------------------------------------------------------
    # Membership / Lodge
    # -------------------------------------------------------------------------
    x_is_not_member = fields.Boolean("Is not an Elks Member", index=True)
    x_detail_id = fields.Char("DetailID", index=True)
    x_detail_lodge_id = fields.Char("DetailLodgeID")
    x_detail_lodge_num = fields.Char("DetailLodgeNum")
    x_detail_member_num = fields.Char("DetailMemberNum", index=True)
    x_lodge_report_lodge_name = fields.Char("LodgeReportLodgeName")

    # -------------------------------------------------------------------------
    # Name components / salutation
    # -------------------------------------------------------------------------
    x_detail_name_prefix = fields.Char("DetailNamePrefix")
    x_detail_first_name = fields.Char("DetailFirstName")
    x_detail_name_salutation = fields.Char("DetailNameSalutation")  # maps to title
    x_detail_middle_name = fields.Char("DetailMiddleName")
    x_detail_last_name = fields.Char("DetailLastName")
    x_detail_name_suffix = fields.Char("DetailNameSuffix")

    # -------------------------------------------------------------------------
    # Elks specifics / accounting
    # -------------------------------------------------------------------------
    x_detail_elk_title = fields.Char("DetailElkTitle")
    x_detail_delinquent_months = fields.Integer("DetailDelinquentMonths")
    x_detail_dues_paid_to_date = fields.Date("DetailDuesPaidToDate")

    # -------------------------------------------------------------------------
    # Address (source) + USPS/CASS
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # Household
    # -------------------------------------------------------------------------
    x_detail_spouse_first_name = fields.Char("DetailSpouseFirstName")
    x_detail_spouse_last_name = fields.Char("DetailSpouseLastName")
    x_detail_head_of_household_num = fields.Char("DetailHeadOfHouseholdNum")
    x_detail_is_head_of_household = fields.Boolean("DetailIsHeadOfHousehold")

    # -------------------------------------------------------------------------
    # Phones / Email (raw)
    # (We do not set native `mobile`/`fax` in this build; we only feed `phone`.)
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # User values (opaque slots from source system)
    # -------------------------------------------------------------------------
    x_detail_user_value_001 = fields.Char("DetailUserValue001")
    x_detail_user_value_002 = fields.Char("DetailUserValue002")
    x_detail_user_value_003 = fields.Char("DetailUserValue003")
    x_detail_user_value_004 = fields.Char("DetailUserValue004")
    x_detail_user_value_005 = fields.Char("DetailUserValue005")
    x_detail_user_value_006 = fields.Char("DetailUserValue006")
    x_detail_user_value_007 = fields.Char("DetailUserValue007")
    x_detail_user_value_008 = fields.Char("DetailUserValue008")
    x_detail_user_value_009 = fields.Char("DetailUserValue009")

    # -------------------------------------------------------------------------
    # Dates / Years
    # -------------------------------------------------------------------------
    x_last_life_date = fields.Date("LastLifeDate")
    x_last_hon_life_date = fields.Date("LastHonLifeDate")
    x_detail_pey_start_year = fields.Integer("DetailPEYStartYear")
    x_detail_per_start_year = fields.Integer("DetailPERStartYear")
    x_detail_poy_start_year = fields.Integer("DetailPOYStartYear")

    # -------------------------------------------------------------------------
    # Misc
    # -------------------------------------------------------------------------
    x_maiden_name = fields.Char("MaidenName")
    x_enotices_ok = fields.Boolean("eNoticesOK")
    x_branch_of_service = fields.Char("branchOfService")
    x_discharge_type = fields.Char("dischargeType")
    x_discharge_date = fields.Date("dischargeDate")
    x_sortfield = fields.Char("Sortfield")
    x_original_index = fields.Char("OriginalIndex")

    # -------------------------------------------------------------------------
    # Officers
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # Heads-up (Odoo 19 constraints)
    # -------------------------------------------------------------------------
    # _sql_constraints is deprecated. For DB-level uniqueness, define
    # `model.Constraint` entries in `_constraints`. We keep ORM checks below.
    #
    # Example (if you want DB constraints later):
    #
    # _constraints = [
    #     models.UniqueConstraint(
    #         name="res_partner_uniq_member_num",
    #         fields=["x_detail_member_num"],
    #         message="Another contact already has this Elks Member Number.",
    #     ),
    #     models.UniqueConstraint(
    #         name="unique_elks_officer_position",
    #         fields=["x_elks_officer_position"],
    #         message="There can be only one holder for each Elks officer position.",
    #     ),
    # ]

    # =========================================================================
    # Helpers
    # =========================================================================
    def _prepare_person_defaults(self, vals):
        """Ensure partner is an individual.

        Used on import/create/write for any record tied to a member number to
        prevent accidental company contacts.
        """
        vals = dict(vals or {})
        vals.setdefault('company_type', 'person')
        if vals.get('company_type') == 'person':
            vals['is_company'] = False
            vals.setdefault('type', 'contact')   # explicit is better than implicit
            vals['company_name'] = False
        return vals

    def _elks_compose_name(self, vals=None):
        """Compose display name from Elks name parts (first, middle, last)."""
        if vals is None:
            first = (self.x_detail_first_name or "").strip()
            middle = (self.x_detail_middle_name or "").strip()
            last = (self.x_detail_last_name or "").strip()
        else:
            first = (vals.get("x_detail_first_name") or "").strip()
            middle = (vals.get("x_detail_middle_name") or "").strip()
            last = (vals.get("x_detail_last_name") or "").strip()
        return " ".join([p for p in (first, middle, last) if p]).strip()

    def _compose_phone(self, area, number, ext=None):
        """Build a human-readable phone string like '206-5551234 x12'."""
        area = (area or "").strip()
        number = (number or "").strip()
        ext = (ext or "").strip() if ext else ""
        if not area and not number:
            return False
        core = number or area
        if area and number:
            core = f"{area}-{number}" if "-" not in number and " " not in number else f"{area} {number}"
        if ext:
            core = f"{core} x{ext}"
        return core

    def _find_country(self, val):
        """Resolve a country by code or by name (case-insensitive)."""
        if not val:
            return False
        value = val.strip()
        Country = self.env["res.country"]
        return Country.search([("code", "=ilike", value)], limit=1) or \
               Country.search([("name", "=ilike", value)], limit=1) or False

    def _find_state(self, val, country=False):
        """Resolve a state by code or by name, optionally restricted by country."""
        if not val:
            return False
        value = val.strip()
        domain = [("country_id", "=", country.id)] if country else []
        State = self.env["res.country.state"]
        return State.search(domain + [("code", "=ilike", value)], limit=1) or \
               State.search(domain + [("name", "=ilike", value)], limit=1) or False

    def _find_title(self, val):
        """Resolve (or create) a partner title from a salutation string."""
        if not val:
            return False
        name = val.strip()
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

    # =========================================================================
    # Computes / Constraints
    # =========================================================================
    @api.depends('x_elks_officer_position')
    def _compute_x_elks_officer_type(self):
        """Derive officer type (elected vs appointed) from the position."""
        elected = {
            'exalted_ruler', 'leading_knight', 'loyal_knight',
            'lecturing_knight', 'secretary', 'treasurer',
        }
        for rec in self:
            if rec.x_elks_officer_position in elected:
                rec.x_elks_officer_type = 'elected'
            elif rec.x_elks_officer_position:
                rec.x_elks_officer_type = 'appointed'
            else:
                rec.x_elks_officer_type = False

    @api.depends('x_elks_officer_position')
    def _compute_x_is_elks_officer(self):
        """Boolean convenience for UI & filters."""
        for rec in self:
            rec.x_is_elks_officer = bool(rec.x_elks_officer_position)

    @api.constrains('x_elks_officer_position', 'active')
    def _check_unique_officer_position(self):
        """Soft uniqueness check so users get a clear message (UX)."""
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
                raise ValidationError(
                    _("Only one member can be '%s'. Current holder: %s") % (label, other.display_name)
                )

    @api.constrains('x_detail_member_num')
    def _check_unique_member_num(self):
        """Member number must be unique across all partners (incl. archived)."""
        for rec in self:
            num = (rec.x_detail_member_num or "").strip()
            if not num:
                continue
            dup = self.with_context(active_test=False).search([
                ('id', '!=', rec.id),
                ('x_detail_member_num', '=', num),
            ], limit=1)
            if dup:
                raise ValidationError(_("Another contact already has this Elks Member Number."))

    # =========================================================================
    # Create / Write
    # =========================================================================
    @api.model_create_multi
    def create(self, vals_list):
        """Import-friendly create with de-duplication by member number.

        Behavior:
        - If an incoming row has x_detail_member_num matching an existing partner
          (even archived), we update that record instead of creating a duplicate.
        - Partners with a member number are forced to person/contact shape.
        - Ensures a non-empty `name` (built from x_* parts, email, or a fallback).
        - After all rows, runs `action_update_elk_members()` on touched records.
        """
        def norm(num):
            return str(num).strip() if num else ""

        # Prefetch existing records by member numbers present in the batch
        nums = list({norm(v.get("x_detail_member_num")) for v in vals_list if v.get("x_detail_member_num")})
        existing = self.with_context(active_test=False).search(
            [("x_detail_member_num", "in", [n for n in nums if n])]
        ) if nums else self.browse()
        by_num = {rec.x_detail_member_num.strip(): rec for rec in existing if rec.x_detail_member_num}

        touched = self.browse()
        to_create = []

        for vals in vals_list:
            vals = dict(vals or {})
            vals = self._prepare_person_defaults(vals)

            # Ensure a display name
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
                # Update existing (merge), keep the member number intact
                rec = by_num[num]
                upd = dict(vals)
                upd.pop("x_detail_member_num", None)
                rec.write(upd)

                # Make sure the shape remains a person/contact
                if rec.is_company or rec.company_type != "person":
                    rec.write({"is_company": False, "company_type": "person"})

                touched |= rec
            else:
                to_create.append(vals)

        if to_create:
            created = super().create(to_create)
            for r in created:
                if r.x_detail_member_num:
                    by_num[r.x_detail_member_num.strip()] = r
            touched |= created

        # Post-process mapping (useful after imports)
        if touched:
            overwrite = bool(self.env.context.get("elks_overwrite", True))
            touched.action_update_elk_members(overwrite=overwrite, only_with_elks=False)

        return touched

    def write(self, vals):
        """Keep Elks members as individuals and maintain name coherence.

        - If any record in `self` has a member number and caller does not
          explicitly change company fields, enforce person/contact shape.
        - If name parts changed and the display name is blank, rebuild it.
        """
        if ("is_company" not in vals) and ("company_type" not in vals):
            if any(rec.x_detail_member_num for rec in self):
                vals = self._prepare_person_defaults(vals)

        res = super().write(vals)

        # Backfill missing display name after editing name parts
        if any(k in vals for k in ("x_detail_first_name", "x_detail_middle_name", "x_detail_last_name")):
            for rec in self:
                if not (rec.name or "").strip():
                    composed = rec._elks_compose_name()
                    if composed:
                        super(ResPartner, rec).write({"name": composed})
        return res

    # =========================================================================
    # Mapping helpers / actions
    # =========================================================================
    def action_apply_elks_mapping(self):
        """Conservative one-way sync from x_* to native fields.

        Only sets native fields when the x_* source is present and the target
        differs. Safe to run repeatedly. Prefers cell over home for `phone`.
        """
        has = self._fields  # field presence guard (instances may vary)
        has_title = 'title' in has
        has_email = 'email' in has
        has_name = 'name' in has
        has_phone = 'phone' in has
        has_street = 'street' in has
        has_street2 = 'street2' in has
        has_city = 'city' in has
        has_zip = 'zip' in has
        has_country = 'country_id' in has
        has_state = 'state_id' in has

        for rec in self:
            vals = {}

            # Name
            if has_name:
                parts = [rec.x_detail_first_name, rec.x_detail_middle_name, rec.x_detail_last_name]
                combined = " ".join([p.strip() for p in parts if p and p.strip()])
                if combined and combined != (getattr(rec, 'name', '') or ''):
                    vals["name"] = combined

            # Title
            if has_title:
                title = rec._find_title(rec.x_detail_name_salutation)
                if title and getattr(rec, 'title', False) != title:
                    vals["title"] = title.id

            # Email
            if has_email:
                x_email = (rec.x_detail_email_address or "").strip()
                cur_email = (getattr(rec, 'email', '') or '').strip()
                if x_email and cur_email != x_email:
                    vals["email"] = x_email

            # Country / State resolution first (used by address too)
            country_obj = False
            if has_country and rec.x_detail_active_country:
                country_obj = rec._find_country(rec.x_detail_active_country)
                if country_obj:
                    vals["country_id"] = country_obj.id

            if has_state and rec.x_detail_active_state:
                state_obj = rec._find_state(rec.x_detail_active_state, country_obj or getattr(rec, 'country_id', False))
                if state_obj:
                    vals["state_id"] = state_obj.id

            # Address
            if has_street and rec.x_detail_active_address_line1:
                vals["street"] = rec.x_detail_active_address_line1
            if has_street2 and rec.x_detail_active_address_line2:
                vals["street2"] = rec.x_detail_active_address_line2
            if has_city and rec.x_detail_active_city:
                vals["city"] = rec.x_detail_active_city
            if has_zip and rec.x_detail_active_zip:
                vals["zip"] = rec.x_detail_active_zip

            # Phone (prefer cell, then home)
            if has_phone:
                home = rec._compose_phone(rec.x_detail_home_area_code, rec.x_detail_home_phone, rec.x_detail_home_phone_ext)
                cell = rec._compose_phone(rec.x_detail_cell_area_code, rec.x_detail_cell_phone, None)
                best = cell or home
                cur = (getattr(rec, 'phone', '') or '').strip()
                if best and cur != best:
                    vals["phone"] = best

            if vals:
                rec.write(vals)

    def action_copy_core_from_elks(self, overwrite=False):
        """Copy x_* → native fields (street/street2/city/state/zip/country/email/phone).

        If `overwrite` is False (default), only empty targets are filled.
        If `overwrite` is True, existing values are replaced.
        """
        has = self._fields
        has_email = 'email' in has
        has_phone = 'phone' in has
        has_country = 'country_id' in has
        has_state = 'state_id' in has

        for rec in self:
            vals = {}

            def set_if(value, target):
                """Set target if value is non-empty and field exists; honor overwrite."""
                if not value or target not in has:
                    return
                current = (getattr(rec, target, '') or '').strip()
                if overwrite or not current:
                    vals[target] = value

            # Country & State (do this first; address may rely on country/state context)
            country_obj = None
            if has_country and rec.x_detail_active_country:
                country_obj = rec._find_country(rec.x_detail_active_country)
                if country_obj and (overwrite or not getattr(rec, 'country_id', False)):
                    vals["country_id"] = country_obj.id
            else:
                country_obj = getattr(rec, 'country_id', False)

            if has_state and rec.x_detail_active_state:
                state_obj = rec._find_state(rec.x_detail_active_state, country_obj)
                if state_obj and (overwrite or not getattr(rec, 'state_id', False)):
                    vals["state_id"] = state_obj.id

            # Address lines + city + zip
            set_if(rec.x_detail_active_address_line1, "street")
            set_if(rec.x_detail_active_address_line2, "street2")
            set_if(rec.x_detail_active_city, "city")
            set_if(rec.x_detail_active_zip, "zip")

            # Email
            if has_email:
                x_email = (rec.x_detail_email_address or "").strip()
                set_if(x_email, "email")

            # Phone (prefer cell, then home)
            if has_phone:
                home = rec._compose_phone(rec.x_detail_home_area_code, rec.x_detail_home_phone, rec.x_detail_home_phone_ext)
                cell = rec._compose_phone(rec.x_detail_cell_area_code, rec.x_detail_cell_phone, None)
                best = cell or home
                set_if(best, "phone")

            if vals:
                rec.write(vals)

    def action_update_elk_members(self, overwrite=False, only_with_elks=True):
        """Run both mapping helpers on a set of partners.

        When called on a recordset: runs only on `self`.
        When called on an empty recordset:
          * If `only_with_elks` is True (default), runs on any partner that has
            *any* of the Elks x_* fields populated (domain built as OR of fields).
          * Otherwise runs on *all* partners.

        Returns:
            int: number of partners processed.
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
                # Proper prefix-notation OR domain: ['|', '|', ..., term1, term2, ...]
                terms = [(f, '!=', False) for f in fields_to_check]
                domain = (['|'] * (len(terms) - 1)) + terms
            else:
                domain = []

            partners = Partner.search(domain)

        if not partners:
            return 0

        partners.action_apply_elks_mapping()
        partners.action_copy_core_from_elks(overwrite=overwrite)
        return len(partners)
