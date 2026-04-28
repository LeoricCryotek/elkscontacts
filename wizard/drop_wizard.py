# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


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
    )

    # -- Quick-check reasons --
    reason_nonpayment = fields.Boolean('Non-Payment of Dues')
    reason_resigned = fields.Boolean('Resigned')
    reason_expelled = fields.Boolean('Expelled')
    reason_deceased = fields.Boolean('Deceased')
    reason_other = fields.Boolean('Other')

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

        # Store reason on the partner
        self.partner_id.write({
            'x_drop_reason': reason_key,
            'x_drop_date': self.drop_date,
            'x_drop_notes': self.drop_notes or reason_str,
        })

        # Post to chatter
        note_line = f"Notes: {self.drop_notes}" if self.drop_notes else ""
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
                'event_type': 'dropped',
                'event_date': self.drop_date,
                'comment_1': reason_str,
                'comment_2': self.drop_notes or False,
                'source': 'manual',
            })

        # Now actually archive (skip our override to avoid recursion)
        super(type(self.partner_id), self.partner_id).action_archive()

        return {'type': 'ir.actions.act_window_close'}
