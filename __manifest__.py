# -*- coding: utf-8 -*-
{
    'name': 'Elks Contacts',
    'summary': 'Manage Elks Member Contact Information',
    'version': '19.0.1.0.0',
    'sequence': 10,
    'category': 'Contacts',
    'description': """
Elks Contacts
=============
Tools to manage Elks member contact data and related views.
""",
    'author': 'Danny Santiago',
    'website': 'https://dannysantiago.info',
    'license': 'LGPL-3',

    'depends': ['base', 'contacts'],

    'data': [
        'views/elks_contact_views.xml',
        'views/elks_menus.xml',
        'views/elks_action.xml',
        'views/res_users_elks_views.xml',
        'views/res_partner_kanban_elks.xml',
        'views/res_partner_officer_views.xml',
        'views/res_partner_search_elks.xml',
        'views/res_partner_lodge_records_views.xml',
        'data/elks_cron.xml',
    ],
    'demo': [
        # 'demo/elks_demo.xml',
    ],

    'assets': {
        'web.assets_backend': [
            # 'elks_contacts/static/src/js/*.js',
            # 'elks_contacts/static/src/scss/*.scss',
        ],
        'web.assets_frontend': [
            # 'elks_contacts/static/src/js/website/*.js',
        ],
    },

    'installable': True,
    'application': True,
    'auto_install': False,
}
