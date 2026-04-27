# -*- coding: utf-8 -*-
"""CLMS Member Directory Import Wizard.

Imports the "All Active Members - Full Directory" CSV export from the
Elks CLMS system.  Handles date format differences (ISO vs locale),
maps columns to x_detail_* fields, and leverages the existing
res.partner.create() merge-by-member-number logic.
"""
import base64
import csv
import datetime
import io

from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)

# Map CSV column headers (case-insensitive, stripped) → res.partner field names.
# The CSV headers come from the CLMS export and may vary slightly between versions.
COLUMN_MAP = {
    'detaillodgenum': 'x_detail_lodge_num',
    'detaildelinquentmonths': 'x_detail_delinquent_months',
    'detailnameprefix': 'x_detail_name_prefix',
    'detailfirstname': 'x_detail_first_name',
    'detailmiddlename': 'x_detail_middle_name',
    'detaillastname': 'x_detail_last_name',
    'detailnamesuffix': 'x_detail_name_suffix',
    'detailmembernum': 'x_detail_member_num',
    'detailduespaidtodate': 'x_detail_dues_paid_to_date',
    'detailspousefirstname': 'x_detail_spouse_first_name',
    'detailactiveaddressline1': 'x_detail_active_address_line1',
    'detailactiveaddressline2': 'x_detail_active_address_line2',
    'detailactivecity': 'x_detail_active_city',
    'detailactivestate': 'x_detail_active_state',
    'detailactivezip': 'x_detail_active_zip',
    'detailactivecountry': 'x_detail_active_country',
    'detailhomeareacode': 'x_detail_home_area_code',
    'detailhomephone': 'x_detail_home_phone',
    'detailhomephoneext': 'x_detail_home_phone_ext',
    'detailworkareacode': 'x_detail_work_area_code',
    'detailworkphone': 'x_detail_work_phone',
    'detailworkphoneext': 'x_detail_work_phone_ext',
    'detailcellareacode': 'x_detail_cell_area_code',
    'detailcellphone': 'x_detail_cell_phone',
    'detailfaxareacode': 'x_detail_fax_area_code',
    'detailfaxphone': 'x_detail_fax_phone',
    'detailemailaddress': 'x_detail_email_address',
    'detailspouselastname': 'x_detail_spouse_last_name',
    'detailactivesendnomail': 'x_detail_active_send_no_mail',
    'detailactiveisundeliverable': 'x_detail_active_is_undeliverable',
    'detailactivesendnomagazine': 'x_detail_active_send_no_magazine',
    'detailheadofhouseholdnum': 'x_detail_head_of_household_num',
    'detailisheadofhousehold': 'x_detail_is_head_of_household',
    'detailelktitle': 'x_detail_elk_title',
    'detailnamesalutation': 'x_detail_name_salutation',
    'detailid': 'x_detail_id',
    'detaillodgeid': 'x_detail_lodge_id',
    'originalindex': 'x_original_index',
    # User value fields
    'detailuservalue001': 'x_detail_user_value_001',
    'detailuservalue002': 'x_detail_user_value_002',
    'detailuservalue003': 'x_detail_user_value_003',
    'detailuservalue004': 'x_detail_user_value_004',
    'detailuservalue005': 'x_detail_user_value_005',
    'detailuservalue006': 'x_detail_user_value_006',
    'detailuservalue007': 'x_detail_user_value_007',
    'detailuservalue008': 'x_detail_user_value_008',
    'detailuservalue009': 'x_detail_user_value_009',
    # Date fields
    'lastlifedate': 'x_last_life_date',
    'lasthonlifedate': 'x_last_hon_life_date',
    'dischargedate': 'x_discharge_date',
    # Other misc
    'enoticesok': 'x_enotices_ok',
    'branchofservice': 'x_branch_of_service',
    'dischargetype': 'x_discharge_type',
    'maidenname': 'x_maiden_name',
    'sortfield': 'x_sortfield',
}

# Fields that contain dates and need parsing
DATE_FIELDS = {
    'x_detail_dues_paid_to_date',
    'x_last_life_date',
    'x_last_hon_life_date',
    'x_discharge_date',
}

# Fields that should be integers
INT_FIELDS = {
    'x_detail_delinquent_months',
}

# Fields that are booleans (CLMS uses various true/false representations)
BOOL_FIELDS = {
    'x_detail_active_send_no_mail',
    'x_detail_active_is_undeliverable',
    'x_detail_active_send_no_magazine',
    'x_detail_is_head_of_household',
    'x_enotices_ok',
}


