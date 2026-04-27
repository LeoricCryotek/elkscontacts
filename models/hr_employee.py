# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    x_is_volunteer = fields.Boolean(
        string='Is Volunteer',
        help='Automatically set when the linked contact is marked as a volunteer.',
    )

    x_volunteer_training_ids = fields.One2many(
        'elks.volunteer.training', 'employee_id',
        string='Volunteer Training',
    )
    x_training_complete = fields.Boolean(
        string='All Training Complete',
        compute='_compute_training_complete',
        store=True,
        help='True when every assigned training record is marked as trained '
             'and none have expired.',
    )

    @api.depends(
        'x_volunteer_training_ids',
        'x_volunteer_training_ids.is_trained',
        'x_volunteer_training_ids.is_expired',
    )
    def _compute_training_complete(self):
        for rec in self:
            trainings = rec.x_volunteer_training_ids
            if not trainings:
                rec.x_training_complete = False
            else:
                rec.x_training_complete = (
                    all(t.is_trained for t in trainings)
                    and not any(t.is_expired for t in trainings)
                )

    # -----------------------------------------------------------------
    # Bidirectional link: when work_contact_id is set to an Elks member
    # contact, flag that contact as a volunteer and link back.
    # -----------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        emps = super().create(vals_list)
        for emp in emps:
            emp._sync_contact_volunteer_flag()
        return emps

    def write(self, vals):
        # Capture the old contact link so we can untangle if it changed
        old_contacts = {e.id: e.work_contact_id for e in self}
        res = super().write(vals)
        if 'work_contact_id' in vals or 'x_is_volunteer' in vals:
            for emp in self:
                emp._sync_contact_volunteer_flag(
                    old_contact=old_contacts.get(emp.id)
                )
        return res

    def _sync_contact_volunteer_flag(self, old_contact=None):
        """Keep the linked contact's volunteer flag in sync with this
        employee.

        * If ``work_contact_id`` is set and the employee's volunteer flag
          is on (or the contact was already a volunteer), mark the
          contact as a volunteer and point ``x_volunteer_employee_id``
          at this employee.
        * If the contact link was cleared or changed, and the previously
          linked contact's ``x_volunteer_employee_id`` still points at
          this employee, clear that back-link so the contact no longer
          claims to have an employee record.
        """
        self.ensure_one()

        # If the contact was changed, clear any stale back-link on the
        # old contact so it doesn't still point at this employee.
        if old_contact and old_contact != self.work_contact_id:
            if old_contact.x_volunteer_employee_id == self:
                old_contact.sudo().write({'x_volunteer_employee_id': False})
                old_contact.message_post(
                    body=(
                        "<strong>Employee link removed</strong><br/>"
                        f"Employee {self.name} (ID {self.id}) is no longer "
                        "linked to this contact."
                    ),
                    message_type='comment', subtype_xmlid='mail.mt_note',
                )

        partner = self.work_contact_id
        if not partner:
            return

        # Only apply the Elks volunteer sync when the contact is an Elks
        # contact (member OR already marked as volunteer).  We don't want
        # to flag every random hr.employee.work_contact_id as a volunteer.
        is_elks = partner.x_is_member or partner.x_is_volunteer
        if not is_elks:
            return

        vals = {}
        if not partner.x_is_volunteer:
            vals['x_is_volunteer'] = True
        if partner.x_volunteer_employee_id != self:
            vals['x_volunteer_employee_id'] = self.id

        if vals:
            partner.sudo().write(vals)
            # Ensure the volunteer department is set on this employee
            if not self.department_id or self.department_id.name != 'Volunteers':
                dept = partner._get_or_create_volunteer_department()
                self.sudo().write({
                    'department_id': dept.id,
                    'x_is_volunteer': True,
                })
            partner.message_post(
                body=(
                    "<strong>Linked to Employee Record</strong><br/>"
                    f"Employee: {self.name} (ID {self.id})<br/>"
                    "Volunteer flag enabled automatically."
                ),
                message_type='comment', subtype_xmlid='mail.mt_note',
            )
            self.message_post(
                body=(
                    "<strong>Linked to Elks Contact</strong><br/>"
                    f"Contact: {partner.name}"
                    f" (#{partner.x_detail_member_num or 'N/A'})"
                ),
                message_type='comment', subtype_xmlid='mail.mt_note',
            )
            _logger.info(
                'Bidirectional link: employee %s ↔ partner %s (volunteer flag set)',
                self.id, partner.id,
            )
