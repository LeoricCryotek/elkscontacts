# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ElksEmployeeMergeWizard(models.TransientModel):
    """Merge duplicate HR employee records for a contact.

    When a contact is marked as a volunteer a new ``hr.employee`` may be
    created even though one already existed (e.g. the contact was already
    an employee via another workflow).  This wizard lets the user pick
    which employee record to keep and consolidates volunteer training,
    skills, and resume lines from the duplicate into it.
    """
    _name = 'elks.employee.merge.wizard'
    _description = 'Merge Duplicate Employee Records'

    # ---- fields ----
    partner_id = fields.Many2one(
        'res.partner', string='Contact', required=True,
        help='The contact whose duplicate employee records will be merged.',
    )
    duplicate_employee_ids = fields.Many2many(
        'hr.employee', string='Duplicate Employees',
        compute='_compute_duplicate_employees',
        help='All employee records linked to this contact.',
    )
    duplicate_count = fields.Integer(
        string='Duplicates Found',
        compute='_compute_duplicate_employees',
    )
    keep_employee_id = fields.Many2one(
        'hr.employee', string='Employee to Keep', required=True,
        domain="[('id', 'in', duplicate_employee_ids)]",
        help='Select the employee record you want to keep.  '
             'All training, skills, and resume data from the other records '
             'will be moved into this one, and the duplicates will be archived.',
    )
    archive_duplicates = fields.Boolean(
        string='Archive Duplicates', default=True,
        help='When checked, duplicate employee records will be archived '
             'after merging.  Uncheck to permanently delete them instead.',
    )

    # ---- computed ----
    @api.depends('partner_id')
    def _compute_duplicate_employees(self):
        Employee = self.env['hr.employee'].sudo()
        for wiz in self:
            if wiz.partner_id:
                emps = Employee.with_context(active_test=False).search([
                    ('work_contact_id', '=', wiz.partner_id.id),
                ])
                wiz.duplicate_employee_ids = emps
                wiz.duplicate_count = len(emps)
            else:
                wiz.duplicate_employee_ids = Employee
                wiz.duplicate_count = 0

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Auto-select the oldest (lowest-ID) employee as the one to keep."""
        if self.duplicate_employee_ids:
            self.keep_employee_id = self.duplicate_employee_ids.sorted('id')[0]
        else:
            self.keep_employee_id = False

    # ---- action ----
    def action_merge(self):
        """Merge all duplicate employee records into the selected one."""
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Please select a contact first.'))
        if not self.keep_employee_id:
            raise UserError(_('Please select the employee record to keep.'))

        keep = self.keep_employee_id
        dupes = self.duplicate_employee_ids - keep

        if not dupes:
            raise UserError(_(
                'No duplicate employee records found for %s.  Nothing to merge.',
                self.partner_id.name,
            ))

        merged_training = 0
        merged_skills = 0
        merged_resume = 0

        for dupe in dupes:
            # -- Move volunteer training records --
            trainings = self.env['elks.volunteer.training'].sudo().search([
                ('employee_id', '=', dupe.id),
            ])
            for t in trainings:
                # Only move if the keep employee doesn't already have
                # a training record for the same area
                existing = self.env['elks.volunteer.training'].sudo().search([
                    ('employee_id', '=', keep.id),
                    ('training_area', '=', t.training_area),
                ], limit=1)
                if existing:
                    # Keep whichever has the more recent training date
                    if t.date_trained and (
                        not existing.date_trained
                        or t.date_trained > existing.date_trained
                    ):
                        existing.write({
                            'date_trained': t.date_trained,
                            'expiration_date': t.expiration_date,
                            'is_trained': t.is_trained,
                        })
                    t.sudo().unlink()
                else:
                    t.write({'employee_id': keep.id})
                merged_training += 1

            # -- Move employee skills (hr.employee.skill) --
            if hasattr(dupe, 'employee_skill_ids'):
                for skill in dupe.employee_skill_ids:
                    existing_skill = self.env['hr.employee.skill'].sudo().search([
                        ('employee_id', '=', keep.id),
                        ('skill_id', '=', skill.skill_id.id),
                    ], limit=1)
                    if not existing_skill:
                        skill.write({'employee_id': keep.id})
                        merged_skills += 1
                    else:
                        skill.sudo().unlink()

            # -- Move resume lines (hr.resume.line) --
            if hasattr(dupe, 'resume_line_ids'):
                for line in dupe.resume_line_ids:
                    line.write({'employee_id': keep.id})
                    merged_resume += 1

            # -- Archive or delete the duplicate --
            if self.archive_duplicates:
                dupe.write({'active': False})
                _logger.info(
                    'Archived duplicate employee %s (id=%s) after merge into %s',
                    dupe.name, dupe.id, keep.id,
                )
            else:
                _logger.info(
                    'Deleted duplicate employee %s (id=%s) after merge into %s',
                    dupe.name, dupe.id, keep.id,
                )
                dupe.sudo().unlink()

        # Ensure the kept employee has volunteer flag set if the contact is one
        vals = {'x_is_volunteer': self.partner_id.x_is_volunteer}
        if self.partner_id.x_is_volunteer:
            dept = self.partner_id._get_or_create_volunteer_department()
            vals['department_id'] = dept.id
        keep.write(vals)

        # Point the contact's volunteer link to the kept employee
        self.partner_id.write({'x_volunteer_employee_id': keep.id})

        _logger.info(
            'Merged employees for partner %s: kept=%s, '
            'training=%d, skills=%d, resume=%d',
            self.partner_id.id, keep.id,
            merged_training, merged_skills, merged_resume,
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Employee Records Merged'),
                'message': _(
                    'Kept employee "%(name)s" (ID %(id)s).  '
                    'Moved %(t)d training, %(s)d skill, and %(r)d resume '
                    'records from %(d)d duplicate(s).',
                    name=keep.name,
                    id=keep.id,
                    t=merged_training,
                    s=merged_skills,
                    r=merged_resume,
                    d=len(dupes),
                ),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