class ClmsImportWizard(models.TransientModel):
    _name = "clms.import.wizard"
    _description = "CLMS Member Directory Import"

    file_data = fields.Binary("CLMS CSV File", required=True)
    file_name = fields.Char("Filename")
    overwrite = fields.Boolean(
        "Overwrite Existing Data", default=True,
        help="If checked, existing member records will be fully updated "
             "with the CSV data.  If unchecked, only empty fields are filled.",
    )

    state = fields.Selection([
        ('setup', 'Setup'),
        ('done', 'Done'),
    ], default='setup')
    result_message = fields.Text("Import Results", readonly=True)

    def action_import(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_("Please upload a CLMS CSV file."))

        raw = base64.b64decode(self.file_data)
        try:
            content = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            content = raw.decode('latin-1')

        result = self._import_clms(content)
        self.write({
            'state': 'done',
            'result_message': result,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _import_clms(self, content):
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            raise UserError(_("Empty or invalid CSV file."))

        # Build column mapping for this specific CSV
        col_map = {}
        unmapped = []
        for col in reader.fieldnames:
            key = col.strip().lower().replace('_', '').replace(' ', '')
            if key in COLUMN_MAP:
                col_map[col] = COLUMN_MAP[key]
            elif key not in ('group', 'recordtypecode', 'recordstatus',
                             'detailrecordtypecode', 'detailrecordstatus'):
                unmapped.append(col)

        if not col_map:
            raise UserError(_(
                "No CLMS columns found in the CSV. "
                "Expected columns like DetailMemberNum, DetailFirstName, etc.\n"
                "Found: %s"
            ) % ", ".join(reader.fieldnames))

        Partner = self.env['res.partner'].with_context(
            elks_overwrite=self.overwrite,
        )

        created = 0
        updated = 0
        skipped = 0
        errors = []
        vals_list = []

        for i, row in enumerate(reader, start=2):
            try:
                vals = {'x_is_not_member': False}
                member_num = None

                for csv_col, field_name in col_map.items():
                    raw_val = (row.get(csv_col) or '').strip()
                    if not raw_val:
                        continue

                    if field_name in DATE_FIELDS:
                        parsed = self._parse_date(raw_val)
                        if parsed:
                            vals[field_name] = parsed
                    elif field_name in INT_FIELDS:
                        try:
                            vals[field_name] = int(raw_val)
                        except ValueError:
                            pass
                    elif field_name in BOOL_FIELDS:
                        vals[field_name] = raw_val.lower() in (
                            'true', '1', 'yes', 'y', 't',
                        )
                    else:
                        vals[field_name] = raw_val

                    if field_name == 'x_detail_member_num':
                        member_num = raw_val

                if not member_num:
                    skipped += 1
                    continue

                vals_list.append(vals)

            except Exception as e:
                errors.append(f"Row {i}: {e}")

        # Use the model's create() which handles merge-by-member-number
        if vals_list:
            _logger.info("CLMS import: processing %d records...", len(vals_list))
            try:
                results = Partner.create(vals_list)
                # Count created vs updated by checking which already existed
                existing_nums = set()
                all_partners = Partner.with_context(active_test=False).search([
                    ('x_detail_member_num', '!=', False),
                ])
                existing_nums = {
                    p.x_detail_member_num.strip()
                    for p in all_partners
                    if p.x_detail_member_num
                }
                for v in vals_list:
                    num = (v.get('x_detail_member_num') or '').strip()
                    if num in existing_nums:
                        updated += 1
                    else:
                        created += 1
            except Exception as e:
                errors.append(f"Batch create error: {e}")

        # Build results
        parts = [
            f"CLMS IMPORT RESULTS: {len(vals_list)} records processed"
        ]
        if created or updated:
            parts[0] += f" ({created} new, {updated} updated)"
        if skipped:
            parts.append(f"\nSkipped {skipped} rows with no member number.")
        if unmapped:
            parts.append(f"\nUnmapped CSV columns (ignored): {', '.join(unmapped)}")
        if errors:
            parts.append(f"\n--- ERRORS ({len(errors)}) ---")
            parts.extend(f"  {e}" for e in errors)

        return "\n".join(parts)

    @staticmethod
    def _parse_date(val):
        """Parse dates from CLMS exports, handling multiple formats.

        CLMS has exported dates in various formats over the years:
          2027-04-01  (ISO, current)
          04/01/2027  (US)
          04.01.2027  (US with dots)
          4/1/2027    (US short)
        """
        if not val:
            return False
        val = val.strip()
        for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m.%d.%Y', '%m-%d-%Y',
                    '%m/%d/%y', '%m.%d.%y'):
            try:
                return datetime.datetime.strptime(val, fmt).date()
            except ValueError:
                continue
        _logger.warning("Could not parse date: %s", val)
        return False
