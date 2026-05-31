# -*- coding: utf-8 -*-
"""Helper models for the CLMS-mirroring tabs on the partner form.

Four small models cover the CLMS Flags, Remarks, Custom Fields, and
Auxiliaries tabs.  Each is intentionally minimal — they exist to
structure data the CLMS UI surfaces; richer behaviour can be layered
on later without breaking the existing schema.
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


# ════════════════════════════════════════════════════════════════════
#  CLMS Flags  — Reminder Flags tab
# ════════════════════════════════════════════════════════════════════
class ElksMemberFlag(models.Model):
    _name = "elks.member.flag"
    _description = "Member Reminder Flag (CLMS Flags tab)"
    _order = "flag_date desc, id desc"

    partner_id = fields.Many2one(
        'res.partner', string="Member", required=True,
        ondelete='cascade', index=True,
    )
    flag_type = fields.Selection(
        [('reminder', 'Reminder'),
         ('hold', 'Hold'),
         ('warning', 'Warning'),
         ('info', 'Information'),
         ('other', 'Other')],
        string="Flag Type", required=True, default='reminder',
    )
    flag_date = fields.Date(
        "Date", required=True, default=fields.Date.context_today,
    )
    flag_text = fields.Text("Reminder Flag Text")
    action_text = fields.Char(
        "Action",
        help="What needs to be done about this flag.",
    )
    active = fields.Boolean(default=True)


# ════════════════════════════════════════════════════════════════════
#  CLMS Remarks  — Remarks tab
# ════════════════════════════════════════════════════════════════════
class ElksMemberRemark(models.Model):
    _name = "elks.member.remark"
    _description = "Member Remark (CLMS Remarks tab)"
    _order = "remark_date desc, id desc"

    partner_id = fields.Many2one(
        'res.partner', string="Member", required=True,
        ondelete='cascade', index=True,
    )
    remark_date = fields.Date(
        "Date", required=True, default=fields.Date.context_today,
    )
    author_id = fields.Many2one(
        'res.users', string="Author",
        default=lambda self: self.env.user,
    )
    remark_text = fields.Text("Remark", required=True)


# ════════════════════════════════════════════════════════════════════
#  CLMS Custom Fields  — Custom tab
# ════════════════════════════════════════════════════════════════════
class ElksMemberCustomField(models.Model):
    _name = "elks.member.custom_field"
    _description = "Member Custom Field (CLMS Custom tab)"
    _order = "field_name, id"

    partner_id = fields.Many2one(
        'res.partner', string="Member", required=True,
        ondelete='cascade', index=True,
    )
    field_name = fields.Char(
        "Field Name", required=True,
        help="The custom field label (e.g. 'esanman' in CLMS).",
    )
    field_value = fields.Char("Value")
    notes = fields.Text("Notes")


# ════════════════════════════════════════════════════════════════════
#  CLMS Auxiliaries  — Auxiliaries tab
# ════════════════════════════════════════════════════════════════════
class ElksAuxiliary(models.Model):
    _name = "elks.auxiliary"
    _description = "Lodge Auxiliary (e.g. Emblem Club)"
    _order = "name"

    name = fields.Char("Auxiliary Name", required=True)
    code = fields.Char("Code", help="Short code (e.g. 'EC' for Emblem Club).")
    description = fields.Text("Description")
    active = fields.Boolean(default=True)


class ElksAuxiliaryMembership(models.Model):
    _name = "elks.auxiliary.membership"
    _description = "Member's Auxiliary Membership"
    _order = "date_joined desc, id desc"

    partner_id = fields.Many2one(
        'res.partner', string="Member", required=True,
        ondelete='cascade', index=True,
    )
    auxiliary_id = fields.Many2one(
        'elks.auxiliary', string="Auxiliary", required=True,
        ondelete='restrict',
    )
    date_joined = fields.Date(
        "Date Joined", default=fields.Date.context_today,
    )
    date_left = fields.Date("Date Left")
    role = fields.Char(
        "Role / Office",
        help="The member's role within the auxiliary (e.g. President).",
    )
    active = fields.Boolean(default=True)

    @api.constrains('partner_id', 'auxiliary_id', 'active')
    def _check_one_active_per_aux(self):
        for rec in self:
            if not rec.active:
                continue
            existing = self.search([
                ('partner_id', '=', rec.partner_id.id),
                ('auxiliary_id', '=', rec.auxiliary_id.id),
                ('active', '=', True),
                ('id', '!=', rec.id),
            ])
            if existing:
                raise ValidationError(_(
                    "%(member)s already has an active membership in "
                    "%(aux)s. Archive the previous record before adding "
                    "a new one.",
                    member=rec.partner_id.display_name,
                    aux=rec.auxiliary_id.name,
                ))


# ════════════════════════════════════════════════════════════════════
#  Extend res.partner with the One2many relations into the new models
# ════════════════════════════════════════════════════════════════════
class ResPartnerClmsTabs(models.Model):
    _inherit = "res.partner"

    x_reminder_flag_ids = fields.One2many(
        'elks.member.flag', 'partner_id', string="Reminder Flags",
    )
    x_remark_ids = fields.One2many(
        'elks.member.remark', 'partner_id', string="Remarks",
    )
    x_custom_field_ids = fields.One2many(
        'elks.member.custom_field', 'partner_id', string="Custom Fields",
    )
    x_auxiliary_membership_ids = fields.One2many(
        'elks.auxiliary.membership', 'partner_id',
        string="Auxiliary Memberships",
    )
