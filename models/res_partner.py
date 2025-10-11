# -*- coding: utf-8 -*-
"""
Elks Contacts – partner helpers for dues status and field mapping.

This extension adds:
  1) A stored boolean `x_is_dues_paid` (computed from `x_detail_dues_paid_to_date`)
     so you can search/filter/group by “dues paid in the last 12 months”.
  2) A utility action `action_copy_core_from_elks` that copies selected
     x_* fields (coming from Elks import) into native `res.partner` fields.
     It respects an `overwrite` flag.

Compatibility:
  - Odoo 19.0 (saas-18+). No deprecated `attrs/states` here.
  - Assumes helper methods `_find_country`, `_find_state`, and `_compose_phone`
    are available on `res.partner` (they exist elsewhere in your module).

Author: you :)
"""

from __future__ import annotations

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class ResPartner(models.Model):
    """Extend partners with Elks-specific helpers and a searchable dues flag."""
    _inherit = "res.partner"

    # -------------------------------------------------------------------------
    # Source field (already present in your model, repeated here for clarity)
    # -------------------------------------------------------------------------
    x_detail_dues_paid_to_date = fields.Date(
        string="DetailDuesPaidToDate",
        help=(
            "Date through which the member's dues are paid. "
            "Used to compute the boolean 'Dues Paid (last 12 months)'."
        ),
    )

    # -------------------------------------------------------------------------
    # Derived/searchable field – "Paid within last 12 months"
    # -------------------------------------------------------------------------
    x_is_dues_paid = fields.Boolean(
        string="Dues Paid (last 12 months)",
        help=(
            "Checked if DetailDuesPaidToDate is within the last 12 months. "
            "Stored for fast filtering/grouping and updated by compute and cron."
        ),
        compute="_compute_is_dues_paid",
        compute_sudo=True,   # make compute independent from the viewer's rights
        store=True,          # stored so we can filter/group efficiently
        index=True,          # common to search on kanban/list
    )

    # ----------------------------- COMPUTE -----------------------------------
    @api.depends("x_detail_dues_paid_to_date")
    def _compute_is_dues_paid(self) -> None:
        """Set `x_is_dues_paid` based on a rolling 12-month window.

        Logic:
          - Today minus 12 months is the cutoff.
          - If x_detail_dues_paid_to_date >= cutoff -> True; else False.

        Notes:
          - Uses context-aware date (respects user TZ/date context).
          - Lightweight: a single comparison per record.
        """
        today = fields.Date.context_today(self)
        cutoff = today - relativedelta(months=12)

        for rec in self:
            d = rec.x_detail_dues_paid_to_date
            rec.x_is_dues_paid = bool(d and d >= cutoff)

    # ------------------------------ CRON -------------------------------------
    @api.model
    def cron_update_is_dues_paid(self) -> int:
        """Nightly maintenance job to keep `x_is_dues_paid` fresh.

        Why needed if it's computed + stored?
            - Stored computed fields update when dependencies change.
              Here, time itself is a dependency (the 12-month window),
              so a periodic recompute keeps the boolean aligned without
              needing to touch the source date.

        What it does:
            - Finds records that should flip from False->True or True->False
              *based on today’s cutoff* and updates them in batch.

        Returns:
            int: number of partner records updated (set True + set False).

        Safe-by-default:
            - Uses sudo to avoid access glitches for normal users.
            - Limits to active partners to keep noise low.
        """
        today = fields.Date.context_today(self)
        cutoff = today - relativedelta(months=12)
        Partner = self.env["res.partner"].sudo()

        # 1) Become True: previously False, has a date, date >= cutoff
        to_true = Partner.search([
            ("active", "=", True),
            ("x_is_dues_paid", "=", False),
            ("x_detail_dues_paid_to_date", "!=", False),
            ("x_detail_dues_paid_to_date", ">=", cutoff),
        ])
        if to_true:
            to_true.write({"x_is_dues_paid": True})

        # 2) Become False: previously True, and (no date OR date < cutoff)
        to_false = Partner.search([
            ("active", "=", True),
            ("x_is_dues_paid", "=", True),
            "|",
                ("x_detail_dues_paid_to_date", "=", False),
                ("x_detail_dues_paid_to_date", "<", cutoff),
        ])
        if to_false:
            to_false.write({"x_is_dues_paid": False})

        return len(to_true) + len(to_false)

    # --------------------------- FIELD MAPPING --------------------------------
    def action_copy_core_from_elks(self, overwrite: bool = False) -> None:
        """Copy selected Elks x_* fields into native partner fields.

        Args:
            overwrite (bool): If True, always overwrite target fields.
                              If False (default), only fill *empty* targets.

        What gets copied (when provided):
            - Address: street, street2, city, zip, country_id, state_id
            - Email:   email
            - Phone:   prefer cell; if absent, use home
                       (Writes to `phone`. Writes to `mobile` *only if* that field exists.)

        Resolution helpers:
            - Country resolved with `_find_country`
            - State   resolved with `_find_state`
            - Phones  combined with `_compose_phone`

        Notes:
            - Safe to call on any recordset size; writes are per-record but
              only performed if there is at least one value to set.
            - The method is idempotent when overwrite=False.
            - Designed to NOT crash if your database lacks optional fields
              like `mobile` (guards below).
        """
        # Guard native targets once per recordset (lean installs may not have all fields)
        native = self._fields
        has_street = 'street' in native
        has_street2 = 'street2' in native
        has_city = 'city' in native
        has_zip = 'zip' in native
        has_country = 'country_id' in native
        has_state = 'state_id' in native
        has_email = 'email' in native
        has_phone = 'phone' in native
        has_mobile = 'mobile' in native  # may be missing in some minimal installs

        for rec in self:
            vals: dict = {}

            def set_if(value: str | bool | int | None,
                       target_field: str) -> None:
                """Assign `value` into vals[target_field] respecting overwrite mode."""
                if not value or target_field not in native:
                    return
                current_value = getattr(rec, target_field, False)
                current_str = (current_value or "") if isinstance(current_value, str) else current_value
                if overwrite or not current_str:
                    vals[target_field] = value

            # ---------------- Country & State (do first, useful context) ----------------
            country = None
            if has_country and rec.x_detail_active_country:
                country_obj = rec._find_country(rec.x_detail_active_country)
                if country_obj and (overwrite or not getattr(rec, 'country_id', False)):
                    vals["country_id"] = country_obj.id
                country = country_obj or getattr(rec, 'country_id', False)
            else:
                country = getattr(rec, 'country_id', False)

            if has_state and rec.x_detail_active_state:
                state_obj = rec._find_state(rec.x_detail_active_state, country)
                if state_obj and (overwrite or not getattr(rec, 'state_id', False)):
                    vals["state_id"] = state_obj.id

            # ---------------- Address lines & city/zip ----------------
            if has_street:
                set_if(rec.x_detail_active_address_line1, "street")
            if has_street2:
                set_if(rec.x_detail_active_address_line2, "street2")
            if has_city:
                set_if(rec.x_detail_active_city, "city")
            if has_zip:
                set_if(rec.x_detail_active_zip, "zip")

            # ---------------- Email ----------------
            if has_email:
                x_email = (rec.x_detail_email_address or "").strip()
                set_if(x_email, "email")

            # ---------------- Phone (prefer cell, else home) ----------------
            cell = rec._compose_phone(rec.x_detail_cell_area_code, rec.x_detail_cell_phone, None)
            home = rec._compose_phone(rec.x_detail_home_area_code, rec.x_detail_home_phone, rec.x_detail_home_phone_ext)
            best = cell or home

            # Always try to fill `phone` first (widely present)
            if has_phone:
                set_if(best, "phone")

            # Optionally mirror to `mobile` if that field exists (and you want it)
            if has_mobile and cell:
                set_if(cell, "mobile")

            # Single write per record (if anything to update)
            if vals:
                rec.write(vals)
