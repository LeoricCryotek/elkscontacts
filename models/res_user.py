from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    # Mirror the partner field so it’s visible/editable on the User form
    x_detail_member_num = fields.Char(
        related='partner_id.x_detail_member_num',
        store=True,
        readonly=False,
        string='Member Number',  # label on the user form (can also override in the view)
    )
