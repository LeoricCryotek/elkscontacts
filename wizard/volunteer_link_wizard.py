# -*- coding: utf-8 -*-
"""Wizard: link a volunteer contact to an existing employee, or create one.

Triggered when a contact is flagged as a volunteer but is not yet linked to
an ``hr.employee`` record.  The wizard searches the employee directory for
likely matches (by email, name similarity, or work_contact_id) and presents
them to the user.  The user then picks an existing employee to link, or
chooses to create a new one.
"""
import logging
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _norm(s):
    """Lowercase, strip, collapse whitespace."""
    if not s:
        return ''
    return re.sub(r'\s+', ' ', str(s).strip().lower())


class ElksVolunteerLinkWizard(models.TransientModel):
    _name = 'elks.volunteer.link.wizard'
    _description = 'Link Volunteer to Existing Employee'

    partner_id = fields.Many2one(
        'res.partner', string='Volunteer Contact', required=True,
    )

    # Candidate matches found by the search
    candidate_line_ids = fields.One2many(
        'elks.volunteer.link.wizard.line', 'wizard_id',
        string='Possible Matches',
    )

    # The user picks one of the candidates (or none)
    selected_employee_id = fields.Many2one(
        'hr.employee', string='Link to Existing Employee',
        help='Pick the employee record that corresponds to this volunteer. '
             'Leave empty to create a new employee record instead.',
    )

    create_new = fields.Boolean(
        'Create a New Employee Record', default=False,
        help='Check this to create a brand-new employee record for this volunteer '
             'instead of linking to an existing one.',
    )
    force_relink = fields.Boolean(
        'Force Relink (override existing contact link)', default=False,
        help='Check if the selected employee is already linked to a '
             'different contact and you want to reassign them here.',
    )

    # Info for the form
    candidate_count = fields.Integer(
        'Candidates Found', compute='_compute_candidate_count',
    )
    contact_email = fields.Char(related='partner_id.email', readonly=True)
    contact_phone = fields.Char(related='partner_id.phone', readonly=True)

    @api.depends('candidate_line_ids')
    def _compute_candidate_count(self):
        for wiz in self:
            wiz.candidate_count = len(wiz.candidate_line_ids)

    @api.onchange('candidate_line_ids')
    def _onchange_candidate_selection(self):
        """Sync is_selected toggle → selected_employee_id (no save needed)."""
        selected = self.candidate_line_ids.filtered('is_selected')
        if selected:
            # Keep only the most recently toggled one
            if len(selected) > 1:
                for line in selected[:-1]:
                    line.is_selected = False
                selected = selected[-1:]
            self.selected_employee_id = selected.employee_id
            self.create_new = False
        elif not self.create_new:
            self.selected_employee_id = False

    # ------------------------------------------------------------------
    # Default get: populate candidates on wizard open
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        partner_id = self.env.context.get('default_partner_id')
        if partner_id:
            partner = self.env['res.partner'].browse(partner_id)
            candidates = self._find_candidates(partner)
            vals['candidate_line_ids'] = [
                (0, 0, {
                    'employee_id': c['employee'].id,
                    'match_reason': c['reason'],
                    'confidence': c['confidence'],
                })
                for c in candidates
            ]
            # If there's a single high-confidence match, pre-select it
            if candidates and candidates[0]['confidence'] == 'high':
                vals['selected_employee_id'] = candidates[0]['employee'].id
            elif not candidates:
                vals['create_new'] = True
        return vals

    # ------------------------------------------------------------------
    # Candidate search
    # ------------------------------------------------------------------
    @api.model
    def _find_candidates(self, partner):
        """Return a list of {employee, reason, confidence} dicts.

        Confidence levels:
          high    — unambiguous (email exact match, or work_contact_id link)
          medium  — full first + last name match
          low     — partial match (last name only, or similar name)
        """
        Employee = self.env['hr.employee'].sudo()
        all_emps = Employee.with_context(active_test=False).search([])

        email_norm = _norm(partner.email)
        first = _norm(partner.x_detail_first_name or '')
        last = _norm(partner.x_detail_last_name or '')
        if not first and not last:
            # Try to split the display name
            parts = _norm(partner.name).split(' ')
            if len(parts) >= 2:
                first, last = parts[0], parts[-1]
            elif parts:
                last = parts[0]

        seen = set()
        candidates = []

        def add(emp, reason, confidence):
            if emp.id in seen:
                return
            seen.add(emp.id)
            candidates.append({
                'employee': emp,
                'reason': reason,
                'confidence': confidence,
            })

        # 1. Already linked via work_contact_id (high)
        for emp in all_emps.filtered(lambda e: e.work_contact_id.id == partner.id):
            add(emp, _('Already linked to this contact'), 'high')

        # 2. Exact work_email match (high)
        if email_norm:
            for emp in all_emps:
                if _norm(emp.work_email) == email_norm or _norm(emp.private_email) == email_norm:
                    add(emp, _('Work email matches'), 'high')

        # 3. Exact first + last name match (medium)
        if first and last:
            for emp in all_emps:
                en = _norm(emp.name)
                if first in en and last in en:
                    add(emp, _('Name matches (%s %s)') % (first.title(), last.title()), 'medium')

        # 4. Last name match only (low)
        if last:
            for emp in all_emps:
                en = _norm(emp.name)
                if last in en:
                    add(emp, _('Last name matches (%s)') % last.title(), 'low')

        # Sort: high → medium → low
        order = {'high': 0, 'medium': 1, 'low': 2}
        candidates.sort(key=lambda c: order.get(c['confidence'], 99))
        return candidates

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_link_or_create(self):
        """Either link to the selected employee or create a new one."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('No contact specified.'))

        Employee = self.env['hr.employee'].sudo()
        partner = self.partner_id

        if self.selected_employee_id and not self.create_new:
            emp = self.selected_employee_id

            # Guard: if this employee is already linked to a DIFFERENT
            # partner, refuse unless the user really means to reassign.
            if emp.work_contact_id and emp.work_contact_id != partner:
                if not self.force_relink:
                    raise UserError(_(
                        "Employee \"%(emp)s\" is already linked to a "
                        "different contact: %(other)s.  Click this button "
                        "again with 'Force Relink' checked if you really "
                        "mean to move this employee to %(partner)s."
                    ) % {
                        'emp': emp.name,
                        'other': emp.work_contact_id.name,
                        'partner': partner.name,
                    })

                # If forcing relink, clear the old back-link
                if emp.work_contact_id.x_volunteer_employee_id == emp:
                    emp.work_contact_id.sudo().write({
                        'x_volunteer_employee_id': False,
                    })
                    emp.work_contact_id.message_post(
                        body=(
                            f"<strong>Employee Reassigned</strong><br/>"
                            f"Employee {emp.name} is now linked to "
                            f"{partner.name} instead."
                        ),
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )

            dept = partner._get_or_create_volunteer_department()
            emp.write({
                'active': True,
                'x_is_volunteer': True,
                'department_id': dept.id,
                'work_contact_id': partner.id,
            })
            partner.write({'x_volunteer_employee_id': emp.id})

            partner.message_post(
                body=_(
                    '<strong>Linked to Existing Employee</strong><br/>'
                    'Employee: %(name)s (ID %(eid)s)<br/>'
                    'Department: %(dept)s'
                ) % {
                    'name': emp.name, 'eid': emp.id, 'dept': dept.name,
                },
                message_type='comment', subtype_xmlid='mail.mt_note',
            )
            emp.message_post(
                body=_(
                    '<strong>Linked to Volunteer Contact</strong><br/>'
                    'Contact: %(name)s (#%(num)s)'
                ) % {
                    'name': partner.name,
                    'num': partner.x_detail_member_num or 'N/A',
                },
                message_type='comment', subtype_xmlid='mail.mt_note',
            )

            _logger.info(
                'Linked partner %s to existing employee %s via wizard',
                partner.id, emp.id,
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Linked'),
                    'message': _('Volunteer %(name)s linked to employee %(emp)s.') % {
                        'name': partner.name, 'emp': emp.name,
                    },
                    'type': 'success',
                    'next': {'type': 'ir.actions.act_window_close'},
                },
            }

        # Otherwise create a new employee
        dept = partner._get_or_create_volunteer_department()
        emp_vals = {
            'name': partner.name or 'Volunteer',
            'work_phone': partner.phone or False,
            'work_email': partner.email or False,
            'department_id': dept.id,
            'job_title': 'Volunteer',
            'work_contact_id': partner.id,
            'x_is_volunteer': True,
        }
        # Auto-set PIN from the last 4 digits of the contact's phone
        auto_pin = partner._extract_pin_from_phone()
        if auto_pin:
            emp_vals['pin'] = auto_pin
        emp = Employee.create(emp_vals)
        partner.write({'x_volunteer_employee_id': emp.id})

        partner.message_post(
            body=_(
                '<strong>New Employee Record Created</strong><br/>'
                'Employee: %(name)s (ID %(eid)s)<br/>'
                'Department: %(dept)s<br/>'
                'Kiosk PIN: %(pin)s'
            ) % {
                'name': emp.name, 'eid': emp.id, 'dept': dept.name,
                'pin': 'Auto-set from phone' if auto_pin else 'Not set — no phone on file',
            },
            message_type='comment', subtype_xmlid='mail.mt_note',
        )

        _logger.info(
            'Created new employee %s for volunteer partner %s via wizard',
            emp.id, partner.id,
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Employee Created'),
                'message': _('New employee record created for %(name)s.') % {
                    'name': partner.name,
                },
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class ElksVolunteerLinkWizardLine(models.TransientModel):
    _name = 'elks.volunteer.link.wizard.line'
    _description = 'Volunteer Link Wizard - Candidate Employee'
    _order = 'confidence, id'

    wizard_id = fields.Many2one(
        'elks.volunteer.link.wizard', ondelete='cascade', required=True,
    )
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    employee_email = fields.Char(related='employee_id.work_email', readonly=True)
    employee_department = fields.Char(related='employee_id.department_id.name', readonly=True)
    employee_active = fields.Boolean(related='employee_id.active', readonly=True)
    match_reason = fields.Char('Why Matched', readonly=True)
    confidence = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ], string='Confidence', readonly=True)
    is_selected = fields.Boolean('Selected', default=False)
