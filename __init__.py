from . import models
from . import wizard


def _pre_init_set_application_defaults(env):
    """Set default values on existing membership application records so that
    new NOT-NULL / required columns don't fail on module upgrade."""
    # Skip on fresh install (table may not exist yet)
    env.cr.execute("""
        SELECT 1 FROM information_schema.tables
         WHERE table_name = 'elks_membership_application'
    """)
    if not env.cr.fetchone():
        return
    # Helper: only update columns that already exist in the table
    def _safe_update(col, value):
        env.cr.execute("""
            SELECT 1 FROM information_schema.columns
             WHERE table_name = 'elks_membership_application'
               AND column_name = %s
        """, (col,))
        if env.cr.fetchone():
            env.cr.execute(
                f"UPDATE elks_membership_application SET {col} = %s WHERE {col} IS NULL",
                (value,),
            )

    _safe_update('application_type', 'new')

    # Boolean columns that are now required=True — set NULL → False
    for col in (
        'q_belief_in_god',
        'q_us_citizen',
        'q_no_subversive_affiliation',
        'q_never_convicted_felony',
        'q_willing_to_assume_obligation',
        'q_bona_fide_resident',
        'q_good_character',
        'applicant_served_military',
    ):
        _safe_update(col, False)