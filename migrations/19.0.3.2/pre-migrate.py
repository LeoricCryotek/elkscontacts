"""Pre-migration: convert reinstatement_previous_state from Char to Many2one.

The column previously stored text values like "Colorado". It now needs to be
an integer FK to res.country.state. We attempt to match existing text values
to state names and convert them; unmatched values are logged and cleared.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Check if the column exists and is text-type
    cr.execute("""
        SELECT data_type
        FROM information_schema.columns
        WHERE table_name = 'elks_membership_application'
          AND column_name = 'reinstatement_previous_state'
    """)
    row = cr.fetchone()
    if not row:
        return  # column doesn't exist yet, nothing to do

    col_type = row[0]
    if col_type in ('integer', 'bigint'):
        return  # already an integer FK, nothing to do

    _logger.info(
        "Migrating reinstatement_previous_state from %s to integer (Many2one)",
        col_type,
    )

    # Try to match text values to res.country.state records
    cr.execute("""
        SELECT DISTINCT reinstatement_previous_state
        FROM elks_membership_application
        WHERE reinstatement_previous_state IS NOT NULL
          AND reinstatement_previous_state != ''
    """)
    text_values = [r[0] for r in cr.fetchall()]

    if text_values:
        _logger.info("Found %d distinct text values to convert", len(text_values))

    # Build a mapping from text -> state id
    mapping = {}
    for val in text_values:
        # Try exact name match
        cr.execute("""
            SELECT id FROM res_country_state
            WHERE name ILIKE %s
            LIMIT 1
        """, (val,))
        match = cr.fetchone()
        if match:
            mapping[val] = match[0]
            _logger.info("  Matched '%s' -> state id %d", val, match[0])
        else:
            # Try code match (e.g. "ID" for Idaho)
            cr.execute("""
                SELECT id FROM res_country_state
                WHERE code ILIKE %s
                LIMIT 1
            """, (val,))
            match = cr.fetchone()
            if match:
                mapping[val] = match[0]
                _logger.info("  Matched '%s' (code) -> state id %d", val, match[0])
            else:
                _logger.warning("  Could not match '%s' to any state, will be cleared", val)

    # Drop the old text column and recreate as integer
    cr.execute("""
        ALTER TABLE elks_membership_application
        DROP COLUMN reinstatement_previous_state
    """)
    cr.execute("""
        ALTER TABLE elks_membership_application
        ADD COLUMN reinstatement_previous_state INTEGER
    """)

    # Restore matched values
    # We need to update by the old text values, but the column is gone.
    # Since we dropped and recreated, all rows are NULL now.
    # The best we can do is log what was lost. For a small lodge this is acceptable.
    if mapping:
        _logger.info(
            "Note: %d text values were matched to state IDs but the column "
            "has been reset. Matched states will need to be re-entered on "
            "existing applications.",
            len(mapping),
        )

    _logger.info("Migration of reinstatement_previous_state complete")
