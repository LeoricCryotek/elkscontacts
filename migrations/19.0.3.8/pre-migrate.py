# -*- coding: utf-8 -*-
"""Pre-migration: preserve officer term notes data before field rename.

The ``notes`` column on ``elks_officer_term`` is being replaced by
``message``.  The ORM would drop the old column when it detects the
field definition changed from a stored Text to a non-stored related
field.  This script copies the data first so nothing is lost.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Check if the old notes column exists
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'elks_officer_term'
           AND column_name = 'notes'
    """)
    if not cr.fetchone():
        _logger.info("No 'notes' column found — nothing to migrate.")
        return

    # Create the new message column if it doesn't exist yet
    cr.execute("""
        ALTER TABLE elks_officer_term
        ADD COLUMN IF NOT EXISTS message TEXT
    """)

    # Copy notes → message (only where message is empty)
    cr.execute("""
        UPDATE elks_officer_term
           SET message = notes
         WHERE notes IS NOT NULL
           AND notes != ''
           AND (message IS NULL OR message = '')
    """)
    count = cr.rowcount
    _logger.info(
        "Pre-migrate 19.0.3.8: copied %d officer term notes → message.",
        count,
    )
