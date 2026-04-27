# -*- coding: utf-8 -*-
import datetime

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


TRAINING_AREAS = [
    ('kitchen', 'Kitchen'),
    ('sanitation', 'Sanitation'),
    ('pos', 'POS'),
    ('office', 'Office'),
    ('lounge_support', 'Lounge Support'),
    ('bartender', 'Bartender'),
    ('event_setup', 'Event Setup'),
    ('first_aid', 'First Aid / Safety'),
]

# Maps training_area keys → xml‑id suffixes in volunteer_training_data.xml
_AREA_SKILL_XMLID = {
    'kitchen':        'elkscontacts.skill_kitchen',
    'sanitation':     'elkscontacts.skill_sanitation',
    'pos':            'elkscontacts.skill_pos',
    'office':         'elkscontacts.skill_office',
    'lounge_support': 'elkscontacts.skill_lounge_support',
    'bartender':      'elkscontacts.skill_bartender',
    'event_setup':    'elkscontacts.skill_event_setup',
    'first_aid':      'elkscontacts.skill_first_aid',
}


def _next_lodge_year_end(self=None):
    """Return the next April 1 (end of the current lodge year).

    If today is Jan–Mar, the current lodge year ends April 1 of this year.
    If today is Apr–Dec, the current lodge year ends April 1 of next year.

    Accepts an optional ``self`` so Odoo can call it as a field default
    (Odoo passes the recordset as the first argument).
    """
    today = datetime.date.today()
    if today.month >= 4:
        return datetime.date(today.year + 1, 4, 1)
    else:
        return datetime.date(today.year, 4, 1)


