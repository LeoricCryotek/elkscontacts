# -*- coding: utf-8 -*-
"""Grant Transfer Dimit wizard.

Mirrors the CLMS "Grant Transfer Dimit" screen so the Secretary can
record an outgoing dimit — the member is transferring FROM this lodge
(0896) TO another lodge, or is signing the petition to charter a
brand-new lodge.

Confirming the wizard:
  * writes x_transfer_out_* fields on the contact,
  * flips x_drop_reason='transfer_out' and x_drop_date=transfer date,
  * posts a chatter note describing the destination,
  * schedules a mail.activity to-do for the Secretary to record the
    dimit in CLMS at Grand Lodge,
  * appends an elks.member.history row (event_type='dropped',
    comment_1 identifies the destination lodge),
  * archives the contact.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class ElksTransferDimitWizard(models.TransientModel):
    _name = 'elks.transfer.dimit.wizard'
    _description = 'Grant Transfer Dimit Wizard'

    partner_id = fields.Many2one(
        'res.partner', string='Member', required=True,
    )
    partner_member_num = fields.Char(
        related='partner_id.x_detail_member_num',
        string='Membership Number', readonly=True,
    )
    from_lodge_num = fields.Char(
        "From Lodge #",
        compute='_compute_from_lodge_num',
        readonly=True,
        help="Our lodge number. Pulled from Lodge Settings.",
    )
    transfer_date = fields.Date(
        "Granted Transfer Dimit",
        required=True,
        default=fields.Date.context_today,
        help="Date the dimit is granted (mm/dd/yyyy in CLMS).",
    )
    to_lodge_num = fields.Char(
        "Dimiting TO Lodge #",
        size=4,
        help="4-digit BPOE number of the destination lodge. "
             "Leave blank ONLY if the member is signing a petition to "
             "charter a brand-new lodge.",
    )
    is_new_lodge = fields.Boolean(
        "Signing Petition to Join a Brand-New Lodge",
        help="Check when there is no destination lodge number because "
             "the member is signing the petition to charter a new lodge.",
    )
    comment = fields.Char(
        "Comment",
        help="Optional free-text comment. Mirrors CLMS 'Comment2'.",
    )

    @api.depends('partner_id')
    def _compute_from_lodge_num(self):
        """Pull our lodge number from elks.lodge.settings (fallback: 0896)."""
        settings = self.env['elks.lodge.settings'].sudo().search([], limit=1)
        lodge_num = (settings.lodge_number or '0896') if settings else '0896'
        # Zero-pad to 4 digits to match CLMS display style
        lodge_num = str(lodge_num).zfill(4) if lodge_num else '0896'
        for rec in self:
            rec.from_lodge_num = lodge_num

    @api.onchange('is_new_lodge')
    def _onchange_is_new_lodge(self):
        """When switching to 'new lodge', clear the destination number
        so the two branches can't have stale data at the same time."""
        if self.is_new_lodge:
            self.to_lodge_num = False

    @api.onchange('to_lodge_num')
    def _onchange_to_lodge_num(self):
        """If the user typed a destination number, they're not petitioning
        for a new lodge — flip the flag off automatically."""
        if self.to_lodge_num:
            self.is_new_lodge = False

    def _validate(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("No member selected."))
        if not self.transfer_date:
            raise UserError(_("Please enter the Granted Transfer Dimit date."))
        if not self.is_new_lodge and not (self.to_lodge_num or '').strip():
            raise UserError(_(
                "Enter the destination lodge's 4-digit BPOE number, "
                "or check 'Signing Petition to Join a Brand-New Lodge' "
                "if there is no destination lodge number yet."
            ))
        if self.to_lodge_num:
            digits = self.to_lodge_num.strip()
            if not digits.isdigit() or len(digits) > 4:
                raise UserError(_(
                    "Dimiting TO Lodge # must be up to 4 numeric digits."
                ))

    def action_confirm_transfer(self):
        self.ensure_one()
        self._validate()

        # Zero-pad the destination lodge to 4 digits for consistency
        # with CLMS display.
        dest_num = False
        if self.to_lodge_num:
            dest_num = self.to_lodge_num.strip().zfill(4)

        dest_display = (
            _("brand-new lodge (petition)") if self.is_new_lodge
            else _("Lodge #%s") % dest_num
        )

        # 1. Persist the transfer fields + drop stamp on the contact.
        partner_vals = {
            'x_transfer_out_date': self.transfer_date,
            'x_transfer_out_to_lodge_num': dest_num or False,
            'x_transfer_out_new_lodge': self.is_new_lodge,
            'x_transfer_out_comment': self.comment or False,
            'x_drop_reason': 'transfer_out',
            'x_drop_date': self.transfer_date,
            'x_drop_notes': _(
                "Transfer Dimit granted to %(dest)s on %(date)s."
                "%(comment)s"
            ) % {
                'dest': dest_display,
                'date': self.transfer_date,
                'comment': (
                    _(" Comment: %s") % self.comment
                ) if self.comment else '',
            },
        }
        self.partner_id.write(partner_vals)

        # 2. Chatter note on the contact.
        self.partner_id.message_post(
            body=_(
                "<b>Transfer Dimit granted</b> by %(user)s<br/>"
                "Date: %(date)s<br/>"
                "From Lodge #%(src)s → %(dest)s<br/>"
                "Member #: %(memnum)s"
                "%(comment_html)s"
            ) % {
                'user': self.env.user.name,
                'date': self.transfer_date,
                'src': self.from_lodge_num or '0896',
                'dest': dest_display,
                'memnum': self.partner_member_num or '—',
                'comment_html': (
                    "<br/>Comment: %s" % self.comment
                ) if self.comment else '',
            },
            subtype_xmlid='mail.mt_note',
        )

        # 3. Schedule a Secretary CLMS to-do (mirrors the drop / death
        #    workflow so the transfer shows up in the CLMS work queue).
        todo_type = self.env.ref(
            'mail.mail_activity_data_todo', raise_if_not_found=False,
        )
        if todo_type:
            secretary_group = self.env.ref(
                'elkscontacts.group_elks_secretary',
                raise_if_not_found=False,
            )
            assignee = self.env.user
            if secretary_group:
                secretary_users = self.env['res.users'].search(
                    [('group_ids', 'in', secretary_group.id)],
                    limit=1,
                )
                if secretary_users:
                    assignee = secretary_users
            deadline = fields.Date.context_today(self) + \
                relativedelta(days=7)
            self.partner_id.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=deadline,
                user_id=assignee.id,
                summary=_(
                    "CLMS: Grant Transfer Dimit for %s",
                ) % (self.partner_id.name or 'member'),
                note=_(
                    "<p>Log this outgoing Transfer Dimit into CLMS at "
                    "Grand Lodge using <b>Grant Transfer Dimit</b>:</p>"
                    "<ul>"
                    "<li><b>GrantedTransferDimit:</b> %(date)s</li>"
                    "<li><b>Lodge Number:</b> %(src)s</li>"
                    "<li><b>Membership Number:</b> %(memnum)s</li>"
                    "<li><b>Comment2:</b> %(comment)s</li>"
                    "<li><b>Dimiting TO Lodge:</b> %(dest)s</li>"
                    "</ul>"
                    "<p>The Odoo contact has already been archived with "
                    "drop reason <i>Transferred Out (Dimit Granted)</i>."
                    "</p>"
                ) % {
                    'date': self.transfer_date,
                    'src': self.from_lodge_num or '0896',
                    'memnum': self.partner_member_num or '—',
                    'comment': self.comment or '—',
                    'dest': (
                        _("(new lodge petition)") if self.is_new_lodge
                        else (dest_num or '—')
                    ),
                },
            )

        # 4. Member history row so the transfer appears on the
        #    contact's History tab.
        if 'elks.member.history' in self.env:
            self.env['elks.member.history'].create({
                'partner_id': self.partner_id.id,
                'event_type': 'dropped',
                'event_date': self.transfer_date,
                'lodge_num_1': self.from_lodge_num or '0896',
                'number_1': self.partner_member_num or '',
                'lodge_num_2': dest_num or '',
                'comment_1': _(
                    "Transfer Dimit granted → %s"
                ) % dest_display,
                'comment_2': self.comment or False,
                'source': 'manual',
            })

        # 5. Archive the contact. Same super() trick as drop wizard to
        #    bypass any overridden action_archive on res.partner.
        super(type(self.partner_id), self.partner_id).action_archive()

        return {'type': 'ir.actions.act_window_close'}
