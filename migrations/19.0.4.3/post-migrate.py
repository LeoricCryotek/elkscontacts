# -*- coding: utf-8 -*-
# ============================================================================
# === HUMAN ===
# Re-alphabetizes the app-launcher grid on upgrade.  Same behavior as
# elkssecretary's "Alphabetize App Menus" tool, automated.
# === AI AGENT ===
# Delegates to alphabetize_app_menus() in __init__.py.  Idempotent.
# ============================================================================
"""19.0.4.3 — Auto-alphabetize app launcher on upgrade."""


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID
    from odoo.addons.elkscontacts import alphabetize_app_menus
    env = api.Environment(cr, SUPERUSER_ID, {})
    alphabetize_app_menus(env)
