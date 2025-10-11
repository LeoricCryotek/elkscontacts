# -*- coding: utf-8 -*-
"""
Elks Contacts – expose the member number on res.users.

What this does
--------------
Adds a related field `x_detail_member_num` on users that points to
`partner_id.x_detail_member_num`. It is:

- stored   → fast to search/group on users;
- writable → edits on the User form write back to the linked partner;
- indexed  → (optional) faster lookups by member number on users.

Notes & caveats
---------------
- Security: Writing to this related field requires write access to the
  underlying partner record. If the current user can edit the User but
  not the partner, the write will fail (expected behavior).
- Consistency: Since it’s a related field, Odoo keeps it in sync both
  ways (read reflects partner; write on user updates the partner).
- Performance: `store=True` means it’s recomputed only when `partner_id`
  or the partner’s `x_detail_member_num` changes; also makes it searchable.
"""

from __future__ import annotations

from odoo import fields, models


class ResUsers(models.Model):
    """Extend Users with a mirrored Elks member number field."""
    _inherit = "res.users"

    x_detail_member_num = fields.Char(
        string="Member Number",
        help=(
            "Elks Member Number mirrored from the linked contact (partner). "
            "Edits here will update the contact’s member number."
        ),
        related="partner_id.x_detail_member_num",
        store=True,          # keep a copy on users for searching/grouping
        readonly=False,      # allow editing from the User form (writes-through)
        index=True,          # optional but handy for searches on users
    )
