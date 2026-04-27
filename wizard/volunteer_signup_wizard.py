# -*- coding: utf-8 -*-
"""Volunteer Quick-Signup Wizard.

Lets staff register a new volunteer (or a walk-in at the kiosk desk)
with minimal info: first name, last name, phone, email, and a PIN
for kiosk check-in.

The wizard:
  1. Searches existing contacts for matches (by email, then name).
  2. Presents any matches so the user can pick one to link.
  3. If no match (or user chooses "create new"), creates a new contact.
  4. Flags the contact as a volunteer.
  5. Creates or links an hr.employee record in the Volunteers department.
  6. Sets the kiosk PIN on the employee so they can immediately clock in.

Everything is logged to chatter on both the contact and the employee.
"""
import logging
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _norm(s):
    return re.sub(r'\s+', ' ', str(s or '').strip().lower())


class ElksVolunteerSignupWizard(models.TransientModel):
    _name = 'elks.volunteer.signup.wizard'
    _description = 'Volunteer Quick Signup'

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------
    state = fields.Selection([
        ('input', 'Enter Info'),
        ('match', 'Review Matches'),
        ('done', 'Done'),
    ], default='input', string='Step')

    # ------------------------------------------------------------------
    # Input fields (step 1)
    # ------------------------------------------------------------------
    first_name = fields.Char("First Name", required=True)
    last_name = fields.Char("Last Name", required=True)
    phone = fields.Char("Phone Number")
    email = fields.Char("Email")
    pin = fields.Char(
        "Kiosk PIN", size=6,
        help="4–6 digit PIN for the attendance kiosk. "
             "Auto-filled from the last 4 digits of the phone number. "
             "Can be changed here or later on the employee record.",
    )

    @api.onchange('phone')
    def _onchange_phone_set_pin(self):
        """Auto-populate PIN with last 4 digits of the phone number."""
        if self.phone and not self.pin:
            digits = re.sub(r'\D', '', self.phone)
            if len(digits) >= 4:
                self.pin = digits[-4:]

    # ------------------------------------------------------------------
    # Match results (step 2)
    # ------------------------------------------------------------------
    match_line_ids = fields.One2many(
        'elks.volunteer.signup.wizard.match', 'wizard_id',
        string='Possible Matches',
    )
    match_count = fields.Integer(compute='_compute_match_count')
    selected_partner_id = fields.Many2one(
        'res.partner', string='Link to Existing Contact',
    )
    create_new = fields.Boolean("Create New Contact", default=False)

    # ------------------------------------------------------------------
    # Result (step 3)
    # ------------------------------------------------------------------
    result_partner_id = fields.Many2one('res.partner', string='Contact', readonly=True)
    result_employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True)
    result_message = fields.Text("Result", readonly=True)

    @api.depends('match_line_ids')
    def _compute_match_count(self):
        for wiz in self:
            wiz.match_count = len(wiz.match_line_ids)

    # ------------------------------------------------------------------
    # Step 1 → Step 2: Search for matches
    # ------------------------------------------------------------------
    def action_search_matches(self):
        """Search contacts for potential matches, then show results."""
        self.ensure_one()
        if not self.first_name or not self.last_name:
            raise UserError(_("First name and last name are required."))

        matches = self._find_contact_matches()

        # Clear old match lines
        self.match_line_ids.unlink()

        if matches:
            self.write({
                'state': 'match',
                'match_line_ids': [
                    (0, 0, {
                        'partner_id': m['partner'].id,
                        'match_reason': m['reason'],
                        'confidence': m['confidence'],
                    }) for m in matches
                ],
            })
        else:
            # No matches — go straight to creation
            return self._action_create_volunteer()

        return self._reopen()

    def _find_contact_matches(self):
        """Search for existing contacts that might be this volunteer."""
        Partner = self.env['res.partner']
        email_norm = _norm(self.email)
        first = _norm(self.first_name)
        last = _norm(self.last_name)

        seen = set()
        matches = []

        def add(partner, reason, confidence):
            if partner.id in seen:
                return
            seen.add(partner.id)
            matches.append({
                'partner': partner,
                'reason': reason,
                'confidence': confidence,
            })

        # 1. Exact email match (high)
        if email_norm:
            email_matches = Partner.with_context(active_test=False).search([
                '|',
                ('email', '=ilike', email_norm),
                ('x_detail_email_address', '=ilike', email_norm),
            ])
            for p in email_matches:
                add(p, _('Email matches: %s') % (p.email or p.x_detail_email_address), 'high')

        # 2. First + last name exact match (medium)
        if first and last:
            name_matches = Partner.with_context(active_test=False).search([
                '|',
                '&', ('x_detail_first_name', '=ilike', first),
                     ('x_detail_last_name', '=ilike', last),
                ('name', 'ilike', f'{first}%{last}'),
            ])
            for p in name_matches:
                add(p, _('Name matches: %s') % p.name, 'medium')

        # 3. Last name only (low)
        if last:
            last_matches = Partner.with_context(active_test=False).search([
                '|',
                ('x_detail_last_name', '=ilike', last),
                ('name', 'ilike', last),
            ], limit=10)
            for p in last_matches:
                add(p, _('Last name matches: %s') % p.name, 'low')

        # 4. Phone match (medium)
        if self.phone:
            phone_clean = re.sub(r'\D', '', self.phone)
            if len(phone_clean) >= 7:
                phone_matches = Partner.with_context(active_test=False).search([
                    '|', '|',
                    ('phone', 'ilike', phone_clean[-7:]),
                    ('mobile', 'ilike', phone_clean[-7:]),
                    ('x_detail_cell_phone', 'ilike', phone_clean[-7:]),
                ], limit=10)
                for p in phone_matches:
                    add(p, _('Phone matches: %s') % (p.phone or p.mobile), 'medium')

        order = {'high': 0, 'medium': 1, 'low': 2}
        matches.sort(key=lambda m: order.get(m['confidence'], 99))
        return matches

    # ------------------------------------------------------------------
    # Step 2 actions: link to existing or create new
    # ------------------------------------------------------------------
    def action_link_selected(self):
        """Link to the selected existing contact."""
        self.ensure_one()
        if not self.selected_partner_id:
            raise UserError(_("Please select a contact to link, or click 'Create New Volunteer'."))
        return self._action_create_volunteer(existing_partner=self.selected_partner_id)

    def action_create_new_volunteer(self):
        """Skip matches and create a brand-new contact + employee."""
        self.ensure_one()
        return self._action_create_volunteer(existing_partner=None)

    # ------------------------------------------------------------------
    # Core: create/link contact and employee
    # ------------------------------------------------------------------
    def _action_create_volunteer(self, existing_partner=None):
        """Create or update the contact, create/link employee, set PIN.

        Args:
            existing_partner: If provided, use this contact instead of creating new.
        """
        self.ensure_one()
        Employee = self.env['hr.employee'].sudo()

        full_name = f"{self.first_name.strip()} {self.last_name.strip()}"

        if existing_partner:
            partner = existing_partner
            # Update contact info if the volunteer provided new data
            update_vals = {}
            if self.phone and not partner.phone:
                update_vals['phone'] = self.phone
            if self.email and not partner.email:
                update_vals['email'] = self.email
                update_vals['x_detail_email_address'] = self.email
            if not partner.x_detail_first_name:
                update_vals['x_detail_first_name'] = self.first_name
            if not partner.x_detail_last_name:
                update_vals['x_detail_last_name'] = self.last_name
            # Flag as volunteer
            update_vals['x_is_volunteer'] = True
            partner.write(update_vals)
            action_desc = _("Linked existing contact")
        else:
            # Create new contact
            partner = self.env['res.partner'].with_context(
                elks_overwrite=False,
            ).create({
                'name': full_name,
                'x_detail_first_name': self.first_name.strip(),
                'x_detail_last_name': self.last_name.strip(),
                'phone': self.phone or False,
                'email': self.email or False,
                'x_detail_email_address': self.email or False,
                'x_is_volunteer': True,
                'x_is_not_member': True,  # Not a member — just a volunteer
                'company_type': 'person',
                'is_company': False,
            })
            action_desc = _("Created new contact")

        # Now find or create the employee record
        dept = partner._get_or_create_volunteer_department()
        emp = partner.x_volunteer_employee_id

        if not emp:
            # Check if _sync_volunteer_employee auto-linked one
            partner.invalidate_recordset(['x_volunteer_employee_id'])
            emp = partner.x_volunteer_employee_id

        if not emp:
            # Search for an employee already linked to this contact
            emp = Employee.with_context(active_test=False).search([
                ('work_contact_id', '=', partner.id),
            ], limit=1)

        if emp:
            # Activate and update existing employee
            emp.write({
                'active': True,
                'x_is_volunteer': True,
                'department_id': dept.id,
                'work_contact_id': partner.id,
            })
            # Set PIN: use wizard value, or auto-extract from contact phone
            pin_to_set = self.pin or partner._extract_pin_from_phone()
            if pin_to_set and not emp.pin:
                emp.write({'pin': pin_to_set})
            partner.write({'x_volunteer_employee_id': emp.id})
            emp_action = _("Linked to existing employee")
        else:
            # Create new employee
            emp_vals = {
                'name': partner.name or full_name,
                'work_phone': self.phone or partner.phone or False,
                'work_email': self.email or partner.email or False,
                'department_id': dept.id,
                'job_title': 'Volunteer',
                'work_contact_id': partner.id,
                'x_is_volunteer': True,
            }
            # Set PIN: use wizard value, or auto-extract from contact phone
            pin_to_set = self.pin or partner._extract_pin_from_phone()
            if pin_to_set:
                emp_vals['pin'] = pin_to_set
            emp = Employee.create(emp_vals)
            partner.write({'x_volunteer_employee_id': emp.id})
            emp_action = _("Created new employee record")

        # Chatter on contact
        partner.message_post(
            body=_(
                "<strong>Volunteer Signed Up</strong><br/>"
                "%(action)s<br/>"
                "Employee: %(emp_name)s (ID %(emp_id)s)<br/>"
                "Department: %(dept)s<br/>"
                "Kiosk PIN: %(pin)s",
                action=action_desc,
                emp_name=emp.name,
                emp_id=emp.id,
                dept=dept.name,
                pin='Set' if self.pin else 'Not set',
            ),
            message_type='comment', subtype_xmlid='mail.mt_note',
        )

        # Chatter on employee
        emp.message_post(
            body=_(
                "<strong>Volunteer Signup</strong><br/>"
                "%(emp_action)s<br/>"
                "Contact: %(partner_name)s<br/>"
                "Phone: %(phone)s | Email: %(email)s",
                emp_action=emp_action,
                partner_name=partner.name,
                phone=self.phone or 'N/A',
                email=self.email or 'N/A',
            ),
            message_type='comment', subtype_xmlid='mail.mt_note',
        )

        _logger.info(
            'Volunteer signup: partner=%s, employee=%s, action=%s',
            partner.id, emp.id, action_desc,
        )

        # Update wizard to show result
        result_msg = _(
            "%(name)s is now registered as a volunteer.\n"
            "Employee record: %(emp)s\n"
            "Department: %(dept)s\n"
            "Kiosk PIN: %(pin)s\n\n"
            "They can now clock in at the attendance kiosk.",
            name=partner.name,
            emp=emp.name,
            dept=dept.name,
            pin='Set — ready for kiosk' if self.pin else 'Not set — set one on the employee record to enable kiosk',
        )
        self.write({
            'state': 'done',
            'result_partner_id': partner.id,
            'result_employee_id': emp.id,
            'result_message': result_msg,
        })
        return self._reopen()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Volunteer Signup'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_open_contact(self):
        """Open the resulting contact record."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Volunteer Contact'),
            'res_model': 'res.partner',
            'res_id': self.result_partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_employee(self):
        """Open the resulting employee record."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Volunteer Employee'),
            'res_model': 'hr.employee',
            'res_id': self.result_employee_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ElksVolunteerSignupWizardMatch(models.TransientModel):
    _name = 'elks.volunteer.signup.wizard.match'
    _description = 'Volunteer Signup - Contact Match'
    _order = 'confidence, id'

    wizard_id = fields.Many2one(
        'elks.volunteer.signup.wizard', ondelete='cascade', required=True,
    )
    partner_id = fields.Many2one('res.partner', string='Contact', required=True)
    partner_name = fields.Char(related='partner_id.name', readonly=True)
    partner_email = fields.Char(related='partner_id.email', readonly=True)
    partner_phone = fields.Char(related='partner_id.phone', readonly=True)
    partner_is_member = fields.Boolean(related='partner_id.x_is_member', readonly=True)
    partner_is_volunteer = fields.Boolean(related='partner_id.x_is_volunteer', readonly=True)
    match_reason = fields.Char('Match Reason', readonly=True)
    confidence = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ], string='Confidence', readonly=True)

    def action_select(self):
        """Pick this match as the contact to link."""
        self.ensure_one()
        self.wizard_id.write({
            'selected_partner_id': self.partner_id.id,
        })
        return self.wizard_id.action_link_selected()
