# -*- coding: utf-8 -*-
"""Inject officer data into the Contact Us page.

Provides an explicit /contactus route that renders the standard
``website.contactus`` template with officer term data added to the
rendering context.  The inherited QWeb template
(``elkscontacts.website_officers_contactus``) picks up the extra
variables and renders the officers section above the contact form.
"""
from odoo import fields as odoo_fields, http
from odoo.http import request


class WebsiteOfficers(http.Controller):

    @http.route('/contactus', type='http', auth='public', website=True, sitemap=True)
    def contactus_with_officers(self, **kwargs):
        """Serve the Contact Us page with officer data in context."""
        OfficerTerm = request.env['elks.officer.term'].sudo()

        # Determine current lodge year
        today = odoo_fields.Date.today()
        if today.month >= 4:
            current_year = f"{today.year}-{today.year + 1}"
        else:
            current_year = f"{today.year - 1}-{today.year}"

        # Fetch officers for the current year, visible on website
        officers = OfficerTerm.search([
            ('lodge_year', '=', current_year),
            ('show_on_website', '=', True),
        ], order='officer_type, position')

        # Group by officer type for display sections
        type_labels = dict(OfficerTerm._fields['officer_type'].selection)
        position_labels = dict(OfficerTerm._fields['position'].selection)

        # Pluralised labels for website section headings
        plural_labels = {
            'elected': 'Elected Officers',
            'appointed': 'Appointed Officers',
            'trustee': 'Trustees',
            'staff': 'Staff / Administrative',
            'honorific': 'Past / Honorific',
            'delegate': 'Delegates',
        }

        # Separate the Exalted Ruler for the featured hero card
        er_officer = None
        grouped = {}
        type_order = [
            'elected', 'trustee', 'appointed',
            'staff', 'honorific', 'delegate',
        ]
        for officer in officers:
            if officer.position == 'exalted_ruler' and not er_officer:
                er_officer = officer
                continue
            otype = officer.officer_type or 'other'
            if otype not in grouped:
                grouped[otype] = {
                    'label': plural_labels.get(
                        otype, type_labels.get(otype, otype.title())),
                    'officers': [],
                }
            grouped[otype]['officers'].append(officer)

        # Maintain display order
        ordered_groups = []
        for t in type_order:
            if t in grouped:
                ordered_groups.append(grouped[t])

        return request.render('website.contactus', {
            'er_officer': er_officer,
            'officers_groups': ordered_groups,
            'officers_position_labels': position_labels,
            'officers_current_year': current_year,
        })
