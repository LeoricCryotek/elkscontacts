# -*- coding: utf-8 -*-
"""Override base_import.import to accept multiple date formats.

Odoo's built-in CSV/XLSX importer only tries the single date format
chosen in the import options dialog.  This override adds a fallback:
if the chosen format fails, try several common alternatives before
raising the error.  This lets the same CSV contain '2027-04-01' (ISO),
'04/01/2027' (US), '04.01.2027' (CLMS), etc. and still import cleanly.
"""
import datetime

from odoo import fields, models, _

try:
    from odoo.addons.base_import.models.base_import import ImportValidationError
except ImportError:
    # Fallback if the base_import addon structure differs between Odoo builds
    class ImportValidationError(Exception):
        def __init__(self, message, **kwargs):
            self.field = kwargs.get('field')
            self.field_type = kwargs.get('field_type')
            super().__init__(message)

DEFAULT_SERVER_DATE_FORMAT = '%Y-%m-%d'
DEFAULT_SERVER_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

# Formats tried (in order) when the user-selected format fails.
_FALLBACK_DATE_FORMATS = (
    '%Y-%m-%d',     # ISO: 2027-04-01
    '%m/%d/%Y',     # US slash: 04/01/2027
    '%m.%d.%Y',     # CLMS dot: 04.01.2027
    '%m-%d-%Y',     # US dash: 04-01-2027
    '%d/%m/%Y',     # EU slash: 01/04/2027
    '%Y/%m/%d',     # ISO slash: 2027/04/01
)


class BaseImportFlexDate(models.TransientModel):
    _inherit = 'base_import.import'

    def _parse_date_from_data(self, data, index, name, field_type, options):
        """Try the user-selected format first, then fall back to common alternatives."""
        dt = datetime.datetime
        fmt_fn = fields.Date.to_string if field_type == 'date' else fields.Datetime.to_string
        d_fmt = options.get('date_format') or DEFAULT_SERVER_DATE_FORMAT
        dt_fmt = options.get('datetime_format') or DEFAULT_SERVER_DATETIME_FORMAT

        for num, line in enumerate(data):
            if not line[index] or isinstance(line[index], datetime.date):
                continue

            v = line[index].strip()

            # 1) Try the user-selected format (datetime first, then date)
            parsed = False
            if dt_fmt and field_type == 'datetime':
                try:
                    line[index] = fmt_fn(dt.strptime(v, dt_fmt))
                    continue
                except ValueError:
                    pass

            try:
                line[index] = fmt_fn(dt.strptime(v, d_fmt))
                continue
            except ValueError:
                pass

            # 2) Fallback — try all common formats
            for fallback in _FALLBACK_DATE_FORMATS:
                if fallback == d_fmt:
                    continue  # already tried
                try:
                    line[index] = fmt_fn(dt.strptime(v, fallback))
                    parsed = True
                    break
                except ValueError:
                    continue

            if parsed:
                continue

            # 3) Nothing worked — raise the original-style error
            raise ImportValidationError(
                _(
                    "Column %(column)s contains incorrect values. "
                    "Error in line %(line)d: could not parse '%(value)s' as a date",
                    column=name, line=num + 1, value=v,
                ),
                field=name, field_type=field_type,
            )
