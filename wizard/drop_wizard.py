# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class ElksDropWizard(models.TransientModel):
    _name = 'elks.drop.wizard'
    _description = 'Drop Member Wizard'

    partner_id = fields.Many2one(
        'res.partner', string='Member', required=True,
    )
    partner_member_num = fields.Char(
        related='partner_id.x_detail_member_num',
        string='Member #', readonly=True,
    )
    drop_date = fields.Date(
        'Date Dropped', required=True,
        default=fields.Date.context_today,
        help="For a death, this should be the date of death.",
    )

    # -- Quick-check reasons --
    reason_nonpayment = fields.Boolean('Non-Payment of Dues')
    reason_resigned = fields.Boolean('Resigned')
    reason_expelled = fields.Boolean('Expelled')
    reason_deceased = fields.Boolean('Deceased')
    reason_other = fields.Boolean('Other')

    # Helper for the view: hide non-death reasons when this wizard was
    # opened from the "Death of Member" smart button (which pre-checks
    # reason_deceased via default context).
    is_death_flow = fields.Boolean(
        compute='_compute_is_death_flow',
        help="True when this wizard was opened specifically to record a "
             "death (other reasons are then hidden in the form).",
    )

    @api.depends('reason_deceased', 'reason_nonpayment', 'reason_resigned',
                 'reason_expelled', 'reason_other')
    def _compute_is_death_flow(self):
        for rec in self:
            rec.is_death_flow = (
                rec.reason_deceased
                and not rec.reason_nonpayment
                and not rec.reason_resigned
                and not rec.reason_expelled
                and not rec.reason_other
            )

    drop_notes = fields.Text(
        'Additional Notes',
        help='Enter any additional details about why the member is being dropped.',
    )

    @api.onchange('reason_nonpayment', 'reason_resigned', 'reason_expelled',
                   'reason_deceased', 'reason_other')
    def _onchange_reasons(self):
        """Auto-populate drop_notes summary from checked reasons."""
        parts = []
        if self.reason_nonpayment:
            parts.append('Non-Payment of Dues')
        if self.reason_resigned:
            parts.append('Resigned')
        if self.reason_expelled:
            parts.append('Expelled')
        if self.reason_deceased:
            parts.append('Deceased')
        if self.reason_other:
            parts.append('Other')
        # Only auto-set if user hasn't typed custom notes
        if parts and not self.drop_notes:
            self.drop_notes = '; '.join(parts)

    def _get_drop_reason_key(self):
        """Return the selection key that best matches the checked reasons."""
        checked = []
        if self.reason_nonpayment:
            checked.append('nonpayment')
        if self.reason_resigned:
            checked.append('resigned')
        if self.reason_expelled:
            checked.append('expelled')
        if self.reason_deceased:
            checked.append('deceased')
        if self.reason_other:
            checked.append('other')
        if not checked:
            return 'other'
        # If exactly one is checked, use it; otherwise 'other'
        return checked[0] if len(checked) == 1 else 'other'

    def action_confirm_drop(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('No member selected.'))

        reason_key = self._get_drop_reason_key()

        # Build the reason display string
        reasons = []
        if self.reason_nonpayment:
            reasons.append('Non-Payment of Dues')
        if self.reason_resigned:
            reasons.append('Resigned')
        if self.reason_expelled:
            reasons.append('Expelled')
        if self.reason_deceased:
            reasons.append('Deceased')
        if self.reason_other:
            reasons.append('Other')

        if not reasons and not self.drop_notes:
            raise UserError(_('Please select at least one reason or enter notes.'))

        reason_str = ', '.join(reasons) if reasons else 'See notes'

        is_death = (reason_key == 'deceased')

        # Store reason on the partner. For a death we also seed the
        # death-CLMS fields so the Secretary's queue shows the record
        # immediately.
        partner_vals = {
            'x_drop_reason': reason_key,
            'x_drop_date': self.drop_date,
            'x_drop_notes': self.drop_notes or reason_str,
        }
        if is_death:
            partner_vals.update({
                'x_date_of_death': self.drop_date,
                'x_death_clms_status': 'pending',
            })
        self.partner_id.write(partner_vals)

        # Post to chatter - different headline for a death vs. a drop.
        note_line = f"Notes: {self.drop_notes}" if self.drop_notes else ""
        if is_death:
            self.partner_id.message_post(
                body=_(
                    "<b>Death of Member recorded</b> by %(user)s<br/>"
                    "Date of death: %(date)s<br/>"
                    "%(notes)s<br/>"
                    "<i>CLMS Status: Pending CLMS Entry. The Secretary "
                    "will mark the death read on the lodge floor and "
                    "push the entry into CLMS at Grand Lodge. The "
                    "contact stays active until then so it remains "
                    "searchable for the floor reading.</i>",
                    user=self.env.user.name,
                    date=self.drop_date,
                    notes=note_line,
                ),
                subtype_xmlid='mail.mt_note',
            )

            # Schedule a CLMS to-do for the Secretary.  Assigned to a
            # user in the Lodge Secretary group when one is available,
            # otherwise to the current user.  Deadline: 7 days out so
            # the Secretary has room for the floor-reading meeting and
            # then the CLMS push.
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
                    # In Odoo 19 res.groups no longer exposes a `users`
                    # relation; invert the lookup by searching res.users
                    # whose group_ids include this group.
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
                        "CLMS: Process death of %s",
                    ) % (self.partner_id.name or 'member'),
                    note=_(
                        "<p>Two-step CLMS workflow for this deceased "
                        "member:</p>"
                        "<ol>"
                        "<li>Read the death announcement on the lodge "
                        "floor at the next regular session, then click "
                        "<b>Mark Read on Floor</b> on the contact.</li>"
                        "<li>Push the death entry into CLMS at Grand "
                        "Lodge, then click <b>Mark Death Processed in "
                        "CLMS</b> on the contact to archive the "
                        "record.</li>"
                        "</ol>"
                        "<p>The contact stays active and searchable "
                        "until step 2 is complete.</p>"
                    ),
                )
        else:
            self.partner_id.message_post(
                body=_(
                    "<b>Member Dropped</b> by %(user)s<br/>"
                    "Date: %(date)s<br/>"
                    "Reason: %(reason)s<br/>"
                    "%(notes)s",
                    user=self.env.user.name,
                    date=self.drop_date,
                    reason=reason_str,
                    notes=note_line,
                ),
                subtype_xmlid='mail.mt_note',
            )

        # Log to member history if the model exists
        if hasattr(self.env, 'registry') and 'elks.member.history' in self.env:
            self.env['elks.member.history'].create({
                'partner_id': self.partner_id.id,
                'event_type': 'deceased' if is_death else 'dropped',
                'event_date': self.drop_date,
                'comment_1': reason_str,
                'comment_2': self.drop_notes or False,
                'source': 'manual',
            })

        # Archive the contact - EXCEPT for a death. The deceased flow
        # defers archiving until the Secretary clicks "Mark Death
        # Processed in CLMS" so the record stays searchable through
        # the floor reading and CLMS push.
        if not is_death:
            super(type(self.partner_id), self.partner_id).action_archive()

        return {'type': 'ir.actions.act_window_close'}
