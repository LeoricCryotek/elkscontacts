# -*- coding: utf-8 -*-
"""Post-migration: create ir.model.access records for new models.

The three models added in 19.0.3.3 (elks.member.history,
elks.suspension.wizard, elks.drop.wizard) failed to register their
ir.model external IDs during the upgrade, causing the security CSV to
crash.  This migration creates the access records directly via SQL
after the models are fully initialised.
"""
import logging

_logger = logging.getLogger(__name__)

# (external_id, name, model_technical_name)
_NEW_ACCESS_RULES = [
    ('access_elks_member_history', 'elks.member.history', 'elks.member.history'),
    ('access_elks_suspension_wizard', 'elks.suspension.wizard', 'elks.suspension.wizard'),
    ('access_elks_drop_wizard', 'elks.drop.wizard', 'elks.drop.wizard'),
]

MODULE = 'elkscontacts'


def migrate(cr, version):
    """Ensure ir.model.access records exist for the three new models."""
    for xml_id, name, model_name in _NEW_ACCESS_RULES:
        # 1. Find the ir.model record for this model
        cr.execute("SELECT id FROM ir_model WHERE model = %s", (model_name,))
        row = cr.fetchone()
        if not row:
            _logger.warning(
                "post-migrate: model %s not found in ir_model — skipping "
                "access rule '%s'.  The model will get access rules on the "
                "next upgrade.",
                model_name, xml_id,
            )
            continue
        model_id = row[0]

        # 2. Find base.group_user
        cr.execute("""
            SELECT res_id FROM ir_model_data
             WHERE module = 'base' AND name = 'group_user'
        """)
        group_row = cr.fetchone()
        group_id = group_row[0] if group_row else None

        # 3. Check if the access record already exists (by external id)
        cr.execute("""
            SELECT 1 FROM ir_model_data
             WHERE module = %s AND name = %s
        """, (MODULE, xml_id))
        if cr.fetchone():
            _logger.info("post-migrate: access rule '%s' already exists", xml_id)
            continue

        # 4. Create the ir.model.access record
        cr.execute("""
            INSERT INTO ir_model_access (name, model_id, group_id,
                                         perm_read, perm_write,
                                         perm_create, perm_unlink,
                                         create_uid, write_uid,
                                         create_date, write_date)
            VALUES (%s, %s, %s, true, true, true, true,
                    1, 1, now() AT TIME ZONE 'UTC', now() AT TIME ZONE 'UTC')
            RETURNING id
        """, (name, model_id, group_id))
        access_id = cr.fetchone()[0]

        # 5. Register the external id so future upgrades can find it
        cr.execute("""
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
            VALUES (%s, %s, 'ir.model.access', %s, false)
        """, (MODULE, xml_id, access_id))

        _logger.info(
            "post-migrate: created access rule '%s' for model %s (id=%s)",
            xml_id, model_name, access_id,
        )