class ElksVolunteerTraining(models.Model):
    _name = 'elks.volunteer.training'
    _description = 'Volunteer Training Record'
    _order = 'training_area, date_trained desc'
    _rec_name = 'display_name'

    employee_id = fields.Many2one(
        'hr.employee', string='Volunteer', required=True,
        ondelete='cascade', index=True,
    )
    training_area = fields.Selection(
        TRAINING_AREAS, string='Training Area', required=True, index=True,
    )
    is_trained = fields.Boolean(string='Trained', default=False)
    date_trained = fields.Date(string='Date Trained')
    trainer_id = fields.Many2one(
        'res.partner', string='Trained By',
        domain="[('x_is_member', '=', True)]",
        help='The Elks member who conducted the training.',
    )
    expiration_date = fields.Date(
        string='Expiration Date',
        default=_next_lodge_year_end,
        help='Defaults to April 1 (end of the current lodge year).',
    )
    is_expired = fields.Boolean(
        string='Expired', compute='_compute_is_expired', store=True,
    )
    notes = fields.Text(string='Notes')

    # Link‑back fields so we can clean up if training is un‑marked
    resume_line_id = fields.Many2one(
        'hr.resume.line', string='Resume Line',
        ondelete='set null', copy=False,
    )
    employee_skill_id = fields.Many2one(
        'hr.employee.skill', string='Employee Skill',
        ondelete='set null', copy=False,
    )

    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('training_area', 'employee_id.name')
    def _compute_display_name(self):
        labels = dict(TRAINING_AREAS)
        for rec in self:
            area = labels.get(rec.training_area, rec.training_area or '')
            name = rec.employee_id.name or ''
            rec.display_name = f"{area} — {name}"

    @api.depends('expiration_date')
    def _compute_is_expired(self):
        today = fields.Date.today()
        for rec in self:
            if rec.expiration_date:
                rec.is_expired = rec.expiration_date < today
            else:
                rec.is_expired = False

    @api.onchange('is_trained')
    def _onchange_is_trained(self):
        """Auto-fill today's date and expiration when marking as trained."""
        if self.is_trained:
            if not self.date_trained:
                self.date_trained = fields.Date.today()
            if not self.expiration_date:
                self.expiration_date = _next_lodge_year_end()

    @api.constrains('employee_id', 'training_area')
    def _check_unique_training_per_employee(self):
        for rec in self:
            existing = self.search([
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('training_area', '=', rec.training_area),
            ], limit=1)
            if existing:
                label = dict(TRAINING_AREAS).get(rec.training_area, rec.training_area)
                raise ValidationError(_(
                    '"%s" already has a training record for %s.'
                ) % (rec.employee_id.name, label))

    # ------------------------------------------------------------------
    # Resume + Skill sync helpers
    # ------------------------------------------------------------------

    def _get_skill_for_area(self, area_key):
        """Return the hr.skill record for the given training area key."""
        xmlid = _AREA_SKILL_XMLID.get(area_key)
        if not xmlid:
            return self.env['hr.skill']
        return self.env.ref(xmlid, raise_if_not_found=False) or self.env['hr.skill']

    def _sync_resume_line(self):
        """Create or remove a resume line when training is completed / uncompleted."""
        ResumeLine = self.env['hr.resume.line']
        resume_type = self.env.ref(
            'elkscontacts.resume_type_volunteer_training',
            raise_if_not_found=False,
        )
        labels = dict(TRAINING_AREAS)

        for rec in self:
            if rec.is_trained and not rec.resume_line_id:
                area_label = labels.get(rec.training_area, rec.training_area or '')
                trainer_name = rec.trainer_id.name if rec.trainer_id else ''
                desc = f"Trained by {trainer_name}" if trainer_name else ''
                vals = {
                    'employee_id': rec.employee_id.id,
                    'name': f"{area_label} Certification",
                    'date_start': rec.date_trained or fields.Date.today(),
                    'date_end': rec.expiration_date or False,
                    'description': desc,
                }
                if resume_type:
                    vals['line_type_id'] = resume_type.id
                line = ResumeLine.create(vals)
                rec.resume_line_id = line.id
            elif not rec.is_trained and rec.resume_line_id:
                rec.resume_line_id.unlink()
                rec.resume_line_id = False

    def _sync_employee_skill(self):
        """Create or update an employee skill / certification record."""
        EmpSkill = self.env['hr.employee.skill']
        skill_type = self.env.ref(
            'elkscontacts.skill_type_volunteer_cert',
            raise_if_not_found=False,
        )
        level_certified = self.env.ref(
            'elkscontacts.skill_level_certified',
            raise_if_not_found=False,
        )
        level_not_started = self.env.ref(
            'elkscontacts.skill_level_not_started',
            raise_if_not_found=False,
        )
        if not skill_type:
            return

        for rec in self:
            skill = rec._get_skill_for_area(rec.training_area)
            if not skill:
                continue

            if rec.is_trained:
                if rec.employee_skill_id:
                    # Update existing to certified + refresh dates
                    vals = {}
                    if level_certified:
                        vals['skill_level_id'] = level_certified.id
                    vals['valid_from'] = rec.date_trained or fields.Date.today()
                    vals['valid_to'] = rec.expiration_date or False
                    rec.employee_skill_id.write(vals)
                else:
                    # Create new
                    vals = {
                        'employee_id': rec.employee_id.id,
                        'skill_id': skill.id,
                        'skill_type_id': skill_type.id,
                        'skill_level_id': (level_certified or level_not_started).id,
                        'valid_from': rec.date_trained or fields.Date.today(),
                        'valid_to': rec.expiration_date or False,
                    }
                    emp_skill = EmpSkill.create(vals)
                    rec.employee_skill_id = emp_skill.id
            else:
                # Un‑trained: remove the skill record
                if rec.employee_skill_id:
                    rec.employee_skill_id.unlink()
                    rec.employee_skill_id = False

    # ------------------------------------------------------------------
    # CRUD overrides — trigger sync after save
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        trained = records.filtered('is_trained')
        if trained:
            trained._sync_resume_line()
            trained._sync_employee_skill()
        return records

    def write(self, vals):
        res = super().write(vals)
        # Only sync when relevant fields changed
        if any(f in vals for f in ('is_trained', 'date_trained', 'expiration_date',
                                    'trainer_id', 'training_area')):
            self._sync_resume_line()
            self._sync_employee_skill()
        return res
